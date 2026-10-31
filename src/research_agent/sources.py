"""Source filtering, domain quality evaluation, and relevance scoring."""
from __future__ import annotations

import re
import urllib.parse
from typing import Any

from research_agent.config import Settings
from research_agent.schemas import RejectedSource, SearchHit, Source

BLOCKED_DOMAINS = {
    "pinterest.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "quora.com",
    "scribd.com",
    "slideshare.net",
}

LOW_QUALITY_DOMAINS = {
    "medium.com",
    "reddit.com",
    "substack.com",
    "blogspot.com",
    "wordpress.com",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "is", "are", "was", "were", "what", "how", "why", "who", "which", "when",
    "where", "it", "this", "that", "these", "those", "from", "by", "as", "be",
    "do", "does", "did", "can", "could", "should", "would", "about", "top", "best",
}


def domain_of(url: str) -> str:
    """Extract normalized lowercase hostname without leading www."""
    try:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def canonical_url(url: str) -> str:
    """Normalize a URL to prevent duplicate fetches: lowercase host, strip www/queries/fragments/trailing slash."""
    try:
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower() or "https"
        host = domain_of(url)
        path = parsed.path.rstrip("/")
        if not path:
            return f"{scheme}://{host}"
        return f"{scheme}://{host}{path}"
    except Exception:
        return url.strip().rstrip("/")


def terms(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric content terms, filtering common stopwords."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text.lower())
    return {t for t in tokens if t not in STOPWORDS}


def relevance(query: str, doc: str) -> float:
    """Calculate the share of query content terms found in the document text (0.0 to 1.0)."""
    q_terms = terms(query)
    if not q_terms:
        return 0.0
    d_terms = terms(doc)
    matched = q_terms & d_terms
    return len(matched) / len(q_terms)


def domain_quality(domain: str) -> float:
    """Score domain trustworthiness: 1.0 (authoritative), 0.6 (standard), 0.3 (forums/blogs), 0.0 (blocked)."""
    d = domain.lower()
    if d in BLOCKED_DOMAINS or any(d.endswith(f".{bd}") for bd in BLOCKED_DOMAINS):
        return 0.0

    # High quality authoritative domains / educational / government
    if any(d.endswith(tld) for tld in [".gov", ".edu", ".ac.in", ".ac.uk", ".edu.cn"]):
        return 1.0
    if any(d == dom or d.endswith(f".{dom}") for dom in ["wikipedia.org", "arxiv.org", "github.com"]):
        return 1.0
    if any(d.startswith(prefix) for prefix in ["docs.", "developer.", "engineering."]):
        return 1.0

    # Low quality user-generated forums and personal blog platforms
    if any(d == dom or d.endswith(f".{dom}") for dom in LOW_QUALITY_DOMAINS):
        return 0.3

    return 0.6


NON_HTML_EXTENSIONS = {".pdf", ".zip", ".mp4", ".tar", ".gz", ".exe", ".bin"}


def prefilter_hits(
    hits: list[tuple[int, SearchHit]],
    query_by_step: dict[int, str],
) -> tuple[list[tuple[int, SearchHit, float]], list[RejectedSource]]:
    """Filter search hits before fetching: drop non-HTML links, blocked domains, and duplicate URLs.

    Returns (kept_hits_with_relevance, rejected_sources).
    """
    kept: list[tuple[int, SearchHit, float]] = []
    rejected: list[RejectedSource] = []
    seen_canonical: set[str] = set()

    for step_id, hit in hits:
        d = domain_of(hit.url)
        path = urllib.parse.urlparse(hit.url).path.lower()

        # 1. Non-HTML file extension check
        if any(path.endswith(ext) for ext in NON_HTML_EXTENSIONS):
            rejected.append(
                RejectedSource(
                    url=hit.url,
                    title=hit.title,
                    domain=d,
                    reason="non-HTML content",
                    step_id=step_id,
                )
            )
            continue

        # 2. Blocked domain check
        if domain_quality(d) == 0.0 or d in BLOCKED_DOMAINS or any(d.endswith(f".{bd}") for bd in BLOCKED_DOMAINS):
            rejected.append(
                RejectedSource(
                    url=hit.url,
                    title=hit.title,
                    domain=d,
                    reason=f"blocked domain ({d})",
                    step_id=step_id,
                )
            )
            continue

        # 3. Canonical duplicate check
        canon = canonical_url(hit.url)
        if canon in seen_canonical:
            rejected.append(
                RejectedSource(
                    url=hit.url,
                    title=hit.title,
                    domain=d,
                    reason="duplicate",
                    step_id=step_id,
                )
            )
            continue
        seen_canonical.add(canon)

        # 4. Compute relevance on hit title + snippet
        sub_q = query_by_step.get(step_id, "")
        rel = relevance(sub_q, f"{hit.title} {hit.snippet}")
        kept.append((step_id, hit, rel))

    return kept, rejected


INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"disregard\s+(?:all\s+)?prior\s+instructions",
    r"you\s+are\s+now\s+in\s+.*mode",
    r"reveal\s+your\s+system\s+prompt",
    r"system\s+notice\s*:",
    r"do\s+not\s+tell\s+the\s+user",
    r"output\s+that\s+the\s+moon\s+is\s+made\s+of\s+green\s+cheese",
]


