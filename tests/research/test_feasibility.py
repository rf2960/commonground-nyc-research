import json
from pathlib import Path

import pytest

from commonground.research import (
    CafeConstraints,
    Fact,
    MissingEvidence,
    ResearchBrief,
    ResearchResult,
    evaluate_all_cafes,
    evaluate_cafe_feasibility,
)


FIXTURES = Path(__file__).parent / "fixtures"
CAFE_ID = "cafe:gplaces:fixture-expansion-cafe"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def round_two_facts() -> tuple[Fact, ...]:
    results = [
        ResearchResult.model_validate(item) for item in fixture("round_2_results.json")
    ]
    return tuple(fact for result in results for fact in result.facts)


def changed_fact(fact: Fact, **changes) -> Fact:
    payload = fact.model_dump(mode="json")
    payload.update(changes)
    return Fact.model_validate(payload)


def replace_fact(facts: tuple[Fact, ...], fact_id: str, **changes) -> tuple[Fact, ...]:
    return tuple(
        changed_fact(fact, **changes) if fact.fact_id == fact_id else fact
        for fact in facts
    )


def test_round_two_fixture_computes_expected_feasible_result():
    expected = fixture("expected_feasibility.json")

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, round_two_facts())

    assert result.model_dump(mode="json") == expected


def test_exact_route_over_limit_dominates_cafe_success():
    facts = replace_fact(round_two_facts(), "fact:transit:r2:001", value=36)

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts)

    assert result.status == "COMMUTE_LIMIT_EXCEEDED"
    assert [reason.code for reason in result.reasons] == ["TRAVELER_LIMIT_EXCEEDED"]
    reason = result.reasons[0]
    assert reason.traveler_id == "traveler:alice"
    assert reason.actual_minutes == 36
    assert reason.limit_minutes == 35
    assert reason.input_fact_ids == ("fact:transit:r2:001",)


@pytest.mark.parametrize(
    ("fact_id", "value", "expected_code"),
    [
        ("fact:cafe:r2:005", 4.0, "RATING_BELOW_MINIMUM"),
        ("fact:cafe:r2:006", 3, "PRICE_LEVEL_NOT_ALLOWED"),
        ("fact:cafe:r2:007", "CLOSED_TEMPORARILY", "CAFE_NOT_OPERATIONAL"),
        ("fact:cafe:r2:008", False, "CAFE_NOT_OPEN_AT_MEETING_TIME"),
    ],
)
def test_each_cafe_hard_constraint_has_a_deterministic_blocker(
    fact_id, value, expected_code
):
    facts = replace_fact(round_two_facts(), fact_id, value=value)

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts)

    assert result.status == "CAFE_CONSTRAINT_FAILED"
    assert expected_code in [reason.code for reason in result.reasons]


def test_missing_hours_stays_insufficient_and_cites_the_gap():
    facts = tuple(
        fact for fact in round_two_facts() if fact.fact_id != "fact:cafe:r2:008"
    )
    gap = MissingEvidence(
        missing_id="missing:cafe:r2:001",
        candidate_id=CAFE_ID,
        field="open_at_meeting_time",
        reason_code="PROVIDER_FIELD_MISSING",
        detail="Regular opening periods were absent.",
        retryable=False,
        next_action="Ask the user to verify with the venue.",
    )

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts, [gap])

    assert result.status == "EVIDENCE_INSUFFICIENT"
    assert result.reasons[0].code == "REQUIRED_EVIDENCE_MISSING"
    assert result.reasons[0].input_missing_ids == ("missing:cafe:r2:001",)


def test_missing_route_is_specific_to_one_traveler():
    facts = tuple(
        fact for fact in round_two_facts() if fact.fact_id != "fact:transit:r2:002"
    )
    gap = MissingEvidence(
        missing_id="missing:transit:r2:001",
        candidate_id=CAFE_ID,
        subject_id="traveler:bob",
        field="transit_duration_minutes",
        reason_code="ROUTE_UNAVAILABLE",
        detail="No exact-cafe route was returned for Bob.",
        retryable=False,
        next_action="Report Bob's exact commute as unknown.",
    )

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts, [gap])

    assert result.status == "EVIDENCE_INSUFFICIENT"
    reason = result.reasons[0]
    assert reason.traveler_id == "traveler:bob"
    assert reason.input_missing_ids == ("missing:transit:r2:001",)


def test_untracked_absence_is_a_contract_error_not_a_silent_unknown():
    facts = tuple(
        fact for fact in round_two_facts() if fact.fact_id != "fact:cafe:r2:005"
    )

    with pytest.raises(ValueError, match="absent without a MissingEvidence"):
        evaluate_cafe_feasibility(brief(), CAFE_ID, facts)


def test_conflicting_newest_facts_make_evidence_insufficient():
    facts = round_two_facts()
    rating = next(fact for fact in facts if fact.fact_id == "fact:cafe:r2:005")
    conflict = changed_fact(rating, fact_id="fact:cafe:r2:009", value=4.1)

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, (*facts, conflict))

    assert result.status == "EVIDENCE_INSUFFICIENT"
    reason = next(reason for reason in result.reasons if reason.code == "CONFLICTING_FACTS")
    assert set(reason.input_fact_ids) == {
        "fact:cafe:r2:005",
        "fact:cafe:r2:009",
    }


def test_duration_equal_to_limit_passes_without_rounding():
    facts = replace_fact(round_two_facts(), "fact:transit:r2:002", value=30)

    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts)

    assert result.status == "FEASIBLE"


def test_inactive_optional_filters_do_not_require_unavailable_facts():
    base = brief()
    relaxed_brief = base.model_copy(
        update={
            "cafe_constraints": CafeConstraints(
                min_rating=0,
                price_levels=(),
                require_open=False,
            )
        }
    )
    optional_fact_ids = {
        "fact:cafe:r2:005",
        "fact:cafe:r2:006",
        "fact:cafe:r2:008",
    }
    facts = tuple(
        fact for fact in round_two_facts() if fact.fact_id not in optional_fact_ids
    )

    result = evaluate_cafe_feasibility(relaxed_brief, CAFE_ID, facts)

    assert result.status == "FEASIBLE"


def test_evaluate_all_cafes_is_stable_and_rejects_empty_evidence():
    results = evaluate_all_cafes(brief(), round_two_facts())

    assert [result.cafe_id for result in results] == [CAFE_ID]

    with pytest.raises(ValueError, match="no cafe evidence"):
        evaluate_all_cafes(brief(), [])


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_nonfinite_route_duration_cannot_be_feasible(value):
    facts = replace_fact(round_two_facts(), 'fact:transit:r2:001', value=value)
    result = evaluate_cafe_feasibility(brief(), CAFE_ID, facts)
    assert result.status == 'EVIDENCE_INSUFFICIENT'
    assert any(reason.code == 'INVALID_FACT_VALUE' for reason in result.reasons)


@pytest.mark.parametrize('coordinates', [
    {'lat': float('nan'), 'lng': -73.9}, {'lat': 91, 'lng': -73.9},
    {'lat': 40.7, 'lng': 181}, {'lat': True, 'lng': -73.9},
])
def test_invalid_exact_coordinates_cannot_support_recommendation(coordinates):
    facts = replace_fact(round_two_facts(), 'fact:cafe:r2:004', value=coordinates)
    assert evaluate_cafe_feasibility(brief(), CAFE_ID, facts).status == 'EVIDENCE_INSUFFICIENT'
