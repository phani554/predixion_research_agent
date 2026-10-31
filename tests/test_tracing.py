from __future__ import annotations

from pydantic import BaseModel

from research_agent.llm import FakeLLM, structured
from research_agent.tracing import Tracer


class Item(BaseModel):
    title: str


def test_tracer_counts_two_calls_and_tokens() -> None:
    tracer = Tracer()
    fake = FakeLLM(
        script={
            "call_1": ['{"title": "First"}'],
            "call_2": ['{"title": "Second"}'],
        }
    )

    r1 = structured(fake, [{"role": "user", "content": "1"}], Item, tracer=tracer, purpose="call_1")
    r2 = structured(fake, [{"role": "user", "content": "2"}], Item, tracer=tracer, purpose="call_2")

    assert r1.title == "First"
    assert r2.title == "Second"

    assert tracer.metrics.llm_calls == 2
    # FakeLLM default returns 10 prompt tokens and 10 completion tokens
    assert tracer.metrics.input_tokens == 20
    assert tracer.metrics.output_tokens == 20


def test_tracer_span_and_event() -> None:
    tracer = Tracer()
    with tracer.span("planning"):
        tracer.event("plan_created", step_count=3)

    assert len(tracer.spans) == 1
    assert tracer.spans[0]["name"] == "planning"
    assert tracer.spans[0]["duration_s"] >= 0.0

    assert len(tracer.events) == 1
    assert tracer.events[0]["name"] == "plan_created"
    assert tracer.events[0]["step_count"] == 3


def test_tracer_exception_in_span_records_error_and_propagates(tmp_path) -> None:
    import json
    import pytest

    tracer = Tracer(runs_dir=str(tmp_path), price_in=0.30, price_out=2.50)

    with pytest.raises(ValueError, match="Boom"):
        with tracer.span("execute_step", step_id=1):
            raise ValueError("Boom")

    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span["span"] == "execute_step"
    assert span["status"] == "error"
    assert "Boom" in span["error"]
    assert span["duration_ms"] >= 0.0

    # Ensure written to JSONL
    trace_file = tmp_path / f"{tracer.run_id}.jsonl"
    assert trace_file.exists()
    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(line.get("span") == "execute_step" and line.get("status") == "error" for line in lines)


def test_tracer_cost_estimate_calculation() -> None:
    # WHEN a run uses 1,000,000 prompt tokens at price-in 0.30 and 0 completion tokens
    # THEN est_cost_usd is 0.30
    tracer = Tracer(price_in=0.30, price_out=2.50)
    tracer.record_llm(prompt_tokens=1_000_000, completion_tokens=0, purpose="planning")

    metrics = tracer.finish(sources_considered=5, sources_used=2)
    assert round(metrics.est_cost_usd, 2) == 0.30
    assert round(metrics.estimated_cost_usd, 2) == 0.30
    assert metrics.prompt_tokens == 1_000_000
    assert metrics.completion_tokens == 0
    assert metrics.sources_considered == 5
    assert metrics.sources_used == 2


def test_invalid_output_records_invalid_output_status_and_preview(tmp_path) -> None:
    from research_agent.llm import StructuredOutputError
    import pytest

    tracer = Tracer(runs_dir=str(tmp_path))
    # Returns invalid json twice so it fails after repair
    bad_fake = FakeLLM(script={"testing": ["not valid json", "still not json"]})

    with pytest.raises(StructuredOutputError):
        structured(bad_fake, [{"role": "user", "content": "hi"}], Item, tracer=tracer, purpose="testing")

    trace_file = tmp_path / f"{tracer.run_id}.jsonl"
    assert trace_file.exists()
    import json
    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    invalid_spans = [line for line in lines if line.get("span") == "llm" and line.get("status") == "invalid_output"]
    assert len(invalid_spans) >= 1
    assert "preview" in invalid_spans[0]
    assert invalid_spans[0]["preview"] == "still not json"


def test_end_to_end_trace_writes_jsonl_spans_and_events(tmp_path) -> None:
    import json
    from research_agent.agent import run_research
    from research_agent.config import Settings
    from research_agent.schemas import SearchHit

    plan_json = json.dumps({
        "in_scope": True,
        "out_of_scope_reason": None,
        "intent": "comparison",
        "restated_question": "Compare A and B",
        "steps": [
            {"id": 1, "sub_question": "A features", "tool": "web_search", "query": "tool A features", "rationale": "r1"},
            {"id": 2, "sub_question": "B features", "tool": "wikipedia", "query": "tool B overview", "rationale": "r2"},
        ],
        "answer_shape": "Side-by-side comparison",
        "assumptions": [],
    })

    synth_json = json.dumps({
        "short_answer": "A and B compare well according to sources.",
        "key_findings": [
            {
                "statement": "A is fast and B is scalable.",
                "source_ids": ["S1"],
            }
        ],
        "limitations": ["Limited public benchmarks."],
        "assumptions": ["Assuming standard configurations."],
        "next_steps": ["Try benchmarks."],
        "self_confidence": "high",
    })

    fake_llm = FakeLLM(script={
        "planning": [plan_json],
        "synthesis": [synth_json],
    })

    fake_tools = {
        "web_search": lambda query, **kw: [
            SearchHit(
                title="Tool A Features",
                url="https://milvus.io/docs/a",
                snippet="Tool A features include high speed and low latency.",
            )
        ],
        "wikipedia": lambda query, **kw: {
            "title": "Tool B Overview",
            "url": "https://en.wikipedia.org/wiki/B",
            "summary": "Tool B features include scalability and high throughput.",
        },
        "fetch_page": lambda url, **kw: "Full content: Tool A features include high speed and low latency.",
    }

    cfg = Settings(runs_dir=str(tmp_path), faults=["custom:flag"])
    tracer = Tracer(runs_dir=str(tmp_path), price_in=0.5, price_out=1.5)

    res = run_research(
        "Compare A and B for developers",
        settings=cfg,
        llm=fake_llm,
        tools=fake_tools,
        tracer=tracer,
    )

    assert res.answer.status in ("answered", "partial")

    trace_file = tmp_path / f"{tracer.run_id}.jsonl"
    assert trace_file.exists()
    lines = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    events = [entry.get("event") for entry in lines if "event" in entry]
    spans = [entry.get("span") for entry in lines if "span" in entry]

    assert "run_started" in events
    assert "run_finished" in events
    assert "plan" in spans
    assert "execute" in spans
    assert "tool" in spans
    assert "synthesize" in spans
    assert "ground" in spans

    # Check run_started has faults and question
    start_entry = next(e for e in lines if e.get("event") == "run_started")
    assert start_entry["question"] == "Compare A and B for developers"
    assert "custom:flag" in start_entry["faults"]


