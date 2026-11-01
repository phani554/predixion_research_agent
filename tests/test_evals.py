"""Tests for the evaluation dataset and evaluation runner."""
from __future__ import annotations

from pathlib import Path
import yaml


def test_eval_queries_yaml_loads_and_categories_cover_all_types() -> None:
    yaml_path = Path("evals/queries.yaml")
    assert yaml_path.is_file(), "evals/queries.yaml must exist"

    content = yaml_path.read_text(encoding="utf-8")
    cases = yaml.safe_load(content)

    assert isinstance(cases, list), "queries.yaml root must be a list of cases"
    assert len(cases) >= 10, f"Expected at least 10 cases, got {len(cases)}"

    case_ids = set()
    categories = set()

    for case in cases:
        assert isinstance(case, dict), "Each case must be a dictionary"
        assert "id" in case, "Case missing 'id'"
        assert "category" in case, f"Case {case['id']} missing 'category'"
        assert "question" in case, f"Case {case['id']} missing 'question'"
        assert "expect" in case, f"Case {case['id']} missing 'expect'"

        assert case["id"] not in case_ids, f"Duplicate case id: {case['id']}"
        case_ids.add(case["id"])
        categories.add(case["category"])

    expected_categories = {"happy_path", "edge", "safety", "failure"}
    missing_categories = expected_categories - categories
    assert not missing_categories, f"Missing required categories: {missing_categories}"

    # Verify specific required scenarios
    assert "empty" in case_ids or any(c["category"] == "safety" and not c["question"].strip() for c in cases)
    assert "arithmetic" in case_ids or any("42" in c["question"] for c in cases)
    assert any(c.get("faults") for c in cases), "Expected at least one case with injected faults"


def test_check_passes_valid_result() -> None:
    from evals.run_evals import check
    from research_agent.schemas import Confidence, FinalAnswer, Finding, RunMetrics, RunResult, SourceRef

    case = {
        "id": "test-1",
        "category": "happy_path",
        "question": "What is Python?",
        "expect": {
            "status_in": ["answered"],
            "min_sources": 1,
            "min_findings": 1,
            "confidence_not": ["low"],
        },
    }

    ans = FinalAnswer(
        question="What is Python?",
        status="answered",
        short_answer="Python is a programming language.",
        key_findings=[Finding(statement="Python is versatile.", source_ids=["S1"])],
        sources=[SourceRef(id="S1", title="Python org", url="https://python.org")],
        confidence=Confidence.high,
        confidence_score=0.9,
    )
    result = RunResult(run_id="run_1", answer=ans, metrics=RunMetrics())

    failures = check(case, result)
    assert failures == []


def test_check_fails_on_invariants() -> None:
    from evals.run_evals import check
    from research_agent.schemas import Confidence, FinalAnswer, Finding, RunMetrics, RunResult, SourceRef

    case = {
        "id": "test-inv",
        "category": "happy_path",
        "question": "Q",
        "expect": {"status_in": ["answered"]},
    }

    # 1. Finding without citation
    ans1 = FinalAnswer.model_construct(
        question="Q",
        status="answered",
        short_answer="Ans",
        key_findings=[Finding.model_construct(statement="No cite statement", source_ids=[])],
        sources=[SourceRef(id="S1", title="Title", url="https://example.com")],
        confidence=Confidence.medium,
        confidence_score=0.5,
    )
    res1 = RunResult(run_id="run_inv1", answer=ans1, metrics=RunMetrics())
    f1 = check(case, res1)
    assert any("without citations" in err for err in f1)

    # 2. Cited ID not in sources
    ans2 = FinalAnswer(
        question="Q",
        status="answered",
        short_answer="Ans",
        key_findings=[Finding(statement="Ghost cite statement", source_ids=["S99"])],
        sources=[SourceRef(id="S1", title="Title", url="https://example.com")],
        confidence=Confidence.medium,
        confidence_score=0.5,
    )
    res2 = RunResult(run_id="run_inv2", answer=ans2, metrics=RunMetrics())
    f2 = check(case, res2)
    assert any("not found in sources" in err for err in f2)


def test_check_handles_crash() -> None:
    from evals.run_evals import check

    case = {"id": "crashed", "category": "edge", "question": "Q", "expect": {}}
    err = RuntimeError("Something blew up")
    failures = check(case, err)
    assert len(failures) == 1
    assert "crashed: RuntimeError: Something blew up" in failures[0]


def test_report_generates_markdown_table() -> None:
    from evals.run_evals import report

    rows = [
        {
            "id": "case-1",
            "category": "happy_path",
            "passed": True,
            "status": "answered",
            "confidence": "high (0.90)",
            "findings": "2 (0)",
            "sources": 2,
            "latency": "1.50s",
            "tool_failures": 0,
            "notes": "",
        },
        {
            "id": "case-2",
            "category": "failure",
            "passed": False,
            "status": "error",
            "confidence": "low (0.00)",
            "findings": "0 (0)",
            "sources": 0,
            "latency": "0.50s",
            "tool_failures": 1,
            "notes": "tool failed",
        },
    ]

    md = report(rows)
    assert "| ID | Category | Pass | Status | Confidence | Findings (Weak) | Sources | Latency | Tool Failures | Notes |" in md
    assert "| case-1 | happy_path | PASS | answered | high (0.90) | 2 (0) | 2 | 1.50s | 0 |" in md
    assert "| case-2 | failure | FAIL | error | low (0.00) | 0 (0) | 0 | 0.50s | 1 | tool failed |" in md


def test_evaluation_summary_exists_and_contains_results() -> None:
    eval_doc = Path("docs/EVALUATION.md")
    assert eval_doc.is_file(), "docs/EVALUATION.md must exist"

    content = eval_doc.read_text(encoding="utf-8")
    assert "Evaluation" in content
    assert "| ID |" in content or "| Category |" in content
    assert "happy_path" in content or "vector-dbs" in content

    # Check results folder has files
    results_dir = Path("evals/results")
    assert results_dir.is_dir()
    json_results = list(results_dir.glob("*.json"))
    md_results = list(results_dir.glob("*.md"))
    assert len(json_results) >= 1, "Expected at least one saved JSON result in evals/results/"
    assert len(md_results) >= 1, "Expected at least one saved Markdown report in evals/results/"


