import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from commonground.research import ResearchBrief, ResearchResult
from commonground.research.cafe_agent import AreaObservation, build_cafe_result, run_cafe_task
from commonground.research.lead import LeadOrchestrator
from commonground.research.models import Coordinates
from commonground.research.runner import ResearchContext, ResearchRunner
from commonground.research.service import DeepResearchService

FIXTURES = Path(__file__).parent / 'fixtures'
NOW = datetime(2026, 10, 1, 16, tzinfo=timezone.utc)
PLACE = {
    'id': 'fixture-yulia', 'displayName': {'text': 'Fixture Cafe'},
    'formattedAddress': '123 Fixture Street, New York, NY',
    'location': {'latitude': 40.736, 'longitude': -73.991},
    'rating': 4.5, 'priceLevel': 'PRICE_LEVEL_MODERATE',
    'businessStatus': 'OPERATIONAL',
    'googleMapsUri': 'https://maps.google.com/?cid=123',
    'regularOpeningHours': {'periods': [
        {'open': {'day': 6, 'hour': 9}, 'close': {'day': 6, 'hour': 17}}]},
}
CAFE = 'cafe:gplaces:fixture-yulia'


def brief():
    return ResearchBrief.model_validate_json((FIXTURES / 'research_brief.json').read_text(encoding="utf-8"))


def task():
    return LeadOrchestrator.build_initial_tasks(brief())[1]


def context(**changes):
    return ResearchContext(messages=[], allowed_tools=('search_cafes_in_areas',), max_turns=1, **changes)


def normalize(places=None):
    return build_cafe_result(brief(), task(), tuple(
        AreaObservation(area.candidate_id, Coordinates(lat=area.lat, lng=area.lng), NOW,
                        tuple(places if places is not None else [deepcopy(PLACE)]))
        for area in brief().initial_candidates))


def fields(result):
    return {fact.predicate: fact for fact in result.facts if fact.candidate_id == CAFE}


@pytest.fixture(autouse=True)
def no_live_requests(monkeypatch):
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY', 'fixture-secret')
    fake = Mock(return_value=[deepcopy(PLACE)])
    monkeypatch.setattr('commonground.research.cafe_agent.provider._request_area', fake)
    return fake


def test_success_has_cited_fields_and_exact_destination():
    result = normalize()
    data = fields(result)
    assert result.status == 'complete'
    assert data['address'].value == PLACE['formattedAddress']
    assert data['coordinates'].value == {'lat': 40.736, 'lng': -73.991}
    assert data['price_level'].value == 2
    assert data['business_status'].value == 'OPERATIONAL'
    assert data['open_at_meeting_time'].value is True
    assert data['open_at_meeting_time'].provisional is True
    assert data['open_at_meeting_time'].valid_for['meeting_time'] == brief().meeting_time.isoformat()
    assert ResearchResult.model_validate_json(result.model_dump_json()) == result
    assert all(f.source_ids for f in result.facts)
    assert any(str(s.url) == PLACE['googleMapsUri'] for s in result.sources)


def test_missing_future_hours_is_a_gap_never_a_boolean():
    place = deepcopy(PLACE)
    place.pop('regularOpeningHours')
    result = normalize([place])
    assert result.status == 'partial'
    assert 'open_at_meeting_time' not in fields(result)
    gap = next(g for g in result.missing if g.field == 'open_at_meeting_time')
    assert gap.candidate_id == CAFE
    assert gap.reason_code == 'PROVIDER_FIELD_MISSING'
    assert not gap.retryable
    assert 'venue' in gap.next_action


def test_duplicate_id_retains_all_stable_parent_ids_once():
    result = normalize([deepcopy(PLACE), deepcopy(PLACE)])
    parents = fields(result)['parent_candidate_id']
    assert parents.value == 'area:initial:downtown-brooklyn'
    assert parents.valid_for['parent_candidate_ids'] == sorted(task().candidate_ids)
    assert len([f for f in result.facts if f.candidate_id == CAFE and f.predicate == 'name']) == 1
    assert len(parents.source_ids) == 4


@pytest.mark.parametrize('field', ['displayName', 'formattedAddress', 'location', 'rating', 'priceLevel', 'businessStatus'])
def test_missing_fields_are_retained_as_explicit_gaps(field):
    place = deepcopy(PLACE)
    place.pop(field)
    result = normalize([place])
    expected = {'displayName': 'name', 'formattedAddress': 'address', 'location': 'coordinates',
                'rating': 'rating', 'priceLevel': 'price_level', 'businessStatus': 'business_status'}[field]
    assert expected not in fields(result)
    assert any(g.candidate_id == CAFE and g.field == expected for g in result.missing)


