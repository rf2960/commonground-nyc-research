"""Bounded Google Routes evidence collection for Project 2 Transit tasks.

The inherited Project 1 request function remains the only provider boundary.  This
module resolves stable Project 2 IDs to coordinates, calls that boundary off the event
loop, and normalizes every traveler/destination pair into cited facts or an explicit
gap.  Commute-limit decisions remain in ``feasibility.py``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any

from commonground import transit as provider

from .models import (
    Coordinates,
    Fact,
    MissingEvidence,
    ResearchBrief,
    ResearchResult,
    ResearchTask,
    Source,
)
from .runner import ResearchContext


MAX_DESTINATIONS = 6
ROUTES_DOC = "https://developers.google.com/maps/documentation/routes"


@dataclass(frozen=True)
class TransitPairObservation:
    """One normalized traveler/destination provider observation."""

    candidate_id: str
    traveler_id: str
    destination_kind: str
    observed_at: datetime
    duration_minutes: float | None = None
    route_available: bool | None = None
    error_code: str | None = None


def _coordinates(value: Any) -> Coordinates | None:
    if not isinstance(value, dict):
        return None
    try:
        return Coordinates.model_validate(value)
    except (TypeError, ValueError):
        return None


def _destination_kind(candidate_id: str) -> str:
    return "exact_cafe" if candidate_id.startswith("cafe:gplaces:") else "area_center"


def _same_instant(raw: Any, expected: datetime) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() is not None
        and parsed == expected
    )


def _expected_pairs(
    brief: ResearchBrief,
    task: ResearchTask,
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (candidate_id, traveler.traveler_id)
        for candidate_id in task.candidate_ids
        for traveler in brief.travelers
    )


def build_transit_result(
    brief: ResearchBrief,
    task: ResearchTask,
    observations: tuple[TransitPairObservation, ...],
    *,
    source_accessed_at: datetime | None = None,
    request_summary: dict[str, Any] | None = None,
) -> ResearchResult:
    """Build a contract-valid result without applying any commute limit."""

    if task.agent != "transit_researcher" or task.research_id != brief.research_id:
        raise ValueError("Transit task must reference this brief and transit_researcher")
    if tuple(
        (observation.candidate_id, observation.traveler_id)
        for observation in observations
    ) != _expected_pairs(brief, task):
        raise ValueError("Every requested traveler/destination pair must be ordered once")
    if (source_accessed_at is None) != (request_summary is None):
        raise ValueError("Routes source metadata must be supplied together")

    facts: list[Fact] = []
    missing: list[MissingEvidence] = []
    sources: tuple[Source, ...] = ()
    source_id: str | None = None
    sequence = int(task.task_id.rsplit(":", 1)[1]) * 1000

    if source_accessed_at is not None and request_summary is not None:
        digest_input = json.dumps(
            {
                "task_id": task.task_id,
                "accessed_at": source_accessed_at.isoformat(),
                "request": request_summary,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = sha256(digest_input.encode()).hexdigest()[:20]
        source_id = f"source:google-routes:{digest}"
        sources = (
            Source(
                source_id=source_id,
                provider="google_routes",
                title="Routes API transit matrix",
                url=ROUTES_DOC,
                accessed_at=source_accessed_at,
                request_summary=request_summary,
                attribution="Google Maps",
            ),
        )

    def add_fact(
        observation: TransitPairObservation,
        predicate: str,
        value: Any,
        *,
        unit: str | None = None,
    ) -> None:
        if source_id is None:
            raise ValueError("Provider facts require a Routes source")
        facts.append(
            Fact(
                fact_id=(
                    f"fact:transit:r{task.round}:"
                    f"{sequence + len(facts) + 1:03d}"
                ),
                candidate_id=observation.candidate_id,
                subject_id=observation.traveler_id,
                predicate=predicate,
                value=value,
                unit=unit,
                observed_at=observation.observed_at,
                valid_for={
                    "arrival_time": brief.meeting_time.isoformat(),
                    "destination_kind": observation.destination_kind,
                },
                source_ids=(source_id,),
            )
        )

    def add_gap(observation: TransitPairObservation, reason_code: str) -> None:
        detail, retryable, next_action = {
            "DEPENDENCY_NOT_READY": (
                "The selected destination did not have one unambiguous cited coordinate.",
                False,
                "Obtain cited destination coordinates before requesting an exact route.",
            ),
            "ROUTE_UNAVAILABLE": (
                "Google Routes returned no transit route for this traveler and destination.",
                False,
                "Report this exact commute as unavailable; do not substitute an area estimate.",
            ),
            "PROVIDER_ERROR": (
                "Google Routes did not return usable pair-level transit evidence.",
                True,
                "Retry only within the single bounded follow-up if this route is decision-critical.",
            ),
            "STALE_EVIDENCE": (
                "Google Routes returned evidence for a different or ambiguous arrival time.",
                False,
                "Request the routes again for the brief's exact timezone-aware arrival time.",
            ),
        }[reason_code]
        missing.append(
            MissingEvidence(
                missing_id=(
                    f"missing:transit:r{task.round}:"
                    f"{sequence + len(missing) + 1:03d}"
                ),
                candidate_id=observation.candidate_id,
                subject_id=observation.traveler_id,
                field="transit_duration_minutes",
                reason_code=reason_code,
                detail=detail,
                retryable=retryable,
                next_action=next_action,
            )
        )

    for observation in observations:
        if observation.error_code is not None:
            if observation.error_code == "ROUTE_UNAVAILABLE" and source_id is not None:
                add_fact(observation, "route_available", False)
            add_gap(observation, observation.error_code)
            continue
        if (
            observation.route_available is not True
            or isinstance(observation.duration_minutes, bool)
            or not isinstance(observation.duration_minutes, (int, float))
            or not math.isfinite(observation.duration_minutes)
            or observation.duration_minutes < 0
        ):
            add_gap(observation, "PROVIDER_ERROR")
            continue
        add_fact(observation, "route_available", True)
        add_fact(
            observation,
            "transit_duration_minutes",
            observation.duration_minutes,
            unit="minutes",
        )

    status = "partial" if missing and facts else "failed" if missing else "complete"
    return ResearchResult(
        task_id=task.task_id,
        agent=task.agent,
        round=task.round,
        status=status,
        facts=tuple(facts),
        sources=sources,
        missing=tuple(missing),
        candidate_ids_considered=task.candidate_ids,
        summary=(
            f"Collected pair-level transit evidence for {len(observations) - len(missing)} "
            f"of {len(observations)} requested traveler/destination pairs; "
            f"{len(missing)} explicit gaps."
        ),
    )


def _dependency_coordinates(
    context: ResearchContext,
    brief: ResearchBrief,
    task: ResearchTask,
) -> dict[str, Coordinates]:
    values: dict[str, list[Coordinates]] = {}
    declared_dependencies = set(task.dependencies)
    for result in context.dependency_results:
        if (
            not result.task_id.startswith(f"task:{brief.session_id}:")
            or result.round > task.round
        ):
            continue
        for fact in result.facts:
            if (
                fact.fact_id not in declared_dependencies
                or fact.predicate != "coordinates"
                or fact.candidate_id not in task.candidate_ids
            ):
                continue
            expected_agent = (
                "cafe_researcher"
                if fact.candidate_id.startswith("cafe:gplaces:")
                else "expansion_researcher"
            )
            if result.agent != expected_agent:
                continue
            coordinate = _coordinates(fact.value)
            if coordinate is not None:
                values.setdefault(fact.candidate_id, []).append(coordinate)
    return {
        candidate_id: coordinates[0]
        for candidate_id, coordinates in values.items()
        if coordinates and all(value == coordinates[0] for value in coordinates)
    }


async def run_transit_task(
    context: ResearchContext,
    brief: ResearchBrief,
    task: ResearchTask,
) -> ResearchResult:
    """Three-input callable for ``build_research_service(transit=run_transit_task)``."""

    if (
        task.agent != "transit_researcher"
        or task.research_id != brief.research_id
        or "get_transit_matrix" not in task.allowed_tools
        or "get_transit_matrix" not in context.allowed_tools
        or context.max_turns < 1
        or not 1 <= len(task.candidate_ids) <= MAX_DESTINATIONS
    ):
        raise ValueError("Invalid or unbounded Transit Researcher task")

    initial_coordinates = {
        candidate.candidate_id: Coordinates(lat=candidate.lat, lng=candidate.lng)
        for candidate in brief.initial_candidates
    }
    dependency_coordinates = _dependency_coordinates(context, brief, task)
    coordinates = {**initial_coordinates, **dependency_coordinates}
    destinations: list[dict[str, Any]] = []
    unresolved: set[str] = set()
    for candidate_id in task.candidate_ids:
        coordinate = coordinates.get(candidate_id)
        if coordinate is None:
            unresolved.add(candidate_id)
            continue
        destinations.append({"area": candidate_id, **coordinate.model_dump()})

    observations_by_pair: dict[tuple[str, str], TransitPairObservation] = {}
    now = datetime.now(timezone.utc)
    for candidate_id in unresolved:
        for traveler in brief.travelers:
            observations_by_pair[(candidate_id, traveler.traveler_id)] = (
                TransitPairObservation(
                    candidate_id=candidate_id,
                    traveler_id=traveler.traveler_id,
                    destination_kind=_destination_kind(candidate_id),
                    observed_at=now,
                    error_code="DEPENDENCY_NOT_READY",
                )
            )

    source_accessed_at: datetime | None = None
    request_summary: dict[str, Any] | None = None
    if destinations:
        origins = [
            {
                "traveler_id": traveler.traveler_id,
                **traveler.resolved_location.model_dump(),
            }
            for traveler in brief.travelers
        ]
        try:
            raw_result = await asyncio.to_thread(
                provider.get_transit_matrix,
                origins=origins,
                candidate_areas=destinations,
                arrival_time=brief.meeting_time.isoformat(),
                include_driving=False,
            )
            payload = json.loads(raw_result)
        except Exception:
            payload = {"error": "redacted"}
        source_accessed_at = datetime.now(timezone.utc)

        raw_pairs = payload.get("route_pairs") if isinstance(payload, dict) else None
        if isinstance(payload, dict) and isinstance(raw_pairs, list):
            provider_arrival_time = payload.get("arrival_time")
            request_summary = {
                "origin_count": len(origins),
                "destination_count": len(destinations),
                "candidate_ids": [destination["area"] for destination in destinations],
                "destination_kinds": [
                    _destination_kind(destination["area"])
                    for destination in destinations
                ],
                "arrival_time": brief.meeting_time.isoformat(),
                "provider_arrival_time": provider_arrival_time,
                "provider_reported_partial": bool(payload.get("error")),
                "travel_mode": "TRANSIT",
                "include_driving": False,
            }
            indexed: dict[tuple[str, str], dict[str, Any]] = {}
            duplicates: set[tuple[str, str]] = set()
            if _same_instant(provider_arrival_time, brief.meeting_time):
                for raw_pair in raw_pairs:
                    if not isinstance(raw_pair, dict):
                        continue
                    area = raw_pair.get("area")
                    traveler_id = raw_pair.get("traveler_id")
                    if not isinstance(area, str) or not isinstance(traveler_id, str):
                        continue
                    key = (area, traveler_id)
                    if key in indexed:
                        duplicates.add(key)
                    elif key in _expected_pairs(brief, task):
                        indexed[key] = raw_pair

            for destination in destinations:
                candidate_id = destination["area"]
                for traveler in brief.travelers:
                    key = (candidate_id, traveler.traveler_id)
                    raw_pair = indexed.get(key)
                    common = {
                        "candidate_id": candidate_id,
                        "traveler_id": traveler.traveler_id,
                        "destination_kind": _destination_kind(candidate_id),
                        "observed_at": source_accessed_at,
                    }
                    if not _same_instant(provider_arrival_time, brief.meeting_time):
                        observations_by_pair[key] = TransitPairObservation(
                            **common,
                            error_code="STALE_EVIDENCE",
                        )
                    elif key in duplicates or raw_pair is None:
                        observations_by_pair[key] = TransitPairObservation(
                            **common,
                            error_code="PROVIDER_ERROR",
                        )
                    elif raw_pair.get("route_available") is False:
                        observations_by_pair[key] = TransitPairObservation(
                            **common,
                            route_available=False,
                            error_code="ROUTE_UNAVAILABLE",
                        )
                    else:
                        observations_by_pair[key] = TransitPairObservation(
                            **common,
                            route_available=raw_pair.get("route_available"),
                            duration_minutes=raw_pair.get("transit_minutes"),
                        )
        else:
            for destination in destinations:
                candidate_id = destination["area"]
                for traveler in brief.travelers:
                    observations_by_pair[(candidate_id, traveler.traveler_id)] = (
                        TransitPairObservation(
                            candidate_id=candidate_id,
                            traveler_id=traveler.traveler_id,
                            destination_kind=_destination_kind(candidate_id),
                            observed_at=source_accessed_at,
                            error_code="PROVIDER_ERROR",
                        )
                    )
            # An error response is a gap, not a source for a factual claim.
            source_accessed_at = None

    observations = tuple(
        observations_by_pair[pair] for pair in _expected_pairs(brief, task)
    )
    return build_transit_result(
        brief,
        task,
        observations,
        source_accessed_at=source_accessed_at,
        request_summary=request_summary,
    )
