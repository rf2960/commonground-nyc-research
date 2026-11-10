"""Deterministic hard-constraint evaluation over normalized research evidence."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Iterable

from .models import (
    Fact,
    FeasibilityReason,
    FeasibilityResult,
    MissingEvidence,
    ResearchBrief,
)


RULE_VERSION = "feasibility-v1"


def _same_instant(raw: Any, expected: datetime) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return False
    return parsed == expected


def _matching_facts(
    facts: tuple[Fact, ...],
    cafe_id: str,
    predicate: str,
    *,
    subject_id: str | None = None,
    meeting_time: datetime | None = None,
    exact_route: bool = False,
) -> tuple[Fact, ...]:
    matches = []
    for fact in facts:
        if fact.candidate_id != cafe_id or fact.predicate != predicate:
            continue
        if subject_id is not None and fact.subject_id != subject_id:
            continue
        if exact_route:
            if fact.valid_for.get("destination_kind") != "exact_cafe":
                continue
            if meeting_time is None or not _same_instant(
                fact.valid_for.get("arrival_time"), meeting_time
            ):
                continue
        if predicate == "open_at_meeting_time" and meeting_time is not None:
            if not _same_instant(fact.valid_for.get("meeting_time"), meeting_time):
                continue
        matches.append(fact)
    return tuple(matches)


def _matching_missing(
    missing: tuple[MissingEvidence, ...],
    cafe_id: str,
    field: str,
    subject_id: str | None,
) -> tuple[MissingEvidence, ...]:
    return tuple(
        gap
        for gap in missing
        if gap.candidate_id == cafe_id
        and gap.field == field
        and gap.subject_id == subject_id
    )


def _current_fact(
    matches: tuple[Fact, ...],
) -> tuple[Fact | None, tuple[Fact, ...]]:
    """Return the newest unambiguous fact, or conflicting newest facts."""

    if not matches:
        return None, ()
    latest_time = max(fact.observed_at for fact in matches)
    latest = tuple(fact for fact in matches if fact.observed_at == latest_time)
    first_value = latest[0].value
    if any(fact.value != first_value for fact in latest[1:]):
        return None, latest
    return latest[0], ()


def _required_fact(
    *,
    facts: tuple[Fact, ...],
    missing: tuple[MissingEvidence, ...],
    cafe_id: str,
    predicate: str,
    evidence_reasons: list[FeasibilityReason],
    subject_id: str | None = None,
    meeting_time: datetime | None = None,
    exact_route: bool = False,
) -> Fact | None:
    candidates = _matching_facts(
        facts,
        cafe_id,
        predicate,
        subject_id=subject_id,
        meeting_time=meeting_time,
        exact_route=exact_route,
    )
    fact, conflicts = _current_fact(candidates)
    if conflicts:
        evidence_reasons.append(
            FeasibilityReason(
                code="CONFLICTING_FACTS",
                traveler_id=subject_id if subject_id and subject_id.startswith("traveler:") else None,
                input_fact_ids=tuple(item.fact_id for item in conflicts),
            )
        )
        return None
    if fact is not None:
        return fact

    gaps = _matching_missing(missing, cafe_id, predicate, subject_id)
    if not gaps:
        subject_note = f" for {subject_id}" if subject_id else ""
        raise ValueError(
            f"required {predicate}{subject_note} is absent without a MissingEvidence record"
        )
    evidence_reasons.append(
        FeasibilityReason(
            code="REQUIRED_EVIDENCE_MISSING",
            traveler_id=subject_id if subject_id and subject_id.startswith("traveler:") else None,
            input_missing_ids=tuple(gap.missing_id for gap in gaps),
        )
    )
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _invalid_fact_reason(fact: Fact, *, traveler_id: str | None = None) -> FeasibilityReason:
    return FeasibilityReason(
        code="INVALID_FACT_VALUE",
        traveler_id=traveler_id,
        input_fact_ids=(fact.fact_id,),
    )


def evaluate_cafe_feasibility(
    brief: ResearchBrief,
    cafe_id: str,
    facts: Iterable[Fact],
    missing: Iterable[MissingEvidence] = (),
) -> FeasibilityResult:
    """Evaluate one exact cafe without model arithmetic or constraint relaxation.

    Absence must already be normalized as MissingEvidence. An untracked required field
    is a contract error, because silently treating it as missing would hide an adapter
    bug from the Lead and Writer.
    """

    if not cafe_id.startswith("cafe:gplaces:"):
        raise ValueError("cafe_id must be a stable Google Places cafe ID")

    fact_records = tuple(facts)
    missing_records = tuple(missing)
    evidence_reasons: list[FeasibilityReason] = []
    commute_reasons: list[FeasibilityReason] = []
    cafe_reasons: list[FeasibilityReason] = []

    required_cafe_fields = (
        "parent_candidate_id",
        "name",
        "address",
        "coordinates",
        "business_status",
    )
    cafe_facts: dict[str, Fact | None] = {
        field: _required_fact(
            facts=fact_records,
            missing=missing_records,
            cafe_id=cafe_id,
            predicate=field,
            evidence_reasons=evidence_reasons,
        )
        for field in required_cafe_fields
    }

    parent = cafe_facts["parent_candidate_id"]
    if parent is not None and (
        not isinstance(parent.value, str) or not parent.value.startswith("area:")
    ):
        evidence_reasons.append(_invalid_fact_reason(parent))

    for text_field in ("name", "address"):
        fact = cafe_facts[text_field]
        if fact is not None and (
            not isinstance(fact.value, str) or not fact.value.strip()
        ):
            evidence_reasons.append(_invalid_fact_reason(fact))

    coordinates = cafe_facts["coordinates"]
    if coordinates is not None:
        value = coordinates.value
        if not isinstance(value, dict) or _number(value.get("lat")) is None or _number(
            value.get("lng")
        ) is None:
            evidence_reasons.append(_invalid_fact_reason(coordinates))
        elif not (-90 <= value["lat"] <= 90 and -180 <= value["lng"] <= 180):
            evidence_reasons.append(_invalid_fact_reason(coordinates))

    business_status = cafe_facts["business_status"]
    if business_status is not None:
        if not isinstance(business_status.value, str):
            evidence_reasons.append(_invalid_fact_reason(business_status))
        elif business_status.value != "OPERATIONAL":
            cafe_reasons.append(
                FeasibilityReason(
                    code="CAFE_NOT_OPERATIONAL",
                    input_fact_ids=(business_status.fact_id,),
                )
            )

    if brief.cafe_constraints.min_rating > 0:
        rating = _required_fact(
            facts=fact_records,
            missing=missing_records,
            cafe_id=cafe_id,
            predicate="rating",
            evidence_reasons=evidence_reasons,
        )
        if rating is not None:
            rating_value = _number(rating.value)
            if rating_value is None or not 0 <= rating_value <= 5:
                evidence_reasons.append(_invalid_fact_reason(rating))
            elif rating_value < brief.cafe_constraints.min_rating:
                cafe_reasons.append(
                    FeasibilityReason(
                        code="RATING_BELOW_MINIMUM",
                        input_fact_ids=(rating.fact_id,),
                    )
                )

    if brief.cafe_constraints.price_levels:
        price = _required_fact(
            facts=fact_records,
            missing=missing_records,
            cafe_id=cafe_id,
            predicate="price_level",
            evidence_reasons=evidence_reasons,
        )
        if price is not None:
            if isinstance(price.value, bool) or not isinstance(price.value, int):
                evidence_reasons.append(_invalid_fact_reason(price))
            elif price.value not in brief.cafe_constraints.price_levels:
                cafe_reasons.append(
                    FeasibilityReason(
                        code="PRICE_LEVEL_NOT_ALLOWED",
                        input_fact_ids=(price.fact_id,),
                    )
                )

    if brief.cafe_constraints.require_open:
        opening = _required_fact(
            facts=fact_records,
            missing=missing_records,
            cafe_id=cafe_id,
            predicate="open_at_meeting_time",
            evidence_reasons=evidence_reasons,
            meeting_time=brief.meeting_time,
        )
        if opening is not None:
            if not isinstance(opening.value, bool):
                evidence_reasons.append(_invalid_fact_reason(opening))
            elif not opening.value:
                cafe_reasons.append(
                    FeasibilityReason(
                        code="CAFE_NOT_OPEN_AT_MEETING_TIME",
                        input_fact_ids=(opening.fact_id,),
                    )
                )

    for traveler in brief.travelers:
        duration = _required_fact(
            facts=fact_records,
            missing=missing_records,
            cafe_id=cafe_id,
            predicate="transit_duration_minutes",
            evidence_reasons=evidence_reasons,
            subject_id=traveler.traveler_id,
            meeting_time=brief.meeting_time,
            exact_route=True,
        )
        if duration is None:
            continue
        minutes = _number(duration.value)
        if minutes is None or minutes < 0:
            evidence_reasons.append(
                _invalid_fact_reason(duration, traveler_id=traveler.traveler_id)
            )
        elif minutes > traveler.max_commute_minutes:
            commute_reasons.append(
                FeasibilityReason(
                    code="TRAVELER_LIMIT_EXCEEDED",
                    traveler_id=traveler.traveler_id,
                    actual_minutes=minutes,
                    limit_minutes=traveler.max_commute_minutes,
                    input_fact_ids=(duration.fact_id,),
                )
            )

    all_reasons = tuple(evidence_reasons + commute_reasons + cafe_reasons)
    if evidence_reasons:
        status = "EVIDENCE_INSUFFICIENT"
    elif commute_reasons:
        status = "COMMUTE_LIMIT_EXCEEDED"
    elif cafe_reasons:
        status = "CAFE_CONSTRAINT_FAILED"
    else:
        status = "FEASIBLE"

    return FeasibilityResult(
        cafe_id=cafe_id,
        status=status,
        reasons=all_reasons,
        rule_version=RULE_VERSION,
    )


def evaluate_all_cafes(
    brief: ResearchBrief,
    facts: Iterable[Fact],
    missing: Iterable[MissingEvidence] = (),
) -> tuple[FeasibilityResult, ...]:
    """Evaluate every cafe ID present in facts or missing-evidence records."""

    fact_records = tuple(facts)
    missing_records = tuple(missing)
    cafe_ids = sorted(
        {
            record.candidate_id
            for record in (*fact_records, *missing_records)
            if record.candidate_id.startswith("cafe:gplaces:")
        }
    )
    if not cafe_ids:
        raise ValueError("no cafe evidence was provided")
    return tuple(
        evaluate_cafe_feasibility(brief, cafe_id, fact_records, missing_records)
        for cafe_id in cafe_ids
    )
