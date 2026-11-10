"""MTA station loading and bounded expansion-candidate normalization."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import requests

from commonground.candidates import _haversine_km

from .models import Fact, ResearchBrief, ResearchResult, ResearchTask, Source


DATASET_ID = "39hk-dx4f"
DATASET_API_URL = f"https://data.ny.gov/resource/{DATASET_ID}.json"
DATASET_PAGE_URL = (
    "https://data.ny.gov/Transportation/MTA-Subway-Stations/39hk-dx4f/about_data"
)
REQUEST_TIMEOUT_SECONDS = 15
MAX_DATASET_ROWS = 5000
MAX_EXPANSION_CANDIDATES = 3
INITIAL_DUPLICATE_RADIUS_KM = 0.5
SELECTED_DIVERSITY_RADIUS_KM = 0.4
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class MTADataError(RuntimeError):
    """Credential-free provider/validation failure safe for an agent boundary."""


@dataclass(frozen=True)
class MTAStation:
    station_id: str
    gtfs_stop_id: str
    complex_id: str
    name: str
    borough: str
    routes: tuple[str, ...]
    lat: float
    lng: float

    @property
    def candidate_id(self) -> str:
        return f"area:mta:{self.station_id}"


def _text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"MTA record is missing {field}")
    return value.strip()


def _coordinate(record: dict[str, Any], field: str, low: float, high: float) -> float:
    value = record.get(field)
    if isinstance(value, bool):
        raise ValueError(f"MTA record has invalid {field}")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"MTA record has invalid {field}") from error
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"MTA record has out-of-range {field}")
    return number


def _station(record: Any) -> MTAStation:
    if not isinstance(record, dict):
        raise ValueError("MTA station record must be an object")
    station_id = _text(record, "station_id")
    if not _SAFE_ID.fullmatch(station_id):
        raise ValueError("MTA station_id cannot form a stable candidate ID")
    routes = tuple(
        dict.fromkeys(_text(record, "daytime_routes").replace(",", " ").split())
    )
    return MTAStation(
        station_id=station_id,
        gtfs_stop_id=_text(record, "gtfs_stop_id"),
        complex_id=_text(record, "complex_id"),
        name=_text(record, "stop_name"),
        borough=_text(record, "borough"),
        routes=routes,
        lat=_coordinate(record, "gtfs_latitude", 40.45, 41.05),
        lng=_coordinate(record, "gtfs_longitude", -74.35, -73.65),
    )


def parse_mta_stations(records: Any) -> tuple[MTAStation, ...]:
    """Normalize the official Socrata rows and deterministically deduplicate IDs."""

    if not isinstance(records, list):
        raise MTADataError("MTA Subway Stations response must be a JSON list")
    stations: dict[str, MTAStation] = {}
    for record in records:
        try:
            station = _station(record)
        except ValueError:
            continue
        stations.setdefault(station.station_id, station)
    if not stations:
        raise MTADataError("MTA Subway Stations response contained no valid stations")
    return tuple(sorted(stations.values(), key=lambda item: item.station_id))


def fetch_mta_stations(
    *,
    getter: Callable[..., Any] = requests.get,
    now: Callable[[], datetime] | None = None,
) -> tuple[tuple[MTAStation, ...], datetime]:
    """Fetch one bounded snapshot from the official data.ny.gov Socrata endpoint."""

    try:
        response = getter(
            DATASET_API_URL,
            params={"$limit": MAX_DATASET_ROWS},
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as error:
        raise MTADataError("MTA Subway Stations request timed out") from error
    except requests.RequestException as error:
        raise MTADataError(
            f"MTA Subway Stations request failed: {type(error).__name__}"
        ) from error
    if getattr(response, "status_code", 500) >= 400:
        raise MTADataError(
            f"MTA Subway Stations returned HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except (TypeError, ValueError) as error:
        raise MTADataError("MTA Subway Stations returned invalid JSON") from error
    retrieved_at = (now or (lambda: datetime.now(timezone.utc)))()
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("MTA retrieval timestamp must include a time zone")
    return parse_mta_stations(payload), retrieved_at


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def select_expansion_stations(
    brief: ResearchBrief,
    stations: Iterable[MTAStation],
    *,
    max_candidates: int = MAX_EXPANSION_CANDIDATES,
) -> tuple[MTAStation, ...]:
    """Choose geographically useful stations omitted from the initial shortlist."""

    if not 1 <= max_candidates <= MAX_EXPANSION_CANDIDATES:
        raise ValueError("max_candidates must be between 1 and 3")
    initial_names = {
        _normalized_name(candidate.name) for candidate in brief.initial_candidates
    }
    eligible = []
    for station in stations:
        if _normalized_name(station.name) in initial_names:
            continue
        if any(
            _haversine_km(station.lat, station.lng, candidate.lat, candidate.lng)
            <= INITIAL_DUPLICATE_RADIUS_KM
            for candidate in brief.initial_candidates
        ):
            continue
        distances = tuple(
            _haversine_km(
                station.lat,
                station.lng,
                traveler.resolved_location.lat,
                traveler.resolved_location.lng,
            )
            for traveler in brief.travelers
        )
        eligible.append(
            (
                max(distances),
                sum(distances) / len(distances),
                -len(station.routes),
                station.station_id,
                station,
            )
        )
    ranked = [item[-1] for item in sorted(eligible, key=lambda item: item[:-1])]

    selected: list[MTAStation] = []
    for station in ranked:
        if all(
            _haversine_km(station.lat, station.lng, item.lat, item.lng)
            > SELECTED_DIVERSITY_RADIUS_KM
            for item in selected
        ):
            selected.append(station)
        if len(selected) == max_candidates:
            return tuple(selected)
    for station in ranked:
        if station not in selected:
            selected.append(station)
        if len(selected) == max_candidates:
            break
    return tuple(selected)


def build_expansion_result(
    task: ResearchTask,
    brief: ResearchBrief,
    stations: Iterable[MTAStation],
    *,
    accessed_at: datetime,
) -> ResearchResult:
    """Convert selected MTA records into cited ResearchResult facts."""

    if task.agent != "expansion_researcher":
        raise ValueError("MTA expansion adapter requires an expansion_researcher task")
    if task.research_id != brief.research_id:
        raise ValueError("task must reference the supplied research brief")
    if accessed_at.tzinfo is None or accessed_at.utcoffset() is None:
        raise ValueError("accessed_at must include a time zone")

    selected = select_expansion_stations(brief, stations)
    facts: list[Fact] = []
    sources: list[Source] = []
    sequence = 1
    for station in selected:
        source_id = f"source:mta-stations:{station.station_id}"
        sources.append(
            Source(
                source_id=source_id,
                provider="mta_subway_stations",
                title=f"MTA Subway Stations record: {station.name}",
                url=DATASET_PAGE_URL,
                accessed_at=accessed_at,
                request_summary={
                    "dataset_id": DATASET_ID,
                    "station_id": station.station_id,
                    "retrieved_at": accessed_at.isoformat(),
                },
                provider_record_ids=(station.station_id,),
                attribution="New York State Open Data / MTA",
            )
        )
        values = (
            ("station_name", station.name, None),
            ("coordinates", {"lat": station.lat, "lng": station.lng}, "WGS84"),
            ("routes_or_lines", station.routes, None),
            (
                "expansion_selection_reason",
                (
                    "Omitted from the initial shortlist, not a near-duplicate, and "
                    "selected by bounded group-distance and route-diversity heuristics."
                ),
                None,
            ),
        )
        for predicate, value, unit in values:
            facts.append(
                Fact(
                    fact_id=f"fact:expansion:r{task.round}:{sequence:03d}",
                    candidate_id=station.candidate_id,
                    subject_id=station.candidate_id,
                    predicate=predicate,
                    value=value,
                    unit=unit,
                    observed_at=accessed_at,
                    valid_for={
                        "dataset_id": DATASET_ID,
                        "station_id": station.station_id,
                    },
                    source_ids=(source_id,),
                    provisional=False,
                )
            )
            sequence += 1

    considered = (
        tuple(station.candidate_id for station in selected)
        if selected
        else task.candidate_ids
    )
    return ResearchResult(
        task_id=task.task_id,
        agent=task.agent,
        round=task.round,
        status="complete",
        facts=tuple(facts),
        sources=tuple(sources),
        missing=(),
        candidate_ids_considered=considered,
        summary=(
            f"Selected {len(selected)} bounded MTA expansion candidate(s)."
            if selected
            else "No non-duplicate MTA expansion candidate passed the selection bound."
        ),
    )
