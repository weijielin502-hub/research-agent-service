from app.providers import TavilySearch


def test_tavily_request_uses_bearer_header(monkeypatch):
    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "Example", "url": "https://example.org/a",
                                 "content": "A source snippet", "raw_content": "Full page body",
                                 "score": 0.7}]}

    def fake_post(url, **kwargs):
        seen.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.providers.httpx.post", fake_post)
    items = TavilySearch("test-key").search("example query")
    assert seen["url"] == "https://api.tavily.com/search"
    assert seen["headers"] == {"Authorization": "Bearer test-key"}
    assert "api_key" not in seen["json"]
    assert seen["json"]["query"] == "example query"
    assert seen["json"]["max_results"] == 20
    assert seen["json"]["include_raw_content"] == "markdown"
    assert items[0]["title"] == "Example"
    assert items[0]["raw_content"] == "Full page body"


def test_tavily_extract_retries_missing_body(monkeypatch):
    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"url": "https://example.org/a", "raw_content": "Whole page"}],
                    "failed_results": [{"url": "https://example.org/b"}]}

    def fake_post(url, **kwargs):
        seen.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.providers.httpx.post", fake_post)
    result = TavilySearch("test-key").extract(["https://example.org/a", "https://example.org/b"])
    assert seen["url"] == "https://api.tavily.com/extract"
    assert seen["json"]["urls"] == ["https://example.org/a", "https://example.org/b"]
    assert result == {"https://example.org/a": "Whole page"}
