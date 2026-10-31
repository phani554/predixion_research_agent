from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from research_agent.config import Settings
from research_agent.tools.base import BlockedError, PermanentToolError, run_tool
from research_agent.tools.fetch_page import fetch_page
from research_agent.tools.url_safety import check_url


def test_private_and_non_http_urls_blocked() -> None:
    blocked_urls = [
        "http://127.0.0.1:8000/admin",
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost:3000/",
        "ftp://ftp.example.com/file.txt",
    ]

    for url in blocked_urls:
        with pytest.raises(BlockedError):
            check_url(url)

        # Also verify run_tool returns status blocked without raising
        result = run_tool("fetch_page", fetch_page, {"url": url}, settings=Settings())
        assert result.status == "blocked"


def test_fetch_page_unsupported_content_type() -> None:
    # PDF should fail with permanent error
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/pdf"}

    with patch("httpx.Client.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value = mock_resp
        result = run_tool("fetch_page", fetch_page, {"url": "https://example.com/file.pdf"}, settings=Settings())
        assert result.status == "error"
        assert "unsupported content-type" in (result.error or "").lower()


@pytest.mark.live
def test_fetch_page_live() -> None:
    result = run_tool(
        "fetch_page",
        fetch_page,
        {"url": "https://en.wikipedia.org/wiki/Python_(programming_language)"},
        settings=Settings(page_char_limit=1000),
    )
    assert result.status == "ok"
    assert isinstance(result.data, str)
    assert len(result.data) <= 1000
    assert "python" in result.data.lower()

