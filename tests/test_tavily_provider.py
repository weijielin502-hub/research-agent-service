from app.providers import TavilySearch


def test_tavily_request_uses_bearer_header(monkeypatch):
    seen = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"title": "Example", "url": "https://example.org/a",
                                 "content": "A source snippet", "score": 0.7}]}

    def fake_post(url, **kwargs):
        seen.update({"url": url, **kwargs})
        return Response()

    monkeypatch.setattr("app.providers.httpx.post", fake_post)
    items = TavilySearch("test-key").search("example query")
    assert seen["url"] == "https://api.tavily.com/search"
    assert seen["headers"] == {"Authorization": "Bearer test-key"}
    assert "api_key" not in seen["json"]
    assert seen["json"]["query"] == "example query"
    assert items[0]["title"] == "Example"
