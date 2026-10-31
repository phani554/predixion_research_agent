"""Research execution orchestrator, budgeting, and round execution."""
from __future__ import annotations

import collections
import concurrent.futures
import threading
import time
from typing import Any, Callable

from research_agent.config import Settings
from research_agent.schemas import Evidence, PlanStep, RejectedSource, ResearchPlan, SearchHit, Source
from research_agent.sources import canonical_url, domain_of, prefilter_hits, score_source, select_sources
from research_agent.tools.base import run_tool
from research_agent.tools.fetch_page import fetch_page
from research_agent.tools.web_search import web_search
from research_agent.tools.wikipedia import wikipedia

DEFAULT_TOOLS = {
    "web_search": web_search,
    "wikipedia": wikipedia,
    "fetch_page": fetch_page,
}


class Budget:
    """Thread-safe tool call and time deadline tracker."""

    def __init__(self, max_calls: int, deadline_s: float | None = None) -> None:
        self.max_calls = max_calls
        self.deadline = (time.monotonic() + deadline_s) if deadline_s is not None else None
        self.calls_made = 0
        self.exhausted = False
        self._lock = threading.Lock()

    def take(self) -> bool:
        """Attempt to consume one tool call budget unit. Returns True if granted."""
        with self._lock:
            if self.deadline and time.monotonic() >= self.deadline:
                self.exhausted = True
                return False
            if self.calls_made >= self.max_calls:
                self.exhausted = True
                return False
            self.calls_made += 1
            return True


