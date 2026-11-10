import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from commonground.research import (
    Fact,
    FeasibilityResult,
    FollowUpDecision,
    MissingEvidence,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def round_trip(model_type, payload):
    first = model_type.model_validate(payload)
    second = model_type.model_validate_json(first.model_dump_json())
    assert second == first
    return first


def valid_task(**changes):
    payload = {
        "task_id": "task:session-123:r1:transit:1",
        "research_id": "research:session-123:1",
        "round": 1,
        "agent": "transit_researcher",
        "objective": "Measure arrival ETAs to initial centers",
        "candidate_ids": ["area:initial:union-square"],
        "dependencies": [],
        "allowed_tools": ["get_transit_matrix"],
    }
    payload.update(changes)
    return payload


def test_all_fixed_contract_artifacts_round_trip():
    round_trip(ResearchBrief, fixture("research_brief.json"))
    for result in fixture("round_1_results.json"):
        round_trip(ResearchResult, result)
    round_trip(FollowUpDecision, fixture("follow_up_decision.json"))
    for result in fixture("round_2_results.json"):
        round_trip(ResearchResult, result)
    round_trip(FeasibilityResult, fixture("expected_feasibility.json"))


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["travelers"].append(
                copy.deepcopy(payload["travelers"][0])
            ),
            "traveler IDs must be unique",
        ),
        (
            lambda payload: payload["initial_candidates"].append(
                copy.deepcopy(payload["initial_candidates"][0])
            ),
            "candidate IDs must be unique",
        ),
        (
            lambda payload: payload.__setitem__("meeting_time", "2026-10-10T14:00:00"),
            "meeting_time must include an explicit time zone",
        ),
        (
            lambda payload: payload["travelers"][0].__setitem__(
                "max_commute_minutes", 0
            ),
            "greater than 0",
        ),
        (
            lambda payload: payload.__setitem__("session_id", "different-session"),
            "research_id must contain the brief session_id",
        ),
    ],
)
def test_brief_rejects_ambiguous_or_unjoinable_inputs(mutate, message):
    payload = fixture("research_brief.json")
    mutate(payload)

    with pytest.raises(ValidationError, match=message):
        ResearchBrief.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"round": 3},
        {"agent": "lead"},
        {"task_id": "task:session-123:r1:cafe:1"},
        {"candidate_ids": ["area:initial:union-square", "area:initial:union-square"]},
        {"allowed_tools": []},
        {"research_id": "research:different-session:1"},
    ],
)
def test_task_rejects_unsupported_round_role_or_duplicate_targets(changes):
    with pytest.raises(ValidationError):
        ResearchTask.model_validate(valid_task(**changes))


def test_valid_research_task_is_immutable_and_round_trips():
    task = round_trip(ResearchTask, valid_task())

    with pytest.raises(ValidationError):
        task.round = 2


def test_fact_requires_a_real_value_and_at_least_one_source():
    fact = fixture("round_1_results.json")[0]["facts"][0]

    without_sources = copy.deepcopy(fact)
    without_sources["source_ids"] = []
    with pytest.raises(ValidationError):
        Fact.model_validate(without_sources)

    missing_value = copy.deepcopy(fact)
    missing_value["value"] = None
    with pytest.raises(ValidationError, match="MissingEvidence"):
        Fact.model_validate(missing_value)


def test_missing_evidence_has_a_stable_id_and_can_name_a_traveler():
    missing = MissingEvidence.model_validate(
        {
            "missing_id": "missing:transit:r2:001",
            "candidate_id": "cafe:gplaces:fixture-expansion-cafe",
            "subject_id": "traveler:alice",
            "field": "transit_duration_minutes",
            "reason_code": "ROUTE_UNAVAILABLE",
            "detail": "No route was returned for this traveler and exact cafe.",
            "retryable": False,
            "next_action": "Report the route as unknown.",
        }
    )

    assert missing.missing_id == "missing:transit:r2:001"
    assert missing.subject_id == "traveler:alice"

    with pytest.raises(ValidationError):
        MissingEvidence.model_validate(
            {
                **missing.model_dump(mode="json"),
                "missing_id": "not-stable",
            }
        )


def test_result_rejects_uncited_fact_and_unsupported_status():
    result = fixture("round_1_results.json")[0]

    uncited = copy.deepcopy(result)
    uncited["facts"][0]["source_ids"] = ["source:google-routes:not-in-result"]
    with pytest.raises(ValidationError, match="absent from this result"):
        ResearchResult.model_validate(uncited)

    unsupported = copy.deepcopy(result)
    unsupported["status"] = "unknown"
    with pytest.raises(ValidationError):
        ResearchResult.model_validate(unsupported)


