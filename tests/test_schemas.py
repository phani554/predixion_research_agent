from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_agent.schemas import (
    AnswerStatus,
    Confidence,
    FinalAnswer,
    Finding,
    RunMetrics,
    RunResult,
    SourceRef,
)


def test_finding_requires_a_citation() -> None:
    # A finding with no source ids must fail validation
    with pytest.raises(ValidationError):
        Finding(statement="Water is wet", source_ids=[])

    # Valid finding with at least one citation
    finding = Finding(statement="Water is wet", source_ids=["src-1"])
    assert finding.statement == "Water is wet"
    assert finding.source_ids == ["src-1"]
    assert finding.support == "supported"


def test_final_answer_fields() -> None:
    ans = FinalAnswer(
        question="What is Python?",
        status="answered",
        short_answer="A programming language.",
        key_findings=[Finding(statement="High level", source_ids=["s1"])],
        sources=[SourceRef(id="s1", title="Python Home", url="https://python.org")],
        confidence=Confidence.high,
        confidence_score=0.95,
        confidence_reasons=["Direct official documentation cited"],
        limitations=[],
        assumptions=[],
        next_steps=[],
    )
    assert ans.status == "answered"
    assert ans.confidence == Confidence.high
    assert 0.0 <= ans.confidence_score <= 1.0


def test_confidence_score_range_validation() -> None:
    with pytest.raises(ValidationError):
        FinalAnswer(
            question="What is Python?",
            status="answered",
            short_answer="A programming language.",
            key_findings=[Finding(statement="High level", source_ids=["s1"])],
            sources=[SourceRef(id="s1", title="Python Home", url="https://python.org")],
            confidence=Confidence.high,
            confidence_score=1.5,  # Invalid: > 1.0
            confidence_reasons=[],
            limitations=[],
            assumptions=[],
            next_steps=[],
        )

