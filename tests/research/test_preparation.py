import json
from datetime import datetime

from commonground.research import (
    CafeConstraints,
    ResearchIntake,
    TravelerIntake,
    prepare_research_brief,
)


def complete_intake() -> ResearchIntake:
    return ResearchIntake(
        meeting_time=datetime.fromisoformat("2026-10-10T14:00:00-04:00"),
        travelers=(
            TravelerIntake(
                traveler_id="traveler:alice",
                input_location="Columbia University",
                max_commute_minutes=35,
            ),
            TravelerIntake(
                traveler_id="traveler:bob",
                input_location="Astoria",
                max_commute_minutes=30,
            ),
        ),
        cafe_constraints=CafeConstraints(min_rating=4.3, price_levels=(1, 2)),
    )


def resolved_payload():
    return {
        "resolved_locations": [
            {"traveler_id": "traveler:alice", "lat": 40.8075, "lng": -73.9626},
            {"traveler_id": "traveler:bob", "lat": 40.7644, "lng": -73.9235},
        ],
        "unresolved": [],
    }


def candidate_payload():
    return {
        "candidate_areas": [
            {"area": "Union Square", "lat": 40.7359, "lng": -73.9911},
            {"area": "Downtown Brooklyn", "lat": 40.6928, "lng": -73.9903},
        ]
    }


def test_incomplete_intake_calls_no_project_one_tool():
    calls = []

    def resolver(_locations):
        calls.append("resolver")
        return "{}"

    outcome = prepare_research_brief(
        ResearchIntake(),
        session_id="session-123",
        resolver=resolver,
    )

    assert outcome.brief is None
    assert outcome.tool_calls == ()
    assert calls == []
    assert "at least two travelers" in outcome.response


def test_unresolved_origin_stops_before_candidate_generation():
    calls = []

    def resolver(_locations):
        calls.append("resolver")
        return json.dumps(
            {
                "resolved_locations": [resolved_payload()["resolved_locations"][0]],
                "unresolved": [
                    {
                        "traveler_id": "traveler:bob",
                        "query": "Astoria",
                        "reason": "No unambiguous match",
                    }
                ],
            }
        )

    def generator(**_kwargs):
        calls.append("generator")
        return json.dumps(candidate_payload())

    outcome = prepare_research_brief(
        complete_intake(),
        session_id="session-123",
        resolver=resolver,
        candidate_generator=generator,
    )

    assert outcome.brief is None
    assert calls == ["resolver"]
    assert len(outcome.tool_calls) == 1
    assert "traveler:bob" in outcome.response
    assert "No unambiguous match" in outcome.response


def test_complete_intake_reuses_project_one_tools_and_builds_brief():
    calls = []

    def resolver(locations):
        calls.append(("resolver", locations))
        return json.dumps(resolved_payload())

    def generator(**kwargs):
        calls.append(("generator", kwargs))
        return json.dumps(candidate_payload())

    outcome = prepare_research_brief(
        complete_intake(),
        session_id="session-123",
        resolver=resolver,
        candidate_generator=generator,
    )

    assert outcome.brief is not None
    assert outcome.brief.research_id == "research:session-123:1"
    assert [call["name"] for call in outcome.tool_calls] == [
        "resolve_group_locations",
        "generate_candidate_areas",
    ]
    assert all(call["agent"] == "lead" for call in outcome.tool_calls)
    assert [item[0] for item in calls] == ["resolver", "generator"]


def test_provider_error_is_returned_without_candidate_generation():
    outcome = prepare_research_brief(
        complete_intake(),
        session_id="session-123",
        resolver=lambda _locations: json.dumps({"error": "provider unavailable"}),
        candidate_generator=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("candidate generator must not run")
        ),
    )

    assert outcome.brief is None
    assert "provider unavailable" in outcome.response
    assert len(outcome.tool_calls) == 1
