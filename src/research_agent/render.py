"""Format research outputs into human-readable Markdown."""
from __future__ import annotations

from research_agent.schemas import RunResult


def to_markdown(result: RunResult, verbose: bool = False) -> str:
    """Render a RunResult into clean, structured Markdown for terminal or file inspection.

    Handles answered states as well as honest refusals, errors, and optional verbose metrics.
    """
    ans = result.answer
    lines: list[str] = [
        f"# Research: {ans.question}",
        "",
        f"**Status:** `{ans.status}`",
        "",
        "## Short Answer",
        ans.short_answer,
        "",
    ]

    if ans.key_findings:
        lines.append("## Key Findings")
        for finding in ans.key_findings:
            cites = ", ".join(f"[{sid}]" for sid in finding.source_ids)
            support_tag = " ⚠️ _(weak)_" if finding.support == "weak" else ""
            lines.append(f"- {finding.statement} {cites}{support_tag}")
        lines.append("")

    if ans.sources:
        lines.append("## Sources")
        for src in ans.sources:
            lines.append(f"- **[{src.id}]** [{src.title}]({src.url})")
        lines.append("")

    lines.append(f"## Confidence: {ans.confidence.value.upper()} ({ans.confidence_score:.2f})")
    if ans.confidence_reasons:
        for reason in ans.confidence_reasons:
            lines.append(f"- {reason}")
    lines.append("")

    if ans.limitations:
        lines.append("## Limitations")
        for item in ans.limitations:
            lines.append(f"- {item}")
        lines.append("")

    if ans.assumptions:
        lines.append("## Assumptions")
        for item in ans.assumptions:
            lines.append(f"- {item}")
        lines.append("")

    if ans.next_steps:
        lines.append("## Next Steps")
        for item in ans.next_steps:
            lines.append(f"- {item}")
        lines.append("")

    if verbose:
        if result.plan:
            lines.append("## Research Plan")
            for step in result.plan:
                step_id = getattr(step, "id", None) or (step.get("id") if isinstance(step, dict) else "?")
                tool = getattr(step, "tool", None) or (step.get("tool") if isinstance(step, dict) else "")
                sub_q = getattr(step, "sub_question", None) or (step.get("sub_question") if isinstance(step, dict) else "")
                query = getattr(step, "query", None) or (step.get("query") if isinstance(step, dict) else "")
                lines.append(f"{step_id}. **[{tool}]** {sub_q} (query: `{query}`)")
            lines.append("")

        lines.append("## Run Metrics")
        lines.append(f"- Run ID: `{result.run_id}`")
        lines.append(f"- Total time: {result.metrics.total_time_s:.2f}s")
        lines.append(f"- LLM calls: {result.metrics.llm_calls}")
        lines.append(f"- Tool calls: {result.metrics.tool_calls}")
        lines.append(f"- Tokens: {result.metrics.input_tokens} in / {result.metrics.output_tokens} out")
        lines.append(f"- Estimated cost: ${result.metrics.estimated_cost_usd:.4f}")
        lines.append("")

    return "\n".join(lines).strip()

