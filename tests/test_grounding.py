"""Tests for citation grounding, faithfulness checks, and confidence scoring."""
from __future__ import annotations

import pytest

from research_agent.schemas import (
    Confidence,
    DraftAnswer,
    DraftFinding,
    Evidence,
    FinalAnswer,
    PlanStep,
    ResearchPlan,
    Source,
    SourceRef,
)


def test_uncited_and_unknown_citations_removed() -> None:
    from research_agent.grounding import ground

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is Milvus?",
        steps=[
            PlanStep(
                id=1,
                sub_question="What is Milvus?",
                tool="web_search",
                query="milvus vector database",
            )
        ],
    )

    s1 = Source(
        id="S1",
        url="https://milvus.io/docs",
        title="Milvus Docs",
        content="Milvus is an open-source vector database built for similarity search.",
        snippet="Milvus is a vector database.",
        domain="milvus.io",
        score=0.85,
        relevance=0.9,
        step_id=1,
        step_ids=[1],
    )
    evidence = Evidence(sources=[s1], rejected=[])

    draft = DraftAnswer(
        short_answer="Milvus is an open-source vector database.",
        key_findings=[
            DraftFinding(
                statement="Milvus is an open-source vector database for similarity search.",
                source_ids=["S1", "S9"],  # S9 is unknown
            ),
            DraftFinding(
                statement="This finding has no citations at all.",
                source_ids=[],  # Uncited finding
            ),
        ],
        limitations=["Some initial limitation."],
        assumptions=["Standard hardware."],
        next_steps=[],
        self_confidence=Confidence.high,
    )

    answer = ground(
        question="What is Milvus?",
        draft=draft,
        plan=plan,
        evidence=evidence,
    )

    assert isinstance(answer, FinalAnswer)
    # Finding citing S9 and uncited finding are cleaned up
    assert len(answer.key_findings) == 1
    assert answer.key_findings[0].source_ids == ["S1"]
    assert len(answer.sources) == 1
    assert answer.sources[0].id == "S1"
    assert answer.sources[0].url == "https://milvus.io/docs"

    # Limitations report the removed unknown citation and uncited finding
    assert any("removed" in lim.lower() or "citation" in lim.lower() for lim in answer.limitations)


def test_invented_number_is_weak() -> None:
    from research_agent.grounding import support_level

    cited_text = "Milvus is an open-source vector database that can index billions of high-dimensional vectors."

    # Number 42 is not mentioned anywhere in cited_text
    invented_statement = "Milvus handles 42 trillion vectors in production."
    assert support_level(invented_statement, cited_text) == "weak"

    # Fully supported statement
    supported_statement = "Milvus is an open-source vector database."
    assert support_level(supported_statement, cited_text) == "supported"


def test_ground_reports_weak_findings_in_limitations() -> None:
    from research_agent.grounding import ground

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is Milvus?",
        steps=[PlanStep(id=1, sub_question="Milvus scale", tool="web_search", query="milvus scale")],
    )

    s1 = Source(
        id="S1",
        url="https://milvus.io/scale",
        title="Milvus Scale",
        content="Milvus scales out horizontally to handle billions of vector embeddings.",
        snippet="Scales to billions of vectors.",
        domain="milvus.io",
        score=0.8,
        relevance=0.8,
    )
    evidence = Evidence(sources=[s1], rejected=[])

    draft = DraftAnswer(
        short_answer="Milvus scaling details.",
        key_findings=[
            DraftFinding(
                statement="Milvus handles 999 trillion vectors.",  # invented number 999
                source_ids=["S1"],
            ),
        ],
        limitations=[],
        assumptions=[],
        next_steps=[],
        self_confidence=Confidence.high,
    )

    answer = ground("What is Milvus?", draft, plan, evidence)
    assert len(answer.key_findings) == 1
    assert answer.key_findings[0].support == "weak"
    assert any("weak" in lim.lower() for lim in answer.limitations)


