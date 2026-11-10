import asyncio
import json
from pathlib import Path

import pytest

from commonground.research import ResearchBrief, ResearchResult, ResearchRunner, ResearchTask


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def task(agent: str, sequence: int = 1, **changes) -> ResearchTask:
    token = agent.removesuffix("_researcher")
    tools = {
        "transit_researcher": ["get_transit_matrix"],
        "cafe_researcher": ["search_cafes_in_areas"],
        "expansion_researcher": ["search_mta_expansion_candidates"],
    }
    payload = {
        "task_id": f"task:session-123:r1:{token}:{sequence}",
        "research_id": "research:session-123:1",
        "round": 1,
        "agent": agent,
        "objective": f"Collect {token} evidence",
        "candidate_ids": ["area:initial:union-square"],
        "dependencies": [],
        "allowed_tools": tools[agent],
    }
    payload.update(changes)
    return ResearchTask.model_validate(payload)


def complete_result(task_value: ResearchTask) -> ResearchResult:
    return ResearchResult.model_validate(
        {
            "task_id": task_value.task_id,
            "agent": task_value.agent,
            "round": task_value.round,
            "status": "complete",
            "facts": [],
            "sources": [],
            "missing": [],
            "candidate_ids_considered": task_value.candidate_ids,
            "summary": "Fixture executor completed the bounded task.",
        }
    )


def initial_tasks() -> list[ResearchTask]:
    return [
        task("expansion_researcher", 3),
        task("cafe_researcher", 2),
        task("transit_researcher", 1),
    ]


def test_initial_researchers_run_concurrently_and_return_deterministic_order():
    active = 0
    max_active = 0

    async def executor(context, brief_value, task_value):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.02)
        active -= 1
        return complete_result(task_value)

    results = asyncio.run(
        ResearchRunner(executor).run_initial_round(brief(), initial_tasks())
    )

    assert max_active == 3
    assert [result.agent for result in results] == [
        "transit_researcher",
        "cafe_researcher",
        "expansion_researcher",
    ]


def test_each_researcher_receives_a_fresh_context_and_scoped_toolset():
    contexts = []
    original_message_counts = []

    async def executor(context, brief_value, task_value):
        contexts.append(context)
        original_message_counts.append(len(context.messages))
        context.messages.append({"role": "assistant", "content": task_value.agent})
        await asyncio.sleep(0)
        return complete_result(task_value)

    asyncio.run(ResearchRunner(executor, max_turns=5).run_initial_round(brief(), initial_tasks()))

    assert len({id(context) for context in contexts}) == 3
    assert len({id(context.messages) for context in contexts}) == 3
    assert original_message_counts == [2, 2, 2]
    assert all(context.max_turns == 5 for context in contexts)
    assert {context.allowed_tools for context in contexts} == {
        ("get_transit_matrix",),
        ("search_cafes_in_areas",),
        ("search_mta_expansion_candidates",),
    }


def test_cross_role_tool_is_rejected_without_calling_executor():
    called = False

    async def executor(context, brief_value, task_value):
        nonlocal called
        called = True
        return complete_result(task_value)

    invalid = task(
        "transit_researcher",
        allowed_tools=["search_cafes_in_areas"],
    )
    result = asyncio.run(ResearchRunner(executor).run_task(brief(), invalid))

    assert not called
    assert result.status == "failed"
    assert result.missing[0].reason_code == "VALIDATION_ERROR"
    assert result.missing[0].candidate_id == invalid.candidate_ids[0]


def test_one_researcher_failure_preserves_other_results_and_explicit_gap():
    async def executor(context, brief_value, task_value):
        if task_value.agent == "cafe_researcher":
            raise RuntimeError("provider response must not leak into the trace")
        return complete_result(task_value)

    results = asyncio.run(
        ResearchRunner(executor).run_initial_round(brief(), initial_tasks())
    )
    by_agent = {result.agent: result for result in results}

    assert by_agent["transit_researcher"].status == "complete"
    assert by_agent["expansion_researcher"].status == "complete"
    cafe = by_agent["cafe_researcher"]
    assert cafe.status == "failed"
    assert cafe.missing[0].reason_code == "AGENT_EXECUTION_ERROR"
    assert "provider response" not in cafe.summary
    assert cafe.missing[0].retryable is True


def test_timeout_becomes_a_retryable_missing_evidence_record():
    async def executor(context, brief_value, task_value):
        await asyncio.sleep(0.05)
        return complete_result(task_value)

    result = asyncio.run(
        ResearchRunner(executor, task_timeout_seconds=0.001).run_task(
            brief(), task("transit_researcher")
        )
    )

    assert result.status == "failed"
    assert result.missing[0].reason_code == "TIMEOUT"
    assert result.missing[0].retryable is True


def test_mismatched_or_invalid_executor_result_becomes_validation_gap():
    async def executor(context, brief_value, task_value):
        other = task("transit_researcher", sequence=9)
        return complete_result(other)

    requested = task("transit_researcher")
    result = asyncio.run(ResearchRunner(executor).run_task(brief(), requested))

    assert result.task_id == requested.task_id
    assert result.status == "failed"
    assert result.missing[0].reason_code == "VALIDATION_ERROR"
    assert result.missing[0].retryable is False


@pytest.mark.parametrize(
    "tasks_value",
    [
        [task("transit_researcher"), task("cafe_researcher")],
        [
            task("transit_researcher", 1),
            task("transit_researcher", 2),
            task("cafe_researcher", 3),
        ],
    ],
)
def test_initial_round_requires_exactly_the_three_researcher_roles(tasks_value):
    async def executor(context, brief_value, task_value):
        return complete_result(task_value)

    with pytest.raises(ValueError, match="exactly one"):
        asyncio.run(ResearchRunner(executor).run_initial_round(brief(), tasks_value))


@pytest.mark.parametrize("max_turns", [0, 13])
def test_runner_rejects_unbounded_or_empty_turn_budgets(max_turns):
    async def executor(context, brief_value, task_value):
        return complete_result(task_value)

    with pytest.raises(ValueError, match="max_turns"):
        ResearchRunner(executor, max_turns=max_turns)
