"""Application boundary joining Lead, Writer, and the compatible `/chat` trace."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .lead import LeadOrchestrator, LeadRun
from .models import ResearchBrief, ResearchResult, ResearchTask
from .runner import ResearchRunner
from .writer import EvidenceWriter, WriterReport


@dataclass(frozen=True)
class DeepResearchOutput:
    response: str
    tool_calls: tuple[dict[str, Any], ...]
    run: LeadRun
    report: WriterReport


class DeepResearchService:
    """Execute one bounded research run through an injected Researcher executor."""

    def __init__(
        self,
        runner: ResearchRunner,
        *,
        writer: EvidenceWriter | None = None,
    ) -> None:
        self._lead = LeadOrchestrator(runner)
        self._writer = writer or EvidenceWriter()

    async def run(self, brief: ResearchBrief) -> DeepResearchOutput:
        lead_run = await self._lead.run(brief)
        report = self._writer.write(lead_run)
        return DeepResearchOutput(
            response=report.response,
            tool_calls=build_research_trace(lead_run, report),
            run=lead_run,
            report=report,
        )

    def run_sync(self, brief: ResearchBrief) -> DeepResearchOutput:
        """Synchronous boundary used by FastAPI's existing sync `/chat` handler."""

        return asyncio.run(self.run(brief))


def _task_event(task: ResearchTask, result: ResearchResult) -> dict[str, Any]:
    if result.task_id != task.task_id:
        raise ValueError("trace task/result IDs do not match")
    return {
        "agent": task.agent,
        "round": task.round,
        "name": task.allowed_tools[0],
        "args": {
            "task_id": task.task_id,
            "research_id": task.research_id,
            "candidate_ids": list(task.candidate_ids),
            "dependencies": list(task.dependencies),
        },
        "result": result.model_dump_json(),
    }


def build_research_trace(
    run: LeadRun,
    report: WriterReport,
) -> tuple[dict[str, Any], ...]:
    """Build deterministic Project 2 trace entries without changing legacy keys."""

    trace: list[dict[str, Any]] = [
        {
            "agent": "lead",
            "round": 1,
            "name": "prepare_research_brief",
            "args": {
                "research_id": run.brief.research_id,
                "session_id": run.brief.session_id,
            },
            "result": run.brief.model_dump_json(),
        }
    ]
    round_one_by_task = {
        result.task_id: result for result in run.round_one_results
    }
    for task in run.initial_tasks:
        trace.append(_task_event(task, round_one_by_task[task.task_id]))

    writer_round = 1
    if run.follow_up_decision is not None:
        writer_round = 2
        trace.append(
            {
                "agent": "lead",
                "round": 2,
                "name": "choose_follow_up",
                "args": {
                    "research_id": run.brief.research_id,
                    "max_follow_up_rounds": run.brief.max_follow_up_rounds,
                },
                "result": run.follow_up_decision.model_dump_json(),
            }
        )
    round_two_by_task = {
        result.task_id: result for result in run.round_two_results
    }
    for task in run.round_two_tasks:
        trace.append(_task_event(task, round_two_by_task[task.task_id]))

    trace.append(
        {
            "agent": "lead",
            "round": writer_round,
            "name": "evaluate_feasibility",
            "args": {
                "research_id": run.brief.research_id,
                "rule_version": "feasibility-v1",
            },
            "result": json.dumps(
                [item.model_dump(mode="json") for item in run.feasibility_results],
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    )
    trace.append(
        {
            "agent": "writer",
            "round": writer_round,
            "name": "write_evidence_report",
            "args": {
                "research_id": run.brief.research_id,
                "claim_count": len(report.claims),
                "unknown_count": len(report.unknowns),
            },
            "result": json.dumps(
                {
                    "recommended_cafe_id": report.recommended_cafe_id,
                    "writer_mode": report.writer_mode,
                    "model": report.model,
                    "response": report.response,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    )
    return tuple(trace)
