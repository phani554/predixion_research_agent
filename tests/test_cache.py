from __future__ import annotations

import time
from research_agent.cache import Cache
from research_agent.config import Settings
from research_agent.tools.base import run_tool


def test_cache_hit_skips_call(tmp_path) -> None:
    cache = Cache(directory=tmp_path, ttl_s=60)
    calls = 0

    def sample_tool(query: str) -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"result": f"found for {query}"}

    args = {"query": "python"}
    settings = Settings()

    # First call - cache miss
    res1 = run_tool("sample", sample_tool, args, settings=settings, cache=cache)
    assert res1.status == "ok"
    assert res1.cached is False
    assert calls == 1
    assert res1.data == {"result": "found for python"}

    # Second call - cache hit (must skip the call)
    res2 = run_tool("sample", sample_tool, args, settings=settings, cache=cache)
    assert res2.status == "ok"
    assert res2.cached is True
    assert calls == 1
    assert res2.data == {"result": "found for python"}


def test_failed_results_are_not_cached(tmp_path) -> None:
    from research_agent.tools.base import PermanentToolError

    cache = Cache(directory=tmp_path, ttl_s=60)
    calls = 0

    def failing_tool() -> None:
        nonlocal calls
        calls += 1
        raise PermanentToolError("Fatal error")

    settings = Settings()
    res1 = run_tool("failing", failing_tool, {}, settings=settings, cache=cache)
    assert res1.status == "error"
    assert calls == 1

    # Second call must not be cached and should run again
    res2 = run_tool("failing", failing_tool, {}, settings=settings, cache=cache)
    assert res2.status == "error"
    assert res2.cached is False
    assert calls == 2

