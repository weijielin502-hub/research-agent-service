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
    assert detail["result"]["search_depth"] == "fixture"
    assert detail["result"]["total_elapsed_ms"] >= 0
    assert any(event["step"] == "search_timing" for event in detail["events"])
    metrics = client.get("/api/metrics").json()
    assert metrics["completed_runs"] == 1 and metrics["search_calls"] >= 1
    assert client.get("/api/runs").json()[0]["id"] == run_id
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health").json()["model_enabled"] is False
    assert "Research Agent" in client.get("/").text


def test_api_rejects_blank_topic(tmp_path):
    client = TestClient(create_app(f"sqlite:///{tmp_path / 'test.db'}", FixtureSearch()))
    assert client.post("/api/runs", json={"topic": "   "}).status_code == 422
    assert client.get("/api/runs/missing").status_code == 404
    assert client.post("/api/runs", json={"topic": "sample", "start_date": "2026-02-01",
                                           "end_date": "2026-01-01"}).status_code == 422
    assert client.post("/api/runs", json={"topic": "sample", "time_range": "week",
                                           "start_date": "2026-01-01"}).status_code == 422
    assert client.post("/api/runs", json={"topic": "sample", "time_range": "week"}).status_code == 422


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


def test_api_forwards_time_filter_and_records_search_latency(tmp_path, monkeypatch):
    seen = []

    class DatedSearch:
        name = "tavily"

        def search(self, query, **options):
            seen.append(options)
            return [{"title": "Example", "url": "https://example.org/page",
                     "content": "snippet", "raw_content": "Full page", "score": 0.8}]

    monkeypatch.setattr("app.agent.summarize", lambda *args, **kwargs: ("Result [1]", "model"))
    client = TestClient(create_app(f"sqlite:///{tmp_path / 'dated.db'}", DatedSearch()))
    run_id = client.post("/api/runs", json={"topic": "sample topic", "time_range": "month"}).json()["id"]
    detail = client.get(f"/api/runs/{run_id}").json()
    assert detail["status"] == "completed"
    assert seen == [{"time_range": "month"}, {"time_range": "month"}]
    assert detail["result"]["search_options"] == {"time_range": "month"}
    assert all(event["search_depth"] == "basic" for event in detail["events"]
               if event["step"] == "search_timing")
    assert client.get("/api/metrics").json()["search_calls"] == 2
