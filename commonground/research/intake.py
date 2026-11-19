"""Deterministic clarification and ResearchBrief construction for the Lead."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Callable, Iterable, Literal

from pydantic import Field, field_validator, model_validator

from commonground.candidates import generate_candidate_areas
from commonground.locations import resolve_group_locations

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


@dataclass(frozen=True)
class BriefPreparation:
    """Pre-research outcome plus the Project 1 calls safe to expose in `/chat`."""

    brief: ResearchBrief | None
    response: str
    tool_calls: tuple[dict[str, Any], ...]


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
    traveler_labels = {
        traveler.traveler_id: _traveler_label(traveler.traveler_id, index)
        for index, traveler in enumerate(intake.travelers)
    }
    known = [
        (
            f"{traveler_labels[traveler.traveler_id]} from "
            f"{traveler.input_location}"
        )
        for traveler in intake.travelers
        if traveler.input_location
    ]
    requests: list[str] = []
    for gap in gaps:
        labels = [traveler_labels[item] for item in gap.traveler_ids]
        if gap.code == "TRAVELERS_REQUIRED":
            requests.append(
                "who is traveling and where each person is starting (names like "
                "Alex and Blair are helpful, but Traveler 1 and Traveler 2 also work)"
            )
        elif gap.code == "ORIGIN_REQUIRED":
            requests.append("a starting location for " + _natural_join(labels))
        elif gap.code == "COMMUTE_LIMIT_REQUIRED":
            requests.append(
                "the maximum one-way commute for " + _natural_join(labels)
            )
        elif gap.code == "MEETING_TIME_REQUIRED":
            requests.append("the arrival date and time, including the timezone")
        else:
            requests.append(
                "an explicit timezone for the meeting time (for example, Eastern Time)"
            )

    acknowledgement = (
        "I have " + _natural_join(known) + ". " if known else ""
    )
    if len(requests) == 1:
        return acknowledgement + "One more detail: please provide " + requests[0] + "."
    return (
        acknowledgement
        + "To finish the search, please provide:\n- "
        + "\n- ".join(requests)
        + "."
    )


def intake_help_message(message: str) -> str | None:
    """Answer common intake vocabulary questions instead of repeating a form prompt."""

    normalized = " ".join(message.casefold().split())
    asks_for_meaning = any(
        phrase in normalized
        for phrase in ("what does", "what is", "what's", "meaning", "mean", "explain")
    )
    mentions_commute_limit = (
        "commute" in normalized
        and any(term in normalized for term in ("maximum", "max", "limit", "one-way"))
    )
    if not (asks_for_meaning and mentions_commute_limit):
        return None
    return (
        "Maximum one-way commute means the most time each person is willing to "
        "spend traveling from their starting location to the meeting place in one "
        "direction, not round trip. For example, you can reply: ‘Traveler 1: 20 "
        "minutes; Traveler 2: 30 minutes.’"
    )


def merge_research_intakes(
    previous: ResearchIntake | None,
    current: ResearchIntake,
) -> ResearchIntake:
    """Keep validated slots across clarification turns while allowing corrections."""

    if previous is None:
        return current
    travelers = {item.traveler_id: item for item in previous.travelers}
    previous_by_ordinal = {
        ordinal: item.traveler_id
        for item in previous.travelers
        if (ordinal := _traveler_ordinal(item.traveler_id)) is not None
    }
    for item in current.travelers:
        stable_id = item.traveler_id
        if stable_id not in travelers:
            ordinal = _traveler_ordinal(stable_id)
            if ordinal is not None:
                stable_id = previous_by_ordinal.get(ordinal, stable_id)
        old = travelers.get(stable_id)
        if old is None:
            travelers[stable_id] = item
            continue
        travelers[stable_id] = TravelerIntake(
            traveler_id=stable_id,
            input_location=item.input_location or old.input_location,
            max_commute_minutes=(
                item.max_commute_minutes
                if item.max_commute_minutes is not None
                else old.max_commute_minutes
            ),
        )
    return ResearchIntake(
        question=current.question,
        meeting_time=current.meeting_time or previous.meeting_time,
        travelers=tuple(travelers.values()),
        cafe_constraints=current.cafe_constraints,
    )


def _traveler_ordinal(traveler_id: str) -> int | None:
    slug = traveler_id.removeprefix("traveler:")
    match = re.fullmatch(r"(?:traveler-)?([1-6])", slug)
    return int(match.group(1)) if match else None


def _natural_join(values: Iterable[str]) -> str:
    items = [item for item in values if item]
    if not items:
        return "the group"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _traveler_label(traveler_id: str, index: int) -> str:
    slug = traveler_id.removeprefix("traveler:")
    generic = {"traveler", "travelers", "person", "people", "another", "someone"}
    parts = [part for part in slug.split("-") if part and not part.isdigit()]
    if not parts or any(part in generic for part in parts):
        return f"Traveler {index + 1}"
    return " ".join(part.capitalize() for part in parts)


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


def _tool_payload(raw: str, tool_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"{tool_name} returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{tool_name} returned a non-object response")
    return payload


def prepare_research_brief(
    intake: ResearchIntake,
    *,
    session_id: str,
    research_sequence: int = 1,
    resolver: Callable[[list[dict[str, Any]]], str] | None = None,
    candidate_generator: Callable[..., str] | None = None,
) -> BriefPreparation:
    """Reuse Project 1 tools once intake is complete, without dispatching Researchers."""

    gaps = find_intake_gaps(intake)
    if gaps:
        return BriefPreparation(
            brief=None,
            response=clarification_message(intake),
            tool_calls=(),
        )

    resolver_fn = resolver or resolve_group_locations
    generator_fn = candidate_generator or generate_candidate_areas
    location_args = {
        "locations": [
            {
                "traveler_id": traveler.traveler_id,
                "query": traveler.input_location,
            }
            for traveler in intake.travelers
        ]
    }
    location_raw = resolver_fn(location_args["locations"])
    calls: list[dict[str, Any]] = [
        {
            "agent": "lead",
            "round": 1,
            "name": "resolve_group_locations",
            "args": location_args,
            "result": location_raw,
        }
    ]
    try:
        location_payload = _tool_payload(location_raw, "resolve_group_locations")
    except ValueError as error:
        return BriefPreparation(None, str(error), tuple(calls))
    if location_payload.get("error"):
        return BriefPreparation(
            None,
            "Location resolution could not start: "
            + str(location_payload["error"])[:300],
            tuple(calls),
        )

    unresolved = location_payload.get("unresolved", [])
    if not isinstance(unresolved, list):
        return BriefPreparation(
            None,
            "Location resolution returned an invalid unresolved-location list.",
            tuple(calls),
        )
    if unresolved:
        details = []
        for item in unresolved:
            if not isinstance(item, dict):
                continue
            traveler_id = str(item.get("traveler_id", "unknown traveler"))
            reason = str(item.get("reason", "location was not resolved"))[:160]
            details.append(f"{traveler_id}: {reason}")
        return BriefPreparation(
            None,
            "Please clarify only these unresolved origins:\n- "
            + "\n- ".join(details or ["Provider returned an unreadable record."]),
            tuple(calls),
        )

    resolved_locations = location_payload.get("resolved_locations")
    if not isinstance(resolved_locations, list):
        return BriefPreparation(
            None,
            "Location resolution returned no usable resolved-location list.",
            tuple(calls),
        )

    candidate_args = {
        "resolved_locations": resolved_locations,
        "max_candidates": 4,
    }
    candidate_raw = generator_fn(**candidate_args)
    calls.append(
        {
            "agent": "lead",
            "round": 1,
            "name": "generate_candidate_areas",
            "args": candidate_args,
            "result": candidate_raw,
        }
    )
    try:
        candidate_payload = _tool_payload(candidate_raw, "generate_candidate_areas")
    except ValueError as error:
        return BriefPreparation(None, str(error), tuple(calls))
    if candidate_payload.get("error"):
        return BriefPreparation(
            None,
            "Initial candidate generation failed: "
            + str(candidate_payload["error"])[:300],
            tuple(calls),
        )
    candidate_areas = candidate_payload.get("candidate_areas")
    if not isinstance(candidate_areas, list):
        return BriefPreparation(
            None,
            "Initial candidate generation returned no usable candidate list.",
            tuple(calls),
        )

    try:
        brief = build_research_brief(
            intake,
            session_id=session_id,
            resolved_locations=resolved_locations,
            candidate_areas=candidate_areas,
            research_sequence=research_sequence,
        )
    except (TypeError, ValueError) as error:
        return BriefPreparation(
            None,
            f"The resolved research brief failed validation: {str(error)[:300]}",
            tuple(calls),
        )
    return BriefPreparation(
        brief=brief,
        response="Research inputs are resolved and ready for bounded dispatch.",
        tool_calls=tuple(calls),
    )
