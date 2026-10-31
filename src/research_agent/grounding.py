"""Citation grounding, faithfulness checking, and confidence scoring."""
from __future__ import annotations

import re
from typing import Any, Literal

from research_agent.schemas import (
    Confidence,
    DraftAnswer,
    DraftFinding,
    Evidence,
    FinalAnswer,
    Finding,
    ResearchPlan,
    Source,
    SourceRef,
)
from research_agent.sources import terms


def dedupe(items: list[str]) -> list[str]:
    """Deduplicate a list of strings while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def support_level(statement: str, cited_text: str) -> Literal["supported", "weak"]:
    """Evaluate whether statement is supported by cited text via number check and 40% lexical overlap."""
    if not statement:
        return "weak"

    # 1. Number verification: every number in statement must appear in cited_text
    numbers = re.findall(r"\b\d+(?:[\.,]\d+)*\b", statement)
    cited_lower = cited_text.lower()
    for num in numbers:
        clean_num = num.replace(",", "")
        if num.lower() not in cited_lower and clean_num not in cited_lower:
            return "weak"

    # 2. Lexical content overlap check: >= 40% of content words must appear in cited_text
    st_terms = terms(statement)
    if not st_terms:
        return "supported"

    c_terms = terms(cited_text)
    overlap = len(st_terms & c_terms) / len(st_terms)
    if overlap < 0.40:
        return "weak"

    return "supported"


CONFIDENCE_RANK = {
    Confidence.low: 1,
    Confidence.medium: 2,
    Confidence.high: 3,
}


def score_to_level(score: float) -> Confidence:
    """Map a 0.0-1.0 confidence score to high, medium, or low confidence level."""
    if score >= 0.70:
        return Confidence.high
    if score >= 0.45:
        return Confidence.medium
    return Confidence.low


def confidence_score(
    cited: list[Source],
    findings: list[Finding],
    plan: ResearchPlan,
    evidence: Evidence,
    dropped_count: int = 0,
) -> tuple[float, list[str]]:
    """Compute multi-factor confidence score (0.0 to 1.0) and explainable reasons list."""
    cited_count = len(cited)
    source_factor = min(cited_count / 4.0, 1.0)

    cited_domains = {s.domain for s in cited if s.domain}
    domain_factor = min(len(cited_domains) / 3.0, 1.0)

    if plan.steps:
        covered = sum(
            1
            for step in plan.steps
            if any((step.id in s.step_ids or s.step_id == step.id) for s in cited)
        )
        coverage = covered / len(plan.steps)
    else:
        coverage = 1.0

    avg_source_score = (sum(s.score for s in cited) / cited_count) if cited_count > 0 else 0.0

    base_score = (
        0.30 * source_factor
        + 0.20 * domain_factor
        + 0.30 * coverage
        + 0.20 * avg_source_score
    )

    reasons = [
        f"Cited sources factor: {source_factor:.2f} ({cited_count} source(s))",
        f"Domain diversity factor: {domain_factor:.2f} ({len(cited_domains)} domain(s))",
        f"Sub-question coverage factor: {coverage:.2f}",
        f"Average source quality factor: {avg_source_score:.2f}",
    ]

    penalties = 0.0

    # 1. Tool errors penalty (0.05 per tool failure up to 0.20)
    if evidence.tool_errors:
        tool_pen = min(len(evidence.tool_errors) * 0.05, 0.20)
        penalties += tool_pen
        reasons.append(f"Penalty for {len(evidence.tool_errors)} tool failure(s): -{tool_pen:.2f}")

    # 2. Suspected injection in cited evidence (-0.15)
    if any("prompt_injection_suspected" in s.flags for s in cited):
        penalties += 0.15
        reasons.append("Penalty for suspected prompt injection in cited evidence: -0.15")

    # 3. Invalid citations or dropped findings (-0.10)
    if dropped_count > 0:
        penalties += 0.10
        reasons.append(f"Penalty for {dropped_count} invalid citation(s) or dropped finding(s): -0.10")

    # 4. Weak findings share (up to 0.20 * weak share)
    if findings:
        weak_count = sum(1 for f in findings if f.support == "weak")
        weak_share = weak_count / len(findings)
        weak_pen = 0.20 * weak_share
        if weak_pen > 0:
            penalties += weak_pen
            reasons.append(f"Penalty for {weak_count} weak finding(s) ({weak_share:.0%}): -{weak_pen:.2f}")

    # 5. Majority snippet-only sources (-0.10)
    if cited_count > 0:
        snippet_count = sum(1 for s in cited if "snippet_only" in s.flags or not s.content.strip())
        if (snippet_count / cited_count) > 0.5:
            penalties += 0.10
            reasons.append("Penalty for majority snippet-only evidence: -0.10")

    raw_score = base_score - penalties
    clamped_score = max(0.0, min(1.0, raw_score))
    return round(clamped_score, 4), reasons


def ground(
    question: str,
    draft: DraftAnswer,
    plan: ResearchPlan,
    evidence: Evidence,
) -> FinalAnswer:
    """Ground drafted answer by validating citations, verifying faithfulness, and computing confidence."""
    valid_sources_by_id = {s.id: s for s in evidence.sources}

    valid_findings: list[Finding] = []
    removed_citations = 0
    removed_findings = 0
    weak_findings_count = 0

    for df in draft.key_findings:
        valid_sids: list[str] = []
        for sid in df.source_ids:
            if sid in valid_sources_by_id:
                if sid not in valid_sids:
                    valid_sids.append(sid)
            else:
                removed_citations += 1

        if not valid_sids:
            removed_findings += 1
            continue

        cited_text = " ".join(
            f"{valid_sources_by_id[sid].title} {valid_sources_by_id[sid].content} {valid_sources_by_id[sid].snippet}"
            for sid in valid_sids
        )
        sup = support_level(df.statement, cited_text)
        if sup == "weak":
            weak_findings_count += 1

        valid_findings.append(
            Finding(
                statement=df.statement,
                source_ids=valid_sids,
                support=sup,
            )
        )

    # List only cited sources in the order they appear in evidence.sources
    cited_sids = {sid for f in valid_findings for sid in f.source_ids}
    cited_sources = [
        SourceRef(id=s.id, title=s.title, url=s.url)
        for s in evidence.sources
        if s.id in cited_sids
    ]
    cited_source_objs = [s for s in evidence.sources if s.id in cited_sids]

    limitations = list(draft.limitations)
    if removed_citations > 0 or removed_findings > 0:
        limitations.append(
            f"Grounding removed {removed_citations} invalid citation(s) and {removed_findings} uncited finding(s)."
        )

    if weak_findings_count > 0:
        limitations.append(
            f"{weak_findings_count} finding(s) marked weak due to unverified numbers or low text overlap."
        )

    # Compute code-derived confidence score and reasons
    dropped_count = removed_citations + removed_findings
    raw_conf_score, conf_reasons = confidence_score(
        cited=cited_source_objs,
        findings=valid_findings,
        plan=plan,
        evidence=evidence,
        dropped_count=dropped_count,
    )

    code_level = score_to_level(raw_conf_score)

    # Self-rating cap: final level MUST NOT exceed draft.self_confidence
    if CONFIDENCE_RANK[code_level] > CONFIDENCE_RANK[draft.self_confidence]:
        final_level = draft.self_confidence
        conf_reasons.append(
            f"Confidence capped at model self-assessment ({draft.self_confidence.value})."
        )
    else:
        final_level = code_level

    # Determine honest answer status and short answer prefix
    if not valid_findings:
        status = "insufficient_evidence"
        final_level = Confidence.low
        final_conf_score = min(raw_conf_score, 0.20)
        short_answer = "Insufficient evidence to answer the question."
    else:
        if plan.steps:
            covered_steps = sum(
                1
                for step in plan.steps
                if any((step.id in s.step_ids or s.step_id == step.id) for s in cited_source_objs)
            )
            has_uncovered_steps = (covered_steps < len(plan.steps)) or bool(evidence.uncovered_steps)
        else:
            has_uncovered_steps = False

        is_partial = (final_level == Confidence.low or has_uncovered_steps)
        status = "partial" if is_partial else "answered"
        final_conf_score = raw_conf_score

        if final_level == Confidence.low:
            if not draft.short_answer.startswith("Low confidence:"):
                short_answer = f"Low confidence: {draft.short_answer}"
            else:
                short_answer = draft.short_answer
        else:
            short_answer = draft.short_answer

    deduped_limitations = dedupe(limitations)
    deduped_assumptions = dedupe(draft.assumptions)
    deduped_next_steps = dedupe(draft.next_steps)

    return FinalAnswer(
        question=question,
        status=status,
        short_answer=short_answer,
        key_findings=valid_findings,
        sources=cited_sources,
        confidence=final_level,
        confidence_score=final_conf_score,
        confidence_reasons=conf_reasons,
        limitations=deduped_limitations,
        assumptions=deduped_assumptions,
        next_steps=deduped_next_steps,
    )
