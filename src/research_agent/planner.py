"""Research planner module: decomposes research questions into focused, bounded tool execution steps."""
from __future__ import annotations

from typing import Any

from research_agent.config import Settings
from research_agent.llm import LLMClient, LLMError, StructuredOutputError, schema_hint, structured
from research_agent.schemas import PlanStep, ResearchPlan

PLANNER_SYSTEM = f"""You are an expert research planner. Your job is to analyze the user's research question, decide whether it is in-scope, determine its intent, and create a focused execution plan of 1 to 5 steps.

Tool Menu:
- 'web_search': For current information, comparative analyses, product specs, latest news, benchmarks.
- 'wikipedia': For foundational history, encyclopedic background, scientific concepts, and definitions. At most 1-2 steps.

Rules:
1. Every step must have a clear sub-question, a tool ('web_search' or 'wikipedia'), and a search query (2-200 characters). Keep search queries concise and targeted (keywords, not full questions).
2. Out of scope: simple arithmetic, small talk/greetings, code-writing without research, personal opinions, harmful or abusive requests. If out of scope, set in_scope=false and explain out_of_scope_reason. Do not produce steps for out-of-scope questions.
3. List assumptions if the question uses ambiguous or subjective terms (e.g. "top", "best").
4. Keep the plan small, focused, and bounded (1 to 5 steps maximum).

{schema_hint(ResearchPlan)}
"""


def fallback_plan(question: str, reason: str = "") -> ResearchPlan:
    """Deterministic fallback research plan used when planning model fails or produces 0 steps."""
    assumptions = ["Using deterministic fallback plan due to planner failure."]
    if reason:
        assumptions.append(f"Reason: {reason}")

    return ResearchPlan(
        in_scope=True,
        out_of_scope_reason=None,
        intent="explainer",
        restated_question=question,
        steps=[
            PlanStep(
                id=1,
                sub_question=f"General information regarding: {question}",
                tool="web_search",
                query=question[:200],
                rationale="Fallback search for overall context.",
            ),
            PlanStep(
                id=2,
                sub_question=f"Background and encyclopedic definitions for: {question}",
                tool="wikipedia",
                query=question[:200],
                rationale="Fallback lookup for foundational background.",
            ),
        ],
        answer_shape="Overview and key information",
        assumptions=assumptions,
        is_fallback=True,
    )


def normalise_plan(plan: ResearchPlan, question: str, settings: Settings | None = None) -> ResearchPlan:
    """Normalize plan steps, remove duplicate queries, cap step count, and renumber ids 1..n."""
    if not plan.in_scope:
        plan.steps = []
        return plan

    cfg = settings or Settings()
    max_steps = cfg.max_steps or 5

    seen_queries: set[str] = set()
    deduped_steps: list[PlanStep] = []

    for step in plan.steps:
        normalized_q = " ".join(step.query.strip().lower().split())
        if normalized_q in seen_queries:
            continue
        seen_queries.add(normalized_q)
        deduped_steps.append(step)

    # Cap steps at max_steps
    capped_steps = deduped_steps[:max_steps]

    # Renumber step ids 1..n
    renumbered_steps: list[PlanStep] = []
    for i, step in enumerate(capped_steps, start=1):
        renumbered_steps.append(
            PlanStep(
                id=i,
                sub_question=step.sub_question,
                tool=step.tool,
                query=step.query,
                rationale=step.rationale,
            )
        )

    if not renumbered_steps:
        return fallback_plan(question, reason="Plan had 0 steps after deduplication and filtering")

    plan.steps = renumbered_steps
    return plan


def make_plan(
    question: str,
    llm: LLMClient,
    settings: Settings | None = None,
    tracer: Any = None,
) -> ResearchPlan:
    """Generate a validated research plan for the question using the given LLM, with deterministic fallback."""
    cfg = settings or Settings()
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": question},
    ]

    try:
        plan = structured(
            llm,
            messages,
            ResearchPlan,
            tracer=tracer,
            purpose="planning",
        )
        norm = normalise_plan(plan, question, cfg)
        if norm.is_fallback and tracer and hasattr(tracer, "event"):
            tracer.event("planner_fallback", reason="Plan had 0 steps after normalization", question=question)
        return norm
    except (StructuredOutputError, LLMError, Exception) as exc:
        if tracer and hasattr(tracer, "event"):
            tracer.event("planner_fallback", reason=str(exc), question=question)
        return fallback_plan(question, reason=str(exc))
