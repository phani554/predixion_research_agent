"""Web search tool using DDGS metasearch with multiple backend fallback."""
from __future__ import annotations

import logging
from typing import Any

from ddgs.ddgs import DDGS
from research_agent.config import Settings
from research_agent.schemas import SearchHit

logger = logging.getLogger(__name__)

BACKENDS = ["auto", "google", "yahoo", "duckduckgo", "brave", "bing"]


def web_search(
    query: str,
    *,
    settings: Settings | None = None,
    max_results: int | None = None,
) -> list[SearchHit]:
    """Search the web for the given query using ddgs with multiple search engine backends."""
    cfg = settings or Settings()
    limit = max_results or cfg.search_results_per_query or 5

    ddgs_client = DDGS()
    raw_results: list[dict[str, Any]] = []

    for backend in BACKENDS:
        try:
            res = ddgs_client.text(query, backend=backend, max_results=limit)
            if res:
                raw_results = res
                break
        except Exception as exc:
            logger.debug("ddgs search backend '%s' failed for query '%s': %s", backend, query, exc)
            continue

    if not raw_results:
        return []

    hits: list[SearchHit] = []
    for rank, item in enumerate(raw_results[:limit], start=1):
        title = item.get("title") or ""
        url = item.get("href") or item.get("url") or ""
        snippet = item.get("body") or item.get("snippet") or ""
        if title or url:
            hits.append(SearchHit(title=title, url=url, snippet=snippet, rank=rank))

    return hits
