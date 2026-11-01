"""Glass-box web UI: run the agent and watch every stage live.

Read-only view over the existing pipeline. It never changes how the agent works:
it swaps in a Tracer that also pushes each trace record onto a queue, and streams
that queue to the browser with Server-Sent Events. Past runs are replayed from
the same JSONL traces the CLI writes, so the demo still works offline.

    pip install -e ".[ui]"
    python -m research_agent.web          # http://127.0.0.1:8000
"""
from __future__ import annotations

import glob
import json
import os
import queue
import threading
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..agent import run_research
from ..config import Settings
from ..tracing import Tracer

STATIC = os.path.join(os.path.dirname(__file__), "static")
ALLOWED_FAULTS = {"web_search:timeout", "web_search:error", "fetch_page:timeout", "fetch_page:injection",
                  "wikipedia:error", "llm:malformed", "llm:down"}
_DONE = object()


class LiveTracer(Tracer):
    """Same trace as the CLI, plus a 'span_start' notice so the UI can show work in progress."""

    def __init__(self, sink: "queue.Queue[Any]", **kw: Any):
        super().__init__(**kw)
        self.sink = sink

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
        self.sink.put({"span_start": name, "at_ms": self._now_ms(), **_jsonable(attrs)})
        with super().span(name, **attrs) as rec:
            yield rec

    def _emit(self, record: dict[str, Any]) -> None:
        super()._emit(record)
        self.sink.put(_jsonable(record))


def _jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


class RunRequest(BaseModel):
    question: str = Field(max_length=2000)
    faults: list[str] = Field(default_factory=list)
    use_cache: bool = True


app = FastAPI(title="Research Agent - Glass Box", docs_url="/api/docs")
_LIVE: dict[str, "queue.Queue[Any]"] = {}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/config")
def config() -> dict:
    """What the reviewer should know before a run: model, budgets, filter thresholds. Never the key."""
    s = Settings.from_env()
    return {
        "model": s.llm_model or "(not set)",
        "provider": urlparse(s.llm_base_url).hostname or "(not set)",
        "llm_ready": bool(s.llm_base_url and s.llm_model),
        "search": "tavily" if s.tavily_api_key else "ddgs (keyless)",
        "budgets": {"max_plan_steps": s.max_plan_steps, "max_tool_calls": s.max_tool_calls,
                    "max_pages_to_fetch": s.max_pages_to_fetch, "tool_timeout_s": s.tool_timeout_s,
                    "tool_max_retries": s.tool_max_retries, "run_deadline_s": s.run_deadline_s,
                    "max_follow_up_rounds": s.max_follow_up_rounds, "parallelism": s.parallelism},
        "filter": {"min_source_score": s.min_source_score, "max_sources_for_synthesis": s.max_sources_for_synthesis,
                   "max_sources_per_domain": s.max_sources_per_domain},
        "guard": {"min_chars": s.min_question_chars, "max_chars": s.max_question_chars},
        "faults": sorted(ALLOWED_FAULTS),
    }


@app.post("/api/runs")
def start_run(req: RunRequest) -> dict:
    bad = [f for f in req.faults if f not in ALLOWED_FAULTS]
    if bad:
        raise HTTPException(400, f"unknown fault(s): {bad}")
    settings = Settings.from_env()
    settings.faults = set(req.faults)
    settings.use_cache = req.use_cache
    sink: "queue.Queue[Any]" = queue.Queue()
    tracer = LiveTracer(sink, runs_dir=settings.runs_dir, price_in=settings.price_in_per_m, price_out=settings.price_out_per_m)
    _LIVE[tracer.run_id] = sink

    def work() -> None:
        try:
            result = run_research(req.question, settings, tracer=tracer)
            os.makedirs("outputs", exist_ok=True)  # same place the CLI saves runs, so replay finds it
            with open(os.path.join("outputs", f"{result.run_id}.json"), "w", encoding="utf-8") as fh:
                fh.write(result.model_dump_json(indent=2))
            sink.put({"event": "result", "result": result.model_dump(mode="json", exclude={"sources": {"__all__": {"content"}}})})
        finally:
            sink.put(_DONE)

    threading.Thread(target=work, name=f"run-{tracer.run_id}", daemon=True).start()
    return {"run_id": tracer.run_id}


@app.get("/api/runs/{run_id}/stream")
def stream(run_id: str) -> StreamingResponse:
    sink = _LIVE.get(run_id)
    if sink is None:
        raise HTTPException(404, "no live run with that id; use /api/runs/{id}/trace to replay")

    def gen() -> Iterator[str]:
        while True:
            try:
                item = sink.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is _DONE:
                _LIVE.pop(run_id, None)
                yield "event: done\ndata: {}\n\n"
                return
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/runs")
def list_runs(limit: int = 30) -> list[dict]:
    """Saved traces, newest first, with the question and final status for the replay picker."""
    runs_dir = Settings.from_env().runs_dir
    out = []
    for path in sorted(glob.glob(os.path.join(runs_dir, "*.jsonl")), reverse=True)[:limit]:
        q, status, conf, ms = "", "", "", None
        for rec in _read_jsonl(path):
            if rec.get("event") == "run_started":
                q = rec.get("question", "")
            elif rec.get("event") == "answer_ready":
                status = rec["answer"].get("status", "")
                conf = rec["answer"].get("confidence", "")
            elif rec.get("span") == "ground":
                status, conf = status or rec.get("status", ""), conf or rec.get("confidence", "")
            elif rec.get("event") == "run_finished":
                ms = rec.get("metrics", {}).get("latency_ms")
        out.append({"run_id": os.path.basename(path)[:-6], "question": q, "status": status, "confidence": conf, "latency_ms": ms})
    return out


@app.get("/api/runs/{run_id}/trace")
def trace(run_id: str) -> dict:
    runs_dir = Settings.from_env().runs_dir
    path = os.path.join(runs_dir, f"{os.path.basename(run_id)}.jsonl")
    if not os.path.exists(path):
        raise HTTPException(404, "trace not found")
    events = list(_read_jsonl(path))
    result = None
    out_path = os.path.join("outputs", f"{os.path.basename(run_id)}.json")  # written by the CLI
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as fh:
            result = json.load(fh)
    return {"run_id": run_id, "events": events, "result": result}


def _read_jsonl(path: str) -> Iterator[dict]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
