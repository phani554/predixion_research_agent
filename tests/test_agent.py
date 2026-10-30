from __future__ import annotations

from unittest.mock import patch

from research_agent.agent import run_research
from research_agent.schemas import RunResult


def test_run_research_invalid_input() -> None:
    result = run_research("   ")
    assert isinstance(result, RunResult)
    assert result.answer.status == "invalid_input"
    assert "too short" in result.answer.short_answer.lower() or "empty" in result.answer.short_answer.lower()
    assert len(result.answer.sources) == 0


def test_run_research_pipeline_not_implemented() -> None:
    result = run_research("What is quantum computing?")
    assert isinstance(result, RunResult)
    assert result.answer.status == "error"
    assert any("not implemented" in lim.lower() for lim in result.answer.limitations)


def test_run_research_catches_unexpected_exception() -> None:
    # Simulate an unexpected crash inside the pipeline
    with patch("research_agent.agent.check_question", side_effect=RuntimeError("Simulated explosion")):
        result = run_research("What is quantum computing?")
        assert isinstance(result, RunResult)
        assert result.answer.status == "error"
        assert any("Simulated explosion" in lim for lim in result.answer.limitations)


def test_run_research_out_of_scope() -> None:
    import json
    from research_agent.llm import FakeLLM

    out_of_scope_plan = {
        "in_scope": False,
        "out_of_scope_reason": "Arithmetic calculation is out of scope.",
        "intent": "other",
        "restated_question": "What is 17 multiplied by 23?",
        "steps": [],
        "answer_shape": "",
        "assumptions": [],
        "is_fallback": False,
    }
    fake_llm = FakeLLM(script={"planning": [json.dumps(out_of_scope_plan)]})
    result = run_research("What is 17 multiplied by 23?", llm=fake_llm)

    assert result.answer.status == "out_of_scope"
    assert "arithmetic" in result.answer.short_answer.lower()
    assert result.metrics.tool_calls == 0

