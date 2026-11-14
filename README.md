# Research Agent Service

![Python](https://img.shields.io/badge/Python-3.12-3776AB) ![FastAPI](https://img.shields.io/badge/API-FastAPI-009688) ![Tests](https://img.shields.io/badge/tests-pytest-6A5ACD)

**A quick proof of concept for turning a question into a source-linked research brief.** This portfolio demo shows a small retrieval workflow as an API-backed agent with bounded search decisions, persistent run history, explicit failure states, and a simple UI. It is intended for local exploration and interviews, not production research or unattended fact checking. Offline mode uses synthetic articles at `example.*` domains and needs no secrets.

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

Use `.env.example` as a configuration reference, then export `SEARCH_PROVIDER=tavily` and `TAVILY_API_KEY` in your shell or process manager. Tavily requests up to 20 basic-search results and extracts their full page bodies. Missing bodies are retried with Tavily Extract. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL` for a DeepSeek-written summary. Complete page bodies are sent directly or in consecutive model chunks; search snippets never replace failed page extraction. A live run fails visibly if no body is available, model synthesis fails, or the 5,000,000-character safety limit is exceeded. Offline fixture mode remains available without credentials. [Workflow and limits](FLOW.md) explains the chunking and result fields.

On Windows, run `./start_live.ps1` from this directory. It reads Tavily and optional model configuration from an ignored `.env.local` if present, or prompts for the Tavily key without echoing it. It starts a separate live server at <http://127.0.0.1:8001>. The existing offline server on port 8000 can remain running. Live Tavily results depend on your API plan and network access.

### Start a full-page live run on Windows

1. In PowerShell, go to this repository: `cd E:\yytt\demo整理\research-agent-service`.
2. Install dependencies if needed: `python -m pip install -r requirements.txt`.
3. Create `.env.local` in this directory with `TAVILY_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.deepseek.com`, and `OPENAI_MODEL=deepseek-flash`. Keep real values only in this ignored file; do not put keys in commands, README or Git.
4. Run `.\start_live.ps1` and leave that PowerShell window open. Open <http://127.0.0.1:8001>; `/health` should report `provider=tavily` and `model_enabled=true`. Live run metadata is saved in the ignored `live_research.db` file.
5. Enter a topic, optionally choose a published-date window, and click **Run research agent**. Selecting a time window strictly excludes pages without a detectable publication date. Search depth is fixed at `basic`. Full-page processing may take several minutes. The page shows search response time per call, total report time, page-read progress, the number of complete pages, and any pages whose body was unavailable. The finished answer should show `Mode: model` and numbered citations. `/api/metrics` reports average measured search response time and average completed report time over the latest 20 runs for this provider; sample counts are shown alongside each average.
6. Press `Ctrl+C` in the PowerShell window to stop the service. After editing `.env.local` or source code, restart the service for changes to take effect.

## Verification

Run `python -m pytest -q`. Tests cover deduplication, bounded retry, search failure, API validation and persisted results. The workflow also runs in GitHub Actions. Regenerate public sample artifacts with `python -m scripts.generate_example`.

## Design decisions and limits

- SQLite keeps the default demo easy to run. The store accepts a SQLAlchemy database URL for PostgreSQL, but PostgreSQL deployment has not been verified in this demo.
- FastAPI background tasks are suitable for a single-process local demo. A durable external job queue would be needed before multi-worker production deployment.
- No login or rate limiting is included. Run locally or behind appropriate controls; do not expose this demo as a public service with a live API key.
- Citation validation checks that cited IDs exist. It does not prove every model claim is entailed by the source; a stronger claim-level evaluator is future work.

## Provenance

New demo code inspired by an earlier local retrieval/cleaning/reporting workflow. No original outputs, search results, `.env` or internal data were copied.
