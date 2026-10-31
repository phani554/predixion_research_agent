"""Wikipedia lookup tool using MediaWiki search and REST summary API."""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx

from research_agent.config import Settings
from research_agent.tools.base import PermanentToolError, TransientToolError

USER_AGENT = "ResearchAgentBot/1.0 (https://example.com/research-agent; research-agent@example.com)"


def wikipedia(
    query: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Retrieve title, canonical URL, and summary for the best-matching Wikipedia article.

    Returns a dict with title, url, summary or None if no match is found.
    """
    cfg = settings or Settings()
    timeout = cfg.tool_timeout_s or 10.0
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": "1",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            # 1. Search for top matching article title
            search_resp = client.get(search_url, params=params, headers=headers)
            if search_resp.status_code == 429:
                raise TransientToolError("Wikipedia API rate limited")
            if search_resp.status_code >= 500:
                raise TransientToolError(f"Wikipedia server error: HTTP {search_resp.status_code}")
            if search_resp.status_code >= 400:
                raise PermanentToolError(f"Wikipedia client error: HTTP {search_resp.status_code}")

            search_data = search_resp.json()
            search_results = search_data.get("query", {}).get("search", [])
            if not search_results:
                return None

            best_title = search_results[0].get("title", "")
            if not best_title:
                return None

            # 2. Fetch page summary
            encoded_title = urllib.parse.quote(best_title.replace(" ", "_"))
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_title}"

            summary_resp = client.get(summary_url, headers=headers)
            if summary_resp.status_code == 404:
                return {
                    "title": best_title,
                    "url": f"https://en.wikipedia.org/wiki/{encoded_title}",
                    "summary": "",
                }
            if summary_resp.status_code == 429:
                raise TransientToolError("Wikipedia API rate limited")
            if summary_resp.status_code >= 500:
                raise TransientToolError(f"Wikipedia server error: HTTP {summary_resp.status_code}")
            if summary_resp.status_code >= 400:
                raise PermanentToolError(f"Wikipedia client error: HTTP {summary_resp.status_code}")

            summary_data = summary_resp.json()
            canonical_url = (
                summary_data.get("content_urls", {}).get("desktop", {}).get("page")
                or f"https://en.wikipedia.org/wiki/{encoded_title}"
            )
            extract = summary_data.get("extract") or ""

            return {
                "title": summary_data.get("title", best_title),
                "url": canonical_url,
                "summary": extract,
            }

    except httpx.TimeoutException as exc:
        raise TransientToolError(f"Wikipedia request timed out: {exc}") from exc
    except httpx.NetworkError as exc:
        raise TransientToolError(f"Wikipedia network error: {exc}") from exc
    except (PermanentToolError, TransientToolError):
        raise
    except Exception as exc:
        raise TransientToolError(f"Wikipedia lookup failed: {exc}") from exc

