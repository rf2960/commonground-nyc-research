import asyncio
import json
from pathlib import Path

import pytest

from commonground.research import (
    LeadOrchestrator,
    ResearchBrief,
    ResearchContext,
    ResearchResult,
    run_transit_task,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief():
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def initial_task():
    return LeadOrchestrator.build_initial_tasks(brief())[0]


def context(*, dependency_results=()):
    return ResearchContext(
        messages=[],
        allowed_tools=("get_transit_matrix",),
        max_turns=1,
        dependency_results=dependency_results,
    )


def provider_payload(brief_value, candidate_ids, durations=None, unavailable=()):
    durations = durations or {}
    unavailable = set(unavailable)
    pairs = []
    for traveler in brief_value.travelers:
        for candidate_id in candidate_ids:
            key = (candidate_id, traveler.traveler_id)
            if key in unavailable:
                pairs.append(
                    {
                        "traveler_id": traveler.traveler_id,
                        "area": candidate_id,
                        "route_available": False,
                        "transit_minutes": None,
                        "reason": "fixture route unavailable",
                    }
                )
            else:
                pairs.append(
                    {
                        "traveler_id": traveler.traveler_id,
                        "area": candidate_id,
                        "route_available": True,
                        "transit_minutes": durations.get(key, 20.0),
                    }
                )
    return json.dumps(
        {
            "route_pairs": pairs,
            "arrival_time": "2026-10-10T18:00:00Z",
            "provider": "google_routes",
        }
    )


def facts(result):
    return {
        (fact.candidate_id, fact.subject_id, fact.predicate): fact
        for fact in result.facts
    }


def exact_cafe_task(brief_value):
    cafe_result = ResearchResult.model_validate(fixture("round_2_results.json")[0])
    coordinate = next(
        fact
        for fact in cafe_result.facts
        if fact.candidate_id == "cafe:gplaces:fixture-expansion-cafe"
        and fact.predicate == "coordinates"
    )
    task = LeadOrchestrator._research_task(
        brief_value,
        round_number=2,
        agent="transit_researcher",
        objective="Fixture exact-cafe route verification",
        candidate_ids=("cafe:gplaces:fixture-expansion-cafe",),
        dependencies=(coordinate.fact_id,),
    )
    return task, cafe_result


def test_area_center_task_emits_ordered_cited_pair_facts(monkeypatch):
    b = brief()
    task = initial_task()
    captured = {}
    durations = {
        ("area:initial:union-square", "traveler:alice"): 35.0,
        ("area:initial:union-square", "traveler:bob"): 30.0,
    }

    def fake_matrix(**kwargs):
        captured.update(kwargs)
        return provider_payload(b, task.candidate_ids, durations)

    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        fake_matrix,
    )
    result = asyncio.run(run_transit_task(context(), b, task))

    assert result.status == "complete"
    assert result.candidate_ids_considered == task.candidate_ids
    assert len(result.facts) == len(b.travelers) * len(task.candidate_ids) * 2
    assert not result.missing
    assert captured["include_driving"] is False
    assert captured["arrival_time"] == b.meeting_time.isoformat()
    assert [origin["traveler_id"] for origin in captured["origins"]] == [
        traveler.traveler_id for traveler in b.travelers
    ]
    assert [area["area"] for area in captured["candidate_areas"]] == list(
        task.candidate_ids
    )

    by_key = facts(result)
    boundary = by_key[
        ("area:initial:union-square", "traveler:bob", "transit_duration_minutes")
    ]
    assert boundary.value == 30.0
    assert boundary.valid_for == {
        "arrival_time": b.meeting_time.isoformat(),
        "destination_kind": "area_center",
    }
    assert by_key[
        ("area:initial:union-square", "traveler:bob", "route_available")
    ].value is True
    assert result.sources[0].request_summary["travel_mode"] == "TRANSIT"
    assert "key" not in result.model_dump_json().lower()


def test_round_two_uses_cited_exact_cafe_coordinates(monkeypatch):
    b = brief()
    task, cafe_result = exact_cafe_task(b)
    captured = {}

    def fake_matrix(**kwargs):
        captured.update(kwargs)
        return provider_payload(b, task.candidate_ids)

    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        fake_matrix,
    )
    result = asyncio.run(
        run_transit_task(
            context(dependency_results=(cafe_result,)),
            b,
            task,
        )
    )

    assert result.status == "complete"
    assert captured["candidate_areas"] == [
        {
            "area": "cafe:gplaces:fixture-expansion-cafe",
            "lat": 40.751,
            "lng": -73.9398,
        }
    ]
    assert all(
        fact.candidate_id == "cafe:gplaces:fixture-expansion-cafe"
        and fact.valid_for["destination_kind"] == "exact_cafe"
        for fact in result.facts
    )


