"""OpenFIQA Studio control plane.

Per ADR-0001 this process owns every scientific operation; the desktop shell renders and observes.
Per ADR-0002 no engine is imported here — engines run as subprocesses in their own environments.
Per ADR-0003 ``/api/plugins`` reports blocked engines with their blocker id rather than hiding them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_adapters.base import AdapterFailed, AdapterUnavailable  # noqa: E402
from studio_adapters.registry import adapter_run_spec, get_adapter  # noqa: E402
from studio_backend.projects import ProjectStore  # noqa: E402
from studio_backend.registry import PluginNotExecutable, PluginRegistry  # noqa: E402
from studio_backend.samples import (  # noqa: E402
    SampleAccessDenied,
    list_samples,
    media_type,
    resolve_servable,
)
from studio_backend.runs import RunManager, RunSpec  # noqa: E402
from studio_workflow.executor import WorkflowExecutor, workflow_digest  # noqa: E402
from studio_workflow.executor import BLOCKED_KINDS  # noqa: E402
from studio_workflow.graph import NODE_PORTS, Workflow, WorkflowError  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = Path(os.environ.get("OFS_WORKSPACE", REPO_ROOT / "var" / "workspace"))

API_VERSION = "0.1.0"

# The desktop shell is a different origin from the control plane, so the browser enforces CORS.
# This is an explicit allowlist rather than "*": ADR-0008 makes the studio local-first, and a
# wildcard would let any page the user happens to open reach a backend that indexes biometric
# datasets. Extra origins can be added for development via OFS_EXTRA_ORIGINS (comma-separated).
LOCAL_ORIGINS = [
    "http://localhost:5273",
    "http://127.0.0.1:5273",
    "tauri://localhost",
    "http://tauri.localhost",
    "https://tauri.localhost",
]


def _allowed_origins() -> list[str]:
    extra = os.environ.get("OFS_EXTRA_ORIGINS", "")
    return LOCAL_ORIGINS + [o.strip() for o in extra.split(",") if o.strip()]


class CreateProject(BaseModel):
    name: str


class AssessRequest(BaseModel):
    image_path: str


class WorkflowBody(BaseModel):
    yaml: str
    workdir: str | None = None
    limit: int | None = None


class DegradeRequest(BaseModel):
    image_path: str
    operator: str
    parameters: dict[str, Any] = {}


class CreateRun(BaseModel):
    label: str
    argv: list[str]
    env: dict[str, str] = {}
    cwd: str | None = None


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="OpenFIQA Studio", version=API_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.state.registry = PluginRegistry()
    app.state.projects = ProjectStore(workspace or DEFAULT_WORKSPACE)
    app.state.runs = RunManager()

    # ------------------------------------------------------------------ health

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        registry: PluginRegistry = app.state.registry
        return {
            "status": "ok",
            "api_version": API_VERSION,
            "workspace": str(app.state.projects.workspace),
            "plugins": len(registry.all()),
            "executable_plugins": registry.executable(),
        }

    # ------------------------------------------------------------------ plugins

    @app.get("/api/plugins")
    def list_plugins() -> dict[str, Any]:
        registry: PluginRegistry = app.state.registry
        plugins = registry.all()
        return {
            "plugins": plugins,
            "counts": {
                "total": len(plugins),
                "executable": sum(1 for p in plugins if p["executable"]),
                "blocked": sum(1 for p in plugins if p["availability"]["state"] == "BLOCKED"),
                "unverified": sum(
                    1 for p in plugins if p["availability"]["state"] == "UNVERIFIED"
                ),
            },
        }

    @app.get("/api/plugins/{plugin_id}")
    def get_plugin(plugin_id: str) -> dict[str, Any]:
        manifest = app.state.registry.get(plugin_id)
        if manifest is None:
            raise HTTPException(status_code=404, detail=f"no such plugin: {plugin_id}")
        return manifest

    # ------------------------------------------------------------------ projects

    @app.post("/api/projects", status_code=201)
    def create_project(body: CreateProject) -> dict[str, Any]:
        return app.state.projects.create(body.name).to_dict()

    @app.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        return {"projects": [p.to_dict() for p in app.state.projects.list()]}

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        project = app.state.projects.open(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"no such project: {project_id}")
        return project.to_dict()

    @app.get("/api/projects/{project_id}/runs")
    def project_runs(project_id: str) -> dict[str, Any]:
        project = app.state.projects.open(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"no such project: {project_id}")
        return {"runs": app.state.projects.runs(project)}

    @app.get("/api/artifacts")
    def list_artifacts(project_id: str) -> dict[str, Any]:
        project = app.state.projects.open(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"no such project: {project_id}")
        return {"artifacts": app.state.projects.artifacts(project)}

    # ------------------------------------------------------------------ models

    @app.get("/api/models")
    def list_models() -> dict[str, Any]:
        """Model registry. Empty until P08 — reported honestly rather than with placeholders."""
        return {"models": [], "note": "model registry lands in P08"}

    # ------------------------------------------------------------------ samples (Image Lab)

    @app.get("/api/samples")
    def samples(limit: int = 200) -> dict[str, Any]:
        return {"samples": list_samples(limit=limit)}

    @app.get("/api/samples/image")
    def sample_image(path: str) -> FileResponse:
        """Serve one image to the local shell.

        Restricted to configured corpus roots. Without that check this endpoint is an arbitrary
        file-read reachable from any origin the CORS allowlist admits.
        """
        try:
            resolved = resolve_servable(path)
        except SampleAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        return FileResponse(resolved, media_type=media_type(resolved))

    @app.post("/api/samples/degrade")
    def degrade(body: DegradeRequest) -> dict[str, Any]:
        """Apply one degradation and return the result plus its transform record.

        The SOURCE must be servable — a caller cannot degrade /etc/passwd into the derived
        directory and then read it back through the image endpoint.
        """
        from studio_backend.samples import derived_root
        from studio_transforms import operators as ops

        try:
            source = resolve_servable(body.image_path)
        except SampleAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None

        try:
            output, record = ops.apply(
                body.operator, ops.load(source), parameters=body.parameters
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

        # Named by the transform's OUTPUT hash: identical settings reuse one file, and the name
        # states what the bytes are rather than when they were made.
        destination = derived_root() / f"{record.output_sha256[:24]}.png"
        if not destination.exists():
            output.save(destination)

        return {
            "path": str(destination),
            "transform": record.to_dict(),
            "source_path": str(source),
        }

    @app.post("/api/samples/detect")
    def detect(body: AssessRequest) -> dict[str, Any]:
        """Face box, keypoints, 106 landmarks and head pose for one sample.

        Deliberately NOT a QualityVector: a landmark set is geometry, not a measurement of quality,
        and typing it as one would let it flow into places that average scores.
        """
        from studio_adapters.detect_adapter import DetectAdapter, geometry_is_consistent

        try:
            source = resolve_servable(body.image_path)
        except SampleAccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None

        adapter = DetectAdapter()
        try:
            payload = adapter.run(source)
        except AdapterFailed as exc:
            raise HTTPException(
                status_code=422,
                detail={"error": str(exc), "stderr": exc.stderr[-2000:]},
            ) from None

        consistent, problems = geometry_is_consistent(payload)
        payload["geometry_consistent"] = consistent
        payload["geometry_problems"] = problems
        return payload

    # ------------------------------------------------------------------ workflows

    @app.get("/api/workflows/node-kinds")
    def node_kinds() -> dict[str, Any]:
        """The canvas's connection rules, served FROM the backend.

        ADR-0001 and ADR-0004: the frontend must not carry its own copy of the type system. If it
        did, a schema change would leave the canvas happily drawing edges the executor rejects.
        The graph editor asks for these and enforces exactly them.
        """
        return {
            "kinds": [
                {
                    "kind": kind,
                    "inputs": ports["inputs"],
                    "outputs": ports["outputs"],
                    "blocked_by": BLOCKED_KINDS.get(kind),
                }
                for kind, ports in NODE_PORTS.items()
            ]
        }

    @app.post("/api/workflows/validate")
    def validate_workflow(body: WorkflowBody) -> dict[str, Any]:
        try:
            workflow = Workflow.from_yaml(body.yaml)
        except WorkflowError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        problems = workflow.validate()
        return {
            "name": workflow.name,
            "valid": not problems,
            "problems": problems,
            "workflow_sha256": workflow_digest(workflow),
            "nodes": len(workflow.nodes),
            "edges": len(workflow.edges),
        }

    @app.post("/api/workflows/run")
    def run_workflow(body: WorkflowBody) -> dict[str, Any]:
        """The GUI path.

        ADR-0009: this calls the SAME compiler and executor the CLI calls. There is no separate
        GUI execution path, so the two cannot drift into different results.
        """
        try:
            workflow = Workflow.from_yaml(body.yaml)
            workflow.require_valid()
        except WorkflowError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

        workdir = Path(body.workdir) if body.workdir else app.state.projects.workspace / "wf"
        manifest = WorkflowExecutor(workdir).run(workflow, limit_samples=body.limit)
        return manifest.to_dict()

    # ------------------------------------------------------------------ runs

    @app.post("/api/runs", status_code=201)
    async def create_run(body: CreateRun) -> dict[str, Any]:
        if not body.argv:
            raise HTTPException(status_code=422, detail="argv must not be empty")
        manager: RunManager = app.state.runs
        run = manager.create(RunSpec(label=body.label, argv=body.argv, env=body.env, cwd=body.cwd))
        await manager.start(run)
        return run.to_dict()

    def _assert_executable(plugin_id: str) -> None:
        registry: PluginRegistry = app.state.registry
        try:
            registry.assert_executable(plugin_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"no such plugin: {plugin_id}") from None
        except PluginNotExecutable as exc:
            # The refusal carries the blocker id so a caller learns *why*. That is the whole point
            # of keeping blocked engines in the registry instead of hiding them.
            raise HTTPException(
                status_code=409,
                detail={
                    "plugin_id": exc.plugin_id,
                    "state": exc.state,
                    "blocker_id": exc.blocker_id,
                    "reason": exc.reason,
                },
            ) from None

    @app.post("/api/engines/{plugin_id}/assess")
    def assess(plugin_id: str, body: AssessRequest) -> dict[str, Any]:
        """Run one engine on one image and return a typed QualityVector.

        Synchronous: an ofiqpy assessment takes a couple of seconds, and a caller that asked for
        one measurement wants the measurement, not a job id to poll.
        """
        _assert_executable(plugin_id)
        adapter = get_adapter(plugin_id)
        if adapter is None:
            raise HTTPException(
                status_code=501,
                detail={
                    "plugin_id": plugin_id,
                    "message": f"no adapter is implemented for {plugin_id} yet",
                },
            )
        try:
            result = adapter.run(body.image_path)
        except AdapterUnavailable as exc:
            raise HTTPException(
                status_code=409, detail={"plugin_id": plugin_id, "reason": str(exc)}
            ) from None
        except AdapterFailed as exc:
            # The engine's failure is reported as a failure. It is never converted into a default
            # score, which would look like a measurement to everything downstream.
            raise HTTPException(
                status_code=422,
                detail={
                    "plugin_id": plugin_id,
                    "error": str(exc),
                    "exit_code": exc.exit_code,
                    "stderr": exc.stderr[-2000:],
                },
            ) from None

        return {
            "quality_vector": result.typed,
            "provenance": {
                **adapter.describe(),
                "argv": result.argv,
                "env": result.env,
                "exit_code": result.exit_code,
                "duration_s": round(result.duration_s, 3),
                "started_at": result.started_at,
            },
            # Preserved unparsed alongside the typed object, per the P04 gate.
            "raw_output": result.raw_stdout,
        }

    @app.get("/api/engines/{plugin_id}/status")
    def engine_status(plugin_id: str) -> dict[str, Any]:
        adapter = get_adapter(plugin_id)
        if adapter is None:
            return {"plugin_id": plugin_id, "adapter": False, "available": False,
                    "reason": "no adapter implemented"}
        ok, reason = adapter.available()
        return {
            "plugin_id": plugin_id,
            "adapter": True,
            "available": ok,
            "reason": reason,
            "describe": adapter.describe(),
        }

    @app.post("/api/runs/plugin/{plugin_id}", status_code=201)
    async def run_plugin(plugin_id: str, body: AssessRequest) -> dict[str, Any]:
        """Same work as /assess, but through the run system so output streams over the WebSocket."""
        _assert_executable(plugin_id)
        spec = adapter_run_spec(plugin_id, body.image_path)
        if spec is None:
            raise HTTPException(
                status_code=501,
                detail={"plugin_id": plugin_id, "message": f"no adapter for {plugin_id} yet"},
            )
        manager: RunManager = app.state.runs
        run = manager.create(RunSpec(label=f"{plugin_id}:{Path(body.image_path).name}", **spec))
        await manager.start(run)
        return run.to_dict()

    @app.get("/api/runs")
    def list_runs() -> dict[str, Any]:
        return {"runs": app.state.runs.all()}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        run = app.state.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"no such run: {run_id}")
        return {**run.to_dict(), "events": app.state.runs.events(run_id)}

    @app.post("/api/runs/{run_id}/cancel")
    async def cancel_run(run_id: str) -> dict[str, Any]:
        run = app.state.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"no such run: {run_id}")
        cancelled = await app.state.runs.cancel(run_id)
        return {"run_id": run_id, "cancel_requested": cancelled, "status": run.status}

    @app.websocket("/ws/runs/{run_id}")
    async def run_events(websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        manager: RunManager = app.state.runs
        if manager.get(run_id) is None:
            await websocket.send_json({"type": "error", "detail": f"no such run: {run_id}"})
            await websocket.close()
            return
        try:
            async for event in manager.subscribe(run_id):
                await websocket.send_json(event)
        except WebSocketDisconnect:
            return
        finally:
            try:
                await websocket.close()
            except RuntimeError:
                pass

    return app


app = create_app()
