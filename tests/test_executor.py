"""Tests for research execution, budgeting, and round-robin orchestration."""
from __future__ import annotations

import pytest

from research_agent.config import Settings
from research_agent.schemas import PlanStep, ResearchPlan, SearchHit


def test_happy_path_collects_ranked_sources() -> None:
    from research_agent.executor import Evidence, Executor

    plan = ResearchPlan(
        in_scope=True,
        intent="comparison",
        restated_question="What is a vector database and how does Milvus work?",
        steps=[
            PlanStep(
                id=1,
                sub_question="How does Milvus work as a vector database?",
                tool="web_search",
                query="milvus vector database architecture",
            ),
            PlanStep(
                id=2,
                sub_question="What is a vector database?",
                tool="wikipedia",
                query="vector database",
            ),
        ],
    )

    fake_tools = {
        "web_search": lambda query, **kw: [
            SearchHit(
                title="Milvus Architecture Overview",
                url="https://milvus.io/docs/overview",
                snippet="Milvus is an open-source vector database designed for AI similarity search and high scalability.",
            )
        ],
        "fetch_page": lambda url, **kw: (
            "Milvus is an open-source vector database designed specifically for AI similarity search. "
            "It decouples storage and computation, allowing it to scale elastically and handle billions of vectors."
        ),
        "wikipedia": lambda query, **kw: {
            "title": "Vector database",
            "url": "https://en.wikipedia.org/wiki/Vector_database",
            "summary": (
                "A vector database is a database designed to index and query vector embeddings. "
                "Unlike traditional relational databases, vector databases optimize for approximate nearest neighbor search."
            ),
        },
    }

    settings = Settings(
        max_tool_calls=10,
        parallelism=2,
        max_pages_to_fetch=4,
    )
    executor = Executor(settings=settings, tools=fake_tools)
    evidence = executor.run(plan)

    assert isinstance(evidence, Evidence)
    assert len(evidence.sources) == 2
    assert [s.id for s in evidence.sources] == ["S1", "S2"]
    assert evidence.sources[0].score >= evidence.sources[1].score
    domains = {s.domain for s in evidence.sources}
    assert "milvus.io" in domains
    assert any("wikipedia.org" in d for d in domains)
    assert evidence.uncovered_steps == []
    assert evidence.budget_exhausted is False
    assert evidence.candidates_considered >= 2
    assert evidence.tool_errors == []


def test_failed_fetch_degrades_to_snippet() -> None:
    from research_agent.executor import Executor
    from research_agent.tools.base import PermanentToolError

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is Milvus?",
        steps=[
            PlanStep(
                id=1,
                sub_question="What is Milvus?",
                tool="web_search",
                query="milvus vector database",
            ),
        ],
    )

    def failing_fetch(url: str, **kw):
        raise PermanentToolError("HTTP 403 Forbidden")

    fake_tools = {
        "web_search": lambda query, **kw: [
            SearchHit(
                title="Milvus Official",
                url="https://milvus.io/page",
                snippet="Milvus is an open-source vector database built for GenAI similarity search.",
            )
        ],
        "fetch_page": failing_fetch,
    }

    settings = Settings(
        max_tool_calls=10,
        max_pages_to_fetch=1,
        min_source_score=0.1,  # allow snippet source through
    )
    executor = Executor(settings=settings, tools=fake_tools)
    evidence = executor.run(plan)

    # Error recorded in tool_errors
    assert any("403" in err or "fetch_page failed" in err for err in evidence.tool_errors)

    # Degrades to snippet-only candidate flagged fetch_error
    assert len(evidence.sources) == 1
    src = evidence.sources[0]
    assert src.content == ""
    assert "Milvus is an open-source vector database" in src.snippet
    assert "fetch_error" in src.flags
    assert "snippet_only" in src.flags


def test_round_robin_page_budget_distribution() -> None:
    from research_agent.executor import Executor

    plan = ResearchPlan(
        in_scope=True,
        intent="comparison",
        restated_question="Compare vector databases",
        steps=[
            PlanStep(
                id=1,
                sub_question="Milvus features",
                tool="web_search",
                query="milvus features",
            ),
            PlanStep(
                id=2,
                sub_question="Qdrant features",
                tool="web_search",
                query="qdrant features",
            ),
        ],
    )

    step1_hits = [
        SearchHit(title=f"Milvus doc {i}", url=f"https://milvus{i}.io/doc", snippet="Milvus features details")
        for i in range(1, 7)
    ]
    step2_hits = [
        SearchHit(title=f"Qdrant doc {i}", url=f"https://qdrant{i}.io/doc", snippet="Qdrant features details")
        for i in range(1, 3)
    ]

    fetched_urls: list[str] = []

    def mock_fetch(url: str, **kw) -> str:
        fetched_urls.append(url)
        return "Features and architecture documentation."

    fake_tools = {
        "web_search": lambda query, **kw: step1_hits if "milvus" in query else step2_hits,
        "fetch_page": mock_fetch,
    }

    settings = Settings(
        max_tool_calls=10,
        max_pages_to_fetch=4,
    )
    executor = Executor(settings=settings, tools=fake_tools)
    executor.run(plan)

    # Should fetch alternatingly up to 4 pages: 2 from step 1, 2 from step 2
    assert len(fetched_urls) == 4
    assert fetched_urls == [
        "https://milvus1.io/doc",
        "https://qdrant1.io/doc",
        "https://milvus2.io/doc",
        "https://qdrant2.io/doc",
    ]


