import json
from types import SimpleNamespace

import pytest

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


def test_model_receives_twenty_complete_page_bodies_and_checks_citations(monkeypatch):
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
                "content": "snippet", "body": "x" * 1200 + f"END{i}"} for i in range(1, 21)]

    seen["answer"] = "Finding [1]. Another finding [20]."
    answer, mode = summarize("topic", sources, require_full_body=True)
    records = json.loads(seen["request"]["messages"][1]["content"].split("Source evidence:\n", 1)[1])
    assert mode == "model" and answer == seen["answer"]
    assert len(records) == 20 and records[-1]["id"] == 20
    assert all(record["body"].endswith(f"END{record['id']}") for record in records)
    assert seen["client"]["base_url"] == "https://api.deepseek.com"
    assert seen["request"]["extra_body"] == {"thinking": {"type": "disabled"}}

    seen["answer"] = "Unsupported claim [21]."
    with pytest.raises(ValueError, match="valid source IDs"):
        summarize("topic", sources, require_full_body=True)


def test_large_page_is_sent_in_all_chunks(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            calls.append(kwargs["messages"][1]["content"])
            content = "Relevant fact" if "page_text" in calls[-1] else "Result [1]"
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr("app.agent.OpenAI", FakeClient)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-flash")
    body = "x" * 100_000 + "TAIL_MARKER"
    answer, mode = summarize("topic", [{"id": 1, "title": "Page", "url": "https://example.org/1",
                                        "content": "snippet", "body": body}], require_full_body=True)
    chunks = [json.loads(call)["page_text"] for call in calls[:-1]]
    assert mode == "model" and answer == "Result [1]"
    assert "".join(chunks) == body and len(chunks) == 2


def test_tavily_missing_body_is_marked_and_never_sent_as_snippet(monkeypatch):
    class PartialTavily:
        name = "tavily"

        def search(self, query):
            return [{"title": "Full", "url": "https://example.org/full", "content": "snippet",
                     "raw_content": "The full page body", "score": 1},
                    {"title": "Missing", "url": "https://example.org/missing", "content": "snippet only",
                     "raw_content": "", "score": 0.5}]

        def extract(self, urls):
            assert urls == ["https://example.org/missing"]
            return {}

    seen = {}

    def fake_summarize(topic, sources, **kwargs):
        seen["sources"] = sources
        assert kwargs["require_full_body"]
        return "Supported [1]", "model"

    monkeypatch.setattr("app.agent.summarize", fake_summarize)
    events = []
    result = ResearchAgent(PartialTavily(), min_sources=1).run("topic", events.append)
    assert len(seen["sources"]) == 1 and seen["sources"][0]["body"] == "The full page body"
    assert result["extracted_pages"] == 1 and len(result["extraction_failures"]) == 1
    assert result["sources"][1]["content_type"] == "search_snippet_only"
    assert all("body" not in source for source in result["sources"])
    assert not any(event["step"] == "extract_error" for event in events)
