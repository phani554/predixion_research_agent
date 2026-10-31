from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from research_agent.config import Settings
from research_agent.tools.base import run_tool
from research_agent.tools.wikipedia import wikipedia


def test_wikipedia_no_match() -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"query": {"search": []}}

    with patch("httpx.Client.get", return_value=mock_resp):
        res = run_tool("wikipedia", wikipedia, {"query": "completely_unmatched_query_xyz_999"}, settings=Settings())
        assert res.status == "empty"


@pytest.mark.live
def test_wikipedia_live() -> None:
    res = run_tool(
        "wikipedia",
        wikipedia,
        {"query": "retrieval augmented generation"},
        settings=Settings(),
    )
    assert res.status == "ok"
    assert isinstance(res.data, dict)
    assert "Retrieval-augmented generation" in res.data["title"]
    assert "https://en.wikipedia.org/wiki/" in res.data["url"]
    assert "retrieval" in res.data["summary"].lower()