def test_round_two_can_route_to_cited_expansion_area_center(monkeypatch):
    b = brief()
    expansion_result = next(
        ResearchResult.model_validate(item)
        for item in fixture("round_1_results.json")
        if item["agent"] == "expansion_researcher"
    )
    coordinate = next(
        fact
        for fact in expansion_result.facts
        if fact.predicate == "coordinates"
    )
    task = LeadOrchestrator._research_task(
        b,
        round_number=2,
        agent="transit_researcher",
        objective="Fixture expansion-center verification",
        candidate_ids=(coordinate.candidate_id,),
        dependencies=(coordinate.fact_id,),
    )
    captured = {}

    def fake_matrix(**kwargs):
        captured.update(kwargs)
        return provider_payload(b, task.candidate_ids)

    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        fake_matrix,
    )
    result = asyncio.run(
        run_transit_task(
            context(dependency_results=(expansion_result,)),
            b,
            task,
        )
    )

    assert result.status == "complete"
    assert captured["candidate_areas"] == [
        {
            "area": "area:mta:fixture-queensboro-plaza",
            "lat": 40.7506,
            "lng": -73.9402,
        }
    ]
    assert all(
        fact.valid_for["destination_kind"] == "area_center"
        for fact in result.facts
    )


def test_missing_exact_coordinates_never_calls_provider(monkeypatch):
    b = brief()
    task, _ = exact_cafe_task(b)

    def unexpected_call(**kwargs):
        raise AssertionError("provider must not run without cited coordinates")

    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        unexpected_call,
    )
    result = asyncio.run(run_transit_task(context(), b, task))

    assert result.status == "failed"
    assert len(result.missing) == len(b.travelers)
    assert {gap.reason_code for gap in result.missing} == {"DEPENDENCY_NOT_READY"}
    assert {gap.subject_id for gap in result.missing} == {
        traveler.traveler_id for traveler in b.travelers
    }


def test_unavailable_and_missing_pairs_preserve_successful_siblings(monkeypatch):
    b = brief()
    task = initial_task()
    unavailable = {
        ("area:initial:union-square", "traveler:bob"),
    }
    payload = json.loads(provider_payload(b, task.candidate_ids, unavailable=unavailable))
    payload["route_pairs"] = [
        pair
        for pair in payload["route_pairs"]
        if not (
            pair["area"] == "area:initial:downtown-brooklyn"
            and pair["traveler_id"] == "traveler:carol"
        )
    ]
    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        lambda **kwargs: json.dumps(payload),
    )

    result = asyncio.run(run_transit_task(context(), b, task))
    by_key = facts(result)

    assert result.status == "partial"
    assert by_key[
        ("area:initial:union-square", "traveler:alice", "transit_duration_minutes")
    ].value == 20.0
    assert by_key[
        ("area:initial:union-square", "traveler:bob", "route_available")
    ].value is False
    assert {
        (gap.candidate_id, gap.subject_id, gap.reason_code)
        for gap in result.missing
    } == {
        (
            "area:initial:union-square",
            "traveler:bob",
            "ROUTE_UNAVAILABLE",
        ),
        (
            "area:initial:downtown-brooklyn",
            "traveler:carol",
            "PROVIDER_ERROR",
        ),
    }


def test_provider_error_is_pair_complete_and_redacted(monkeypatch):
    b = brief()
    task = initial_task()
    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        lambda **kwargs: json.dumps({"error": "fixture-secret-token"}),
    )

    result = asyncio.run(run_transit_task(context(), b, task))

    assert result.status == "failed"
    assert len(result.missing) == len(b.travelers) * len(task.candidate_ids)
    assert {gap.reason_code for gap in result.missing} == {"PROVIDER_ERROR"}
    assert not result.sources
    assert "fixture-secret-token" not in result.model_dump_json()


def test_no_cross_role_tool_calls(monkeypatch):
    monkeypatch.setattr(
        "commonground.research.transit_agent.provider.get_transit_matrix",
        lambda **kwargs: pytest.fail("invalid context must fail before provider call"),
    )
    invalid_context = ResearchContext(
        messages=[],
        allowed_tools=("search_cafes_in_areas",),
        max_turns=1,
    )
    with pytest.raises(ValueError, match="Invalid or unbounded"):
        asyncio.run(run_transit_task(invalid_context, brief(), initial_task()))
