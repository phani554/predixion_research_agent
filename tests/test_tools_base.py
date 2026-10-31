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


def test_fault_injection_and_failure_counted() -> None:
    from research_agent.tools.base import run_tool, INJECTION_FIXTURE
    from research_agent.tracing import Tracer

    tracer = Tracer()
    # Test <tool>:timeout fault injection
    timeout_settings = Settings(faults=["web_search:timeout"])
    res_timeout = run_tool("web_search", lambda query: ["hit"], {"query": "test"}, settings=timeout_settings, tracer=tracer)
    assert res_timeout.status == "timeout"
    assert "injected" in (res_timeout.error or "").lower()

    # Test <tool>:error fault injection
    error_settings = Settings(faults=["wikipedia:error"])
    res_error = run_tool("wikipedia", lambda query: "article", {"query": "test"}, settings=error_settings, tracer=tracer)
    assert res_error.status == "error"
    assert "injected" in (res_error.error or "").lower()

    # Verify tool calls are counted on tracer
    assert tracer.metrics.tool_calls == 2

    # Test fetch_page:injection
    injection_settings = Settings(faults=["fetch_page:injection"])
    res_inj = run_tool("fetch_page", lambda url: "Normal article content.", {"url": "https://example.com"}, settings=injection_settings)
    assert res_inj.status == "ok"
    assert INJECTION_FIXTURE in res_inj.data

