"""Bounded, fresh-context execution for Project 2 Researchers.

The runner deliberately knows nothing about a particular model SDK.  A model or
fixture executor is injected at the boundary, which keeps concurrency, isolation,
timeouts, and result validation testable without live provider calls.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from pydantic import ValidationError

from .models import (
    ResearchBrief,
    ResearchResult,
    ResearchTask,
    ResearcherAgent,
)


ROLE_TOOL_ALLOWLISTS: Mapping[ResearcherAgent, frozenset[str]] = {
    "transit_researcher": frozenset({"get_transit_matrix"}),
    "cafe_researcher": frozenset({"search_cafes_in_areas"}),
    "expansion_researcher": frozenset({"search_mta_expansion_candidates"}),
}

ROLE_PROMPTS: Mapping[ResearcherAgent, str] = {
    "transit_researcher": (
        "You are the Transit Researcher. Collect route evidence only; do not decide "
        "whether a commute limit passes. Return one ResearchResult JSON object."
    ),
    "cafe_researcher": (
        "You are the Cafe Researcher. Collect cafe and opening-hours evidence only; "
        "never relax the brief's constraints. Return one ResearchResult JSON object."
    ),
    "expansion_researcher": (
        "You are the Expansion Researcher. Propose bounded MTA-backed candidates only; "
        "Routes and Places must verify feasibility. Return one ResearchResult JSON object."
    ),
}

AGENT_ORDER: Mapping[ResearcherAgent, int] = {
    "transit_researcher": 0,
    "cafe_researcher": 1,
    "expansion_researcher": 2,
}


@dataclass
class ResearchContext:
    """One invocation's mutable messages and immutable execution bounds.

    A new instance and a new messages list are created for every task.  Executors may
    append provider/model messages to their own context, but no context is reused.
    """

    messages: list[dict[str, str]]
    allowed_tools: tuple[str, ...]
    max_turns: int
    # Only structured evidence is handed forward, never another agent's messages.
    dependency_results: tuple[ResearchResult, ...] = ()


ResearchExecutor = Callable[
    [ResearchContext, ResearchBrief, ResearchTask],
    Awaitable[ResearchResult | dict[str, Any]],
]


class ResearchRunner:
    """Run bounded Researcher tasks with isolation and partial-failure handling."""

    def __init__(
        self,
        executor: ResearchExecutor,
        *,
        task_timeout_seconds: float = 45.0,
        max_turns: int = 6,
    ) -> None:
        if task_timeout_seconds <= 0:
            raise ValueError("task_timeout_seconds must be positive")
        if not 1 <= max_turns <= 12:
            raise ValueError("max_turns must be between 1 and 12")
        self._executor = executor
        self.task_timeout_seconds = task_timeout_seconds
        self.max_turns = max_turns

    async def run_initial_round(
        self,
        brief: ResearchBrief,
        tasks: tuple[ResearchTask, ...] | list[ResearchTask],
    ) -> tuple[ResearchResult, ...]:
        """Run exactly one task for each of the three Researcher roles in parallel."""

        validated = tuple(tasks)
        expected_agents = set(ROLE_TOOL_ALLOWLISTS)
        actual_agents = {task.agent for task in validated}
        if len(validated) != 3 or actual_agents != expected_agents:
            raise ValueError(
                "initial round requires exactly one transit, cafe, and expansion task"
            )
        if any(task.round != 1 for task in validated):
            raise ValueError("initial round tasks must all have round=1")
        if any(task.research_id != brief.research_id for task in validated):
            raise ValueError("every task must reference the supplied research brief")

        results = await asyncio.gather(
            *(self.run_task(brief, task) for task in validated)
        )
        return tuple(sorted(results, key=lambda result: AGENT_ORDER[result.agent]))

    async def run_task(
        self,
        brief: ResearchBrief,
        task: ResearchTask,
        *,
        dependency_results: tuple[ResearchResult, ...] = (),
    ) -> ResearchResult:
        """Execute one task or convert a bounded failure into explicit missing evidence."""

        if task.research_id != brief.research_id:
            raise ValueError("task must reference the supplied research brief")

        role_allowlist = ROLE_TOOL_ALLOWLISTS[task.agent]
        if not set(task.allowed_tools).issubset(role_allowlist):
            return self._failed_result(task, "VALIDATION_ERROR")

        if any(
            not result.task_id.startswith(f'task:{brief.session_id}:')
            or result.round > task.round
            for result in dependency_results
        ):
            return self._failed_result(task, 'VALIDATION_ERROR')

        context = self._fresh_context(brief, task, dependency_results)
        try:
            payload = await asyncio.wait_for(
                self._executor(context, brief, task),
                timeout=self.task_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return self._failed_result(task, "TIMEOUT")
        except Exception:
            # Do not expose arbitrary exception strings: provider/SDK errors may contain
            # request URLs, credentials, or other details unsafe for prompts and traces.
            return self._failed_result(task, "AGENT_EXECUTION_ERROR")

        try:
            result = ResearchResult.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            return self._failed_result(task, "VALIDATION_ERROR")

        if (
            result.task_id != task.task_id
            or result.agent != task.agent
            or result.round != task.round
        ):
            return self._failed_result(task, "VALIDATION_ERROR")
        return result

    def _fresh_context(
        self,
        brief: ResearchBrief,
        task: ResearchTask,
        dependency_results: tuple[ResearchResult, ...] = (),
    ) -> ResearchContext:
        input_payload = {
            "contract": "research-contract-v1",
            "brief": brief.model_dump(mode="json"),
            "task": task.model_dump(mode="json"),
        }
        # JSON round-trip isolates nested Fact values and Source request summaries,
        # which Pydantic's frozen records alone do not make deeply immutable.
        evidence = tuple(
            ResearchResult.model_validate_json(result.model_dump_json())
            for result in dependency_results
        )
        if evidence:
            input_payload["dependency_results"] = [
                result.model_dump(mode="json") for result in evidence
            ]
        return ResearchContext(
            messages=[
                {"role": "system", "content": ROLE_PROMPTS[task.agent]},
                {
                    "role": "user",
                    "content": json.dumps(
                        input_payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            allowed_tools=tuple(task.allowed_tools),
            max_turns=self.max_turns,
            dependency_results=evidence,
        )

    @staticmethod
    def _failed_result(task: ResearchTask, reason_code: str) -> ResearchResult:
        agent_token = task.agent.removesuffix("_researcher")
        task_sequence = int(task.task_id.rsplit(":", 1)[1])
        reason_text = {
            "AGENT_EXECUTION_ERROR": "The Researcher failed before producing a valid result.",
            "TIMEOUT": "The Researcher exceeded its per-task deadline.",
            "VALIDATION_ERROR": "The Researcher request or result violated its contract.",
        }[reason_code]
        retryable = reason_code in {"AGENT_EXECUTION_ERROR", "TIMEOUT"}
        missing = tuple(
            {
                "missing_id": (
                    f"missing:{agent_token}:r{task.round}:"
                    f"{task_sequence * 100 + index:03d}"
                ),
                "candidate_id": candidate_id,
                "subject_id": None,
                "field": "research_result",
                "reason_code": reason_code,
                "detail": reason_text,
                "retryable": retryable,
                "next_action": (
                    "Lead may use the single bounded follow-up only if this evidence is "
                    "decision-critical; otherwise Writer must report it as unknown."
                ),
            }
            for index, candidate_id in enumerate(task.candidate_ids, start=1)
        )
        return ResearchResult.model_validate(
            {
                "task_id": task.task_id,
                "agent": task.agent,
                "round": task.round,
                "status": "failed",
                "facts": [],
                "sources": [],
                "missing": missing,
                "candidate_ids_considered": task.candidate_ids,
                "summary": reason_text,
            }
        )