def test_nonpassing_filters_remain_evidence_not_a_relaxed_recommendation():
    result = normalize([dict(PLACE, rating=3.0, priceLevel='PRICE_LEVEL_EXPENSIVE')])
    assert fields(result)['rating'].value == 3.0
    assert fields(result)['price_level'].value == 3
    assert LeadOrchestrator._routeable_cafes(brief(), result) == ()


@pytest.mark.parametrize('rating', [True, float('nan'), float('inf'), '4.5', 6])
def test_malformed_rating_stays_unknown(rating):
    result = normalize([dict(PLACE, rating=rating)])
    assert 'rating' not in fields(result)
    assert any(g.field == 'rating' for g in result.missing)


def test_overnight_regular_hours_are_provisional():
    place = dict(PLACE, regularOpeningHours={'periods': [
        {'open': {'day': 5, 'hour': 22}, 'close': {'day': 6, 'hour': 15}}]})
    assert fields(normalize([place]))['open_at_meeting_time'].value is True
    assert fields(normalize([place]))['open_at_meeting_time'].provisional is True


def test_conflicting_overlap_does_not_choose_passing_rating():
    b = brief()
    observations = tuple(AreaObservation(area.candidate_id, Coordinates(lat=area.lat, lng=area.lng),
                                        NOW, (dict(PLACE, rating=rating),))
                         for area, rating in zip(b.initial_candidates, (4.5, 3.0)))
    result = build_cafe_result(b, task(), observations)
    assert 'rating' not in fields(result)
    assert any(g.field == 'rating' and g.reason_code == 'VALIDATION_ERROR' for g in result.missing)


def test_partial_provider_failure_keeps_success_and_redacts_errors(no_live_requests):
    no_live_requests.side_effect = [ValueError('fixture-secret'), [deepcopy(PLACE)]]
    result = asyncio.run(run_cafe_task(context(), brief(), task()))
    assert result.status == 'partial'
    assert fields(result)['name'].value == 'Fixture Cafe'
    assert any(g.reason_code == 'PROVIDER_ERROR' for g in result.missing)
    assert 'fixture-secret' not in result.model_dump_json()


def test_missing_key_and_all_provider_failures_are_explicit(no_live_requests, monkeypatch):
    monkeypatch.delenv('GOOGLE_MAPS_API_KEY')
    result = asyncio.run(run_cafe_task(context(), brief(), task()))
    no_live_requests.assert_not_called()
    assert result.status == 'failed'
    assert len(result.missing) == len(task().candidate_ids)


def test_empty_search_is_bounded_not_proof_no_cafes_exist(no_live_requests):
    no_live_requests.return_value = []
    result = asyncio.run(run_cafe_task(context(), brief(), task()))
    assert result.status == 'complete' and not result.missing
    assert all(f.value == [] and f.valid_for['exhaustive'] is False for f in result.facts)


def test_missing_identity_is_an_area_gap():
    result = normalize([{'displayName': {'text': 'Unknown identity'}}])
    assert all(not f.candidate_id.startswith('cafe:') for f in result.facts)
    assert all(g.field == 'place_identity' for g in result.missing)


@pytest.mark.parametrize('parameter', ['key', 'client_secret', 'password', 'secret', 'x-goog-api-key'])
def test_secret_bearing_maps_url_is_not_echoed(parameter):
    result = normalize([dict(PLACE, googleMapsUri=f'https://maps.google.com/?{parameter}=fixture-secret')])
    assert 'fixture-secret' not in result.model_dump_json()
    assert result.status == 'complete'


def test_malformed_maps_url_does_not_discard_other_evidence():
    result = normalize([dict(PLACE, googleMapsUri='https://[bad-url')])
    assert result.status == 'complete'
    assert fields(result)['name'].value == 'Fixture Cafe'


def test_six_area_request_is_bounded_and_does_not_block_event_loop(no_live_requests):
    from threading import Lock
    from time import sleep
    base = brief().model_dump(mode='json')
    base['initial_candidates'] = [dict(base['initial_candidates'][0],
        candidate_id=f'area:initial:fixture-{index}') for index in range(6)]
    b = ResearchBrief.model_validate(base)
    active = peak = 0
    lock = Lock()
    def fake_request(*args):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        sleep(0.01)
        with lock:
            active -= 1
        return [deepcopy(PLACE)]
    no_live_requests.side_effect = fake_request
    result = asyncio.run(run_cafe_task(context(), b, LeadOrchestrator.build_initial_tasks(b)[1]))
    assert result.status == 'complete'
    assert no_live_requests.call_count == 6
    assert peak == 3
    assert len(fields(result)['parent_candidate_id'].valid_for['parent_candidate_ids']) == 6


