"""Dataset import and manifests (P05 I01–I04).

Images are **referenced, never copied**. A manifest holds a path, a content hash, a subject id and
a classification; the bytes stay where they are. Copying biometric samples into the studio's own
store would multiply the number of places a restricted sample lives, and every copy is somewhere
it can leak from (ADR-0005, ADR-0008).

`classification` is required with no default. An optional field would silently take whatever the
importer forgot, and the failure mode is a restricted sample in a public artifact, discovered after
publication when it cannot be recalled.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Literal

Classification = Literal["PUBLIC", "RESTRICTED", "PRIVATE", "SYNTHETIC", "GENERATED"]

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Sample:
    sample_id: str
    path: str
    sha256: str
    classification: Classification
    subject_id: str | None
    session_id: str | None = None
    authorization: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class DatasetManifest:
    """A referenced set of samples, with subject-aware splitting."""

    def __init__(self, name: str, samples: list[Sample], source: str):
        self.name = name
        self.samples = samples
        self.source = source

    # ------------------------------------------------------------------ import

    @classmethod
    def from_directory(
        cls,
        root: Path,
        *,
        name: str,
        classification: Classification,
        authorization: str | None = None,
        subject_from_parent: bool = True,
        limit: int | None = None,
    ) -> "DatasetManifest":
        """Import a directory tree.

        `subject_from_parent` reads the subject id from the containing directory, which is the
        layout LFW and most enrolment corpora use. Without a subject id there is no way to build a
        subject-disjoint split, so the field is populated at import rather than inferred later.
        """
        root = Path(root)
        if not root.is_dir():
            raise FileNotFoundError(f"not a directory: {root}")
        if classification != "PUBLIC" and not authorization:
            raise ValueError(
                f"classification {classification} requires an authorization statement before import"
            )

        samples: list[Sample] = []
        for path in cls._walk(root):
            digest = sha256_file(path)
            samples.append(
                Sample(
                    sample_id=digest,
                    path=str(path),
                    sha256=digest,
                    classification=classification,
                    subject_id=path.parent.name if subject_from_parent else None,
                    authorization=authorization,
                )
            )
            if limit is not None and len(samples) >= limit:
                break
        return cls(name=name, samples=samples, source=str(root))

    @staticmethod
    def _walk(root: Path) -> Iterator[Path]:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                yield path

    # ------------------------------------------------------------------ queries

    def __len__(self) -> int:
        return len(self.samples)

    @property
    def subjects(self) -> list[str]:
        return sorted({s.subject_id for s in self.samples if s.subject_id})

    def by_subject(self) -> dict[str, list[Sample]]:
        grouped: dict[str, list[Sample]] = {}
        for sample in self.samples:
            if sample.subject_id:
                grouped.setdefault(sample.subject_id, []).append(sample)
        return grouped

    def duplicates(self) -> dict[str, list[str]]:
        """Samples sharing a content hash. Identical bytes under two paths inflate a corpus and
        can put the same image on both sides of a split."""
        seen: dict[str, list[str]] = {}
        for sample in self.samples:
            seen.setdefault(sample.sha256, []).append(sample.path)
        return {digest: paths for digest, paths in seen.items() if len(paths) > 1}

    # ------------------------------------------------------------------ splits

    def subject_disjoint_split(
        self, *, train: float = 0.6, val: float = 0.2, seed: int = 0
    ) -> dict[str, list[Sample]]:
        """Split by SUBJECT, never by sample.

        Splitting by sample puts the same person in train and test, and the resulting accuracy
        measures memorisation rather than generalisation. The seed is explicit so a split can be
        reproduced exactly.
        """
        if not 0 < train < 1 or not 0 <= val < 1 or train + val >= 1:
            raise ValueError("train and val must be fractions with train + val < 1")

        import random

        subjects = self.subjects
        rng = random.Random(seed)
        shuffled = subjects[:]
        rng.shuffle(shuffled)

        n_train = int(len(shuffled) * train)
        n_val = int(len(shuffled) * val)
        assignment = {
            "train": set(shuffled[:n_train]),
            "val": set(shuffled[n_train : n_train + n_val]),
            "test": set(shuffled[n_train + n_val :]),
        }
        return {
            split: [s for s in self.samples if s.subject_id in members]
            for split, members in assignment.items()
        }

    @staticmethod
    def verify_disjoint(splits: dict[str, list[Sample]]) -> bool:
        subject_sets = {
            name: {s.subject_id for s in samples} for name, samples in splits.items()
        }
        names = list(subject_sets)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                if subject_sets[a] & subject_sets[b]:
                    return False
        return True

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source,
            "count": len(self.samples),
            "subjects": len(self.subjects),
            "samples": [s.to_dict() for s in self.samples],
        }

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def read(cls, path: Path) -> "DatasetManifest":
        data = json.loads(Path(path).read_text())
        return cls(
            name=data["name"],
            source=data["source"],
            samples=[Sample(**s) for s in data["samples"]],
        )


def public_export_is_safe(samples: Iterable[Sample]) -> tuple[bool, list[str]]:
    """Default-deny check for anything leaving the machine (ADR-0008)."""
    offenders = [s.path for s in samples if s.classification != "PUBLIC"]
    return (not offenders), offenders
