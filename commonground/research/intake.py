"""Deterministic clarification and ResearchBrief construction for the Lead."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Iterable, Literal

from pydantic import Field, field_validator, model_validator

from .models import (
    CafeConstraints,
    Candidate,
    ContractModel,
    Coordinates,
    NonEmptyStr,
    ResearchBrief,
    Traveler,
    TravelerId,
)


class TravelerIntake(ContractModel):
    traveler_id: TravelerId
    input_location: str | None = None
    max_commute_minutes: Annotated[float, Field(gt=0, le=300)] | None = None

    @field_validator("input_location")
    @classmethod
    def normalize_optional_location(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ResearchIntake(ContractModel):
    question: NonEmptyStr = "Can bounded expansion find a feasible cafe?"
    meeting_time: datetime | None = None
    travelers: Annotated[tuple[TravelerIntake, ...], Field(max_length=6)] = ()
    cafe_constraints: CafeConstraints = Field(default_factory=CafeConstraints)

    @model_validator(mode="after")
    def traveler_ids_are_unique(self) -> ResearchIntake:
        ids = [traveler.traveler_id.casefold() for traveler in self.travelers]
        if len(ids) != len(set(ids)):
            raise ValueError("traveler IDs must be unique")
        return self


class IntakeGap(ContractModel):
    code: Literal[
        "TRAVELERS_REQUIRED",
        "ORIGIN_REQUIRED",
        "COMMUTE_LIMIT_REQUIRED",
        "MEETING_TIME_REQUIRED",
        "MEETING_TIME_TIMEZONE_REQUIRED",
    ]
    field: NonEmptyStr
    traveler_ids: tuple[TravelerId, ...] = ()
    prompt: NonEmptyStr


def find_intake_gaps(intake: ResearchIntake) -> tuple[IntakeGap, ...]:
    """Return stable, actionable gaps without starting any provider or model call."""

    gaps: list[IntakeGap] = []
    if len(intake.travelers) < 2:
        gaps.append(
            IntakeGap(
                code="TRAVELERS_REQUIRED",
                field="travelers",
                prompt="Provide at least two travelers with stable names or IDs.",
            )
        )
    missing_origins = tuple(
        traveler.traveler_id
        for traveler in intake.travelers
        if traveler.input_location is None
    )
    if missing_origins:
        gaps.append(
            IntakeGap(
                code="ORIGIN_REQUIRED",
                field="input_location",
                traveler_ids=missing_origins,
                prompt=(
                    "Provide an NYC-metro starting location for: "
                    + ", ".join(missing_origins)
                    + "."
                ),
            )
        )
    missing_limits = tuple(
        traveler.traveler_id
        for traveler in intake.travelers
        if traveler.max_commute_minutes is None
    )
    if missing_limits:
        gaps.append(
            IntakeGap(
                code="COMMUTE_LIMIT_REQUIRED",
                field="max_commute_minutes",
                traveler_ids=missing_limits,
                prompt=(
                    "Provide a maximum one-way commute in minutes for: "
                    + ", ".join(missing_limits)
                    + "."
                ),
            )
        )
    if intake.meeting_time is None:
        gaps.append(
            IntakeGap(
                code="MEETING_TIME_REQUIRED",
                field="meeting_time",
                prompt="Provide the meeting arrival date and time.",
            )
        )
    elif (
        intake.meeting_time.tzinfo is None
        or intake.meeting_time.utcoffset() is None
    ):
        gaps.append(
            IntakeGap(
                code="MEETING_TIME_TIMEZONE_REQUIRED",
                field="meeting_time",
                prompt=(
                    "Provide the meeting arrival time with an explicit timezone or "
                    "UTC offset, such as 2026-10-10T14:00:00-04:00."
                ),
            )
        )
    return tuple(gaps)


def clarification_message(intake: ResearchIntake) -> str:
    gaps = find_intake_gaps(intake)
    if not gaps:
        return (
            "The required user inputs are complete. Resolve every origin and generate "
            "the initial candidate areas before dispatching Researchers."
        )
    return "Before research can start, I still need:\n- " + "\n- ".join(
        gap.prompt for gap in gaps
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise ValueError("candidate area name cannot form a stable ID")
    return slug


def _resolved_by_traveler(
    records: Iterable[dict[str, Any]],
) -> dict[str, Coordinates]:
    resolved: dict[str, Coordinates] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("resolved location records must be objects")
        traveler_id = record.get("traveler_id")
        if not isinstance(traveler_id, str):
            raise ValueError("resolved location is missing traveler_id")
        if traveler_id in resolved:
            raise ValueError(f"duplicate resolved traveler_id: {traveler_id}")
        resolved[traveler_id] = Coordinates(
            lat=record.get("lat"),
            lng=record.get("lng"),
        )
    return resolved


def _initial_candidates(records: Iterable[dict[str, Any]]) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("candidate area records must be objects")
        name = record.get("area")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("candidate area is missing a readable area name")
        candidate_id = f"area:initial:{_slug(name)}"
        if candidate_id in ids:
            raise ValueError(f"duplicate initial candidate ID: {candidate_id}")
        ids.add(candidate_id)
        candidates.append(
            Candidate(
                candidate_id=candidate_id,
                name=name.strip(),
                kind="initial_area",
                lat=record.get("lat"),
                lng=record.get("lng"),
            )
        )
    if not candidates:
        raise ValueError("at least one initial candidate area is required")
    return tuple(candidates)


def build_research_brief(
    intake: ResearchIntake,
    *,
    session_id: str,
    resolved_locations: Iterable[dict[str, Any]],
    candidate_areas: Iterable[dict[str, Any]],
    research_sequence: int = 1,
) -> ResearchBrief:
    """Join clarified user input to authoritative Project 1 tool outputs."""

    gaps = find_intake_gaps(intake)
    if gaps:
        codes = ", ".join(gap.code for gap in gaps)
        raise ValueError(f"research intake is incomplete: {codes}")
    if research_sequence < 1:
        raise ValueError("research_sequence must be positive")

    resolved = _resolved_by_traveler(resolved_locations)
    expected_ids = {traveler.traveler_id for traveler in intake.travelers}
    if set(resolved) != expected_ids:
        missing = sorted(expected_ids - set(resolved))
        unexpected = sorted(set(resolved) - expected_ids)
        raise ValueError(
            "resolved traveler IDs must match intake; "
            f"missing={missing}, unexpected={unexpected}"
        )

    travelers = tuple(
        Traveler(
            traveler_id=item.traveler_id,
            input_location=item.input_location,
            resolved_location=resolved[item.traveler_id],
            max_commute_minutes=item.max_commute_minutes,
        )
        for item in intake.travelers
    )
    return ResearchBrief(
        research_id=f"research:{session_id}:{research_sequence}",
        session_id=session_id,
        question=intake.question,
        meeting_time=intake.meeting_time,
        travelers=travelers,
        cafe_constraints=intake.cafe_constraints,
        initial_candidates=_initial_candidates(candidate_areas),
        max_follow_up_rounds=1,
    )
