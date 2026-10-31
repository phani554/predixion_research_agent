"""Web page fetching tool with streaming size limits, content-type filtering, and trafilatura extraction."""
from __future__ import annotations

import httpx
import trafilatura

from research_agent.config import Settings
from research_agent.tools.base import PermanentToolError, TransientToolError
from research_agent.tools.url_safety import check_url


def fetch_page(url: str, *, settings: Settings | None = None) -> str:
    """Fetch a public webpage, enforce size and type limits, and extract readable text."""
    cfg = settings or Settings()
    check_url(url)

    timeout = cfg.tool_timeout_s or 10.0
    max_bytes = cfg.max_download_bytes or (2 * 1024 * 1024)
    char_limit = cfg.page_char_limit or 6000

    headers = {
        "User-Agent": "ResearchAgentBot/1.0 (https://example.com/research-agent; research-agent@example.com)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", url, headers=headers) as resp:
                # Check HTTP status codes
                if resp.status_code == 404:
                    raise PermanentToolError(f"HTTP 404 Not Found for {url}")
                if resp.status_code == 429:
                    raise TransientToolError(f"HTTP 429 Rate Limited for {url}")
                if 400 <= resp.status_code < 500:
                    raise PermanentToolError(f"HTTP {resp.status_code} client error for {url}")
                if resp.status_code >= 500:
                    raise TransientToolError(f"HTTP {resp.status_code} server error for {url}")

                # Validate Content-Type
                c_type = resp.headers.get("content-type", "").lower()
                allowed_types = ("text/html", "text/plain", "application/xhtml+xml")
                if not any(t in c_type for t in allowed_types):
                    raise PermanentToolError(f"Unsupported content-type: {c_type}")

                # Download bounded response bytes
                content_bytes = bytearray()
                for chunk in resp.iter_bytes(chunk_size=8192):
                    content_bytes.extend(chunk)
                    if len(content_bytes) >= max_bytes:
                        break

    except httpx.TimeoutException as exc:
        raise TransientToolError(f"Timeout fetching {url}: {exc}") from exc
    except httpx.NetworkError as exc:
        raise TransientToolError(f"Network error fetching {url}: {exc}") from exc
    except (PermanentToolError, TransientToolError):
        raise
    except Exception as exc:
        raise TransientToolError(f"Failed to fetch {url}: {exc}") from exc

    raw_html = content_bytes.decode("utf-8", errors="replace")
    extracted = trafilatura.extract(
        raw_html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )

    if not extracted or not extracted.strip():
        return ""

    cleaned = extracted.strip()
    return cleaned[:char_limit]
