from __future__ import annotations

import json
from research_agent.config import Settings
from research_agent.llm import FakeLLM
from research_agent.planner import make_plan
from research_agent.schemas import ResearchPlan


def test_valid_plan_is_used() -> None:
    plan_dict = {
        "in_scope": True,
        "out_of_scope_reason": None,
        "intent": "comparison",
        "restated_question": "Compare top vector databases for RAG",
        "steps": [
            {
                "id": 1,
                "sub_question": "What are the most popular open-source vector databases?",
                "tool": "web_search",
                "query": "top open source vector databases 2026",
                "rationale": "Identify candidates",
            },
            {
                "id": 2,
                "sub_question": "What is vector database architecture in RAG?",
                "tool": "wikipedia",
                "query": "Vector database",
                "rationale": "Background knowledge",
            },
        ],
        "answer_shape": "Comparison table followed by tradeoffs",
        "assumptions": ["Focus on open-source solutions suitable for startups"],
        "is_fallback": False,
    }

    fake = FakeLLM(script={"planning": [json.dumps(plan_dict)]})
    settings = Settings()

    plan = make_plan("Compare top vector databases for RAG", fake, settings)

    assert isinstance(plan, ResearchPlan)
    assert plan.in_scope is True
    assert plan.intent == "comparison"
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "web_search"
    assert plan.steps[1].tool == "wikipedia"
    assert plan.is_fallback is False


def test_duplicate_queries_removed_and_steps_capped() -> None:
    from research_agent.planner import normalise_plan
    from research_agent.schemas import PlanStep

    # 7 steps with duplicate queries
    steps = [
        PlanStep(id=1, sub_question="Q1", tool="web_search", query="quantum computing basics"),
        PlanStep(id=2, sub_question="Q2", tool="web_search", query="Quantum Computing Basics "),
        PlanStep(id=3, sub_question="Q3", tool="wikipedia", query="Quantum computing"),
        PlanStep(id=4, sub_question="Q4", tool="web_search", query="QUANTUM COMPUTING BASICS"),
        PlanStep(id=5, sub_question="Q5", tool="web_search", query="qubit technologies"),
        PlanStep(id=6, sub_question="Q6", tool="web_search", query="quantum algorithms"),
        PlanStep(id=7, sub_question="Q7", tool="web_search", query="quantum supremacy"),
    ]
    raw_plan = ResearchPlan(in_scope=True, steps=steps)
    settings = Settings(max_steps=5)

    norm_plan = normalise_plan(raw_plan, "What is quantum computing?", settings)

    assert len(norm_plan.steps) <= 5
    # Unique queries count
    queries = [s.query.lower().strip() for s in norm_plan.steps]
    assert len(queries) == len(set(queries))
    # Step IDs renumbered 1..n
    assert [s.id for s in norm_plan.steps] == list(range(1, len(norm_plan.steps) + 1))


def test_out_of_scope_has_no_steps() -> None:
    from research_agent.planner import normalise_plan
    from research_agent.schemas import PlanStep

    steps = [
        PlanStep(id=1, sub_question="Calculate", tool="web_search", query="17 * 23"),
    ]
    raw_plan = ResearchPlan(
        in_scope=False,
        out_of_scope_reason="Arithmetic question without research needs",
        steps=steps,
    )
    norm_plan = normalise_plan(raw_plan, "What is 17 * 23?")

    assert norm_plan.in_scope is False
    assert len(norm_plan.steps) == 0


def test_malformed_twice_yields_fallback_plan() -> None:
    fake = FakeLLM(script={"planning": ["not json 1", "not json 2"]})
    plan = make_plan("Explain transformers in AI", fake, Settings())

    assert plan.is_fallback is True
    assert len(plan.steps) == 2
    assert plan.steps[0].tool == "web_search"
    assert plan.steps[1].tool == "wikipedia"
    assert any("fallback" in a.lower() for a in plan.assumptions)


def test_llm_error_yields_fallback_plan() -> None:
    from research_agent.llm import LLMError

    fake = FakeLLM(script={"planning": [LLMError("Simulated LLM network down")]})
    plan = make_plan("Explain transformers in AI", fake, Settings())

    assert plan.is_fallback is True
    assert len(plan.steps) == 2
    assert any("Simulated LLM network down" in a for a in plan.assumptions)
