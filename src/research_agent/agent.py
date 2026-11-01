"""Top-level agent orchestration and pipeline entry point."""
from __future__ import annotations

from contextlib import nullcontext
import uuid
from typing import Any

from research_agent.config import Settings
from research_agent.executor import Executor
from research_agent.grounding import dedupe, ground
from research_agent.guard import check_question
from research_agent.llm import FaultyLLM, LLMError, OpenAICompatLLM, StructuredOutputError
from research_agent.planner import make_plan
from research_agent.schemas import Confidence, FinalAnswer, RunMetrics, RunResult, SourceRef
from research_agent.synthesizer import synthesize
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
    cfg = settings if settings is not None else Settings.from_env()
    active_tracer = (
        tracer
        if tracer is not None
        else Tracer(
            runs_dir=cfg.runs_dir,
            price_in=cfg.llm_price_in_per_m,
            price_out=cfg.llm_price_out_per_m,
        )
    )
    run_id = getattr(active_tracer, "run_id", f"run_{uuid.uuid4().hex[:12]}")
    if hasattr(active_tracer, "event"):
        active_tracer.event("run_started", question=question, faults=cfg.faults)

    def _finish(
        answer: FinalAnswer,
        plan_steps: list[dict[str, Any]] | None = None,
        sources: list[SourceRef] | None = None,
        rejected: list[dict[str, Any]] | None = None,
        sources_considered: int = 0,
        sources_used: int = 0,
    ) -> RunResult:
        if active_tracer and hasattr(active_tracer, "event"):
            active_tracer.event("answer_ready", answer=answer.model_dump(mode="json"))
        metrics = (
            active_tracer.finish(sources_considered=sources_considered, sources_used=sources_used)
            if (active_tracer and hasattr(active_tracer, "finish"))
            else RunMetrics()
        )
        return RunResult(
            run_id=run_id,
            answer=answer,
            plan=plan_steps or [],
            sources=sources or [],
            rejected=rejected or [],
            metrics=metrics,
        )

    try:
        clean_q, error = check_question(question, cfg)
        if error:
            return _finish(
                FinalAnswer(
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
                )
            )

        # Execute planning phase
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

        if any(f.startswith("llm:") for f in cfg.faults):
            llm_client = FaultyLLM(llm_client, cfg.faults)

        plan_span = (
            active_tracer.span("plan")
            if hasattr(active_tracer, "span")
            else nullcontext({})
        )
        with plan_span:
            plan = make_plan(clean_q, llm_client, settings=cfg, tracer=active_tracer)

        if active_tracer and hasattr(active_tracer, "event"):
            active_tracer.event("plan_ready", plan=plan.model_dump(mode="json"))

        if not plan.in_scope:
            return _finish(
                FinalAnswer(
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
                plan_steps=[s.model_dump() for s in plan.steps] if plan.steps else [],
            )

        # Execute research plan
        executor = Executor(settings=cfg, tracer=active_tracer, tools=tools)
        execute_span = (
            active_tracer.span("execute")
            if hasattr(active_tracer, "span")
            else nullcontext({})
        )
        with execute_span:
            evidence = executor.run(plan)

        if hasattr(active_tracer, "metrics") and active_tracer.metrics:
            active_tracer.metrics.sources_considered = evidence.candidates_considered

        if active_tracer and hasattr(active_tracer, "event"):
            active_tracer.event(
                "evidence_ready",
                sources=[s.model_dump(mode="json", exclude={"content"}) for s in evidence.sources],
                rejected=[r.model_dump(mode="json") for r in evidence.rejected],
                uncovered=evidence.uncovered_steps,
                tool_errors=evidence.tool_errors[:10],
            )

        if not evidence.sources:
            limitations = []
            if plan.is_fallback:
                limitations.append("Planner failed: using fallback research plan.")
            limitations.extend(evidence.tool_errors)
            if evidence.budget_exhausted:
                limitations.append("Budget exhausted during research execution.")
            if not limitations:
                limitations.append("No authoritative or relevant sources found for query.")

            return _finish(
                FinalAnswer(
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
                plan_steps=[s.model_dump() for s in plan.steps] if plan.steps else [],
                rejected=[r.model_dump() for r in evidence.rejected],
                sources_considered=evidence.candidates_considered,
                sources_used=0,
            )

        # Synthesize draft answer
        try:
            synth_span = (
                active_tracer.span("synthesize")
                if hasattr(active_tracer, "span")
                else nullcontext({})
            )
            with synth_span:
                draft = synthesize(
                    clean_q,
                    plan,
                    evidence.sources,
                    llm_client,
                    tracer=active_tracer,
                )
        except (StructuredOutputError, LLMError, Exception) as synth_err:
            limitations = []
            if plan.is_fallback:
                limitations.append("Planner failed: using fallback research plan.")
            limitations.extend(evidence.tool_errors)
            limitations.append(f"Synthesis failed: {synth_err}")

            selected_source_refs = [SourceRef(id=s.id, title=s.title, url=s.url) for s in evidence.sources]
            return _finish(
                FinalAnswer(
                    question=clean_q,
                    status="error",
                    short_answer=f"Failed to synthesize an answer from the retrieved evidence: {synth_err}",
                    key_findings=[],
                    sources=selected_source_refs,
                    confidence=Confidence.low,
                    confidence_score=0.0,
                    confidence_reasons=["Synthesis generation failed."],
                    limitations=dedupe(limitations),
                    assumptions=plan.assumptions,
                    next_steps=[
                        "Read the retrieved sources directly.",
                        "Retry the research question with a different model or phrasing.",
                    ],
                ),
                plan_steps=[s.model_dump() for s in plan.steps] if plan.steps else [],
                sources=selected_source_refs,
                rejected=[r.model_dump() for r in evidence.rejected],
                sources_considered=evidence.candidates_considered,
                sources_used=len(evidence.sources),
            )

        # Ground the draft answer into FinalAnswer
        ground_span = (
            active_tracer.span("ground")
            if hasattr(active_tracer, "span")
            else nullcontext({})
        )
        with ground_span:
            final_answer = ground(clean_q, draft, plan, evidence)

        # Merge plan fallback, tool errors, budget, and injection limitations
        extra_limitations: list[str] = []
        if plan.is_fallback:
            extra_limitations.append("Planner failed: using fallback research plan.")
        extra_limitations.extend(evidence.tool_errors)
        if evidence.budget_exhausted:
            extra_limitations.append("Budget exhausted during research execution.")
        if any("prompt_injection_suspected" in s.flags for s in evidence.sources):
            extra_limitations.append(
                "Retrieved source text contained patterns that looked like instructions to the AI and was quarantined."
            )

        if extra_limitations:
            final_answer.limitations = dedupe(final_answer.limitations + extra_limitations)

        return _finish(
            final_answer,
            plan_steps=[s.model_dump() for s in plan.steps] if plan.steps else [],
            sources=final_answer.sources,
            rejected=[r.model_dump() for r in evidence.rejected],
            sources_considered=evidence.candidates_considered,
            sources_used=len(final_answer.sources),
        )

    except Exception as exc:
        if active_tracer and hasattr(active_tracer, "event"):
            active_tracer.event("unhandled_exception", error=str(exc))
        return _finish(
            FinalAnswer(
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
            )
        )

