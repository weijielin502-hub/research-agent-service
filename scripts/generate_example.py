"""Regenerate committed synthetic example artifacts without API credentials."""
import json
from pathlib import Path

from app.agent import ResearchAgent
from app.providers import FixtureSearch


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "examples"
    output.mkdir(exist_ok=True)
    events = []
    topic = "Battery recycling programs"
    result = ResearchAgent(FixtureSearch()).run(topic, events.append)
    (output / "sample-run.json").write_text(
        json.dumps({"topic": topic, "events": events, "result": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [result["answer"], "", "## Sources", ""]
    lines.extend(f"{item['id']}. [{item['title']}]({item['url']}) — synthetic fixture"
                 for item in result["sources"])
    (output / "sample-brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {output / 'sample-run.json'} and {output / 'sample-brief.md'}")


if __name__ == "__main__":
    main()
