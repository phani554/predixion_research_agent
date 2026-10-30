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