class Executor:
    """Executes a research plan's tool calls under budgets, ranks and selects evidence."""

    def __init__(
        self,
        settings: Settings | None = None,
        tracer: Any = None,
        cache: Any = None,
        tools: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.tracer = tracer
        self.cache = cache
        self.tools = dict(DEFAULT_TOOLS)
        if tools:
            self.tools.update(tools)

    def _select_fetch_targets(
        self,
        kept_hits_by_step: dict[int, list[tuple[SearchHit, float]]],
        step_order: list[int],
        max_pages: int,
    ) -> list[tuple[int, SearchHit]]:
        """Select fetch targets round-robin across sub-question steps up to max_pages."""
        queues: dict[int, list[SearchHit]] = {}
        for step_id in step_order:
            hits_with_rel = kept_hits_by_step.get(step_id, [])
            sorted_hits = [h for h, _ in sorted(hits_with_rel, key=lambda x: x[1], reverse=True)]
            queues[step_id] = sorted_hits

        targets: list[tuple[int, SearchHit]] = []
        while len(targets) < max_pages:
            added_in_round = 0
            for step_id in step_order:
                if len(targets) >= max_pages:
                    break
                queue = queues.get(step_id, [])
                if queue:
                    hit = queue.pop(0)
                    targets.append((step_id, hit))
                    added_in_round += 1
            if added_in_round == 0:
                break
        return targets

    def _run_round(
        self,
        steps: list[PlanStep],
        budget: Budget,
        all_candidates: dict[str, Source],
        all_rejected: list[RejectedSource],
        tool_errors: list[str],
        query_by_step: dict[int, str],
        pages_fetched: list[int],
    ) -> None:
        cfg = self.settings

        def execute_step(step: PlanStep) -> tuple[int, str, Any, str | None]:
            tool_name = step.tool
            fn = self.tools.get(tool_name)
            if not fn:
                return step.id, tool_name, None, f"Unknown tool: {tool_name}"
            if not budget.take():
                return step.id, tool_name, None, f"Tool call refused for step {step.id} ({tool_name}): budget exhausted"

            res = run_tool(
                name=tool_name,
                fn=fn,
                args={"query": step.query},
                settings=cfg,
                tracer=self.tracer,
                cache=self.cache,
            )
            if res.status not in ("ok", "empty"):
                return step.id, tool_name, None, f"Step {step.id} {tool_name} failed: {res.error or res.status}"
            return step.id, tool_name, res.data, None

        workers = min(len(steps), cfg.parallelism) if steps else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(execute_step, s) for s in steps]
            step_results = [f.result() for f in futures]

        hits_by_step: dict[int, list[tuple[SearchHit, float]]] = collections.defaultdict(list)

        for step_id, tool_name, output, err in step_results:
            if err:
                tool_errors.append(err)
                continue

            if tool_name == "wikipedia" and isinstance(output, dict):
                url = output.get("url", "")
                if url:
                    canon = canonical_url(url)
                    summary = output.get("summary") or ""
                    title = output.get("title") or ""
                    domain = domain_of(url)

                    if canon in all_candidates:
                        existing = all_candidates[canon]
                        if step_id not in existing.step_ids:
                            existing.step_ids.append(step_id)
                    else:
                        src = Source(
                            id="",
                            url=url,
                            title=title,
                            content=summary,
                            snippet=summary[:300] if summary else "",
                            domain=domain,
                            step_id=step_id,
                            step_ids=[step_id],
                        )
                        scored = score_source(src, query_by_step.get(step_id, ""))
                        all_candidates[canon] = scored

            elif tool_name == "web_search" and isinstance(output, list):
                raw_hits = [(step_id, h) for h in output if isinstance(h, SearchHit)]
                kept, rejected = prefilter_hits(raw_hits, query_by_step)
                all_rejected.extend(rejected)
                for sid, hit, rel in kept:
                    hits_by_step[sid].append((hit, rel))

        remaining_pages = max(0, cfg.max_pages_to_fetch - pages_fetched[0])
        step_ids_order = [s.id for s in steps]
        targets = self._select_fetch_targets(hits_by_step, step_ids_order, remaining_pages)

        for step_id, hit in targets:
            pages_fetched[0] += 1
            canon = canonical_url(hit.url)
            if canon in all_candidates:
                existing = all_candidates[canon]
                if step_id not in existing.step_ids:
                    existing.step_ids.append(step_id)
                continue

            fn = self.tools.get("fetch_page")
            if not fn:
                tool_errors.append("fetch_page tool not configured")
                continue

            if not budget.take():
                tool_errors.append(f"Tool call refused for fetch_page ({hit.url}): budget exhausted")
                cand = Source(
                    id="",
                    url=hit.url,
                    title=hit.title,
                    content="",
                    snippet=hit.snippet,
                    domain=domain_of(hit.url),
                    flags=["fetch_budget_exhausted", "snippet_only"],
                    step_id=step_id,
                    step_ids=[step_id],
                )
                scored = score_source(cand, query_by_step.get(step_id, ""))
                all_candidates[canon] = scored
                continue

            fetch_res = run_tool(
                name="fetch_page",
                fn=fn,
                args={"url": hit.url},
                settings=cfg,
                tracer=self.tracer,
                cache=self.cache,
            )

            if fetch_res.status == "ok" and fetch_res.data:
                cand = Source(
                    id="",
                    url=hit.url,
                    title=hit.title,
                    content=str(fetch_res.data),
                    snippet=hit.snippet,
                    domain=domain_of(hit.url),
                    step_id=step_id,
                    step_ids=[step_id],
                )
            else:
                flag = f"fetch_{fetch_res.status}"
                tool_errors.append(f"fetch_page failed for {hit.url}: status={fetch_res.status}, error={fetch_res.error}")
                cand = Source(
                    id="",
                    url=hit.url,
                    title=hit.title,
                    content="",
                    snippet=hit.snippet,
                    domain=domain_of(hit.url),
                    flags=[flag, "snippet_only"],
                    step_id=step_id,
                    step_ids=[step_id],
                )

            scored = score_source(cand, query_by_step.get(step_id, ""))
            all_candidates[canon] = scored

    def run(self, plan: ResearchPlan) -> Evidence:
        """Run the research plan under budgets, reading best pages and checking coverage."""
        cfg = self.settings
        budget = Budget(cfg.max_tool_calls, cfg.run_deadline_s)

        all_candidates: dict[str, Source] = {}
        all_rejected: list[RejectedSource] = []
        tool_errors: list[str] = []
        query_by_step: dict[int, str] = {s.id: s.sub_question for s in plan.steps}
        pages_fetched = [0]
        follow_up_rounds = 0

        # Round 1
        self._run_round(
            plan.steps,
            budget,
            all_candidates,
            all_rejected,
            tool_errors,
            query_by_step,
            pages_fetched,
        )

        def get_uncovered() -> list[int]:
            uncovered_ids: list[int] = []
            for s in plan.steps:
                covered = any(
                    (s.id in c.step_ids or c.step_id == s.id)
                    and c.relevance >= 0.1
                    and c.score >= cfg.min_source_score
                    for c in all_candidates.values()
                )
                if not covered:
                    uncovered_ids.append(s.id)
            return uncovered_ids

        uncovered = get_uncovered()

        # Bounded follow-up round if any steps are uncovered
        if uncovered and cfg.max_follow_up_rounds > 0 and not budget.exhausted:
            follow_up_steps: list[PlanStep] = []
            for uid in uncovered:
                orig_step = next((s for s in plan.steps if s.id == uid), None)
                if not orig_step:
                    continue
                if orig_step.tool == "wikipedia":
                    new_tool = "web_search"
                    new_query = orig_step.sub_question
                else:
                    if orig_step.query == orig_step.sub_question:
                        new_tool = "wikipedia"
                        new_query = orig_step.sub_question
                    else:
                        new_tool = "web_search"
                        new_query = orig_step.sub_question

                follow_up_steps.append(
                    PlanStep(
                        id=orig_step.id,
                        sub_question=orig_step.sub_question,
                        tool=new_tool,
                        query=new_query,
                    )
                )

            if follow_up_steps:
                follow_up_rounds += 1
                self._run_round(
                    follow_up_steps,
                    budget,
                    all_candidates,
                    all_rejected,
                    tool_errors,
                    query_by_step,
                    pages_fetched,
                )
                uncovered = get_uncovered()

        candidates_list = list(all_candidates.values())
        chosen, selection_rejected = select_sources(candidates_list, settings=cfg)
        all_rejected.extend(selection_rejected)

        return Evidence(
            sources=chosen,
            rejected=all_rejected,
            uncovered_steps=uncovered,
            tool_errors=tool_errors,
            follow_up_rounds=follow_up_rounds,
            budget_exhausted=budget.exhausted,
            candidates_considered=len(candidates_list),
        )
