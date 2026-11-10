"""Bounded Places evidence collection; constraint decisions belong to feasibility.

Uses the inherited Places request function and weekly-hours evaluator. Retrieval does
not discard low-rated or unknown-price records: keeping that evidence is necessary to
explain a failure without silently changing any of the user's constraints.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import math
import os
import re
from urllib.parse import parse_qs, urlparse

from commonground import places as provider
from commonground.opening_hours import opening_status
from .models import Coordinates, Fact, MissingEvidence, ResearchBrief, ResearchResult, ResearchTask, Source, SENSITIVE_KEYS
from .runner import ResearchContext

MAX_AREAS = 6
MAX_CONCURRENT_REQUESTS = 3
PLACES_DOC = 'https://developers.google.com/maps/documentation/places/web-service/nearby-search'
FIELDS = ('name', 'address', 'coordinates', 'rating', 'price_level',
          'business_status', 'open_at_meeting_time')


@dataclass(frozen=True)
class AreaObservation:
    candidate_id: str
    coordinates: Coordinates | None
    accessed_at: datetime
    places: tuple[dict, ...] = ()
    error_code: str | None = None


def _coordinates(value) -> Coordinates | None:
    if not isinstance(value, dict):
        return None
    if any(isinstance(value.get(k), bool) or not isinstance(value.get(k), (int, float))
           or not math.isfinite(value[k]) for k in ('lat', 'lng')):
        return None
    try:
        return Coordinates.model_validate(value)
    except ValueError:
        return None


def _source_url(value, place_id: str) -> str:
    """Keep provider Maps links only when credential-free and on a known host."""
    if isinstance(value, str):
        try:
            url = urlparse(value)
        except ValueError:
            return _source_url(None, place_id)
        host = url.hostname or ''
        if (url.scheme == 'https' and not url.username and not url.password
                and (host == 'google.com' or host.endswith('.google.com')
                     or host == 'maps.app.goo.gl')
                and not (set(k.lower() for k in parse_qs(url.query)) & SENSITIVE_KEYS)):
            return value
    return f'https://www.google.com/maps/search/?api=1&query=place&query_place_id={place_id}'


def _values(place: dict, brief: ResearchBrief) -> dict:
    display = place.get('displayName')
    name = display.get('text') if isinstance(display, dict) else None
    location = place.get('location')
    coord = _coordinates({'lat': location.get('latitude'), 'lng': location.get('longitude')}) if isinstance(location, dict) else None
    rating = place.get('rating')
    if (isinstance(rating, bool) or not isinstance(rating, (int, float))
            or not math.isfinite(rating) or not 0 <= rating <= 5):
        rating = None
    price_raw = place.get('priceLevel')
    price = provider.PRICES.get(price_raw) if isinstance(price_raw, str) else None
    status = place.get('businessStatus')
    status = status if status in ('OPERATIONAL', 'CLOSED_TEMPORARILY', 'CLOSED_PERMANENTLY') else None
    normalized_place = dict(place, businessStatus=status)
    hours = opening_status(normalized_place, brief.meeting_time)
    address = place.get('formattedAddress')
    return {
        'name': name.strip() if isinstance(name, str) and name.strip() else None,
        'address': address.strip() if isinstance(address, str) and address.strip() else None,
        'coordinates': coord.model_dump() if coord else None,
        'rating': rating,
        'price_level': price,
        'business_status': status,
        'open_at_meeting_time': hours['open_at_meeting_time'],
        '_hours_basis': hours['opening_status_source'],
    }


def build_cafe_result(
    brief: ResearchBrief, task: ResearchTask, observations: tuple[AreaObservation, ...],
) -> ResearchResult:
    """Normalize one bounded task into cited facts and explicit field-level gaps."""
    if task.agent != 'cafe_researcher' or task.research_id != brief.research_id:
        raise ValueError('Cafe task must reference this brief and cafe_researcher')
    if tuple(o.candidate_id for o in observations) != task.candidate_ids:
        raise ValueError('Every requested area must have one ordered observation')
    facts, sources, missing = [], [], []
    grouped: dict[str, list[tuple[dict, str, str, datetime]]] = {}
    sequence = int(task.task_id.rsplit(':', 1)[1]) * 1000

    def gap(candidate_id, field, reason='PROVIDER_FIELD_MISSING', detail=None):
        missing.append(MissingEvidence(
            missing_id=f'missing:cafe:r{task.round}:{sequence + len(missing) + 1:03d}',
            candidate_id=candidate_id, field=field, reason_code=reason,
            detail=detail or f'Places did not provide usable {field} evidence.',
            retryable=reason == 'PROVIDER_ERROR',
            next_action=('Verify meeting-time opening directly with the venue; keep it unknown.'
                         if field == 'open_at_meeting_time' else
                         'Obtain the missing provider evidence before making a supported recommendation.'),
        ))

    def fact(candidate_id, predicate, value, source_ids, observed_at, valid_for=None, provisional=False):
        facts.append(Fact(
            fact_id=f'fact:cafe:r{task.round}:{sequence + len(facts) + 1:03d}',
            candidate_id=candidate_id, subject_id=candidate_id, predicate=predicate,
            value=value, source_ids=tuple(source_ids), observed_at=observed_at,
            valid_for=valid_for or {}, provisional=provisional,
        ))

    for observation in observations:
        area_id = observation.candidate_id
        if observation.error_code:
            gap(area_id, 'cafe_search_results', observation.error_code,
                'The area search could not supply cafe evidence; no absence is inferred.')
            continue
        if observation.coordinates is None:
            raise ValueError('Successful search requires observed request coordinates')
        digest = sha256((task.task_id + area_id + observation.accessed_at.isoformat()).encode()).hexdigest()[:20]
        search_source_id = f'source:google-places:{digest}'
        request = {
            'candidate_id': area_id,
            'center': observation.coordinates.model_dump(), 'radius_meters': 800,
            'max_result_count': 10, 'field_mask': provider.FIELDS,
            'included_primary_types': ['cafe', 'coffee_shop'],
            'meeting_time': brief.meeting_time.isoformat(),
            'active_constraints': brief.cafe_constraints.model_dump(mode='json'),
            'retrieval_note': 'Collect bounded evidence; apply unchanged constraints in feasibility.',
        }
        record_ids = tuple(sorted({
            p['id'] for p in observation.places if isinstance(p, dict)
            and isinstance(p.get('id'), str) and re.fullmatch(r'[A-Za-z0-9._-]+', p['id'])
        }))
        sources.append(Source(
            source_id=search_source_id, provider='google_places', title='Places nearby cafe search',
            url=PLACES_DOC, accessed_at=observation.accessed_at, request_summary=request,
            provider_record_ids=record_ids, attribution='Google Maps',
        ))
        cafe_ids = []
        for index, place in enumerate(observation.places):
            place_id = place.get('id') if isinstance(place, dict) else None
            if not isinstance(place_id, str) or not re.fullmatch(r'[A-Za-z0-9._-]+', place_id):
                gap(area_id, 'place_identity', 'VALIDATION_ERROR',
                    'A provider record had no usable stable Places ID; no cafe identity was invented.')
                continue
            cafe_id = f'cafe:gplaces:{place_id}'
            cafe_ids.append(cafe_id)
            record_source_id = f'source:google-places:{digest}-{index:02d}'
            sources.append(Source(
                source_id=record_source_id, provider='google_places', title='Google Places cafe record',
                url=_source_url(place.get('googleMapsUri'), place_id), accessed_at=observation.accessed_at,
                request_summary={**request, 'place_id': place_id},
                provider_record_ids=(place_id,), attribution='Google Maps',
            ))
            grouped.setdefault(cafe_id, []).append((place, area_id, record_source_id, observation.accessed_at))
        fact(area_id, 'cafe_search_results', sorted(set(cafe_ids)),
             (search_source_id,), observation.accessed_at,
             {'scope': 'bounded_nearby_search', 'exhaustive': False})

    for cafe_id, records in sorted(grouped.items()):
        parents = sorted({record[1] for record in records})
        normalized = [(_values(p, brief), source_id, timestamp) for p, _, source_id, timestamp in records]
        valid_for = {'parent_candidate_ids': parents}
        fact(cafe_id, 'parent_candidate_id', parents[0],
             tuple(record[2] for record in records), max(record[3] for record in records), valid_for)
        for field in FIELDS:
            known = [(values[field], source_id, timestamp, values['_hours_basis'])
                     for values, source_id, timestamp in normalized if values[field] is not None]
            if not known:
                gap(cafe_id, field)
                continue
            # Conflicting observations stay explicit rather than selecting a value
            # that happens to pass the user's constraints.
            if any(value != known[0][0] for value, *_ in known[1:]):
                gap(cafe_id, field, 'VALIDATION_ERROR',
                    f'Overlapping Places observations disagree on {field}; verification is required.')
                continue
            time_context = dict(valid_for)
            provisional = False
            if field == 'open_at_meeting_time':
                bases = sorted({item[3] for item in known})
                time_context.update(meeting_time=brief.meeting_time.isoformat(), basis=bases[0])
                provisional = 'regular_schedule' in bases
            fact(cafe_id, field, known[0][0], tuple(item[1] for item in known),
                 max(item[2] for item in known), time_context, provisional)
    status = 'partial' if missing and facts else 'failed' if missing else 'complete'
    return ResearchResult(
        task_id=task.task_id, agent=task.agent, round=task.round, status=status,
        facts=tuple(facts), sources=tuple(sources), missing=tuple(missing),
        candidate_ids_considered=task.candidate_ids,
        summary=f'Collected bounded Places evidence for {len(grouped)} unique cafes; {len(missing)} explicit gaps.',
    )


async def run_cafe_task(context: ResearchContext, brief: ResearchBrief, task: ResearchTask) -> ResearchResult:
    """Three-input callable for build_research_service(cafe=run_cafe_task)."""
    if (task.agent != 'cafe_researcher' or task.research_id != brief.research_id
            or 'search_cafes_in_areas' not in task.allowed_tools
            or 'search_cafes_in_areas' not in context.allowed_tools or context.max_turns < 1
            or not 1 <= len(task.candidate_ids) <= MAX_AREAS):
        raise ValueError('Invalid or unbounded Cafe Researcher task')
    if any(not candidate_id.startswith('area:') for candidate_id in task.candidate_ids):
        raise ValueError('Cafe search targets must be area IDs')
    coordinates = {candidate.candidate_id: Coordinates(lat=candidate.lat, lng=candidate.lng)
                   for candidate in brief.initial_candidates}
    # Round-2 coordinates are passed as cited structured evidence, never guessed from
    # display names or recovered from another request's global state.
    expansion_coordinates: dict[str, list[Coordinates]] = {}
    for result in context.dependency_results:
        if (result.agent != 'expansion_researcher'
                or not result.task_id.startswith(f'task:{brief.session_id}:')
                or result.round > task.round):
            continue
        for evidence in result.facts:
            if (evidence.predicate == 'coordinates' and evidence.candidate_id in task.candidate_ids
                    and evidence.candidate_id.startswith('area:mta:')):
                value = _coordinates(evidence.value)
                if value:
                    expansion_coordinates.setdefault(evidence.candidate_id, []).append(value)
    for candidate_id, values in expansion_coordinates.items():
        if all(value == values[0] for value in values):
            coordinates[candidate_id] = values[0]
    key = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def collect(candidate_id):
        coord = coordinates.get(candidate_id)
        if coord is None:
            return AreaObservation(candidate_id, None, datetime.now(timezone.utc), error_code='DEPENDENCY_NOT_READY')
        if not key:
            return AreaObservation(candidate_id, coord, datetime.now(timezone.utc), error_code='PROVIDER_ERROR')
        async with semaphore:
            try:
                places = await asyncio.to_thread(provider._request_area,
                    {'area': candidate_id, **coord.model_dump()}, key)
                if not isinstance(places, list) or len(places) > 10:
                    raise ValueError('Invalid bounded response')
                return AreaObservation(candidate_id, coord, datetime.now(timezone.utc), tuple(places))
            except Exception:
                # Never serialize arbitrary request/SDK error strings or credentials.
                return AreaObservation(candidate_id, coord, datetime.now(timezone.utc), error_code='PROVIDER_ERROR')

    observations = await asyncio.gather(*(collect(candidate_id) for candidate_id in task.candidate_ids))
    return build_cafe_result(brief, task, tuple(observations))
