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


def test_all_tools_failing_yields_no_sources() -> None:
    import json
    from research_agent.llm import FakeLLM
    from research_agent.tools.base import PermanentToolError

    plan_dict = {
        "in_scope": True,
        "intent": "explainer",
        "restated_question": "What is quantum computing?",
        "steps": [
            {
                "id": 1,
                "sub_question": "What is quantum computing?",
                "tool": "web_search",
                "query": "quantum computing basics",
                "rationale": "",
            },
            {
                "id": 2,
                "sub_question": "Quantum computing principles",
                "tool": "wikipedia",
                "query": "quantum computing",
                "rationale": "",
            },
        ],
        "answer_shape": "",
        "assumptions": [],
        "is_fallback": False,
    }
    fake_llm = FakeLLM(script={"planning": [json.dumps(plan_dict)]})

    def failing_tool(*args, **kwargs):
        raise PermanentToolError("Connection refused by provider")

    failing_tools = {
        "web_search": failing_tool,
        "wikipedia": failing_tool,
        "fetch_page": failing_tool,
    }

    result = run_research("What is quantum computing?", llm=fake_llm, tools=failing_tools)
    assert isinstance(result, RunResult)
    assert result.answer.status == "insufficient_evidence"
    assert len(result.answer.sources) == 0
    assert len(result.sources) == 0
    assert any("Connection refused" in lim or "failed" in lim for lim in result.answer.limitations)


def test_tools_all_down_skips_synthesis() -> None:
    import json
    from research_agent.llm import FakeLLM
    from research_agent.tools.base import PermanentToolError

    plan_dict = {
        "in_scope": True,
        "intent": "explainer",
        "restated_question": "What is quantum computing?",
        "steps": [
            {
                "id": 1,
                "sub_question": "What is quantum computing?",
                "tool": "web_search",
                "query": "quantum computing basics",
                "rationale": "",
            },
        ],
        "answer_shape": "",
        "assumptions": [],
        "is_fallback": False,
    }
    fake_llm = FakeLLM(script={"planning": [json.dumps(plan_dict)]})

    def failing_search(*args, **kwargs):
        raise PermanentToolError("Search API unavailable")

    failing_tools = {
        "web_search": failing_search,
        "wikipedia": lambda *a, **kw: None,
        "fetch_page": failing_search,
    }

    result = run_research("What is quantum computing?", llm=fake_llm, tools=failing_tools)
    assert result.answer.status == "insufficient_evidence"
    # Only planner LLM call was made
    assert result.metrics.llm_calls == 1
    assert len(fake_llm.calls) == 1


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

