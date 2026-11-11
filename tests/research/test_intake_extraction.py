import json
from types import SimpleNamespace

import pytest

from commonground.research import (
    IntakeExtractionError,
    extract_research_intake,
    find_intake_gaps,
    intake_from_extraction_payload,
)


MESSAGES = [
    "Alex starts at Columbia University and can travel 35 minutes. "
    "Blair starts in Astoria and can travel 30 minutes. "
    "Meet October 10, 2026 at 2:00 PM Eastern Time."
]


def complete_payload():
    return {
        "meeting_time": "2026-10-10T14:00:00-04:00",
        "meeting_time_quote": "October 10, 2026 at 2:00 PM Eastern Time",
        "travelers": [
            {
                "identity_quote": "Alex",
                "origin_quote": "Columbia University",
                "max_commute_minutes": 35,
                "limit_quote": "Alex starts at Columbia University and can travel 35 minutes",
            },
            {
                "identity_quote": "Blair",
                "origin_quote": "Astoria",
                "max_commute_minutes": 30,
                "limit_quote": "Blair starts in Astoria and can travel 30 minutes",
            },
        ],
    }


def test_payload_builds_complete_intake_only_from_verbatim_quotes():
    intake = intake_from_extraction_payload(complete_payload(), MESSAGES)

    assert intake.meeting_time.isoformat() == "2026-10-10T14:00:00-04:00"
    assert [item.traveler_id for item in intake.travelers] == [
        "traveler:alex",
        "traveler:blair",
    ]
    assert [item.input_location for item in intake.travelers] == [
        "Columbia University",
        "Astoria",
    ]
    assert find_intake_gaps(intake) == ()


def test_payload_rejects_a_quote_not_present_in_user_text():
    payload = complete_payload()
    payload["travelers"][1]["origin_quote"] = "Jamaica"

    with pytest.raises(IntakeExtractionError, match="not found"):
        intake_from_extraction_payload(payload, MESSAGES)


@pytest.mark.parametrize(
    ("cafe_request", "rating", "price"),
    [
        ("Find a moderate-price cafe rated at least 4.3.", 4.3, 2),
        ("Find a cafe with a minimum rating of 5 stars and price level 1.", 5, 1),
    ],
)
def test_cafe_constraints_are_preserved_when_model_extracts_only_travelers_and_time(
    cafe_request, rating, price
):
    intake = intake_from_extraction_payload(complete_payload(), [*MESSAGES, cafe_request])

    assert intake.cafe_constraints.min_rating == rating
    assert intake.cafe_constraints.price_levels == (price,)


def test_payload_keeps_ambiguous_time_missing_for_deterministic_clarification():
    payload = complete_payload()
    payload["meeting_time"] = None
    payload["meeting_time_quote"] = None

    intake = intake_from_extraction_payload(payload, MESSAGES)

    assert [gap.code for gap in find_intake_gaps(intake)] == [
        "MEETING_TIME_REQUIRED"
    ]


def test_payload_rejects_naive_normalized_time_even_with_a_real_quote():
    payload = complete_payload()
    payload["meeting_time"] = "2026-10-10T14:00:00"

    with pytest.raises(IntakeExtractionError, match="explicit UTC offset"):
        intake_from_extraction_payload(payload, MESSAGES)


def test_model_boundary_uses_no_tools_and_parses_json():
    captured = {}

    def completion(**kwargs):
        captured.update(kwargs)
        message = SimpleNamespace(content=json.dumps(complete_payload()))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    intake = extract_research_intake(
        MESSAGES,
        model="test-model",
        vertex_location="global",
        completion=completion,
    )

    assert find_intake_gaps(intake) == ()
    assert captured["model"] == "test-model"
    assert captured["response_format"] == {"type": "json_object"}
    assert "tools" not in captured
    assert captured["messages"][0]["role"] == "system"


def test_model_boundary_rejects_non_json_output():
    def completion(**_kwargs):
        message = SimpleNamespace(content="not json")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    with pytest.raises(IntakeExtractionError, match="invalid intake JSON"):
        extract_research_intake(
            MESSAGES,
            model="test-model",
            vertex_location="global",
            completion=completion,
        )