def test_confidence_capped_by_self_assessment() -> None:
    from research_agent.grounding import ground

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is Milvus?",
        steps=[PlanStep(id=1, sub_question="Milvus overview", tool="web_search", query="milvus overview")],
    )

    s1 = Source(
        id="S1",
        url="https://milvus.io/overview",
        title="Milvus Overview",
        content="Milvus is an open-source vector database built for GenAI similarity search.",
        snippet="Milvus vector database.",
        domain="milvus.io",
        score=0.95,
        relevance=0.95,
        step_id=1,
        step_ids=[1],
    )
    evidence = Evidence(sources=[s1], rejected=[])

    draft = DraftAnswer(
        short_answer="Milvus is a vector database.",
        key_findings=[
            DraftFinding(
                statement="Milvus is an open-source vector database built for similarity search.",
                source_ids=["S1"],
            )
        ],
        limitations=[],
        assumptions=[],
        next_steps=[],
        self_confidence=Confidence.low,  # Model unsure despite strong evidence
    )

    answer = ground("What is Milvus?", draft, plan, evidence)

    assert answer.confidence == Confidence.low
    assert any("capped" in r.lower() for r in answer.confidence_reasons)
    assert answer.short_answer.startswith("Low confidence:")


def test_strong_evidence_gives_high_confidence() -> None:
    from research_agent.grounding import ground

    plan = ResearchPlan(
        in_scope=True,
        intent="comparison",
        restated_question="Vector database landscape",
        steps=[
            PlanStep(id=1, sub_question="Milvus features", tool="web_search", query="milvus"),
            PlanStep(id=2, sub_question="Qdrant features", tool="web_search", query="qdrant"),
            PlanStep(id=3, sub_question="Pinecone features", tool="web_search", query="pinecone"),
        ],
    )

    s1 = Source(
        id="S1",
        url="https://milvus.io/docs",
        title="Milvus",
        content="Milvus handles high-dimensional vector search at scale.",
        snippet="Milvus scale.",
        domain="milvus.io",
        score=0.9,
        relevance=0.9,
        step_id=1,
        step_ids=[1],
    )
    s2 = Source(
        id="S2",
        url="https://qdrant.tech/docs",
        title="Qdrant",
        content="Qdrant is written in Rust for fast similarity search.",
        snippet="Qdrant Rust.",
        domain="qdrant.tech",
        score=0.9,
        relevance=0.9,
        step_id=2,
        step_ids=[2],
    )
    s3 = Source(
        id="S3",
        url="https://pinecone.io/docs",
        title="Pinecone",
        content="Pinecone is a managed cloud vector database service.",
        snippet="Pinecone managed.",
        domain="pinecone.io",
        score=0.9,
        relevance=0.9,
        step_id=3,
        step_ids=[3],
    )
    evidence = Evidence(sources=[s1, s2, s3], rejected=[])

    draft = DraftAnswer(
        short_answer="Vector databases like Milvus, Qdrant, and Pinecone specialize in similarity search.",
        key_findings=[
            DraftFinding(statement="Milvus handles high-dimensional vector search at scale.", source_ids=["S1"]),
            DraftFinding(statement="Qdrant is written in Rust for fast similarity search.", source_ids=["S2"]),
            DraftFinding(statement="Pinecone is a managed cloud vector database service.", source_ids=["S3"]),
        ],
        limitations=[],
        assumptions=[],
        next_steps=[],
        self_confidence=Confidence.high,
    )

    answer = ground("Vector database landscape", draft, plan, evidence)

    assert answer.status == "answered"
    assert answer.confidence == Confidence.high
    assert answer.confidence_score >= 0.70


def test_no_valid_findings_is_insufficient_evidence() -> None:
    from research_agent.grounding import ground

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is Milvus?",
        steps=[PlanStep(id=1, sub_question="Milvus", tool="web_search", query="milvus")],
    )
    evidence = Evidence(sources=[], rejected=[])

    draft = DraftAnswer(
        short_answer="I could not find any verifiable information.",
        key_findings=[],  # No findings
        limitations=[],
        assumptions=[],
        next_steps=[],
        self_confidence=Confidence.high,
    )

    answer = ground("What is Milvus?", draft, plan, evidence)

    assert answer.status == "insufficient_evidence"
    assert answer.confidence == Confidence.low
    assert answer.confidence_score <= 0.20
    assert "insufficient" in answer.short_answer.lower()


