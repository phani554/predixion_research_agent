from __future__ import annotations

import os
import pytest
from pydantic import ValidationError

from research_agent.config import Settings


def test_env_overrides_dotenv(tmp_path) -> None:
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=dotenv-model\nMIN_QUESTION_CHARS=10\n", encoding="utf-8")

    # Set environment variable
    old_model = os.environ.get("LLM_MODEL")
    try:
        os.environ["LLM_MODEL"] = "env-model"
        settings = Settings.from_env(env_path=env_file)
        assert settings.llm_model == "env-model"
        # Since MIN_QUESTION_CHARS wasn't in os.environ, it should come from the file
        assert settings.min_question_chars == 10
    finally:
        if old_model is not None:
            os.environ["LLM_MODEL"] = old_model
        else:
            os.environ.pop("LLM_MODEL", None)


def test_invalid_numeric_setting_raises_error(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MIN_QUESTION_CHARS=not-a-number\n", encoding="utf-8")

    with pytest.raises((ValueError, ValidationError)):
        Settings.from_env(env_path=env_file)

