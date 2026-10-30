"""Top-level agent orchestration and pipeline entry point."""
from __future__ import annotations

import uuid
from typing import Any

from research_agent.config import Settings
from research_agent.guard import check_question
from research_agent.schemas import Confidence, FinalAnswer, RunMetrics, RunResult


def run_research(
    question: str,
    settings: Settings | None = None,
    llm: Any = None,
    tools: Any = None,
    tracer: Any = None,
) -> RunResult:
    """Execute the end-to-end research workflow or return a structured refusal/error.

    Catches any internal failures and ensures callers always receive a validated FinalAnswer contract.
    """
    cfg = settings or Settings()
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    try:
        clean_q, error = check_question(question, cfg)
        if error:
            return RunResult(
                run_id=run_id,
                answer=FinalAnswer(
                    question=question,
                    status="invalid_input",
                    short_answer=error,
                    key_findings=[],
                    sources=[],
                    confidence=Confidence.low,
                    confidence_score=0.0,
                    confidence_reasons=["Input question rejected by input guard."],
                    limitations=[error],
                    assumptions=[],
                    next_steps=["Provide a question that meets length and content requirements."],
                ),
                plan=[],
                sources=[],
                rejected=[],
                metrics=RunMetrics(),
            )

        # Pipeline stub until planning, tool execution, and synthesis stages are implemented
        return RunResult(
            run_id=run_id,
            answer=FinalAnswer(
                question=clean_q,
                status="error",
                short_answer="The research agent pipeline is not implemented yet.",
                key_findings=[],
                sources=[],
                confidence=Confidence.low,
                confidence_score=0.0,
                confidence_reasons=["Pipeline under active development."],
                limitations=["Research pipeline is not implemented yet."],
                assumptions=[],
                next_steps=["Implement planner, tool execution, and synthesis modules."],
            ),
            plan=[],
            sources=[],
            rejected=[],
            metrics=RunMetrics(),
        )

    except Exception as exc:
        return RunResult(
            run_id=run_id,
            answer=FinalAnswer(
                question=question,
                status="error",
                short_answer=f"An unexpected internal error occurred: {exc}",
                key_findings=[],
                sources=[],
                confidence=Confidence.low,
                confidence_score=0.0,
                confidence_reasons=["Execution aborted due to an internal error."],
                limitations=[f"Unexpected error: {type(exc).__name__}: {exc}"],
                assumptions=[],
                next_steps=["Inspect system logs or report the issue."],
            ),
            plan=[],
            sources=[],
            rejected=[],
            metrics=RunMetrics(),
        )

