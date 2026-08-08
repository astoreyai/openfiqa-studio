"""Run scheduler and event stream.

A run executes a real subprocess and streams its real stdout, stderr, and exit code. Nothing here
simulates a run: there is no fake progress, no invented metric, and no synthesised completion. A
run that fails reports the failure and the exit code it actually got.

Cancellation terminates the child process and reports ``cancelled`` — it does not mark a still-
running job as finished.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator

TERMINAL = {"completed", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunSpec:
    """What to execute. ``argv`` is a list — never a shell string.

    Per the P06 security rule the studio never executes arbitrary text as shell code, so there is
    no code path here that accepts a command line to be parsed by a shell.
    """

    label: str
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "argv": self.argv, "env": self.env, "cwd": self.cwd}


@dataclass
class Run:
    id: str
    spec: RunSpec
    status: str = "queued"
    exit_code: int | None = None
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.id,
            "label": self.spec.label,
            "status": self.status,
            "exit_code": self.exit_code,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class RunManager:
    """Owns run state and fans events out to WebSocket subscribers."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    # ---------------------------------------------------------------- accessors

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def all(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._runs.values()]

    def events(self, run_id: str) -> list[dict[str, Any]]:
        run = self._runs.get(run_id)
        return list(run.events) if run else []

    # ---------------------------------------------------------------- events

    async def _emit(self, run: Run, event_type: str, **payload: Any) -> None:
        event = {"run_id": run.id, "type": event_type, "at": _now(), **payload}
        run.events.append(event)
        for queue in self._subscribers.get(run.id, []):
            await queue.put(event)

    async def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield this run's events: everything already emitted, then live ones.

        Replaying the backlog first means a client that connects after a run starts still sees the
        whole stream, rather than joining mid-way and silently missing the beginning.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)
        try:
            run = self._runs.get(run_id)
            if run:
                for event in list(run.events):
                    yield event
                if run.status in TERMINAL:
                    return
            while True:
                event = await queue.get()
                yield event
                if event["type"] in {"completed", "failed", "cancelled"}:
                    return
        finally:
            subs = self._subscribers.get(run_id, [])
            if queue in subs:
                subs.remove(queue)

    # ---------------------------------------------------------------- execution

    def create(self, spec: RunSpec) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], spec=spec)
        self._runs[run.id] = run
        return run

    async def start(self, run: Run) -> None:
        asyncio.create_task(self._execute(run))

    async def _execute(self, run: Run) -> None:
        import os

        await self._emit(run, "queued", label=run.spec.label)
        try:
            env = {**os.environ, **run.spec.env}
            process = await asyncio.create_subprocess_exec(
                *run.spec.argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=run.spec.cwd,
            )
        except (OSError, ValueError) as exc:
            run.status = "failed"
            run.finished_at = _now()
            await self._emit(run, "failed", error=str(exc))
            return

        self._processes[run.id] = process
        run.status = "running"
        await self._emit(run, "started", pid=process.pid)

        async def pump(stream, channel: str) -> None:
            if stream is None:
                return
            async for line in stream:
                await self._emit(run, channel, line=line.decode(errors="replace").rstrip("\n"))

        await asyncio.gather(pump(process.stdout, "stdout"), pump(process.stderr, "stderr"))
        exit_code = await process.wait()
        self._processes.pop(run.id, None)
        run.exit_code = exit_code
        run.finished_at = _now()

        if run.status == "cancelling":
            run.status = "cancelled"
            await self._emit(run, "cancelled", exit_code=exit_code)
        elif exit_code == 0:
            run.status = "completed"
            await self._emit(run, "completed", exit_code=exit_code)
        else:
            run.status = "failed"
            await self._emit(run, "failed", exit_code=exit_code)

    async def cancel(self, run_id: str) -> bool:
        run = self._runs.get(run_id)
        if run is None or run.status in TERMINAL:
            return False
        process = self._processes.get(run_id)
        run.status = "cancelling"
        if process is not None and process.returncode is None:
            process.terminate()
            return True
        return False
