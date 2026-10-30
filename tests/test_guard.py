from __future__ import annotations

from research_agent.config import Settings
from research_agent.guard import check_question


def test_blank_question() -> None:
    settings = Settings()
    clean_q, error = check_question("   ", settings)
    assert clean_q == ""
    assert error is not None
    assert "too short" in error.lower() or "empty" in error.lower()


def test_too_short_question() -> None:
    settings = Settings(min_question_chars=8)
    clean_q, error = check_question("Why?", settings)
    assert error is not None
    assert "too short" in error.lower()


def test_over_long_question() -> None:
    settings = Settings(max_question_chars=500)
    long_q = "a" * 600
    clean_q, error = check_question(long_q, settings)
    assert error is not None
    assert "shorten" in error.lower() or "too long" in error.lower()


def test_valid_question() -> None:
    settings = Settings()
    q = "   What are the effects of caffeine on sleep?   "
    clean_q, error = check_question(q, settings)
    assert error is None
    assert clean_q == "What are the effects of caffeine on sleep?"

