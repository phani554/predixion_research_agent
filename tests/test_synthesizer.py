"""Tests for grounded synthesis and draft answer generation."""
from __future__ import annotations

import json
from research_agent.llm import FakeLLM
from research_agent.schemas import Confidence, DraftAnswer, DraftFinding, PlanStep, ResearchPlan, Source


def test_synthesize_prompt_contains_source_blocks_and_returns_draft_answer() -> None:
    from research_agent.synthesizer import format_evidence, synthesize

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is a vector database?",
        steps=[
            PlanStep(
                id=1,
                sub_question="What is a vector database and how does it work?",
                tool="web_search",
                query="vector database architecture",
            ),
        ],
        answer_shape="A clear explainer with architecture and use cases.",
    )

    sources = [
        Source(
            id="S1",
            url="https://example.com/vector-db",
            title="Vector Database Explained",
            content="A vector database indexes vector embeddings for approximate nearest neighbor search.",
            snippet="Vector embeddings search.",
            domain="example.com",
            score=0.88,
            relevance=0.9,
            flags=[],
        ),
        Source(
            id="S2",
            url="https://example.org/milvus",
            title="Milvus Overview",
            content="Milvus supports billion-scale vector search.",
            snippet="Billion-scale search.",
            domain="example.org",
            score=0.82,
            relevance=0.85,
            flags=["snippet_only"],
        ),
    ]

    # Test format_evidence
    evidence_text = format_evidence(sources)
    assert '<source id="S1" title="Vector Database Explained" url="https://example.com/vector-db">' in evidence_text
    assert '<source id="S2" title="Milvus Overview" url="https://example.org/milvus" flags="snippet_only">' in evidence_text
    assert "</source>" in evidence_text

    draft_dict = {
        "short_answer": "Vector databases specialize in high-dimensional vector search.",
        "key_findings": [
            {
                "statement": "Vector databases use approximate nearest neighbor indexing.",
                "source_ids": ["S1"],
            },
            {
                "statement": "Milvus can scale to billions of vectors.",
                "source_ids": ["S2"],
            },
        ],
        "limitations": ["Limited to public benchmarks."],
        "assumptions": ["Assuming Euclidean distance or cosine similarity."],
        "next_steps": ["Evaluate specific indexing algorithms like HNSW."],
        "self_confidence": "high",
    }

    fake_llm = FakeLLM(script={"synthesis": [json.dumps(draft_dict)]})

    draft = synthesize(
        question="What is a vector database?",
        plan=plan,
        sources=sources,
        llm=fake_llm,
    )

    assert isinstance(draft, DraftAnswer)
    assert draft.short_answer == "Vector databases specialize in high-dimensional vector search."
    assert len(draft.key_findings) == 2
    assert draft.key_findings[0].source_ids == ["S1"]
    assert draft.key_findings[1].source_ids == ["S2"]
    assert draft.self_confidence == Confidence.high

    # Verify prompt contents in FakeLLM calls
    assert len(fake_llm.calls) == 1
    purpose, messages = fake_llm.calls[0]
    assert purpose == "synthesis"
    user_prompt = messages[-1]["content"]
    assert '<source id="S1"' in user_prompt
    assert '<source id="S2"' in user_prompt
    assert "What is a vector database?" in user_prompt

