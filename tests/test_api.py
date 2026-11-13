from fastapi.testclient import TestClient

from app.main import create_app
from app.providers import FixtureSearch


def test_api_persists_run(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}", FixtureSearch())
    client = TestClient(app)
    response = client.post("/api/runs", json={"topic": "Battery recycling programs"})
    assert response.status_code == 202
    run_id = response.json()["id"]
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "completed"
    assert detail["result"]["sources"]
    assert client.get("/api/runs").json()[0]["id"] == run_id
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health").json()["model_enabled"] is False
    assert "Research Agent" in client.get("/").text


def test_api_rejects_blank_topic(tmp_path):
    client = TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}", FixtureSearch()))
    assert client.post("/api/runs", json={"topic": "   "}).status_code == 422
    assert client.get("/api/runs/missing").status_code == 404


def test_api_persists_failed_run(tmp_path):
    class BrokenSearch:
        name = "broken"

        def search(self, query):
            raise TimeoutError("synthetic timeout")

    client = TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}", BrokenSearch()))
    run_id = client.post("/api/runs", json={"topic": "sample topic"}).json()["id"]
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "failed"
    assert run["attempts"] == 2
    assert [event["step"] for event in run["events"]].count("search_error") == 2
