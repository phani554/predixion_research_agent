from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from research_agent.config import Settings
from research_agent.schemas import ToolResult, ToolStatus, SearchHit


def test_transient_error_is_retried() -> None:
    from research_agent.tools.base import TransientToolError, run_tool

    calls = 0

    def flaky_tool():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TransientToolError("Network glitch")
        return {"result": "data"}

    settings = Settings(tool_timeout_s=2.0, tool_max_retries=2)
    with patch("time.sleep"):  # Speed up tests
        result = run_tool("flaky", flaky_tool, {}, settings=settings)

    assert isinstance(result, ToolResult)
    assert result.status == "ok"
    assert result.data == {"result": "data"}
    assert result.attempts == 2
    assert calls == 2


def test_retries_are_bounded() -> None:
    from research_agent.tools.base import TransientToolError, run_tool

    calls = 0

    def always_failing():
        nonlocal calls
        calls += 1
        raise TransientToolError("Repeated failure")

    settings = Settings(tool_timeout_s=2.0, tool_max_retries=2)
    with patch("time.sleep"):
        result = run_tool("always_failing", always_failing, {}, settings=settings)

    assert isinstance(result, ToolResult)
    assert result.status == "error"
    assert result.attempts == 3  # 1 initial + 2 retries
    assert calls == 3


def test_permanent_error_not_retried() -> None:
    from research_agent.tools.base import PermanentToolError, run_tool

    calls = 0

    def not_found():
        nonlocal calls
        calls += 1
        raise PermanentToolError("404 Not Found")

    settings = Settings(tool_timeout_s=2.0, tool_max_retries=2)
    result = run_tool("not_found", not_found, {}, settings=settings)

    assert isinstance(result, ToolResult)
    assert result.status == "error"
    assert result.attempts == 1
    assert calls == 1


def test_hard_timeout() -> None:
    from research_agent.tools.base import run_tool

    def hanging_tool():
        time.sleep(1.0)
        return "finished"

    settings = Settings(tool_timeout_s=0.05, tool_max_retries=0)
    result = run_tool("hanging", hanging_tool, {}, settings=settings)

    assert isinstance(result, ToolResult)
    assert result.status == "timeout"
    assert result.attempts == 1

