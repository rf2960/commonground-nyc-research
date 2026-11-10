import asyncio
import json
from pathlib import Path

from commonground.research import (
    FeasibilityResult,
    FollowUpDecision,
    LeadOrchestrator,
    ResearchBrief,
    ResearchResult,
    ResearchRunner,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def fixture_results(name: str) -> dict[str, ResearchResult]:
    return {
        result.task_id: result
        for result in (
            ResearchResult.model_validate(item) for item in fixture(name)
        )
    }


def test_lead_executes_initial_failure_follow_up_and_decisive_evidence():
    results = {
        **fixture_results("round_1_results.json"),
        **fixture_results("round_2_results.json"),
    }
    calls = []

    async def executor(context, brief_value, task_value):
        calls.append(task_value)
        return results[task_value.task_id]

    outcome = asyncio.run(
        LeadOrchestrator(ResearchRunner(executor)).run(brief())
    )

    expected_decision = FollowUpDecision.model_validate(
        fixture("follow_up_decision.json")
    )
    expected_feasibility = FeasibilityResult.model_validate(
        fixture("expected_feasibility.json")
    )

    assert outcome.follow_up_decision == expected_decision
    assert outcome.feasibility_results == (expected_feasibility,)
    assert len(outcome.initial_tasks) == 3
    assert len(outcome.round_two_tasks) == 2
    assert [task.agent for task in outcome.round_two_tasks] == [
        "cafe_researcher",
        "transit_researcher",
    ]
    assert [task.round for task in calls].count(1) == 3
    assert [task.round for task in calls].count(2) == 2


def test_exact_cafe_transit_task_waits_for_cafe_coordinates():
    results = {
        **fixture_results("round_1_results.json"),
        **fixture_results("round_2_results.json"),
    }
    completion_order = []

    async def executor(context, brief_value, task_value):
        completion_order.append(task_value.task_id)
        if task_value.round == 2:
            available = {fact.fact_id: fact for result in context.dependency_results for fact in result.facts}
            assert all(dependency in available for dependency in task_value.dependencies)
            assert any(fact.predicate == 'coordinates' and fact.candidate_id in task_value.candidate_ids
                       for fact in available.values())
        return results[task_value.task_id]

    outcome = asyncio.run(
        LeadOrchestrator(ResearchRunner(executor)).run(brief())
    )
    cafe_task, transit_task = outcome.round_two_tasks

    assert completion_order.index(cafe_task.task_id) < completion_order.index(
        transit_task.task_id
    )
    assert transit_task.candidate_ids == (
        "cafe:gplaces:fixture-expansion-cafe",
    )
    assert transit_task.dependencies == ("fact:cafe:r2:004",)
    assert cafe_task.candidate_ids == ("area:mta:fixture-queensboro-plaza",)


def test_initial_tasks_are_bounded_and_use_role_scoped_tools():
    tasks = LeadOrchestrator.build_initial_tasks(brief())

    assert [task.agent for task in tasks] == [
        "transit_researcher",
        "cafe_researcher",
        "expansion_researcher",
    ]
    assert {task.allowed_tools for task in tasks} == {
        ("get_transit_matrix",),
        ("search_cafes_in_areas",),
        ("search_mta_expansion_candidates",),
    }
    assert all(task.round == 1 for task in tasks)
    assert all(len(task.candidate_ids) == 2 for task in tasks)


def test_no_expansion_evidence_means_no_unjustified_follow_up():
    round_one = fixture_results("round_1_results.json")
    expansion_id = "task:session-123:r1:expansion:1"
    expansion = round_one[expansion_id]
    round_one[expansion_id] = ResearchResult(
        task_id=expansion.task_id,
        agent=expansion.agent,
        round=expansion.round,
        status="complete",
        facts=(),
        sources=(),
        missing=(),
        candidate_ids_considered=expansion.candidate_ids_considered,
        summary="No non-duplicate expansion candidate was found.",
    )

    async def executor(context, brief_value, task_value):
        return round_one[task_value.task_id]

    outcome = asyncio.run(
        LeadOrchestrator(ResearchRunner(executor)).run(brief())
    )

    assert outcome.follow_up_decision is None
    assert outcome.round_two_tasks == ()
    assert outcome.round_two_results == ()
    assert outcome.feasibility_results == ()


def test_empty_expansion_cafe_result_does_not_invent_a_transit_target():
    results = fixture_results("round_1_results.json")
    empty_cafe = ResearchResult.model_validate(
        {
            "task_id": "task:session-123:r2:cafe:1",
            "agent": "cafe_researcher",
            "round": 2,
            "status": "complete",
            "facts": [],
            "sources": [],
            "missing": [],
            "candidate_ids_considered": [
                "area:mta:fixture-queensboro-plaza"
            ],
            "summary": "No cafe matched the active constraints.",
        }
    )
    results[empty_cafe.task_id] = empty_cafe

    async def executor(context, brief_value, task_value):
        return results[task_value.task_id]

    outcome = asyncio.run(
        LeadOrchestrator(ResearchRunner(executor)).run(brief())
    )

    assert outcome.follow_up_decision is not None
    assert [task.agent for task in outcome.round_two_tasks] == ["cafe_researcher"]
    assert outcome.feasibility_results == ()
