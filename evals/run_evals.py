"""Evaluation runner: executes evaluation cases against the agent, validates invariants and behavioral expectations, and writes JSON/Markdown reports."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
import yaml

from research_agent.agent import run_research
from research_agent.config import Settings
from research_agent.schemas import RunResult


def check(case: dict[str, Any], result: RunResult | Exception) -> list[str]:
    """Evaluate behavioral expectations and universal invariants for an eval case.

    Returns a list of failure reason strings, or an empty list if all checks pass.
    """
    if isinstance(result, Exception):
        return [f"crashed: {type(result).__name__}: {result}"]

    failures: list[str] = []
    ans = result.answer
    expect: dict[str, Any] = case.get("expect", {})

    # Universal Invariant 1: Every finding must have at least one citation
    for f in ans.key_findings:
        if not f.source_ids:
            failures.append(f"finding without citations: '{f.statement[:50]}'")

    # Universal Invariant 2: Every cited ID must exist in sources list
    known_source_ids = {s.id for s in ans.sources}
    for f in ans.key_findings:
        for sid in f.source_ids:
            if sid not in known_source_ids:
                failures.append(f"citation [{sid}] not found in sources")

    # Expectation: status_in
    if "status_in" in expect:
        if ans.status not in expect["status_in"]:
            failures.append(f"status '{ans.status}' not in {expect['status_in']}")

    # Expectation: min_sources
    if "min_sources" in expect:
        if len(ans.sources) < expect["min_sources"]:
            failures.append(f"sources {len(ans.sources)} < {expect['min_sources']}")

    # Expectation: min_findings
    if "min_findings" in expect:
        if len(ans.key_findings) < expect["min_findings"]:
            failures.append(f"findings {len(ans.key_findings)} < {expect['min_findings']}")

    # Expectation: confidence_not
    if "confidence_not" in expect:
        conf_val = getattr(ans.confidence, "value", str(ans.confidence))
        if conf_val in expect["confidence_not"]:
            failures.append(f"confidence '{conf_val}' in forbidden {expect['confidence_not']}")

    # Expectation: mention_any
    if "mention_any" in expect:
        full_text = f"{ans.short_answer} " + " ".join(f.statement for f in ans.key_findings)
        if not any(token.lower() in full_text.lower() for token in expect["mention_any"]):
            failures.append(f"none of {expect['mention_any']} mentioned in answer")

    # Expectation: limitation_any
    if "limitation_any" in expect:
        lims_text = " ".join(ans.limitations) + " " + ans.short_answer
        if not any(token.lower() in lims_text.lower() for token in expect["limitation_any"]):
            failures.append(f"none of {expect['limitation_any']} found in limitations/short_answer")

    # Expectation: not_contains
    if "not_contains" in expect:
        content_text = (
            f"{ans.short_answer} "
            + " ".join(f.statement for f in ans.key_findings)
            + " "
            + " ".join(ans.limitations)
            + " "
            + " ".join(ans.next_steps)
        )
        for forbidden in expect["not_contains"]:
            if forbidden.lower() in content_text.lower():
                failures.append(f"forbidden text '{forbidden}' found in content")

    return failures


def report(rows: list[dict[str, Any]]) -> str:
    """Generate a clean Markdown table summarizing evaluation results."""
    headers = [
        "ID",
        "Category",
        "Pass",
        "Status",
        "Confidence",
        "Findings (Weak)",
        "Sources",
        "Latency",
        "Tool Failures",
        "Notes",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    for r in rows:
        pass_str = "PASS" if r.get("passed") else "FAIL"
        line = (
            f"| {r.get('id', '')} "
            f"| {r.get('category', '')} "
            f"| {pass_str} "
            f"| {r.get('status', '-')} "
            f"| {r.get('confidence', '-')} "
            f"| {r.get('findings', '-')} "
            f"| {r.get('sources', '-')} "
            f"| {r.get('latency', '-')} "
            f"| {r.get('tool_failures', '-')} "
            f"| {r.get('notes', '')} |"
        )
        lines.append(line)

    return "\n".join(lines)


def run_evals(
    cases_path: str | Path = "evals/queries.yaml",
    results_dir: str | Path = "evals/results",
    selected_ids: list[str] | None = None,
    include_baseline: bool = False,
    settings: Settings | None = None,
) -> int:
    """Load cases, run evaluation loop, print status lines, and persist reports."""
    path = Path(cases_path)
    if not path.is_file():
        print(f"Error: Cases file not found at {path}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)

    if not isinstance(cases, list):
        print(f"Error: Invalid YAML format in {path}, expected list", file=sys.stderr)
        return 1

    if selected_ids:
        cases = [c for c in cases if c.get("id") in selected_ids]

    base_cfg = settings or Settings.from_env()
    results_out: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    print(f"\nRunning {len(cases)} evaluation case(s)...\n")

    for case in cases:
        cid = case.get("id", "unknown")
        category = case.get("category", "unknown")
        q = case.get("question", "")

        # Clone settings and set case faults
        cfg = base_cfg.model_copy(deep=True)
        cfg.faults = list(case.get("faults", []))

        # Run agent with crash protection
        result: RunResult | Exception
        try:
            result = run_research(q, settings=cfg)
        except Exception as exc:
            result = exc

        failures = check(case, result)
        passed = len(failures) == 0

        # Build table row
        if isinstance(result, RunResult):
            ans = result.answer
            conf_val = getattr(ans.confidence, "value", str(ans.confidence))
            conf_str = f"{conf_val} ({ans.confidence_score:.2f})"
            weak_count = sum(1 for f in ans.key_findings if f.support == "weak")
            findings_str = f"{len(ans.key_findings)} ({weak_count})"
            sources_count = len(ans.sources)
            latency_str = f"{result.metrics.total_time_s:.2f}s"
            tool_failures = result.metrics.tool_failures
            status_str = ans.status
            result_dump = result.model_dump()
        else:
            conf_str = "-"
            findings_str = "-"
            sources_count = 0
            latency_str = "-"
            tool_failures = 0
            status_str = "crash"
            result_dump = {"error": str(result)}

        row = {
            "id": cid,
            "category": category,
            "passed": passed,
            "status": status_str,
            "confidence": conf_str,
            "findings": findings_str,
            "sources": sources_count,
            "latency": latency_str,
            "tool_failures": tool_failures,
            "notes": "; ".join(failures) if failures else "",
        }
        summary_rows.append(row)

        record = {
            "case": case,
            "passed": passed,
            "failures": failures,
            "result": result_dump,
        }
        results_out.append(record)

        # Print terminal line
        tag = "PASS" if passed else "FAIL"
        note_text = f" ({'; '.join(failures)})" if failures else ""
        print(f"[{tag}] {cid} [{category}]{note_text}")

    # Generate timestamped outputs
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_file = out_dir / f"{timestamp}.json"
    md_file = out_dir / f"{timestamp}.md"

    json_file.write_text(json.dumps(results_out, indent=2, default=str), encoding="utf-8")
    md_report = report(summary_rows)
    md_file.write_text(md_report, encoding="utf-8")

    total = len(cases)
    passed_count = sum(1 for r in summary_rows if r["passed"])
    failed_count = total - passed_count

    print(f"\n{passed_count}/{total} passed ({failed_count} failed).")
    print(f"Saved evaluation reports to:\n  {json_file}\n  {md_file}\n")

    return 0 if failed_count == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run behavioural evaluation suite for the research agent.")
    parser.add_argument("--ids", nargs="*", default=None, help="Specific case IDs to run")
    parser.add_argument("--cases", default="evals/queries.yaml", help="Path to evaluation queries YAML file")
    parser.add_argument("--results-dir", default="evals/results", help="Directory for JSON and Markdown reports")
    parser.add_argument("--baseline", action="store_true", help="Also evaluate against non-agentic baseline")

    args = parser.parse_args(argv)
    return run_evals(
        cases_path=args.cases,
        results_dir=args.results_dir,
        selected_ids=args.ids,
        include_baseline=args.baseline,
    )


if __name__ == "__main__":
    sys.exit(main())

