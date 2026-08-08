"""Provenance DAG (P09 P01–P04).

Provenance is stored as typed relationships between artifacts and traversed in BOTH directions.
A log answers "what happened". The harder question — and the one that catches a real problem — is
"given this published figure, which samples are behind it", and its inverse, "given this subject,
which published claims depend on them". Only the second direction catches a figure that includes a
subject whose authorization was later withdrawn.

No artifact may be an orphan. Registering an edge that names an unknown artifact fails, because a
dangling reference is a lineage that looks complete and is not.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RELATIONS = (
    "DERIVED_FROM",
    "TRANSFORMED_FROM",
    "GENERATED_BY",
    "EVALUATED_BY",
    "TRAINED_FROM",
    "USES_MODEL",
    "USES_DATASET",
    "USES_CONFIG",
    "VISUALIZED_FROM",
    "PUBLISHED_AS",
    "REPRODUCES",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS artifact (
    artifact_id TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    sha256      TEXT,
    created_at  TEXT NOT NULL,
    attributes  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relation (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    subject  TEXT NOT NULL REFERENCES artifact(artifact_id),
    relation TEXT NOT NULL,
    object   TEXT NOT NULL REFERENCES artifact(artifact_id),
    UNIQUE(subject, relation, object)
);
CREATE INDEX IF NOT EXISTS relation_subject ON relation(subject);
CREATE INDEX IF NOT EXISTS relation_object  ON relation(object);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrphanArtifact(KeyError):
    """An edge named an artifact that was never registered."""


@dataclass
class Artifact:
    artifact_id: str
    kind: str
    sha256: str | None
    created_at: str
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "attributes": self.attributes,
        }


class ProvenanceStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as db:
            db.executescript(SCHEMA)
            db.commit()

    # ------------------------------------------------------------------ writes

    def add_artifact(
        self, artifact_id: str, kind: str, *, sha256: str | None = None, **attributes: Any
    ) -> Artifact:
        artifact = Artifact(artifact_id, kind, sha256, _now(), attributes)
        with closing(sqlite3.connect(self.db_path)) as db:
            db.execute(
                "INSERT OR REPLACE INTO artifact "
                "(artifact_id, kind, sha256, created_at, attributes) VALUES (?, ?, ?, ?, ?)",
                (artifact_id, kind, sha256, artifact.created_at, json.dumps(attributes)),
            )
            db.commit()
        return artifact

    def relate(self, subject: str, relation: str, object_: str) -> None:
        if relation not in RELATIONS:
            raise ValueError(f"unknown relation {relation!r}; expected one of {RELATIONS}")
        with closing(sqlite3.connect(self.db_path)) as db:
            for identifier in (subject, object_):
                exists = db.execute(
                    "SELECT 1 FROM artifact WHERE artifact_id = ?", (identifier,)
                ).fetchone()
                if not exists:
                    raise OrphanArtifact(
                        f"{identifier} is not a registered artifact; a dangling reference is a "
                        f"lineage that looks complete and is not"
                    )
            db.execute(
                "INSERT OR IGNORE INTO relation (subject, relation, object) VALUES (?, ?, ?)",
                (subject, relation, object_),
            )
            db.commit()

    # ------------------------------------------------------------------ reads

    def get(self, artifact_id: str) -> Artifact | None:
        with closing(sqlite3.connect(self.db_path)) as db:
            db.row_factory = sqlite3.Row
            row = db.execute(
                "SELECT * FROM artifact WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            return None
        return Artifact(
            row["artifact_id"], row["kind"], row["sha256"], row["created_at"],
            json.loads(row["attributes"]),
        )

    def edges(self, artifact_id: str) -> dict[str, list[tuple[str, str]]]:
        with closing(sqlite3.connect(self.db_path)) as db:
            out = db.execute(
                "SELECT relation, object FROM relation WHERE subject = ? ORDER BY relation, object",
                (artifact_id,),
            ).fetchall()
            inc = db.execute(
                "SELECT relation, subject FROM relation WHERE object = ? ORDER BY relation, subject",
                (artifact_id,),
            ).fetchall()
        return {"outgoing": [tuple(r) for r in out], "incoming": [tuple(r) for r in inc]}

    def ancestors(self, artifact_id: str) -> list[str]:
        """Everything this artifact depends on — figure back to dataset."""
        return self._walk(artifact_id, forward=True)

    def descendants(self, artifact_id: str) -> list[str]:
        """Everything that depends on this artifact — sample forward to published claim."""
        return self._walk(artifact_id, forward=False)

    def _walk(self, start: str, *, forward: bool) -> list[str]:
        if self.get(start) is None:
            raise OrphanArtifact(start)
        column, other = ("subject", "object") if forward else ("object", "subject")
        seen: list[str] = []
        visited = {start}
        frontier = [start]
        with closing(sqlite3.connect(self.db_path)) as db:
            while frontier:
                current = frontier.pop(0)
                rows = db.execute(
                    f"SELECT {other} FROM relation WHERE {column} = ? ORDER BY {other}",
                    (current,),
                ).fetchall()
                for (nxt,) in rows:
                    if nxt not in visited:
                        visited.add(nxt)
                        seen.append(nxt)
                        frontier.append(nxt)
        return seen

    def lineage_path(self, artifact_id: str) -> list[dict[str, Any]]:
        """The full ancestry as artifact records, for a traversal view."""
        records = [self.get(artifact_id)]
        records.extend(self.get(a) for a in self.ancestors(artifact_id))
        return [r.to_dict() for r in records if r is not None]

    def orphans(self) -> list[str]:
        """Artifacts with no relations at all. Every result should have ancestry."""
        with closing(sqlite3.connect(self.db_path)) as db:
            rows = db.execute(
                "SELECT artifact_id FROM artifact WHERE artifact_id NOT IN "
                "(SELECT subject FROM relation UNION SELECT object FROM relation) "
                "ORDER BY artifact_id"
            ).fetchall()
        return [r[0] for r in rows]

    def all_ids(self) -> list[str]:
        with closing(sqlite3.connect(self.db_path)) as db:
            return [r[0] for r in db.execute("SELECT artifact_id FROM artifact ORDER BY created_at")]


def ingest_run_manifest(store: ProvenanceStore, manifest: dict[str, Any]) -> str:
    """Turn a workflow run manifest into provenance artifacts and edges.

    Blocked nodes are registered too, with their blocker id. A lineage that omitted them would show
    a complete pipeline where a stage never ran.
    """
    run_id = f"run:{manifest['workflow_sha256'][:16]}"
    store.add_artifact(
        run_id,
        "run",
        sha256=manifest["workflow_sha256"],
        workflow_name=manifest["workflow_name"],
        status=manifest["status"],
        started_at=manifest["started_at"],
    )

    previous_by_node: dict[str, str] = {}
    for node in manifest["nodes"]:
        node_id = f"{run_id}/{node['node_id']}"
        store.add_artifact(
            node_id,
            f"node:{node['kind']}",
            parameters=node["parameters"],
            status=node["status"],
            blocker_id=node.get("blocker_id"),
            outputs=len(node.get("outputs", [])),
        )
        store.relate(node_id, "GENERATED_BY", run_id)
        previous_by_node[node["node_id"]] = node_id

    # Edges between nodes come from the manifest's own upstream relationships where present.
    for node in manifest["nodes"]:
        node_id = previous_by_node[node["node_id"]]
        for upstream in node.get("upstream", []):
            if upstream in previous_by_node:
                store.relate(node_id, "DERIVED_FROM", previous_by_node[upstream])

    return run_id