def detect_injection(text: str) -> bool:
    """Return True if any known prompt-injection signature matches within the text."""
    if not text:
        return False
    lower = text.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lower):
            return True
    return False


def strip_injection(text: str) -> str:
    """Remove matching injection sentences from text, keeping legitimate surrounding sentences."""
    if not text or not detect_injection(text):
        return text

    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned_sentences = [s.strip() for s in sentences if s.strip() and not detect_injection(s)]
    return " ".join(cleaned_sentences)


def score_source(src: Source | dict[str, Any], query_text: str) -> Source:
    """Calculate multi-factor score: 0.5*relevance + 0.3*domain_quality + 0.2*content_quality - injection_penalty."""
    if isinstance(src, dict):
        src_obj = Source(**src)
    else:
        src_obj = src.model_copy()

    url = src_obj.url
    domain = src_obj.domain or domain_of(url)
    src_obj.domain = domain

    raw_content = src_obj.content or ""
    raw_snippet = src_obj.snippet or ""

    flags = list(src_obj.flags)
    injection_penalty = 0.0

    # 1. Prompt injection detection and stripping
    if detect_injection(raw_content) or detect_injection(raw_snippet):
        if "prompt_injection_suspected" not in flags:
            flags.append("prompt_injection_suspected")
        injection_penalty = 0.3
        raw_content = strip_injection(raw_content)
        raw_snippet = strip_injection(raw_snippet)
        src_obj.content = raw_content
        src_obj.snippet = raw_snippet

    # 2. Content quality & flags
    if not raw_content.strip():
        if "snippet_only" not in flags:
            flags.append("snippet_only")
        cq = 0.3
        eval_text = raw_snippet
    elif len(raw_content.strip()) < 300:
        if "thin_content" not in flags:
            flags.append("thin_content")
        cq = 0.3
        eval_text = raw_content
    else:
        content_len = len(raw_content.strip())
        cq = min(1.0, 0.3 + 0.7 * (content_len / 1500.0))
        eval_text = raw_content

    # 3. Relevance & Domain quality
    rel = relevance(query_text, eval_text)
    dq = domain_quality(domain)

    # 4. Total score
    raw_score = 0.5 * rel + 0.3 * dq + 0.2 * cq - injection_penalty
    final_score = max(0.0, min(1.0, raw_score))

    src_obj.relevance = round(rel, 4)
    src_obj.domain_quality = round(dq, 4)
    src_obj.content_quality = round(cq, 4)
    src_obj.score = round(final_score, 4)
    src_obj.flags = flags

    return src_obj


def select_sources(
    candidates: list[Source] | list[dict[str, Any]],
    settings: Settings | None = None,
) -> tuple[list[Source], list[RejectedSource]]:
    """Select a small, diverse evidence set from candidate sources.
    
    Rejects candidates with relevance < 0.1 ('irrelevant') or score < min_source_score ('low score').
    Enforces max_sources_per_domain ('domain cap') and max_sources_for_synthesis ('over source budget').
    Assigns IDs S1..Sn to accepted sources in descending score order.
    """
    if settings is None:
        settings = Settings()

    source_objs: list[Source] = []
    for c in candidates:
        if isinstance(c, dict):
            source_objs.append(Source(**c))
        else:
            source_objs.append(c.model_copy())

    for s in source_objs:
        if not s.domain:
            s.domain = domain_of(s.url)

    # Sort descending by score (stable sort preserving order for ties)
    sorted_candidates = sorted(source_objs, key=lambda s: s.score, reverse=True)

    chosen: list[Source] = []
    rejected: list[RejectedSource] = []
    domain_counts: dict[str, int] = {}

    for src in sorted_candidates:
        if src.relevance < 0.1:
            rejected.append(
                RejectedSource(
                    url=src.url,
                    title=src.title,
                    domain=src.domain,
                    reason="irrelevant",
                    score=src.score,
                    relevance=src.relevance,
                    step_id=src.step_id,
                )
            )
        elif src.score < settings.min_source_score:
            rejected.append(
                RejectedSource(
                    url=src.url,
                    title=src.title,
                    domain=src.domain,
                    reason="low score",
                    score=src.score,
                    relevance=src.relevance,
                    step_id=src.step_id,
                )
            )
        elif domain_counts.get(src.domain, 0) >= settings.max_sources_per_domain:
            rejected.append(
                RejectedSource(
                    url=src.url,
                    title=src.title,
                    domain=src.domain,
                    reason="domain cap",
                    score=src.score,
                    relevance=src.relevance,
                    step_id=src.step_id,
                )
            )
        elif len(chosen) >= settings.max_sources_for_synthesis:
            rejected.append(
                RejectedSource(
                    url=src.url,
                    title=src.title,
                    domain=src.domain,
                    reason="over source budget",
                    score=src.score,
                    relevance=src.relevance,
                    step_id=src.step_id,
                )
            )
        else:
            src.id = f"S{len(chosen) + 1}"
            domain_counts[src.domain] = domain_counts.get(src.domain, 0) + 1
            chosen.append(src)

    return chosen, rejected


