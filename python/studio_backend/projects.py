"""Project persistence.

SQLite holds project and run metadata. Per ADR-0005 no biometric image bytes are stored here —
samples are referenced by path plus sha256, and the classification field is mandatory so a
restricted sample cannot reach an export by omission.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    studio_commit TEXT
);
CREATE TABLE IF NOT EXISTS run (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES project(id),
    label       TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    finished_at TEXT,
    exit_code   INTEGER,
    spec        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES run(id),
    kind        TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Project:
    id: str
    name: str
    root: Path
    created_at: str = field(default_factory=_now)

    @property
    def db_path(self) -> Path:
        return self.root / "project.sqlite"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "root": str(self.root),
            "created_at": self.created_at,
        }


class ProjectStore:
    """Creates, opens, and lists projects rooted under one workspace directory."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- lifecycle

    def create(self, name: str) -> Project:
        project_id = uuid.uuid4().hex[:12]
        root = self.workspace / project_id
        (root / "artifacts").mkdir(parents=True, exist_ok=True)
        project = Project(id=project_id, name=name, root=root)
        with closing(sqlite3.connect(project.db_path)) as db:
            db.executescript(SCHEMA)
            db.execute(
                "INSERT INTO project (id, name, created_at, studio_commit) VALUES (?, ?, ?, ?)",
                (project.id, project.name, project.created_at, None),
            )
            db.commit()
        (root / "project.json").write_text(json.dumps(project.to_dict(), indent=2))
        return project

    def open(self, project_id: str) -> Project | None:
        root = self.workspace / project_id
        manifest = root / "project.json"
        if not manifest.exists():
            return None
        data = json.loads(manifest.read_text())
        return Project(
            id=data["id"], name=data["name"], root=root, created_at=data["created_at"]
        )

    def list(self) -> list[Project]:
        projects = []
        for manifest in sorted(self.workspace.glob("*/project.json")):
            data = json.loads(manifest.read_text())
            projects.append(
                Project(
                    id=data["id"],
                    name=data["name"],
                    root=manifest.parent,
                    created_at=data["created_at"],
                )
            )
        return projects

    # ---------------------------------------------------------------- runs

    def record_run(self, project: Project, run_id: str, label: str, spec: dict) -> None:
        with closing(sqlite3.connect(project.db_path)) as db:
            db.execute(
                "INSERT INTO run (id, project_id, label, status, created_at, spec) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, project.id, label, "queued", _now(), json.dumps(spec)),
            )
            db.commit()

    def finish_run(self, project: Project, run_id: str, status: str, exit_code: int | None) -> None:
        with closing(sqlite3.connect(project.db_path)) as db:
            db.execute(
                "UPDATE run SET status = ?, finished_at = ?, exit_code = ? WHERE id = ?",
                (status, _now(), exit_code, run_id),
            )
            db.commit()

    def runs(self, project: Project) -> list[dict]:
        with closing(sqlite3.connect(project.db_path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, label, status, created_at, finished_at, exit_code "
                "FROM run ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def artifacts(self, project: Project) -> list[dict]:
        with closing(sqlite3.connect(project.db_path)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                "SELECT id, run_id, kind, path, sha256, created_at FROM artifact ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]
