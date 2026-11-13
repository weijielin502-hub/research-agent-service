"""Search adapters. Fixture data is synthetic and works without credentials."""
import json
import os
from pathlib import Path

import httpx


class FixtureSearch:
    name = "fixture"

    def __init__(self, fixture_path: Path | None = None):
        path = fixture_path or Path(__file__).resolve().parent.parent / "sample_data" / "articles.json"
        self.items = json.loads(path.read_text(encoding="utf-8"))

    def search(self, query: str) -> list[dict]:
        # The second query returns one extra source to demonstrate coverage expansion.
        return self.items[:3] if "overview" not in query.lower() else self.items[2:]


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY is required for the tavily provider")

    def search(self, query: str) -> list[dict]:
        response = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": query, "max_results": 20, "search_depth": "basic"},
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("results", [])
        return [{"title": x.get("title", ""), "url": x.get("url", ""), "content": x.get("content", ""), "score": x.get("score", 0)} for x in items]


def provider_from_env():
    choice = os.getenv("SEARCH_PROVIDER", "fixture").lower()
    if choice == "fixture":
        return FixtureSearch()
    if choice == "tavily":
        return TavilySearch()
    raise ValueError(f"Unknown SEARCH_PROVIDER: {choice}")
