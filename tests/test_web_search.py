from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from research_agent.config import Settings
from research_agent.schemas import SearchHit
from research_agent.tools.web_search import web_search


def test_web_search_all_empty() -> None:
    # When all backends return no results or raise
    with patch("research_agent.tools.web_search.DDGS.text", side_effect=Exception("No results")):
        hits = web_search("xyznonexistentterm12345", settings=Settings())
        assert hits == []


@pytest.mark.live
def test_web_search_live() -> None:
    hits = web_search("Python programming language", settings=Settings())
    assert len(hits) >= 1
    assert all(isinstance(h, SearchHit) for h in hits)
    assert any("python" in h.title.lower() or "python" in h.snippet.lower() for h in hits)
