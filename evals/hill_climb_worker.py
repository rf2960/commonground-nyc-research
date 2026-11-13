"""Score the frozen 50-case contract corpus against one checked-out revision.

This worker is copied into a detached historical worktree by ``evals.hill_climb``.
Missing capabilities count as failed cases instead of making an older revision
un-runnable. That keeps the same 50 held-out expectations across all revisions.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parent if _SCRIPT_DIR.name == "evals" else _SCRIPT_DIR
sys.path.insert(0, str(ROOT))
BRIEF_PATH = ROOT / "tests/research/fixtures/research_brief.json"
RESULT_PATH = ROOT / "tests/research/fixtures/round_2_results.json"
CAFE_ID = "cafe:gplaces:fixture-expansion-cafe"


def _replace_fact(facts, *, predicate: str, value: Any, subject_id: str | None = None):
    matches = 0
    updated = []
    for fact in facts:
        if fact.predicate == predicate and (
            subject_id is None or fact.subject_id == subject_id
        ):
            updated.append(fact.model_copy(update={"value": value}))
            matches += 1
        else:
            updated.append(fact)
    if matches != 1:
        raise ValueError(f"expected one {predicate!r} fact; found {matches}")
    return tuple(updated)


def _remove_fact(facts, *, predicate: str, subject_id: str | None = None):
    removed = tuple(
        fact
        for fact in facts
        if fact.predicate == predicate
        and (subject_id is None or fact.subject_id == subject_id)
    )
    if len(removed) != 1:
        raise ValueError(f"expected one removable {predicate!r} fact")
    return tuple(fact for fact in facts if fact is not removed[0]), removed[0]


def _case(case_id: str, slice_name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "slice": slice_name,
        "passed": passed,
        "detail": detail,
    }


def _feasibility_cases() -> tuple[list[dict[str, Any]], bool]:
    try:
        from commonground.research import (  # type: ignore
            Fact,
            MissingEvidence,
            ResearchBrief,
            ResearchResult,
            evaluate_cafe_feasibility,
        )
    except (ImportError, AttributeError):
        return (
            [
                _case(
                    f"contract-feasibility-capability-{index:03d}",
                    "feasibility_contracts",
                    False,
                    "deterministic feasibility capability unavailable",
                )
                for index in range(1, 41)
            ],
            False,
        )

    brief = ResearchBrief.model_validate(json.loads(BRIEF_PATH.read_text(encoding="utf-8")))
    results = tuple(
        ResearchResult.model_validate(item)
        for item in json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    )
    base_facts = tuple(fact for result in results for fact in result.facts)
    cases: list[dict[str, Any]] = []

    for index in range(10):
        facts = base_facts
        for traveler_id, minutes in (
            ("traveler:alice", 25 + index),
            ("traveler:bob", 20 + index),
            ("traveler:carol", 30 + index),
        ):
            facts = _replace_fact(
                facts,
                predicate="transit_duration_minutes",
                subject_id=traveler_id,
                value=minutes,
            )
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts)
        cases.append(
            _case(
                f"contract-feasible-{index + 1:03d}",
                "feasible_boundaries",
                result.status == "FEASIBLE",
                result.status,
            )
        )

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
        reason_codes = {reason.code for reason in result.reasons}
        cases.append(
            _case(
                f"contract-commute-limit-{index + 1:03d}",
                "commute_limit_blocker",
                result.status == "COMMUTE_LIMIT_EXCEEDED"
                and "TRAVELER_LIMIT_EXCEEDED" in reason_codes,
                f"{result.status}:{sorted(reason_codes)}",
            )
        )

    mutations = (
        ("business_status", "CLOSED_TEMPORARILY", "CAFE_NOT_OPERATIONAL"),
        ("rating", 4.2, "RATING_BELOW_MINIMUM"),
        ("price_level", 4, "PRICE_LEVEL_NOT_ALLOWED"),
        ("open_at_meeting_time", False, "CAFE_NOT_OPEN_AT_MEETING_TIME"),
    )
    for index in range(10):
        predicate, value, expected_reason = mutations[index % len(mutations)]
        facts = _replace_fact(base_facts, predicate=predicate, value=value)
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts)
        reason_codes = {reason.code for reason in result.reasons}
        cases.append(
            _case(
                f"contract-cafe-constraint-{index + 1:03d}",
                "cafe_constraint_blocker",
                result.status == "CAFE_CONSTRAINT_FAILED"
                and expected_reason in reason_codes,
                f"{result.status}:{sorted(reason_codes)}",
            )
        )

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
            missing_id=f"missing:hill-climb:r2:{index:03d}",
            candidate_id=CAFE_ID,
            subject_id=removed.subject_id if subject_id else None,
            field=predicate,
            reason_code="PROVIDER_FIELD_MISSING",
            detail="Frozen hill-climb case intentionally removes one required fact.",
            retryable=True,
            next_action="Retry the responsible provider adapter.",
        )
        result = evaluate_cafe_feasibility(brief, CAFE_ID, facts, (gap,))
        reason_codes = {reason.code for reason in result.reasons}
        cases.append(
            _case(
                f"contract-evidence-missing-{index:03d}",
                "evidence_insufficient",
                result.status == "EVIDENCE_INSUFFICIENT"
                and "REQUIRED_EVIDENCE_MISSING" in reason_codes,
                f"{result.status}:{sorted(reason_codes)}",
            )
        )
    return cases, True


def _intake_cases() -> tuple[list[dict[str, Any]], bool]:
    try:
        from commonground.research import (  # type: ignore
            ResearchIntake,
            TravelerIntake,
            find_intake_gaps,
        )
    except (ImportError, AttributeError):
        return (
            [
                _case(
                    f"contract-intake-{index:03d}",
                    "clarification_and_intake",
                    False,
                    "deterministic intake capability unavailable",
                )
                for index in range(1, 11)
            ],
            False,
        )

    travelers = (
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
    definitions = (
        (ResearchIntake(), ("TRAVELERS_REQUIRED", "MEETING_TIME_REQUIRED")),
        (ResearchIntake(travelers=(travelers[0],)), ("TRAVELERS_REQUIRED", "MEETING_TIME_REQUIRED")),
        (ResearchIntake(travelers=(travelers[0].model_copy(update={"input_location": None}), travelers[1]), meeting_time=meeting_time), ("ORIGIN_REQUIRED",)),
        (ResearchIntake(travelers=(travelers[0], travelers[1].model_copy(update={"max_commute_minutes": None})), meeting_time=meeting_time), ("COMMUTE_LIMIT_REQUIRED",)),
        (ResearchIntake(travelers=travelers), ("MEETING_TIME_REQUIRED",)),
        (ResearchIntake(travelers=travelers, meeting_time="2026-10-10T14:00:00"), ("MEETING_TIME_TIMEZONE_REQUIRED",)),
        (ResearchIntake(travelers=tuple(item.model_copy(update={"input_location": None}) for item in travelers), meeting_time=meeting_time), ("ORIGIN_REQUIRED",)),
        (ResearchIntake(travelers=tuple(item.model_copy(update={"max_commute_minutes": None}) for item in travelers), meeting_time=meeting_time), ("COMMUTE_LIMIT_REQUIRED",)),
        (ResearchIntake(travelers=(travelers[0].model_copy(update={"input_location": None, "max_commute_minutes": None}), travelers[1])), ("ORIGIN_REQUIRED", "COMMUTE_LIMIT_REQUIRED", "MEETING_TIME_REQUIRED")),
        (ResearchIntake(travelers=travelers, meeting_time=meeting_time), ()),
    )
    cases = []
    for index, (intake, expected) in enumerate(definitions, start=1):
        actual = tuple(gap.code for gap in find_intake_gaps(intake))
        cases.append(
            _case(
                f"contract-intake-{index:03d}",
                "clarification_and_intake",
                actual == expected,
                f"expected={expected};actual={actual}",
            )
        )
    return cases, True


def main() -> int:
    feasibility, feasibility_available = _feasibility_cases()
    intake, intake_available = _intake_cases()
    cases = feasibility + intake
    passed = sum(case["passed"] for case in cases)
    print(
        json.dumps(
            {
                "schema_version": "historical-contract-score-v1",
                "cases": len(cases),
                "passed": passed,
                "score": passed / len(cases),
                "capabilities": {
                    "deterministic_feasibility": feasibility_available,
                    "clarification_intake": intake_available,
                },
                "results": cases,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
