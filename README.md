# Research Agent Service

![Python](https://img.shields.io/badge/Python-3.12-3776AB) ![FastAPI](https://img.shields.io/badge/API-FastAPI-009688) ![Tests](https://img.shields.io/badge/tests-pytest-6A5ACD)

**A traceable research task, from question to source-linked brief.** This demo turns a small retrieval workflow into an API-backed agent with bounded search decisions, persistent run history, explicit failure states, and a simple UI. Offline mode uses synthetic articles at `example.*` domains and needs no secrets.

## Try it in two minutes

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\uvicorn app.main:app --reload
```

Open <http://localhost:8000>, leave the sample topic in place and click **Run research agent**. API docs are at <http://localhost:8000/docs>. A pre-generated [sample run](examples/sample-run.json) and [sample brief](examples/sample-brief.md) show the exact offline output.

Docker: `docker compose up --build`, then open the same URL. The Compose demo uses a named volume for SQLite persistence. The image build and an isolated offline container smoke test passed: `/health` returned `ok`, and a submitted fixture run completed with two searches and four deduplicated sources. The Compose volume persistence path has not been exercised.

## What to inspect

```text
POST /api/runs → queued → running → completed / failed
                       │
                       ├─ plan two bounded queries
                       ├─ search via fixture or Tavily adapter
                       ├─ canonicalize and deduplicate sources
                       ├─ assess source coverage; search again if needed
                       └─ synthesize cited answer
```

Each run stores events, number of search attempts, source records and the final answer. `GET /api/runs/{id}` exposes the trace. The fixture deliberately contains a duplicate to make the second query and deduplication visible.

See [the exact workflow and result fields](FLOW.md) for the current search and answer construction rules.

## Live integrations

Use `.env.example` as a configuration reference, then export `SEARCH_PROVIDER=tavily` and `TAVILY_API_KEY` in your shell or process manager. Tavily requests up to 20 basic-search results per query; after deduplication, every retained result is included in the bounded model input. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` for a DeepSeek-written summary. If model output lacks valid source numbers, it falls back to an extractive summary. Offline fixture mode remains available without credentials.

On Windows, run `./start_live.ps1` from this directory. It reads Tavily and optional model configuration from an ignored `.env.local` if present, or prompts for the Tavily key without echoing it. It starts a separate live server at <http://127.0.0.1:8001>. The existing offline server on port 8000 can remain running. Live Tavily results depend on your API plan and network access.

## Verification

Run `python -m pytest -q`. Tests cover deduplication, bounded retry, search failure, API validation and persisted results. The workflow also runs in GitHub Actions. Regenerate public sample artifacts with `python -m scripts.generate_example`.

## Design decisions and limits

- SQLite keeps the default demo easy to run. The store accepts a SQLAlchemy database URL for PostgreSQL, but PostgreSQL deployment has not been verified in this demo.
- FastAPI background tasks are suitable for a single-process local demo. A durable external job queue would be needed before multi-worker production deployment.
- No login or rate limiting is included. Run locally or behind appropriate controls; do not expose this demo as a public service with a live API key.
- Citation validation checks that cited IDs exist. It does not prove every model claim is entailed by the source; a stronger claim-level evaluator is future work.

## Provenance

New demo code inspired by an earlier local retrieval/cleaning/reporting workflow. No original outputs, search results, `.env` or internal data were copied.
