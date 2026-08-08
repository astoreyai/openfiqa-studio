"""P11 security tests — the boundaries, attempted rather than asserted.

A security review that only reads code produces a document. These tests try the thing: a filename
carrying shell metacharacters, an export containing a restricted sample, an environment variable
that must not reach a log. A boundary nobody has pushed on is a boundary nobody has tested.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_backend.app import create_app  # noqa: E402
from studio_data.dataset import Sample, public_export_is_safe  # noqa: E402
from studio_security import sbom  # noqa: E402

needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(workspace=tmp_path / "workspace")) as c:
        yield c


def _wait(client, run_id, timeout=60.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.05)
    pytest.fail("run did not finish")


# ---------------------------------------------------------------- S03 command execution

def test_shell_metacharacters_in_arguments_are_not_interpreted(client, tmp_path):
    """The run system takes argv as a LIST and never builds a shell string.

    If it did, a filename like `x; rm -rf ~` would execute. Here the metacharacters must arrive at
    the child process as literal text.
    """
    canary = tmp_path / "canary.txt"
    canary.write_text("intact")
    hostile = f"payload; rm -f {canary}; echo pwned"

    created = client.post(
        "/api/runs",
        json={"label": "injection", "argv": [sys.executable, "-c", "import sys; print(sys.argv[1])",
                                             hostile]},
    ).json()
    finished = _wait(client, created["run_id"])

    stdout = [e.get("line", "") for e in finished["events"] if e["type"] == "stdout"]

    # The argument arrives whole, as data.
    assert hostile in stdout, "the metacharacters should arrive as literal text"
    # The `rm` never ran.
    assert canary.read_text() == "intact", "the shell executed part of the argument"
    # A shell would have run `echo pwned` as a separate command, producing its own line. Searching
    # the joined output would be wrong: the literal argument legitimately *contains* that text.
    assert "pwned" not in stdout, "a standalone 'pwned' line means the shell interpreted the string"
    assert len(stdout) == 1, f"expected exactly one echoed line, got {stdout}"


def test_run_api_offers_no_shell_string_field(client):
    """There is no way to ask the backend to run a command line. The absence is the control."""
    schema = client.get("/openapi.json").json()
    create_run = schema["components"]["schemas"]["CreateRun"]["properties"]
    assert "argv" in create_run
    assert create_run["argv"]["type"] == "array"
    for forbidden in ("shell", "command", "cmd", "script"):
        assert forbidden not in create_run


def test_empty_or_missing_argv_is_rejected(client):
    assert client.post("/api/runs", json={"label": "x", "argv": []}).status_code == 422
    assert client.post("/api/runs", json={"label": "x"}).status_code == 422


# ---------------------------------------------------------------- S02 biometric data boundary

def test_public_export_refuses_restricted_samples():
    restricted = Sample(
        sample_id="a", path="/private/subject/a.jpg", sha256="0" * 64,
        classification="RESTRICTED", subject_id="s1", authorization="IRB-2026-01",
    )
    public = Sample(
        sample_id="b", path="/public/b.jpg", sha256="1" * 64,
        classification="PUBLIC", subject_id="s2",
    )
    ok, offenders = public_export_is_safe([public, restricted])
    assert not ok
    assert offenders == ["/private/subject/a.jpg"]

    ok, offenders = public_export_is_safe([public])
    assert ok and offenders == []


def test_generated_and_synthetic_are_distinct_classifications():
    """They must never collapse into PUBLIC, or a generated sample becomes indistinguishable from
    an authentic acquisition downstream."""
    from studio_data.dataset import Classification
    import typing

    values = set(typing.get_args(Classification))
    assert {"PUBLIC", "RESTRICTED", "PRIVATE", "SYNTHETIC", "GENERATED"} == values


def test_no_biometric_image_is_tracked_by_git():
    """The repository must never contain a face. Checked against git's own index rather than the
    working tree, because .gitignore protects the tree but the index is what ships."""
    tracked = sbom.git_tracked_files()
    assert tracked, "expected a git index"
    images = [
        f for f in tracked
        if Path(f).suffix.lower() in {".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
    ]
    assert images == [], f"image files are tracked: {images}"

    # The only PNGs permitted are the application icon.
    pngs = [f for f in tracked if f.lower().endswith(".png")]
    assert all("src-tauri/icons/" in f for f in pngs), f"unexpected PNGs tracked: {pngs}"


def test_no_local_machine_paths_are_tracked():
    """config/local-paths.yaml holds machine-specific engine locations, one of which belongs to a
    repository that is not publicly released."""
    assert "config/local-paths.yaml" not in sbom.git_tracked_files()
    assert (REPO / "config" / "local-paths.example.yaml").exists()


# ---------------------------------------------------------------- S04 secrets and logging

def test_run_events_do_not_echo_the_process_environment(client):
    """A run inherits the parent environment so engines can find their weights. None of it may
    appear in the event stream unless the child itself printed it."""
    created = client.post(
        "/api/runs",
        json={"label": "env", "argv": [sys.executable, "-c", "print('finished')"],
              "env": {"OFS_FAKE_SECRET": "super-secret-value"}},
    ).json()
    finished = _wait(client, created["run_id"])

    serialised = json.dumps(finished)
    assert "super-secret-value" not in serialised
    assert "finished" in serialised


def test_run_records_do_not_persist_the_supplied_env(client):
    created = client.post(
        "/api/runs",
        json={"label": "env2", "argv": [sys.executable, "-c", "pass"],
              "env": {"TOKEN": "abcd1234"}},
    ).json()
    _wait(client, created["run_id"])
    listing = json.dumps(client.get("/api/runs").json())
    assert "abcd1234" not in listing


def test_adapter_error_detail_is_truncated(client):
    """Engine stderr is surfaced for diagnosis but bounded, so a failing engine cannot dump an
    unbounded amount of its environment into an HTTP response."""
    import inspect

    from studio_backend import app as app_module

    source = inspect.getsource(app_module)
    assert "exc.stderr[-2000:]" in source


# ---------------------------------------------------------------- S05 plugin trust

def test_blocked_plugins_cannot_be_executed_through_any_route(client):
    """Both execution routes go through the same registry check, so neither can be the soft one."""
    for route in ("/api/engines/ofiq_quality/assess", "/api/runs/plugin/ofiq_quality"):
        response = client.post(route, json={"image_path": "/does/not/matter.jpg"})
        assert response.status_code == 409, route
        assert response.json()["detail"]["blocker_id"] == "B-P01-02"


def test_registry_refuses_to_serve_an_invalid_manifest(tmp_path, monkeypatch):
    """A malformed plugin contract must stop the registry rather than being served partially."""
    from studio_backend.registry import PluginRegistry, RegistryError
    from studio_core import schemas

    bad = {"plugin_id": "broken"}  # missing nearly everything
    monkeypatch.setattr(schemas, "load_plugin_manifests", lambda: {"broken": bad})
    import studio_backend.registry as registry_module

    monkeypatch.setattr(registry_module, "load_plugin_manifests", lambda: {"broken": bad})
    with pytest.raises(RegistryError):
        PluginRegistry()


# ---------------------------------------------------------------- S06 SBOM

def test_sbom_is_generated_from_the_installed_environment():
    """A lockfile says what should be present; this says what is."""
    bill = sbom.generate(timestamp="2026-08-08T00:00:00+00:00")
    names = {c.name.lower() for c in bill.components}

    for expected in ("fastapi", "pydantic", "jsonschema", "pillow", "numpy", "onnxruntime"):
        assert expected in names, f"{expected} missing from the SBOM"

    assert bill.platform["python"].startswith("3.11")
    assert bill.to_dict()["component_count"] == len(bill.components)


def test_sbom_records_engines_that_are_not_pip_packages():
    """An SBOM listing only pip packages would miss that an MIT package runs on BSI-licensed
    weights from a separate repository (B-P01-09)."""
    engines = {e["name"]: e for e in sbom.generate().external_engines}
    assert "ofiqpy" in engines and "OFIQ-Project" in engines
    assert "BSI" in engines["ofiqpy"]["license"]
    if engines["OFIQ-Project"]["present"]:
        assert len(engines["OFIQ-Project"]["commit"]) == 40


def test_sbom_licences_are_read_not_assumed():
    bill = sbom.generate()
    by_name = {c.name.lower(): c for c in bill.components}
    # Every component either reports a licence it declared, or None. Never a guess.
    for component in bill.components:
        assert component.license is None or isinstance(component.license, str)
    assert by_name["pytest"].license is not None


# ---------------------------------------------------------------- S11 offline

def test_the_control_plane_serves_with_no_outbound_network(client, monkeypatch):
    """ADR-0008: local-first. Blocking socket creation must not stop the studio working."""
    import socket

    def refuse(*_args, **_kwargs):
        raise OSError("network disabled for this test")

    monkeypatch.setattr(socket, "socket", refuse)

    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/plugins").json()["counts"]["total"] == 4
    assert client.post("/api/projects", json={"name": "offline"}).status_code == 201


def test_cors_is_an_allowlist_not_a_wildcard(client):
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
    allowed = client.get("/api/health", headers={"Origin": "tauri://localhost"})
    assert allowed.headers["access-control-allow-origin"] == "tauri://localhost"
