"""Small role dispatcher and production composition boundary for Deep Research."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .expansion import build_expansion_result, fetch_mta_stations
from .models import MissingEvidence, ResearchBrief, ResearchResult, ResearchTask, ResearcherAgent
from .runner import ResearchContext, ResearchRunner
from .service import DeepResearchService
from .writer import EvidenceWriter


ResearchAdapter = Callable[
    [ResearchContext, ResearchBrief, ResearchTask],
    Awaitable[ResearchResult | dict[str, Any]],
]
StationLoader = Callable[[], tuple[tuple[Any, ...], Any]]


class ResearchDispatcher:
    """Route one validated task to exactly one role-owned adapter."""

    def __init__(
        self,
        *,
        transit: ResearchAdapter,
        cafe: ResearchAdapter,
        expansion: ResearchAdapter,
    ) -> None:
        self._adapters: dict[ResearcherAgent, ResearchAdapter] = {
            "transit_researcher": transit,
            "cafe_researcher": cafe,
            "expansion_researcher": expansion,
        }

    async def __call__(
        self,
        context: ResearchContext,
        brief: ResearchBrief,
        task: ResearchTask,
    ) -> ResearchResult | dict[str, Any]:
        return await self._adapters[task.agent](context, brief, task)


async def run_expansion_task(
    _context: ResearchContext,
    brief: ResearchBrief,
    task: ResearchTask,
    *,
    loader: StationLoader = fetch_mta_stations,
) -> ResearchResult:
    """Load one bounded MTA snapshot off-loop and normalize it into task evidence."""

    if task.agent != "expansion_researcher":
        raise ValueError("run_expansion_task accepts expansion_researcher tasks only")
    try:
        stations, accessed_at = await asyncio.to_thread(loader)
        return build_expansion_result(
            task,
            brief,
            stations,
            accessed_at=accessed_at,
        )
    except Exception:
        # The MTA tool owns its provider/normalization failure boundary. Never rely
        # only on the outer runner or expose arbitrary SDK/response details.
        task_sequence = int(task.task_id.rsplit(":", 1)[1])
        missing = tuple(
            MissingEvidence(
                missing_id=(
                    f"missing:expansion:r{task.round}:"
                    f"{task_sequence * 100 + index:03d}"
                ),
                candidate_id=candidate_id,
                field="expansion_candidates",
                reason_code="PROVIDER_ERROR",
                detail="The bounded MTA station request failed safely.",
                retryable=True,
                next_action="Retry the official MTA station request or report expansion evidence as unknown.",
            )
            for index, candidate_id in enumerate(task.candidate_ids, start=1)
        )
        return ResearchResult(
            task_id=task.task_id,
            agent=task.agent,
            round=task.round,
            status="failed",
            missing=missing,
            candidate_ids_considered=task.candidate_ids,
            summary="MTA expansion evidence is unavailable; no station result was claimed.",
        )


def build_research_service(
    *,
    transit: ResearchAdapter,
    cafe: ResearchAdapter,
    expansion: ResearchAdapter = run_expansion_task,
    task_timeout_seconds: float = 45.0,
    max_turns: int = 6,
    writer: EvidenceWriter | None = None,
) -> DeepResearchService:
    """Compose role adapters without allowing them to own app globals or constraints."""

    dispatcher = ResearchDispatcher(
        transit=transit,
        cafe=cafe,
        expansion=expansion,
    )
    return DeepResearchService(
        ResearchRunner(
            dispatcher,
            task_timeout_seconds=task_timeout_seconds,
            max_turns=max_turns,
        ),
        writer=writer,
    )
