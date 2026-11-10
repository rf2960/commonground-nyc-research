"""Generate and score 50 provenance-recorded deterministic contract cases.

These cases exercise the same intake and hard-constraint functions used by the app.
They are deliberately labelled synthetic: provider values are mutations of the fixed
vertical-slice fixture, not claims that a live Google or MTA request was made.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from commonground.research import (
    Fact,
    MissingEvidence,
    ResearchBrief,
    ResearchIntake,
    ResearchResult,
    TravelerIntake,
    evaluate_cafe_feasibility,
    find_intake_gaps,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = "tests/research/fixtures/research_brief.json"
RESULT_PATH = "tests/research/fixtures/round_2_results.json"
CAFE_ID = "cafe:gplaces:fixture-expansion-cafe"
PROVENANCE = {
    "kind": "gold",
    "generation": "synthetic boundary mutation",
    "source_paths": [BRIEF_PATH, RESULT_PATH],
    "live_provider_observation": False,
    "prompt_reuse_prohibited": True,
    "description": (
        "Deterministic cases derived from the Project 2 fixed-data vertical slice; "
        "values are not represented as live provider observations."
    ),
}


def _read_json(relative_path: str) -> Any:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _base_evidence() -> tuple[ResearchBrief, tuple[Fact, ...]]:
    brief = ResearchBrief.model_validate(_read_json(BRIEF_PATH))
    results = tuple(
        ResearchResult.model_validate(item) for item in _read_json(RESULT_PATH)
    )
    facts = tuple(fact for result in results for fact in result.facts)
    return brief, facts


def _replace_fact(
    facts: tuple[Fact, ...],
    *,
    predicate: str,
    value: Any,
    subject_id: str | None = None,
) -> tuple[Fact, ...]:
    matches = 0
    updated: list[Fact] = []
    for fact in facts:
        if fact.predicate == predicate and (
            subject_id is None or fact.subject_id == subject_id
        ):
            updated.append(fact.model_copy(update={"value": value}))
            matches += 1
        else:
            updated.append(fact)
    if matches != 1:
        raise ValueError(
            f"expected one fact for predicate={predicate!r}, subject={subject_id!r}; "
            f"found {matches}"
        )
    return tuple(updated)


def _remove_fact(
    facts: tuple[Fact, ...],
    *,
    predicate: str,
    subject_id: str | None = None,
) -> tuple[tuple[Fact, ...], Fact]:
    removed = tuple(
        fact
        for fact in facts
        if fact.predicate == predicate
        and (subject_id is None or fact.subject_id == subject_id)
    )
    if len(removed) != 1:
        raise ValueError(
            f"expected one removable fact for {predicate!r}; found {len(removed)}"
        )
    return tuple(fact for fact in facts if fact is not removed[0]), removed[0]


def _case_record(
    *,
    case_id: str,
    slice_name: str,
    expected_status: str,
    expected_reason_codes: tuple[str, ...],
    actual_status: str,
    actual_reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    passed = actual_status == expected_status and set(expected_reason_codes).issubset(
        actual_reason_codes
    )
    return {
        "case_id": case_id,
        "owner": "ruochen",
        "slice": slice_name,
        "provenance": PROVENANCE,
        "expected": {
            "status": expected_status,
            "required_reason_codes": list(expected_reason_codes),
        },
        "actual": {
            "status": actual_status,
            "reason_codes": list(actual_reason_codes),
        },
        "passed": passed,
    }


def _feasibility_cases() -> list[dict[str, Any]]:
    brief, base_facts = _base_evidence()
    cases: list[dict[str, Any]] = []

    # Ten feasible cases include exact-limit equality and near-boundary durations.
    for index in range(10):
        facts = base_facts
        alice = 25 + index
        bob = 20 + index
        carol = 30 + index
        for traveler_id, minutes in (
            ("traveler:alice", alice),
            ("traveler:bob", bob),
            ("traveler:carol", carol),
        ):
            facts = _replace_fact(
                facts,
                predicate="transit_duration_minutes",
                subject_id=traveler_id,
                value=minutes,
            )
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts)
        cases.append(
            _case_record(
                case_id=f"contract-feasible-{index + 1:03d}",
                slice_name="feasible_boundaries",
                expected_status="FEASIBLE",
                expected_reason_codes=(),
                actual_status=result.status,
                actual_reason_codes=tuple(reason.code for reason in result.reasons),
            )
        )

    # Ten cases prove one minute over a named traveler's hard limit is not relaxed.
    traveler_cycle = tuple(traveler.traveler_id for traveler in brief.travelers)
    limits = {
        traveler.traveler_id: traveler.max_commute_minutes
        for traveler in brief.travelers
    }
    for index in range(10):
        traveler_id = traveler_cycle[index % len(traveler_cycle)]
        facts = _replace_fact(
            base_facts,
            predicate="transit_duration_minutes",
            subject_id=traveler_id,
            value=limits[traveler_id] + 1 + index,
        )
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts)
        cases.append(
            _case_record(
                case_id=f"contract-commute-limit-{index + 1:03d}",
                slice_name="commute_limit_blocker",
                expected_status="COMMUTE_LIMIT_EXCEEDED",
                expected_reason_codes=("TRAVELER_LIMIT_EXCEEDED",),
                actual_status=result.status,
                actual_reason_codes=tuple(reason.code for reason in result.reasons),
            )
        )

    # Ten cafe-condition failures rotate across every deterministic cafe predicate.
    cafe_mutations = (
        ("business_status", "CLOSED_TEMPORARILY", "CAFE_NOT_OPERATIONAL"),
        ("rating", 4.2, "RATING_BELOW_MINIMUM"),
        ("price_level", 4, "PRICE_LEVEL_NOT_ALLOWED"),
        ("open_at_meeting_time", False, "CAFE_NOT_OPEN_AT_MEETING_TIME"),
    )
    for index in range(10):
        predicate, value, reason_code = cafe_mutations[index % len(cafe_mutations)]
        facts = _replace_fact(base_facts, predicate=predicate, value=value)
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts)
        cases.append(
            _case_record(
                case_id=f"contract-cafe-constraint-{index + 1:03d}",
                slice_name="cafe_constraint_blocker",
                expected_status="CAFE_CONSTRAINT_FAILED",
                expected_reason_codes=(reason_code,),
                actual_status=result.status,
                actual_reason_codes=tuple(reason.code for reason in result.reasons),
            )
        )

    # Ten missing-evidence cases prove unknown never becomes false or feasible.
    missing_fields = (
        ("name", None),
        ("address", None),
        ("coordinates", None),
        ("business_status", None),
        ("rating", None),
        ("price_level", None),
        ("open_at_meeting_time", None),
        ("transit_duration_minutes", "traveler:alice"),
        ("transit_duration_minutes", "traveler:bob"),
        ("transit_duration_minutes", "traveler:carol"),
    )
    for index, (predicate, subject_id) in enumerate(missing_fields, start=1):
        facts, removed = _remove_fact(
            base_facts, predicate=predicate, subject_id=subject_id
        )
        gap = MissingEvidence(
            missing_id=f"missing:corpus:r2:{index:03d}",
            candidate_id=CAFE_ID,
            subject_id=removed.subject_id if subject_id else None,
            field=predicate,
            reason_code="PROVIDER_FIELD_MISSING",
            detail="Synthetic corpus case intentionally removes one required fact.",
            retryable=True,
            next_action="Retry the responsible provider adapter.",
        )
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts, (gap,))
        cases.append(
            _case_record(
                case_id=f"contract-evidence-missing-{index:03d}",
                slice_name="evidence_insufficient",
                expected_status="EVIDENCE_INSUFFICIENT",
                expected_reason_codes=("REQUIRED_EVIDENCE_MISSING",),
                actual_status=result.status,
                actual_reason_codes=tuple(reason.code for reason in result.reasons),
            )
        )

    return cases


def _intake_cases() -> list[dict[str, Any]]:
    complete_travelers = (
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
    )
    meeting_time = "2026-10-10T14:00:00-04:00"
    definitions: tuple[tuple[ResearchIntake, tuple[str, ...]], ...] = (
        (ResearchIntake(), ("TRAVELERS_REQUIRED", "MEETING_TIME_REQUIRED")),
        (
            ResearchIntake(travelers=(complete_travelers[0],)),
            ("TRAVELERS_REQUIRED", "MEETING_TIME_REQUIRED"),
        ),
        (
            ResearchIntake(
                travelers=(
                    complete_travelers[0].model_copy(update={"input_location": None}),
                    complete_travelers[1],
                ),
                meeting_time=meeting_time,
            ),
            ("ORIGIN_REQUIRED",),
        ),
        (
            ResearchIntake(
                travelers=(
                    complete_travelers[0],
                    complete_travelers[1].model_copy(
                        update={"max_commute_minutes": None}
                    ),
                ),
                meeting_time=meeting_time,
            ),
            ("COMMUTE_LIMIT_REQUIRED",),
        ),
        (
            ResearchIntake(travelers=complete_travelers),
            ("MEETING_TIME_REQUIRED",),
        ),
        (
            ResearchIntake(
                travelers=complete_travelers,
                meeting_time="2026-10-10T14:00:00",
            ),
            ("MEETING_TIME_TIMEZONE_REQUIRED",),
        ),
        (
            ResearchIntake(
                travelers=tuple(
                    traveler.model_copy(update={"input_location": None})
                    for traveler in complete_travelers
                ),
                meeting_time=meeting_time,
            ),
            ("ORIGIN_REQUIRED",),
        ),
        (
            ResearchIntake(
                travelers=tuple(
                    traveler.model_copy(update={"max_commute_minutes": None})
                    for traveler in complete_travelers
                ),
                meeting_time=meeting_time,
            ),
            ("COMMUTE_LIMIT_REQUIRED",),
        ),
        (
            ResearchIntake(
                travelers=(
                    complete_travelers[0].model_copy(
                        update={"input_location": None, "max_commute_minutes": None}
                    ),
                    complete_travelers[1],
                )
            ),
            (
                "ORIGIN_REQUIRED",
                "COMMUTE_LIMIT_REQUIRED",
                "MEETING_TIME_REQUIRED",
            ),
        ),
        (
            ResearchIntake(
                travelers=complete_travelers,
                meeting_time=meeting_time,
            ),
            (),
        ),
    )
    cases: list[dict[str, Any]] = []
    for index, (intake, expected_codes) in enumerate(definitions, start=1):
        actual_codes = tuple(gap.code for gap in find_intake_gaps(intake))
        cases.append(
            {
                "case_id": f"contract-intake-{index:03d}",
                "owner": "ruochen",
                "slice": "clarification_and_intake",
                "provenance": {
                    **PROVENANCE,
                    "source_paths": ["commonground/research/intake.py"],
                },
                "expected": {"gap_codes": list(expected_codes)},
                "actual": {"gap_codes": list(actual_codes)},
                "passed": actual_codes == expected_codes,
            }
        )
    return cases


def evaluate_contract_corpus() -> dict[str, Any]:
    """Return a stable aggregate result for the 50-case contract corpus."""

    cases = _feasibility_cases() + _intake_cases()
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("contract corpus case IDs must be unique")
    slices = Counter(case["slice"] for case in cases)
    passed = sum(case["passed"] for case in cases)
    return {
        "schema_version": "contract-corpus-result-v1",
        "cases": len(cases),
        "passed": passed,
        "score": passed / len(cases),
        "slices": dict(sorted(slices.items())),
        "results": cases,
    }


def main() -> int:
    result = evaluate_contract_corpus()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["passed"] == result["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
