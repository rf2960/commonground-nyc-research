"""Small role dispatcher and production composition boundary for Deep Research."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .expansion import build_expansion_result, fetch_mta_stations
from .models import ResearchBrief, ResearchResult, ResearchTask, ResearcherAgent
from .runner import ResearchContext, ResearchRunner
from .service import DeepResearchService


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
    stations, accessed_at = await asyncio.to_thread(loader)
    return build_expansion_result(
        task,
        brief,
        stations,
        accessed_at=accessed_at,
    )


def build_research_service(
    *,
    transit: ResearchAdapter,
    cafe: ResearchAdapter,
    expansion: ResearchAdapter = run_expansion_task,
    task_timeout_seconds: float = 45.0,
    max_turns: int = 6,
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
        )
    )
