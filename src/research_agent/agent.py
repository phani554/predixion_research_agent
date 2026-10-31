"""Top-level agent orchestration and pipeline entry point."""
from __future__ import annotations

import uuid
from typing import Any

from research_agent.config import Settings
from research_agent.executor import Executor
from research_agent.guard import check_question
from research_agent.llm import OpenAICompatLLM
from research_agent.planner import make_plan
from research_agent.schemas import Confidence, FinalAnswer, RunMetrics, RunResult, SourceRef
from research_agent.tracing import Tracer


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

        # Execute planning phase
        active_tracer = tracer if tracer is not None else Tracer()
        if llm is None:
            extra_body = None
            if cfg.llm_extra_body:
                import json
                try:
                    extra_body = json.loads(cfg.llm_extra_body)
                except Exception:
                    extra_body = None
            llm_client = OpenAICompatLLM(
                base_url=cfg.llm_base_url or None,
                api_key=cfg.llm_api_key or None,
                model=cfg.llm_model,
                timeout_s=cfg.request_timeout_s,
                min_interval_s=cfg.llm_min_interval_s,
                max_tokens=cfg.llm_max_tokens,
                extra_body=extra_body,
            )
        else:
            llm_client = llm

        plan = make_plan(clean_q, llm_client, settings=cfg, tracer=active_tracer)

        if not plan.in_scope:
            return RunResult(
                run_id=run_id,
                answer=FinalAnswer(
                    question=clean_q,
                    status="out_of_scope",
                    short_answer=plan.out_of_scope_reason or "Question is out of scope for research agent.",
                    key_findings=[],
                    sources=[],
                    confidence=Confidence.low,
                    confidence_score=0.0,
                    confidence_reasons=["Flagged as out of scope by research planner."],
                    limitations=[plan.out_of_scope_reason or "Question is out of scope for research agent."],
                    assumptions=plan.assumptions,
                    next_steps=[],
                ),
                plan=[s.model_dump() for s in plan.steps] if plan.steps else [],
                sources=[],
                rejected=[],
                metrics=active_tracer.metrics,
            )

        # Execute research plan
        executor = Executor(settings=cfg, tracer=active_tracer, tools=tools)
        evidence = executor.run(plan)

        if not evidence.sources:
            limitations = []
            if plan.is_fallback:
                limitations.append("Planner failed: using fallback research plan.")
            limitations.extend(evidence.tool_errors)
            if evidence.budget_exhausted:
                limitations.append("Budget exhausted during research execution.")
            if not limitations:
                limitations.append("No authoritative or relevant sources found for query.")

            return RunResult(
                run_id=run_id,
                answer=FinalAnswer(
                    question=clean_q,
                    status="insufficient_evidence",
                    short_answer="Insufficient evidence to answer the question.",
                    key_findings=[],
                    sources=[],
                    confidence=Confidence.low,
                    confidence_score=0.0,
                    confidence_reasons=["No trustworthy or relevant sources were retrieved to substantiate an answer."],
                    limitations=limitations,
                    assumptions=plan.assumptions,
                    next_steps=["Broaden search query or check tool connectivity."],
                ),
                plan=[s.model_dump() for s in plan.steps] if plan.steps else [],
                sources=[],
                rejected=[r.model_dump() for r in evidence.rejected],
                metrics=active_tracer.metrics,
            )

        # Sources found (synthesis will be wired in change 07)
        limitations = []
        if plan.is_fallback:
            limitations.append("Planner failed: using fallback research plan.")
        limitations.extend(evidence.tool_errors)
        if evidence.uncovered_steps:
            limitations.append(f"Sub-questions uncovered: {evidence.uncovered_steps}")

        return RunResult(
            run_id=run_id,
            answer=FinalAnswer(
                question=clean_q,
                status="answered",
                short_answer=f"Found {len(evidence.sources)} relevant sources.",
                key_findings=[],
                sources=[SourceRef(id=s.id, title=s.title, url=s.url) for s in evidence.sources],
                confidence=Confidence.medium if len(evidence.sources) >= 2 else Confidence.low,
                confidence_score=0.5,
                confidence_reasons=[f"Collected {len(evidence.sources)} sources."],
                limitations=limitations,
                assumptions=plan.assumptions,
                next_steps=[],
            ),
            plan=[s.model_dump() for s in plan.steps] if plan.steps else [],
            sources=[SourceRef(id=s.id, title=s.title, url=s.url) for s in evidence.sources],
            rejected=[r.model_dump() for r in evidence.rejected],
            metrics=active_tracer.metrics,
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

