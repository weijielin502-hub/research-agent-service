from app.agent import ResearchAgent, canonical_url, normalize_items
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
