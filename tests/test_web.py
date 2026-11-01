"""Glass-box UI: the server streams the same trace the CLI writes, and never leaks the API key."""
import json

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from research_agent.web.server import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # runs/ and outputs/ go to a temp dir
    monkeypatch.setenv("LLM_API_KEY", "sk-secret-should-not-leak")
    return TestClient(app)


def test_config_has_budgets_but_no_key(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "max_tool_calls" in r.json()["budgets"]
    assert "sk-secret" not in r.text


def test_unknown_fault_rejected(client):
    assert client.post("/api/runs", json={"question": "x" * 20, "faults": ["rm:-rf"]}).status_code == 400


def test_invalid_input_streams_and_replays(client):
    run_id = client.post("/api/runs", json={"question": "   "}).json()["run_id"]
    with client.stream("GET", f"/api/runs/{run_id}/stream") as r:
        body = "".join(r.iter_text())
    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: {") and line != "data: {}"]
    names = [e.get("event") for e in events]
    assert names[0] == "run_started" and "answer_ready" in names and "run_finished" in names
    assert events[-1]["result"]["answer"]["status"] == "invalid_input"
    saved = client.get(f"/api/runs/{run_id}/trace").json()
    assert saved["result"]["answer"]["status"] == "invalid_input"
    assert any(r["run_id"] == run_id for r in client.get("/api/runs").json())
