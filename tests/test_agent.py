import json
from types import SimpleNamespace

from app.agent import ResearchAgent, canonical_url, normalize_items, summarize
from app.providers import FixtureSearch


def test_dedup_and_grounded_fixture(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    events = []
    result = ResearchAgent(FixtureSearch(), min_sources=4).run("Battery recycling programs", events.append)
    assert result["summary_mode"] == "extractive"
    assert result["queries_used"] == 2
    assert len(result["sources"]) == 4
    assert len({x["url"] for x in result["sources"]}) == 4
    assert "[1]" in result["answer"]
    assert [x["step"] for x in events].count("search") == 2


def test_invalid_url_and_empty_result():
    assert canonical_url("file:///private") == ""
    assert normalize_items([{"title": "x", "url": "file:///private", "content": "y"}]) == []


def test_search_failure_is_recorded():
    class Broken:
        def search(self, query):
            raise TimeoutError()

    events = []
    try:
        ResearchAgent(Broken()).run("sample topic", events.append)
    except RuntimeError as exc:
        assert "All search attempts failed" in str(exc)
    else:
        assert False, "Expected failure"
    assert [x["step"] for x in events].count("search_error") == 2


def test_model_receives_all_twenty_bounded_sources_and_checks_citations(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client"] = kwargs
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=seen["answer"]))])

    monkeypatch.setattr("app.agent.OpenAI", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-flash")
    sources = [{"id": i, "title": f"Source {i}", "url": f"https://example.org/{i}",
                "content": "x" * 1200} for i in range(1, 21)]

    seen["answer"] = "Finding [1]. Another finding [20]."
    answer, mode = summarize("topic", sources)
    records = json.loads(seen["request"]["messages"][1]["content"].split("Source records:\n", 1)[1])
    assert mode == "model" and answer == seen["answer"]
    assert len(records) == 20 and records[-1]["id"] == 20
    assert all(len(record["content"]) == 800 for record in records)
    assert seen["client"]["base_url"] == "https://api.deepseek.com"
    assert seen["request"]["extra_body"] == {"thinking": {"type": "disabled"}}

    seen["answer"] = "Unsupported claim [21]."
    answer, mode = summarize("topic", sources)
    assert mode == "extractive" and "[1]" in answer
