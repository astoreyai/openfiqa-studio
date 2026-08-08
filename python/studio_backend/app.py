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
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_backend.projects import ProjectStore  # noqa: E402
from studio_backend.registry import PluginNotExecutable, PluginRegistry  # noqa: E402
from studio_backend.runs import RunManager, RunSpec  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = Path(os.environ.get("OFS_WORKSPACE", REPO_ROOT / "var" / "workspace"))

API_VERSION = "0.1.0"


class CreateProject(BaseModel):
    name: str


class CreateRun(BaseModel):
    label: str
    argv: list[str]
    env: dict[str, str] = {}
    cwd: str | None = None


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="OpenFIQA Studio", version=API_VERSION)
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

    # ------------------------------------------------------------------ runs

    @app.post("/api/runs", status_code=201)
    async def create_run(body: CreateRun) -> dict[str, Any]:
        if not body.argv:
            raise HTTPException(status_code=422, detail="argv must not be empty")
        manager: RunManager = app.state.runs
        run = manager.create(RunSpec(label=body.label, argv=body.argv, env=body.env, cwd=body.cwd))
        await manager.start(run)
        return run.to_dict()

    @app.post("/api/runs/plugin/{plugin_id}", status_code=201)
    async def run_plugin(plugin_id: str) -> dict[str, Any]:
        """Refuses to execute a plugin whose availability forbids it.

        The refusal carries the blocker id so a caller learns *why*, which is the whole point of
        keeping blocked engines in the registry instead of hiding them.
        """
        registry: PluginRegistry = app.state.registry
        try:
            registry.assert_executable(plugin_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"no such plugin: {plugin_id}") from None
        except PluginNotExecutable as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "plugin_id": exc.plugin_id,
                    "state": exc.state,
                    "blocker_id": exc.blocker_id,
                    "reason": exc.reason,
                },
            ) from None
        raise HTTPException(
            status_code=501,
            detail={
                "plugin_id": plugin_id,
                "message": "adapters land in P04; the registry permits this plugin but no adapter "
                           "exists yet to translate its output into a QualityVector",
            },
        )

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
