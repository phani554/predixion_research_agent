"""Input guard to protect LLM token budget and reject invalid user inputs early."""
from __future__ import annotations

from research_agent.config import Settings


def check_question(question: str, settings: Settings | None = None) -> tuple[str, str | None]:
    """Sanitize and validate a research question before allocating resources or calling models.

    Normalizes whitespace and checks length bounds defined in settings. Returns the cleaned
    question and an error message if invalid.
    """
    cfg = settings or Settings()
    # Normalize internal and surrounding whitespace
    cleaned = " ".join(question.strip().split())

    if len(cleaned) < cfg.min_question_chars:
        return (
            "",
            f"Question is too short ({len(cleaned)} characters; minimum is {cfg.min_question_chars}). Please provide a more detailed question.",
        )

    if len(cleaned) > cfg.max_question_chars:
        return (
            cleaned,
            f"Question is too long ({len(cleaned)} characters; maximum is {cfg.max_question_chars}). Please shorten your question.",
        )

    return (cleaned, None)