@pytest.mark.parametrize(
    "source_change",
    [
        {"url": "https://example.com/data?api_key=do-not-log-this"},
        {"request_summary": {"token": "do-not-log-this"}},
        {"request_summary": {"nested": {"authorization": "do-not-log-this"}}},
    ],
)
def test_source_contract_rejects_credentials(source_change):
    result = fixture("round_1_results.json")[0]
    result["sources"][0].update(source_change)

    with pytest.raises(ValidationError, match="credential|access token"):
        ResearchResult.model_validate(result)


def test_follow_up_contract_rejects_a_second_follow_up_or_unbounded_targets():
    decision = fixture("follow_up_decision.json")

    second_follow_up = copy.deepcopy(decision)
    second_follow_up["round"] = 3
    with pytest.raises(ValidationError):
        FollowUpDecision.model_validate(second_follow_up)

    too_many_targets = copy.deepcopy(decision)
    too_many_targets["selected_ids"] = [
        "area:mta:one",
        "area:mta:two",
        "area:mta:three",
        "area:mta:four",
    ]
    with pytest.raises(ValidationError):
        FollowUpDecision.model_validate(too_many_targets)


def test_feasibility_status_and_blocker_reasons_cannot_contradict():
    feasible = fixture("expected_feasibility.json")
    contradiction = copy.deepcopy(feasible)
    contradiction["reasons"] = [
        {
            "code": "TRAVELER_LIMIT_EXCEEDED",
            "traveler_id": "traveler:alice",
            "actual_minutes": 36,
            "limit_minutes": 35,
            "input_fact_ids": ["fact:transit:r2:001"],
        }
    ]
    with pytest.raises(ValidationError, match="FEASIBLE"):
        FeasibilityResult.model_validate(contradiction)

    unsupported_without_reason = copy.deepcopy(feasible)
    unsupported_without_reason["status"] = "EVIDENCE_INSUFFICIENT"
    with pytest.raises(ValidationError, match="at least one reason"):
        FeasibilityResult.model_validate(unsupported_without_reason)


def test_fixture_proves_initial_failure_justified_follow_up_and_new_evidence():
    brief = ResearchBrief.model_validate(fixture("research_brief.json"))
    round_one = [
        ResearchResult.model_validate(item) for item in fixture("round_1_results.json")
    ]
    decision = FollowUpDecision.model_validate(fixture("follow_up_decision.json"))
    round_two = [
        ResearchResult.model_validate(item) for item in fixture("round_2_results.json")
    ]
    expected = FeasibilityResult.model_validate(fixture("expected_feasibility.json"))

    limits = {traveler.traveler_id: traveler.max_commute_minutes for traveler in brief.travelers}
    transit_round_one = next(result for result in round_one if result.agent == "transit_researcher")
    durations_by_area: dict[str, dict[str, float]] = {}
    for fact in transit_round_one.facts:
        durations_by_area.setdefault(fact.candidate_id, {})[fact.subject_id] = fact.value

    assert all(
        any(minutes > limits[traveler_id] for traveler_id, minutes in durations.items())
        for durations in durations_by_area.values()
    )

    cafe_round_one = next(result for result in round_one if result.agent == "cafe_researcher")
    assert any(
        fact.predicate == "open_at_meeting_time" and fact.value is False
        for fact in cafe_round_one.facts
    )

    expansion_round_one = next(
        result for result in round_one if result.agent == "expansion_researcher"
    )
    expansion_reason = next(
        fact
        for fact in expansion_round_one.facts
        if fact.predicate == "expansion_selection_reason"
    )
    assert decision.selected_ids == ("area:mta:fixture-queensboro-plaza",)
    assert expansion_reason.fact_id in decision.dependencies
    assert decision.round == 2

    cafe_round_two = next(result for result in round_two if result.agent == "cafe_researcher")
    assert any(
        fact.predicate == "open_at_meeting_time" and fact.value is True
        for fact in cafe_round_two.facts
    )

    transit_round_two = next(
        result for result in round_two if result.agent == "transit_researcher"
    )
    exact_durations = {
        fact.subject_id: fact.value
        for fact in transit_round_two.facts
        if fact.predicate == "transit_duration_minutes"
        and fact.valid_for.get("destination_kind") == "exact_cafe"
    }
    assert set(exact_durations) == set(limits)
    assert all(exact_durations[traveler] <= limit for traveler, limit in limits.items())
    assert expected.status == "FEASIBLE"
