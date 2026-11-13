"""Bounded research loop with inspectable decisions and grounded output."""
import logging
import os
import re
from urllib.parse import urlsplit, urlunsplit

from openai import OpenAI

LOG = logging.getLogger(__name__)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", "", ""))


def normalize_items(items: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    clean: list[dict] = []
    for item in sorted(items, key=lambda x: float(x.get("score") or 0), reverse=True):
        url = canonical_url(str(item.get("url", "")))
        title = str(item.get("title", "")).strip()
        content = re.sub(r"\s+", " ", str(item.get("content", ""))).strip()
        title_key = re.sub(r"\W+", "", title.casefold())
        if not url or not title_key or not content or url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        clean.append({"id": len(clean) + 1, "title": title, "url": url,
                      "content": content, "score": round(float(item.get("score") or 0), 3),
                      "domain": urlsplit(url).netloc})
    return clean


def summarize(topic: str, sources: list[dict]) -> tuple[str, str]:
    """Returns (answer, mode). A model answer is accepted only with valid citations."""
    api_key, model = os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL")
    if api_key and model:
        try:
            prompt = "\n".join(f"[{x['id']}] {x['title']}: {x['content']} ({x['url']})" for x in sources)
            response = OpenAI(api_key=api_key, timeout=20).chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "Write a concise research brief. Use only supplied facts. Cite each factual sentence with [source id]. State uncertainty. Never invent a source."},
                    {"role": "user", "content": f"Topic: {topic}\nSources:\n{prompt}"},
                ],
                temperature=0,
            )
            answer = response.choices[0].message.content or ""
            cited = {int(x) for x in re.findall(r"\[(\d+)\]", answer)}
            if cited and cited <= {x["id"] for x in sources}:
                return answer, "model"
            LOG.warning("Model answer lacked valid citations; using extractive fallback")
        except Exception:
            LOG.exception("Model summary failed; using extractive fallback")
    lines = [f"## {topic}", "", "Sample brief grounded in the listed sources:"]
    for source in sources[:4]:
        excerpt = source["content"][:220].rstrip()
        lines.append(f"- {excerpt} [{source['id']}]")
    return "\n".join(lines), "extractive"


class ResearchAgent:
    def __init__(self, provider, min_sources: int = 3, max_queries: int = 2):
        self.provider = provider
        self.min_sources = min_sources
        self.max_queries = max_queries

    def run(self, topic: str, on_event=lambda event: None) -> dict:
        queries = [topic, f"{topic} overview"][: self.max_queries]
        raw: list[dict] = []
        sources: list[dict] = []
        for attempt, query in enumerate(queries, 1):
            on_event({"step": "search", "attempt": attempt, "query": query})
            try:
                raw.extend(self.provider.search(query))
            except Exception as exc:
                on_event({"step": "search_error", "attempt": attempt, "error": type(exc).__name__})
                if attempt == len(queries) and not raw:
                    raise RuntimeError("All search attempts failed") from exc
                continue
            sources = normalize_items(raw)
            on_event({"step": "evaluate", "attempt": attempt, "sources": len(sources)})
            if len(sources) >= self.min_sources:
                break
        if not sources:
            raise RuntimeError("Search returned no usable sources")
        answer, mode = summarize(topic, sources)
        on_event({"step": "synthesize", "mode": mode, "sources": len(sources)})
        return {"answer": answer, "sources": sources, "summary_mode": mode,
                "coverage_warning": len(sources) < self.min_sources,
                "queries_used": attempt}
