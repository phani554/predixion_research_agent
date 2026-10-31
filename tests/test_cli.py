from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from research_agent.cli import main
from research_agent.schemas import FinalAnswer


def test_cli_invalid_input_json(capsys, tmp_path) -> None:
    # Running CLI with blank question and --json must print JSON and exit 2
    out_dir = tmp_path / "outputs"
    with patch("sys.argv", ["research_agent", "   ", "--json", "--out", str(out_dir / "run.json")]):
        exit_code = main()
        assert exit_code == 2

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    validated = FinalAnswer.model_validate(data)
    assert validated.status == "invalid_input"


def test_cli_saves_run_json(capsys, tmp_path) -> None:
    from research_agent.schemas import Confidence, FinalAnswer, RunResult

    out_file = tmp_path / "custom_run.json"
    mock_res = RunResult(
        run_id="run_123",
        answer=FinalAnswer(
            question="What is quantum computing?",
            status="answered",
            short_answer="Quantum computing uses qubits.",
            confidence=Confidence.high,
            confidence_score=0.9,
        ),
    )
    with patch("research_agent.cli.run_research", return_value=mock_res), \
         patch("sys.argv", ["research_agent", "What is quantum computing?", "--out", str(out_file)]):
        exit_code = main()
        assert exit_code == 0

    assert out_file.exists()
    saved_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "answer" in saved_data
    assert "run_id" in saved_data
    assert saved_data["run_id"] == "run_123"


def test_cli_repeatable_fault_flags(tmp_path) -> None:
    from research_agent.schemas import FinalAnswer, RunResult

    out_file = tmp_path / "out.json"
    mock_res = RunResult(
        run_id="run_fault",
        answer=FinalAnswer(
            question="Compare X and Y",
            status="answered",
            short_answer="Done",
        ),
    )

    captured_settings = None

    def fake_run(question, settings=None, **kwargs):
        nonlocal captured_settings
        captured_settings = settings
        return mock_res

    with patch("research_agent.cli.run_research", side_effect=fake_run), \
         patch("sys.argv", [
             "research_agent",
             "Compare X and Y",
             "--fault", "web_search:timeout",
             "--fault", "fetch_page:error",
             "--out", str(out_file),
         ]):
        exit_code = main()
        assert exit_code == 0

    assert captured_settings is not None
    assert "web_search:timeout" in captured_settings.faults
    assert "fetch_page:error" in captured_settings.faults


def test_cli_verbose_output_and_saved_run_json(capsys, tmp_path) -> None:
    from research_agent.schemas import Confidence, FinalAnswer, Finding, RunMetrics, RunResult, SourceRef

    out_file = tmp_path / "verbose_run.json"
    mock_res = RunResult(
        run_id="run_verb",
        answer=FinalAnswer(
            question="Compare LangGraph and CrewAI",
            status="answered",
            short_answer="Both are multi-agent orchestration frameworks.",
            key_findings=[Finding(statement="LangGraph uses graphs.", source_ids=["s1"])],
            sources=[SourceRef(id="s1", title="LangGraph", url="https://example.com/lg")],
            confidence=Confidence.high,
            confidence_score=0.9,
        ),
        plan=[
            {"id": 1, "tool": "web_search", "sub_question": "LangGraph overview", "query": "langgraph overview"},
            {"id": 2, "tool": "wikipedia", "sub_question": "CrewAI overview", "query": "crewai overview"},
        ],
        sources=[SourceRef(id="s1", title="LangGraph", url="https://example.com/lg")],
        rejected=[{"url": "https://pinterest.com/pin/1", "reason": "blocked domain (pinterest.com)"}],
        metrics=RunMetrics(
            total_time_s=3.45,
            latency_ms=3450.0,
            llm_calls=2,
            tool_calls=4,
            tool_failures=1,
            prompt_tokens=1200,
            completion_tokens=350,
            est_cost_usd=0.0012,
            sources_considered=6,
            sources_used=1,
        ),
    )

    with patch("research_agent.cli.run_research", return_value=mock_res), \
         patch("sys.argv", ["research_agent", "Compare LangGraph and CrewAI", "-v", "--out", str(out_file)]):
        exit_code = main()
        assert exit_code == 0

    captured = capsys.readouterr()
    assert "## Research Plan" in captured.out
    assert "1. **[web_search]** LangGraph overview (query: `langgraph overview`)" in captured.out
    assert "2. **[wikipedia]** CrewAI overview (query: `crewai overview`)" in captured.out
    assert "## Run Metrics" in captured.out
    assert "**Metrics:**" in captured.out
    assert "1 tool calls (1 failed)" in captured.out or "4 tool calls (1 failed)" in captured.out

    # Check saved JSON
    saved_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert "plan" in saved_data
    assert len(saved_data["plan"]) == 2
    assert "sources" in saved_data
    assert "rejected" in saved_data
    assert saved_data["rejected"][0]["reason"] == "blocked domain (pinterest.com)"
    assert "metrics" in saved_data
    assert saved_data["metrics"]["tool_failures"] == 1