def test_round_two_uses_cited_expansion_coordinates(no_live_requests):
    results = [ResearchResult.model_validate(r) for r in json.loads((FIXTURES / 'round_1_results.json').read_text(encoding="utf-8"))]
    expansion = next(r for r in results if r.agent == 'expansion_researcher')
    followup = LeadOrchestrator._research_task(brief(), round_number=2, agent='cafe_researcher',
        objective='Fixture expansion search', candidate_ids=('area:mta:fixture-queensboro-plaza',),
        dependencies=('fact:expansion:r1:003',))
    result = asyncio.run(run_cafe_task(context(dependency_results=(expansion,)), brief(), followup))
    assert result.status == 'complete'
    assert no_live_requests.call_args.args[0]['lat'] == 40.7506
    assert fields(result)['parent_candidate_id'].value == 'area:mta:fixture-queensboro-plaza'


def test_round_two_without_coordinates_never_queries_provider(no_live_requests):
    followup = LeadOrchestrator._research_task(brief(), round_number=2, agent='cafe_researcher',
        objective='Fixture expansion search', candidate_ids=('area:mta:missing',))
    result = asyncio.run(run_cafe_task(context(), brief(), followup))
    no_live_requests.assert_not_called()
    assert result.missing[0].reason_code == 'DEPENDENCY_NOT_READY'


def test_no_cross_role_tool_calls(no_live_requests):
    invalid_context = ResearchContext(messages=[], allowed_tools=('get_transit_matrix',), max_turns=1)
    with pytest.raises(ValueError):
        asyncio.run(run_cafe_task(invalid_context, brief(), task()))
    no_live_requests.assert_not_called()


def test_missing_hours_runs_through_actual_lead_feasibility_and_writer(no_live_requests):
    place = deepcopy(PLACE)
    place.pop('regularOpeningHours')
    no_live_requests.return_value = [place]
    b = brief()
    async def execute(ctx, brief_value, task_value):
        if task_value.agent == 'cafe_researcher':
            return await run_cafe_task(ctx, brief_value, task_value)
        if task_value.agent == 'expansion_researcher':
            return ResearchResult(task_id=task_value.task_id, agent=task_value.agent, round=task_value.round,
                status='complete', candidate_ids_considered=task_value.candidate_ids, summary='Synthetic empty expansion.')
        # Synthetic Routes fixture only; this test makes no Routes API calls.
        source = {'source_id': f'source:google-routes:yulia-r{task_value.round}',
            'provider': 'google_routes', 'title': 'Synthetic exact route fixture',
            'url': 'https://developers.google.com/maps/documentation/routes',
            'accessed_at': NOW, 'request_summary': {'fixture': True}, 'attribution': 'Synthetic fixture'}
        route_facts = []
        for index, traveler in enumerate(b.travelers, 1):
            if task_value.round == 2:
                assert any(f.candidate_id == CAFE and f.predicate == 'coordinates'
                           for r in ctx.dependency_results for f in r.facts)
                route_facts.append({'fact_id': f'fact:transit:r2:{index:03d}', 'candidate_id': CAFE,
                    'subject_id': traveler.traveler_id, 'predicate': 'transit_duration_minutes',
                    'value': 20, 'observed_at': NOW, 'source_ids': [source['source_id']],
                    'valid_for': {'arrival_time': b.meeting_time.isoformat(), 'destination_kind': 'exact_cafe'}})
        return ResearchResult.model_validate({'task_id': task_value.task_id, 'agent': task_value.agent,
            'round': task_value.round, 'status': 'complete', 'candidate_ids_considered': task_value.candidate_ids,
            'facts': route_facts, 'sources': [source], 'summary': 'Synthetic Routes fixture.'})
    output = DeepResearchService(ResearchRunner(execute)).run_sync(b)
    assert output.run.feasibility_results[0].status == 'EVIDENCE_INSUFFICIENT'
    assert output.report.recommended_cafe_id is None
    assert 'open_at_meeting_time' in output.response and 'venue' in output.response
    assert all('agent' in event and 'round' in event for event in output.tool_calls)
