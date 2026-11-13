"""HTTP API and tiny static demo UI."""
import logging
import os
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from .agent import ResearchAgent
from .providers import provider_from_env
from .store import Run, make_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOG = logging.getLogger(__name__)


class RunRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    time_range: Literal["day", "week", "month", "year"] | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.time_range and (self.start_date or self.end_date):
            raise ValueError("Choose a relative time range or custom dates, not both")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date")
        return self

    def search_options(self) -> dict:
        return {key: value for key, value in {
            "time_range": self.time_range,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }.items() if value}


def create_app(database_url: str | None = None, provider=None) -> FastAPI:
    app = FastAPI(title="Research Agent Service", version="1.0.0")
    app.state.sessions = make_session_factory(database_url or os.getenv("DATABASE_URL", "sqlite:///./research.db"))
    app.state.provider = provider or provider_from_env()

    def execute(run_id: str, topic: str, search_options: dict):
        started = perf_counter()
        def record(event: dict):
            with app.state.sessions.begin() as session:
                run = session.get(Run, run_id)
                run.events = [*run.events, event]
                if event["step"] == "search":
                    run.attempts = event["attempt"]

        with app.state.sessions.begin() as session:
            session.get(Run, run_id).status = "running"
        try:
            result = ResearchAgent(app.state.provider).run(topic, record, search_options=search_options)
            result["total_elapsed_ms"] = round((perf_counter() - started) * 1000)
            with app.state.sessions.begin() as session:
                run = session.get(Run, run_id)
                run.result = result
                run.status = "completed"
        except Exception as exc:
            LOG.exception("Run %s failed", run_id)
            with app.state.sessions.begin() as session:
                run = session.get(Run, run_id)
                run.status = "failed"
                run.error = str(exc)
        finally:
            record({"step": "run_timing", "elapsed_ms": round((perf_counter() - started) * 1000)})

    @app.get("/health")
    def health():
        return {"status": "ok", "provider": app.state.provider.name,
                "model_enabled": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL"))}

    @app.post("/api/runs", status_code=202)
    def create_run(request: RunRequest, background: BackgroundTasks):
        topic = request.topic.strip()
        if len(topic) < 3:
            raise HTTPException(422, "Topic must contain at least three non-space characters")
        if request.search_options() and app.state.provider.name != "tavily":
            raise HTTPException(422, "Time filters require the Tavily provider")
        run_id = str(uuid4())
        with app.state.sessions.begin() as session:
            session.add(Run(id=run_id, topic=topic, status="queued", provider=app.state.provider.name, events=[]))
        background.add_task(execute, run_id, topic, request.search_options())
        return {"id": run_id, "status": "queued"}

    @app.get("/api/runs")
    def list_runs():
        with app.state.sessions() as session:
            runs = session.scalars(select(Run).order_by(Run.created_at.desc()).limit(20)).all()
            return [{"id": x.id, "topic": x.topic, "status": x.status, "provider": x.provider} for x in runs]

    @app.get("/api/metrics")
    def metrics():
        with app.state.sessions() as session:
            runs = session.scalars(select(Run).where(Run.provider == app.state.provider.name)
                                   .order_by(Run.created_at.desc()).limit(20)).all()
            search_ms = [e["elapsed_ms"] for run in runs for e in run.events
                         if e.get("step") == "search_timing" and e.get("success")]
            completed = [run.result["total_elapsed_ms"] for run in runs
                         if run.status == "completed" and run.result and "total_elapsed_ms" in run.result]
            return {"sample_runs": len(runs), "search_calls": len(search_ms),
                    "avg_search_ms": round(sum(search_ms) / len(search_ms)) if search_ms else None,
                    "completed_runs": len(completed),
                    "avg_total_ms": round(sum(completed) / len(completed)) if completed else None}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        with app.state.sessions() as session:
            run = session.get(Run, run_id)
            if not run:
                raise HTTPException(404, "Run not found")
            return {"id": run.id, "topic": run.topic, "status": run.status,
                    "provider": run.provider, "attempts": run.attempts,
                    "events": run.events, "result": run.result, "error": run.error}

    @app.get("/")
    def home():
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    return app


app = create_app()
