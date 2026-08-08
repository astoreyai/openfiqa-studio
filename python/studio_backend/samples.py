"""Serving sample bytes to the local shell (P05 I06/I07).

The Image Lab needs to display a face. That means the control plane serves image bytes over HTTP,
which is the first time anything in this system does — so the boundary is drawn here explicitly.

**Only files inside a configured corpus root may be served.** The request names a path; the server
resolves it, follows symlinks, and refuses anything that does not land inside a registered root.
Without that, `?path=/etc/shadow` is a file-read primitive reachable from any page the browser will
talk to, and the CORS allowlist is the only thing standing between it and a hostile origin.

Resolution happens before the containment check, not after: `corpus/../../etc/passwd` only looks
contained until it is resolved.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from studio_adapters import paths

CORPUS_KEYS = ("lfw_root",)

SERVABLE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


class SampleAccessDenied(PermissionError):
    """The requested file is outside every configured corpus root."""


def corpus_roots() -> list[Path]:
    roots = []
    for key in CORPUS_KEYS:
        root = paths.get(key, required=False)
        if root and root.exists():
            roots.append(root.resolve())
    return roots


def resolve_servable(requested: str | Path) -> Path:
    """Return a path that is definitely inside a corpus root, or raise.

    Every failure mode raises the same exception type with a message that does not echo the
    resolved path — a containment check that reports where a file *is* becomes a way to probe the
    filesystem one request at a time.
    """
    roots = corpus_roots()
    if not roots:
        raise SampleAccessDenied("no corpus root is configured, so no sample may be served")

    candidate = Path(requested)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise SampleAccessDenied("requested sample is not a readable file") from None

    if resolved.suffix.lower() not in SERVABLE_SUFFIXES:
        raise SampleAccessDenied("requested file is not an image")

    for root in roots:
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        if not resolved.is_file():
            raise SampleAccessDenied("requested sample is not a readable file")
        return resolved

    raise SampleAccessDenied("requested sample is outside every configured corpus root")


def media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def list_samples(limit: int = 200) -> list[dict[str, str]]:
    """Samples available to the Image Lab, from configured corpus roots only.

    Returns paths and subject ids but no bytes and no hashes: hashing a whole corpus on a listing
    request would make browsing cost minutes.
    """
    entries: list[dict[str, str]] = []
    for root in corpus_roots():
        for path in sorted(root.rglob("*")):
            if len(entries) >= limit:
                return entries
            if path.is_file() and path.suffix.lower() in SERVABLE_SUFFIXES:
                entries.append({
                    "path": str(path),
                    "name": path.name,
                    "subject_id": path.parent.name,
                })
    return entries
