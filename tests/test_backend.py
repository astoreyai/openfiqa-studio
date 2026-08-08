"""P03 gate tests — F02, F05, F06, F07, F08, F11.

The gate: the backend serves health, projects persist and reopen, runs stream events, cancellation
works, and the backend terminates cleanly.

Runs here execute real subprocesses with real exit codes. Nothing simulates a run — a test that
asserted on invented progress events would pass against a backend that cannot actually execute
anything, which is precisely the failure this gate exists to catch.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from studio_backend.app import create_app  # noqa: E402

PYTHON = sys.executable


@pytest.fixture
def client(tmp_path):
    app = create_app(workspace=tmp_path / "workspace")
    with TestClient(app) as c:
        yield c


def _wait_for(client, run_id, *, timeout=30.0):
    """Poll until the run reaches a terminal state, then return it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            return body
        time.sleep(0.05)
    pytest.fail(f"run {run_id} did not finish within {timeout}s")


# ---------------------------------------------------------------- health

def test_health_reports_registry_state(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["plugins"] == 4
    assert body["executable_plugins"] == ["ofiqpy"]


# ---------------------------------------------------------------- plugins

def test_blocked_plugins_are_listed_not_hidden(client):
    """ADR-0003. Hiding a blocked engine loses the information that it exists and why."""
    body = client.get("/api/plugins").json()
    ids = {p["plugin_id"] for p in body["plugins"]}
    assert ids == {"ofiqpy", "openfiqa", "ofiq_quality", "ofiq_project"}
    assert body["counts"]["blocked"] == 2

    blocked = {
        p["plugin_id"]: p["availability"]["blocker_id"]
        for p in body["plugins"]
        if p["availability"]["state"] == "BLOCKED"
    }
    assert blocked == {"ofiq_quality": "B-P01-02", "ofiq_project": "B-P01-04"}
    for plugin in body["plugins"]:
        if plugin["availability"]["state"] == "BLOCKED":
            assert plugin["availability"]["reason"]
            assert plugin["executable"] is False


def test_available_plugin_reports_its_evidence(client):
    body = client.get("/api/plugins/ofiqpy").json()
    verified = body["availability"]["verified_by"]
    assert verified["rc"] == 0
    assert verified["n_components"] == 28


def test_unknown_plugin_is_404(client):
    assert client.get("/api/plugins/nope").status_code == 404


def test_executing_a_blocked_plugin_is_refused_with_its_blocker(client):
    response = client.post("/api/runs/plugin/ofiq_quality")
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["state"] == "BLOCKED"
    assert detail["blocker_id"] == "B-P01-02"


def test_permitted_plugin_reports_the_missing_adapter_honestly(client):
    """ofiqpy is executable, but no adapter exists yet. 501 with a reason beats a fake result."""
    response = client.post("/api/runs/plugin/ofiqpy")
    assert response.status_code == 501
    assert "P04" in response.json()["detail"]["message"]


# ---------------------------------------------------------------- projects

def test_project_persists_and_reopens(client):
    created = client.post("/api/projects", json={"name": "lfw-study"}).json()
    assert created["name"] == "lfw-study"

    reopened = client.get(f"/api/projects/{created['id']}").json()
    assert reopened == created

    listed = client.get("/api/projects").json()["projects"]
    assert [p["id"] for p in listed] == [created["id"]]

    assert (Path(created["root"]) / "project.sqlite").exists()
    assert (Path(created["root"]) / "artifacts").is_dir()


def test_project_survives_a_new_app_instance(tmp_path):
    """Persistence means surviving process restart, not just living in memory."""
    workspace = tmp_path / "workspace"
    with TestClient(create_app(workspace=workspace)) as first:
        created = first.post("/api/projects", json={"name": "persisted"}).json()

    with TestClient(create_app(workspace=workspace)) as second:
        reopened = second.get(f"/api/projects/{created['id']}").json()
        assert reopened["name"] == "persisted"
        assert second.get(f"/api/projects/{created['id']}/runs").json()["runs"] == []


def test_unknown_project_is_404(client):
    assert client.get("/api/projects/nope").status_code == 404


# ---------------------------------------------------------------- runs

def test_run_executes_a_real_subprocess_and_reports_its_exit_code(client):
    created = client.post(
        "/api/runs",
        json={"label": "echo", "argv": [PYTHON, "-c", "print('from the run')"]},
    ).json()
    finished = _wait_for(client, created["run_id"])

    assert finished["status"] == "completed"
    assert finished["exit_code"] == 0
    stdout = [e["line"] for e in finished["events"] if e["type"] == "stdout"]
    assert "from the run" in stdout


def test_failing_run_reports_failure_not_success(client):
    created = client.post(
        "/api/runs",
        json={"label": "boom", "argv": [PYTHON, "-c", "import sys; sys.exit(3)"]},
    ).json()
    finished = _wait_for(client, created["run_id"])

    assert finished["status"] == "failed"
    assert finished["exit_code"] == 3


def test_unlaunchable_command_fails_rather_than_hanging(client):
    created = client.post(
        "/api/runs", json={"label": "missing", "argv": ["/nonexistent/binary"]}
    ).json()
    finished = _wait_for(client, created["run_id"])
    assert finished["status"] == "failed"


def test_empty_argv_is_rejected(client):
    assert client.post("/api/runs", json={"label": "empty", "argv": []}).status_code == 422


def test_cancellation_stops_a_running_process(client):
    created = client.post(
        "/api/runs",
        json={"label": "sleeper", "argv": [PYTHON, "-c", "import time; time.sleep(60)"]},
    ).json()
    run_id = created["run_id"]

    deadline = time.time() + 10
    while time.time() < deadline:
        if client.get(f"/api/runs/{run_id}").json()["status"] == "running":
            break
        time.sleep(0.05)
    else:
        pytest.fail("run never reached running state")

    assert client.post(f"/api/runs/{run_id}/cancel").json()["cancel_requested"] is True
    finished = _wait_for(client, run_id, timeout=20)
    assert finished["status"] == "cancelled"


def test_cancelling_a_finished_run_does_not_rewrite_it(client):
    created = client.post(
        "/api/runs", json={"label": "quick", "argv": [PYTHON, "-c", "pass"]}
    ).json()
    finished = _wait_for(client, created["run_id"])
    assert finished["status"] == "completed"

    body = client.post(f"/api/runs/{created['run_id']}/cancel").json()
    assert body["cancel_requested"] is False
    assert body["status"] == "completed"


# ---------------------------------------------------------------- websocket

def test_websocket_streams_run_events(client):
    created = client.post(
        "/api/runs",
        json={"label": "streamed", "argv": [PYTHON, "-c", "print('line one')"]},
    ).json()
    run_id = created["run_id"]

    seen = []
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        while True:
            event = ws.receive_json()
            seen.append(event)
            if event["type"] in {"completed", "failed", "cancelled"}:
                break

    types = [e["type"] for e in seen]
    assert "queued" in types and "started" in types and "completed" in types
    assert "line one" in [e["line"] for e in seen if e["type"] == "stdout"]
    assert all(e["run_id"] == run_id for e in seen)


def test_websocket_replays_backlog_for_a_late_subscriber(client):
    """A client connecting after a run finishes must still see the whole stream."""
    created = client.post(
        "/api/runs", json={"label": "already-done", "argv": [PYTHON, "-c", "print('early')"]}
    ).json()
    run_id = created["run_id"]
    _wait_for(client, run_id)

    seen = []
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        for _ in range(10):
            try:
                seen.append(ws.receive_json())
            except Exception:
                break
            if seen[-1]["type"] in {"completed", "failed", "cancelled"}:
                break

    assert "early" in [e["line"] for e in seen if e["type"] == "stdout"]


def test_websocket_for_unknown_run_reports_an_error(client):
    with client.websocket_connect("/ws/runs/nope") as ws:
        assert ws.receive_json()["type"] == "error"
