from datetime import datetime

import pytest
from pydantic import ValidationError

import app as webapp
from commonground.research import (
    CafeConstraints,
    ResearchIntake,
    TravelerIntake,
    build_research_brief,
    clarification_message,
    find_intake_gaps,
)


def complete_intake() -> ResearchIntake:
    return ResearchIntake(
        question="Can expansion find a feasible cafe?",
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
        cafe_constraints=CafeConstraints(
            min_rating=4.3,
            price_levels=(1, 2),
            require_open=True,
        ),
    )


def test_empty_intake_requires_people_and_meeting_time_without_calling_tools():
    gaps = find_intake_gaps(ResearchIntake())

    assert [gap.code for gap in gaps] == [
        "TRAVELERS_REQUIRED",
        "MEETING_TIME_REQUIRED",
    ]
    message = clarification_message(ResearchIntake())
    assert "at least two travelers" in message
    assert "meeting arrival date and time" in message


def test_clarification_names_only_the_travelers_with_missing_fields():
    intake = ResearchIntake(
        meeting_time=datetime(2026, 10, 10, 14, 0),
        travelers=(
            TravelerIntake(
                traveler_id="traveler:alice",
                input_location="Columbia University",
                max_commute_minutes=35,
            ),
            TravelerIntake(traveler_id="traveler:bob"),
        ),
    )

    gaps = find_intake_gaps(intake)

    assert [gap.code for gap in gaps] == [
        "ORIGIN_REQUIRED",
        "COMMUTE_LIMIT_REQUIRED",
        "MEETING_TIME_TIMEZONE_REQUIRED",
    ]
    assert gaps[0].traveler_ids == ("traveler:bob",)
    assert gaps[1].traveler_ids == ("traveler:bob",)
    assert "traveler:alice" not in clarification_message(intake)
    assert "explicit timezone" in clarification_message(intake)


def test_complete_intake_builds_immutable_brief_from_project_one_outputs():
    intake = complete_intake()
    brief = build_research_brief(
        intake,
        session_id="session-123",
        resolved_locations=[
            {"traveler_id": "traveler:alice", "lat": 40.8075, "lng": -73.9626},
            {"traveler_id": "traveler:bob", "lat": 40.7644, "lng": -73.9235},
        ],
        candidate_areas=[
            {"area": "Union Square", "lat": 40.7359, "lng": -73.9911},
            {
                "area": "Downtown Brooklyn",
                "lat": 40.6928,
                "lng": -73.9903,
            },
        ],
    )

    assert brief.research_id == "research:session-123:1"
    assert brief.session_id == "session-123"
    assert [item.traveler_id for item in brief.travelers] == [
        "traveler:alice",
        "traveler:bob",
    ]
    assert [item.candidate_id for item in brief.initial_candidates] == [
        "area:initial:union-square",
        "area:initial:downtown-brooklyn",
    ]
    assert brief.cafe_constraints == intake.cafe_constraints
    assert find_intake_gaps(intake) == ()

    with pytest.raises(ValidationError):
        brief.question = "mutated"


def test_brief_builder_rejects_unresolved_or_unexpected_traveler_ids():
    with pytest.raises(ValueError, match="must match intake"):
        build_research_brief(
            complete_intake(),
            session_id="session-123",
            resolved_locations=[
                {
                    "traveler_id": "traveler:alice",
                    "lat": 40.8075,
                    "lng": -73.9626,
                },
                {"traveler_id": "traveler:carol", "lat": 40.7, "lng": -73.9},
            ],
            candidate_areas=[
                {"area": "Union Square", "lat": 40.7359, "lng": -73.9911}
            ],
        )


def test_brief_builder_rejects_candidate_names_that_collapse_to_same_id():
    with pytest.raises(ValueError, match="duplicate initial candidate ID"):
        build_research_brief(
            complete_intake(),
            session_id="session-123",
            resolved_locations=[
                {
                    "traveler_id": "traveler:alice",
                    "lat": 40.8075,
                    "lng": -73.9626,
                },
                {"traveler_id": "traveler:bob", "lat": 40.7644, "lng": -73.9235},
            ],
            candidate_areas=[
                {"area": "Union Square", "lat": 40.7359, "lng": -73.9911},
                {"area": "Union--Square", "lat": 40.736, "lng": -73.991},
            ],
        )


def test_duplicate_intake_traveler_ids_are_rejected():
    with pytest.raises(ValidationError, match="traveler IDs must be unique"):
        ResearchIntake(
            travelers=(
                TravelerIntake(traveler_id="traveler:alice"),
                TravelerIntake(traveler_id="traveler:alice"),
            )
        )


def test_chat_uses_partial_intake_for_specific_clarification():
    webapp.sessions.clear()
    webapp.session_last_seen.clear()
    intake = ResearchIntake(
        travelers=(
            TravelerIntake(
                traveler_id="traveler:alice",
                input_location="Columbia University",
                max_commute_minutes=35,
            ),
            TravelerIntake(
                traveler_id="traveler:bob",
                input_location="Astoria",
            ),
        )
    )

    response = webapp.chat(
        webapp.ChatRequest(
            message="Can you start now?",
            mode="research",
            research_intake=intake,
        )
    )

    assert response.tool_calls == []
    assert "traveler:bob" in response.response
    assert "maximum one-way commute" in response.response
    assert "meeting arrival date and time" in response.response
    assert "traveler:alice" not in response.response
