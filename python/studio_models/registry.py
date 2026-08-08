"""Model registry (P08 M14).

States are `EXPERIMENTAL | CANDIDATE | VALIDATED | ARCHIVED`. None implies certification,
accreditation, or operational approval — the studio has no authority to grant any of those, and a
registry that said "APPROVED" would eventually be screenshotted into a slide.

`VALIDATED` means specific evidence exists and is linked. It does not mean anyone accepted it.

Lineage is required at registration rather than attached later. A model whose training data is
recorded afterwards is a model whose training data is remembered, and memory is exactly what
provenance is supposed to replace.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

State = Literal["EXPERIMENTAL", "CANDIDATE", "VALIDATED", "ARCHIVED"]
STATES: tuple[State, ...] = ("EXPERIMENTAL", "CANDIDATE", "VALIDATED", "ARCHIVED")

# Words that would imply an authority the studio does not have.
FORBIDDEN_STATE_WORDS = {"APPROVED", "CERTIFIED", "ACCREDITED", "PRODUCTION", "OPERATIONAL"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS model (
    model_id     TEXT PRIMARY KEY,
    sha256       TEXT NOT NULL,
    path         TEXT NOT NULL,
    framework    TEXT NOT NULL,
    state        TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    info         TEXT NOT NULL,
    lineage      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_evidence (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id  TEXT NOT NULL REFERENCES model(model_id),
    kind      TEXT NOT NULL,
    detail    TEXT NOT NULL,
    added_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LineageIncomplete(ValueError):
    """Registration refused: the record would not say where the model came from."""


@dataclass
class Lineage:
    """Where a model came from. Every field is required, `None` included explicitly.

    Writing `None` is a statement — "this model has no base checkpoint" — whereas omitting the
    field is silence, and silence is indistinguishable from an oversight when the record is read
    six months later.
    """

    source: str
    base_checkpoint: str | None
    dataset_manifest: str | None
    training_run_id: str | None
    git_commit: str | None
    notes: str | None = None

    REQUIRED = ("source", "base_checkpoint", "dataset_manifest", "training_run_id", "git_commit")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "base_checkpoint": self.base_checkpoint,
            "dataset_manifest": self.dataset_manifest,
            "training_run_id": self.training_run_id,
            "git_commit": self.git_commit,
            "notes": self.notes,
        }


@dataclass
class RegisteredModel:
    model_id: str
    sha256: str
    path: str
    framework: str
    state: State
    registered_at: str
    info: dict[str, Any]
    lineage: dict[str, Any]
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "sha256": self.sha256,
            "path": self.path,
            "framework": self.framework,
            "state": self.state,
            "registered_at": self.registered_at,
            "info": self.info,
            "lineage": self.lineage,
            "evidence": self.evidence,
        }


class ModelRegistry:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(SCHEMA)
            db.commit()

    # ------------------------------------------------------------------ registration

    def register(
        self,
        info: Any,
        lineage: Lineage,
        *,
        state: State = "EXPERIMENTAL",
        model_id: str | None = None,
    ) -> RegisteredModel:
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {state!r}")

        missing = [f for f in Lineage.REQUIRED if not hasattr(lineage, f)]
        if missing or not lineage.source:
            raise LineageIncomplete(f"lineage is missing: {missing or ['source']}")

        info_dict = info.to_dict() if hasattr(info, "to_dict") else dict(info)
        identifier = model_id or f"{info_dict['model_id']}@{info_dict['sha256'][:12]}"

        record = RegisteredModel(
            model_id=identifier,
            sha256=info_dict["sha256"],
            path=info_dict["path"],
            framework=info_dict["framework"],
            state=state,
            registered_at=_now(),
            info=info_dict,
            lineage=lineage.to_dict(),
        )
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute(
                "INSERT OR REPLACE INTO model "
                "(model_id, sha256, path, framework, state, registered_at, info, lineage) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.model_id, record.sha256, record.path, record.framework,
                    record.state, record.registered_at,
                    json.dumps(record.info), json.dumps(record.lineage),
                ),
            )
            db.commit()
        return record

    # ------------------------------------------------------------------ state changes

    def promote(self, model_id: str, state: State, *, evidence: str) -> RegisteredModel:
        """Change a model's state. Promotion to VALIDATED requires linked evidence.

        The evidence argument is mandatory for the same reason the state names avoid
        certification language: a state that can be set by assertion alone means nothing.
        """
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}, got {state!r}")
        if state.upper() in FORBIDDEN_STATE_WORDS:
            raise ValueError(f"{state} implies an authority the studio does not have")
        if state == "VALIDATED" and not evidence.strip():
            raise ValueError("promotion to VALIDATED requires evidence")

        with closing(sqlite3.connect(self.db_path)) as db:
            cursor = db.execute(
                "UPDATE model SET state = ? WHERE model_id = ?", (state, model_id)
            )
            if cursor.rowcount == 0:
                raise KeyError(model_id)
            db.execute(
                "INSERT INTO model_evidence (model_id, kind, detail, added_at) VALUES (?, ?, ?, ?)",
                (model_id, f"promoted_to_{state}", evidence, _now()),
            )
            db.commit()
        model = self.get(model_id)
        assert model is not None
        return model

    def add_evidence(self, model_id: str, kind: str, detail: str) -> None:
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute(
                "INSERT INTO model_evidence (model_id, kind, detail, added_at) VALUES (?, ?, ?, ?)",
                (model_id, kind, detail, _now()),
            )
            db.commit()

    # ------------------------------------------------------------------ queries

    def get(self, model_id: str) -> RegisteredModel | None:
        with closing(sqlite3.connect(self.db_path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM model WHERE model_id = ?", (model_id,)).fetchone()
            if row is None:
                return None
            evidence = [
                dict(r)
                for r in db.execute(
                    "SELECT kind, detail, added_at FROM model_evidence WHERE model_id = ? "
                    "ORDER BY added_at",
                    (model_id,),
                ).fetchall()
            ]
        return RegisteredModel(
            model_id=row["model_id"],
            sha256=row["sha256"],
            path=row["path"],
            framework=row["framework"],
            state=row["state"],
            registered_at=row["registered_at"],
            info=json.loads(row["info"]),
            lineage=json.loads(row["lineage"]),
            evidence=evidence,
        )

    def all(self) -> list[RegisteredModel]:
        with closing(sqlite3.connect(self.db_path)) as db:
            ids = [r[0] for r in db.execute("SELECT model_id FROM model ORDER BY registered_at")]
        return [m for m in (self.get(i) for i in ids) if m is not None]

    def verify_integrity(self, model_id: str) -> tuple[bool, str | None]:
        """Re-hash the file and compare. A model whose bytes changed is not the model registered."""
        record = self.get(model_id)
        if record is None:
            raise KeyError(model_id)
        path = Path(record.path)
        if not path.exists():
            return False, f"registered file is missing: {path}"

        from studio_models.loaders import sha256_file

        current = sha256_file(path)
        if current != record.sha256:
            return False, f"sha256 changed: registered {record.sha256[:12]}, on disk {current[:12]}"
        return True, None
