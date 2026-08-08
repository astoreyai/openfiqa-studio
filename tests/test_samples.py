"""P05 I06/I07 — serving sample bytes to the Image Lab.

This is the first endpoint in the system that returns file contents, so most of these tests are
attempts to make it return the wrong file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_backend.app import create_app  # noqa: E402
from studio_backend.samples import (  # noqa: E402
    SampleAccessDenied,
    corpus_roots,
    list_samples,
    resolve_servable,
)

needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(workspace=tmp_path / "workspace")) as c:
        yield c


@pytest.fixture(scope="module")
def a_sample() -> dict:
    if not paths.available("lfw_root"):
        pytest.skip("corpus not configured")
    samples = list_samples(limit=1)
    if not samples:
        pytest.skip("no samples found")
    return samples[0]


# ---------------------------------------------------------------- containment

@needs_corpus
def test_a_corpus_image_is_served(client, a_sample):
    response = client.get("/api/samples/image", params={"path": a_sample["path"]})
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 1000


@needs_corpus
def test_absolute_path_outside_the_corpus_is_refused(client):
    """Without containment this endpoint is an arbitrary file read reachable from any origin the
    CORS allowlist admits."""
    for hostile in ("/etc/passwd", "/etc/hosts", str(REPO / "README.md")):
        response = client.get("/api/samples/image", params={"path": hostile})
        assert response.status_code == 403, hostile


@needs_corpus
def test_traversal_out_of_the_corpus_is_refused(client, a_sample):
    """`corpus/../../etc/passwd` only looks contained until it is resolved, which is why
    resolution happens before the containment check."""
    escape = str(Path(a_sample["path"]).parent / ".." / ".." / ".." / ".." / "etc" / "passwd")
    assert client.get("/api/samples/image", params={"path": escape}).status_code == 403


@needs_corpus
def test_a_non_image_inside_the_corpus_is_refused(tmp_path):
    """Containment alone is not enough — a corpus directory could hold a notes file."""
    root = paths.get("lfw_root")
    intruder = root / "__test_note.txt"
    intruder.write_text("not an image")
    try:
        with pytest.raises(SampleAccessDenied, match="not an image"):
            resolve_servable(intruder)
    finally:
        intruder.unlink()


@needs_corpus
def test_a_missing_file_is_refused_without_revealing_whether_it_exists(client):
    root = paths.get("lfw_root")
    response = client.get(
        "/api/samples/image", params={"path": str(root / "nope" / "missing.jpg")}
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    # The message must not echo a resolved path, or the endpoint becomes a filesystem probe.
    assert "/mnt" not in detail and "missing.jpg" not in detail


def test_no_corpus_configured_means_nothing_is_servable(monkeypatch):
    monkeypatch.setattr("studio_backend.samples.corpus_roots", lambda: [])
    with pytest.raises(SampleAccessDenied, match="no corpus root"):
        resolve_servable("/anything.jpg")


@needs_corpus
def test_symlink_pointing_out_of_the_corpus_is_refused():
    """resolve(strict=True) follows the link, so the check sees the real destination."""
    root = paths.get("lfw_root")
    link = root / "__test_link.jpg"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to("/etc/hosts")
    try:
        with pytest.raises(SampleAccessDenied):
            resolve_servable(link)
    finally:
        link.unlink()


# ---------------------------------------------------------------- listing

@needs_corpus
def test_listing_returns_only_corpus_images(client):
    body = client.get("/api/samples?limit=5").json()["samples"]
    assert len(body) == 5
    roots = [str(r) for r in corpus_roots()]
    for entry in body:
        assert any(entry["path"].startswith(r) for r in roots)
        assert Path(entry["path"]).suffix.lower() in {".jpg", ".jpeg", ".png"}
        assert entry["subject_id"]


@needs_corpus
def test_listing_returns_no_bytes_and_no_hashes(client):
    """Hashing a whole corpus on a listing request would make browsing cost minutes."""
    entry = client.get("/api/samples?limit=1").json()["samples"][0]
    assert set(entry) == {"path", "name", "subject_id"}


@needs_corpus
def test_listing_respects_its_limit(client):
    assert len(client.get("/api/samples?limit=3").json()["samples"]) == 3
