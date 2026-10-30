from __future__ import annotations

from research_agent.render import to_markdown
from research_agent.schemas import Confidence, FinalAnswer, Finding, RunMetrics, RunResult, SourceRef


def test_to_markdown_basic() -> None:
    ans = FinalAnswer(
        question="What is Python?",
        status="answered",
        short_answer="A programming language.",
        key_findings=[Finding(statement="Used for AI and web.", source_ids=["s1"])],
        sources=[SourceRef(id="s1", title="Python Website", url="https://python.org")],
        confidence=Confidence.high,
        confidence_score=0.95,
        confidence_reasons=["Official documentation"],
        limitations=["Scope limited to general definition"],
        assumptions=[],
        next_steps=[],
    )
    res = RunResult(run_id="run_123", answer=ans, metrics=RunMetrics(total_time_s=1.2))

    rendered = to_markdown(res)
    assert "# Question: What is Python?" in rendered or "What is Python?" in rendered
    assert "A programming language." in rendered
    assert "Used for AI and web." in rendered
    assert "[s1]" in rendered
    assert "https://python.org" in rendered
    assert "0.95" in rendered or "high" in rendered


def test_to_markdown_error_state() -> None:
    ans = FinalAnswer(
        question="   ",
        status="invalid_input",
        short_answer="Question is too short.",
        limitations=["Question is too short."],
    )
    res = RunResult(run_id="run_err", answer=ans)

    rendered = to_markdown(res)
    assert "invalid_input" in rendered
    assert "Question is too short." in rendered