def test_budget_is_enforced() -> None:
    from research_agent.executor import Executor

    plan = ResearchPlan(
        in_scope=True,
        intent="comparison",
        restated_question="Compare Milvus and Qdrant",
        steps=[
            PlanStep(
                id=1,
                sub_question="Milvus overview",
                tool="web_search",
                query="milvus vector database",
            ),
            PlanStep(
                id=2,
                sub_question="Qdrant overview",
                tool="wikipedia",
                query="qdrant vector search",
            ),
        ],
    )

    call_count = 0

    def counted_search(query: str, **kw):
        nonlocal call_count
        call_count += 1
        return [
            SearchHit(
                title="Milvus Official",
                url="https://milvus.io/overview",
                snippet="Milvus is an open-source vector database for similarity search.",
            )
        ]

    def counted_wiki(query: str, **kw):
        nonlocal call_count
        call_count += 1
        return {
            "title": "Qdrant",
            "url": "https://en.wikipedia.org/wiki/Qdrant",
            "summary": "Qdrant is a vector similarity search engine.",
        }

    def counted_fetch(url: str, **kw):
        nonlocal call_count
        call_count += 1
        return "Milvus detailed documentation and architecture."

    fake_tools = {
        "web_search": counted_search,
        "wikipedia": counted_wiki,
        "fetch_page": counted_fetch,
    }

    # 1. Budget of 1 call: only 1 tool call runs
    settings = Settings(
        max_tool_calls=1,
        parallelism=1,
        max_pages_to_fetch=2,
    )
    executor = Executor(settings=settings, tools=fake_tools)
    evidence = executor.run(plan)

    assert call_count == 1
    assert evidence.budget_exhausted is True
    assert any("budget exhausted" in err.lower() for err in evidence.tool_errors)

    # 2. Deadline exceeded
    deadline_settings = Settings(
        max_tool_calls=10,
        run_deadline_s=0.0,  # immediate deadline expiration
    )
    deadline_executor = Executor(settings=deadline_settings, tools=fake_tools)
    deadline_evidence = deadline_executor.run(plan)

    assert deadline_evidence.budget_exhausted is True
    assert any("budget exhausted" in err.lower() for err in deadline_evidence.tool_errors)


def test_follow_up_round_switches_tool_for_uncovered_step() -> None:
    from research_agent.executor import Executor

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is an obscure vector index?",
        steps=[
            PlanStep(
                id=1,
                sub_question="What is an obscure vector index?",
                tool="wikipedia",
                query="obscure vector index",
            ),
        ],
    )

    web_search_queries: list[str] = []

    def mock_wiki(query: str, **kw):
        # Wikipedia finds nothing
        return None

    def mock_web_search(query: str, **kw):
        web_search_queries.append(query)
        return [
            SearchHit(
                title="Obscure Index Guide",
                url="https://example.com/obscure-index",
                snippet="Comprehensive guide to an obscure vector index architecture.",
            )
        ]

    def mock_fetch(url: str, **kw):
        return "Detailed guide on the obscure vector index algorithm and implementation."

    fake_tools = {
        "wikipedia": mock_wiki,
        "web_search": mock_web_search,
        "fetch_page": mock_fetch,
    }

    settings = Settings(
        max_tool_calls=10,
        max_pages_to_fetch=2,
        max_follow_up_rounds=1,
    )
    executor = Executor(settings=settings, tools=fake_tools)
    evidence = executor.run(plan)

    # Wikipedia failed -> follow-up round switched to web_search on sub_question
    assert evidence.follow_up_rounds == 1
    assert web_search_queries == ["What is an obscure vector index?"]
    assert evidence.uncovered_steps == []
    assert len(evidence.sources) == 1
    assert evidence.sources[0].url == "https://example.com/obscure-index"


def test_follow_up_switches_web_search_to_wikipedia_when_query_identical() -> None:
    from research_agent.executor import Executor

    plan = ResearchPlan(
        in_scope=True,
        intent="explainer",
        restated_question="What is vector quantization?",
        steps=[
            PlanStep(
                id=1,
                sub_question="vector quantization",
                tool="web_search",
                query="vector quantization",  # identical to sub_question
            ),
        ],
    )

    wiki_queries: list[str] = []

    def empty_web_search(query: str, **kw):
        return []

    def mock_wiki(query: str, **kw):
        wiki_queries.append(query)
        return {
            "title": "Vector quantization",
            "url": "https://en.wikipedia.org/wiki/Vector_quantization",
            "summary": "Vector quantization is a classical quantization technique from signal processing.",
        }

    fake_tools = {
        "web_search": empty_web_search,
        "wikipedia": mock_wiki,
        "fetch_page": lambda url, **kw: "",
    }

    settings = Settings(max_tool_calls=10, max_follow_up_rounds=1)
    executor = Executor(settings=settings, tools=fake_tools)
    evidence = executor.run(plan)

    assert evidence.follow_up_rounds == 1
    assert wiki_queries == ["vector quantization"]
    assert evidence.uncovered_steps == []
    assert len(evidence.sources) == 1




