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

