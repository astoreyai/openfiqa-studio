"""Verification pairs (P05 I05).

The LFW pair protocol is read from the corpus's own `pairs.txt` rather than generated. Generating
pairs would produce a different evaluation from every published LFW number, making comparison to
the literature meaningless — and the whole point of a standard protocol is that it is the same one
everybody else ran.

Format, confirmed by reading the file:

    <folds>\\t<pairs-per-fold>            header, e.g. "10  300"
    <name>\\t<n1>\\t<n2>                  genuine — same subject, images n1 and n2
    <name1>\\t<n1>\\t<name2>\\t<n2>        impostor — different subjects
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Pair:
    pair_id: str
    left: Path
    right: Path
    label: str  # "genuine" | "impostor"
    fold: int

    def to_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "left": str(self.left),
            "right": str(self.right),
            "label": self.label,
            "fold": self.fold,
        }


def _image(root: Path, subject: str, index: int) -> Path:
    return root / subject / f"{subject}_{int(index):04d}.jpg"


def read_lfw_pairs(pairs_file: Path, image_root: Path) -> list[Pair]:
    """Parse the official protocol. Malformed lines raise rather than being skipped.

    Silently dropping a line would change the fold sizes and quietly alter every metric computed
    from them.
    """
    pairs_file = Path(pairs_file)
    image_root = Path(image_root)
    lines = [ln.rstrip("\n") for ln in pairs_file.read_text().splitlines() if ln.strip()]

    header = lines[0].split()
    if len(header) != 2:
        raise ValueError(f"unexpected LFW header: {lines[0]!r}")
    n_folds, per_fold = int(header[0]), int(header[1])

    pairs: list[Pair] = []
    body = lines[1:]
    expected = n_folds * per_fold * 2
    if len(body) != expected:
        raise ValueError(
            f"{pairs_file} has {len(body)} pair lines; the header declares {expected}"
        )

    for i, line in enumerate(body):
        fields = line.split("\t") if "\t" in line else line.split()
        fold = i // (per_fold * 2)
        if len(fields) == 3:
            subject, a, b = fields
            pairs.append(
                Pair(
                    pair_id=f"g{i}",
                    left=_image(image_root, subject, int(a)),
                    right=_image(image_root, subject, int(b)),
                    label="genuine",
                    fold=fold,
                )
            )
        elif len(fields) == 4:
            subject_a, a, subject_b, b = fields
            pairs.append(
                Pair(
                    pair_id=f"i{i}",
                    left=_image(image_root, subject_a, int(a)),
                    right=_image(image_root, subject_b, int(b)),
                    label="impostor",
                    fold=fold,
                )
            )
        else:
            raise ValueError(f"{pairs_file}:{i + 2} has {len(fields)} fields: {line!r}")

    return pairs


def pair_counts(pairs: list[Pair]) -> dict[str, int]:
    return {
        "total": len(pairs),
        "genuine": sum(1 for p in pairs if p.label == "genuine"),
        "impostor": sum(1 for p in pairs if p.label == "impostor"),
        "folds": len({p.fold for p in pairs}),
    }


def missing_images(pairs: list[Pair]) -> list[str]:
    """Pairs referencing a file that is not on disk.

    Reported rather than dropped: a protocol whose images are partly absent yields metrics over a
    silently different population.
    """
    missing = []
    for pair in pairs:
        for side in (pair.left, pair.right):
            if not side.exists():
                missing.append(str(side))
    return missing
