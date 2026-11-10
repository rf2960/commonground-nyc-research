import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from commonground.research import (
    LeadOrchestrator,
    ResearchBrief,
    ResearchContext,
    ResearchDispatcher,
    ResearchResult,
    build_research_service,
    parse_mta_stations,
    run_expansion_task,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def context() -> ResearchContext:
    return ResearchContext(
        messages=[],
        allowed_tools=("search_mta_expansion_candidates",),
        max_turns=6,
    )


def result_by_agent() -> dict[str, ResearchResult]:
    return {
        payload["agent"]: ResearchResult.model_validate(payload)
        for payload in fixture("round_1_results.json")
    }


def test_dispatcher_calls_only_the_task_role_adapter():
    calls = []
    results = result_by_agent()

    def adapter_for(agent):
        async def adapter(_context, _brief, _task):
            calls.append(agent)
            return results[agent]

        return adapter

    dispatcher = ResearchDispatcher(
        transit=adapter_for("transit_researcher"),
        cafe=adapter_for("cafe_researcher"),
        expansion=adapter_for("expansion_researcher"),
    )
    task = LeadOrchestrator.build_initial_tasks(brief())[1]

    result = asyncio.run(dispatcher(context(), brief(), task))

    assert result.agent == "cafe_researcher"
    assert calls == ["cafe_researcher"]


def test_expansion_task_loads_snapshot_and_returns_cited_result():
    stations = parse_mta_stations(fixture("mta_stations.json"))
    accessed_at = datetime.fromisoformat("2026-10-01T16:00:00+00:00")
    task = LeadOrchestrator.build_initial_tasks(brief())[2]

    result = asyncio.run(
        run_expansion_task(
            context(),
            brief(),
            task,
            loader=lambda: (stations, accessed_at),
        )
    )

    assert result.agent == "expansion_researcher"
    assert result.status == "complete"
    assert 1 <= len(result.sources) <= 3
    assert all(source.provider == "mta_subway_stations" for source in result.sources)
    assert all(fact.source_ids for fact in result.facts)


def test_expansion_task_rejects_another_role():
    task = LeadOrchestrator.build_initial_tasks(brief())[0]

    with pytest.raises(ValueError, match="expansion_researcher"):
        asyncio.run(run_expansion_task(context(), brief(), task))


def test_service_factory_preserves_runner_bounds():
    async def unused(_context, _brief, _task):
        raise AssertionError("not called")

    service = build_research_service(
        transit=unused,
        cafe=unused,
        expansion=unused,
        task_timeout_seconds=12,
        max_turns=4,
    )

    assert service._lead._runner.task_timeout_seconds == 12
    assert service._lead._runner.max_turns == 4
