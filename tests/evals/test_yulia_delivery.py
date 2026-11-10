from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from commonground.research.cafe_agent import AreaObservation, build_cafe_result
from commonground.research.models import Coordinates, ResearchBrief
from evals.rubric_judge import RubricJudgeResult
from evals.yulia_delivery import capture_model_evaluation, capture_places_smoke, write_record

ROOT = Path(__file__).resolve().parents[2]


def brief():
    raw = json.loads((ROOT/'tests/research/fixtures/yulia_research_brief.json').read_text())
    raw['meeting_time'] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    return ResearchBrief.model_validate(raw)


def test_places_capture_requires_opt_in_and_key_before_any_request(monkeypatch):
    monkeypatch.delenv('GOOGLE_MAPS_API_KEY', raising=False)
    async def forbidden(*args):
        raise AssertionError('Must not call a paid provider without configuration')
    assert capture_places_smoke(brief(), executor=forbidden)['reason_code'] == 'LIVE_OPT_IN_REQUIRED'
    assert capture_places_smoke(brief(), live=True, executor=forbidden)['reason_code'] == 'MAPS_KEY_NOT_CONFIGURED'


def test_places_capture_is_one_area_normalized_and_credential_free(monkeypatch):
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY', 'fixture-only-secret')
    calls = []
    async def execute(context, b, task):
        calls.append(task)
        area = b.initial_candidates[0]
        place = json.loads((ROOT/'tests/research/fixtures/yulia_places_missing_hours.json').read_text())['places'][0]
        return build_cafe_result(b, task, (AreaObservation(area.candidate_id,
            Coordinates(lat=area.lat, lng=area.lng), datetime.now(timezone.utc), (place,)),))
    record = capture_places_smoke(brief(), live=True, executor=execute)
    assert record['status'] == 'passed'
    assert len(calls) == 1 and len(calls[0].candidate_ids) == 1
    assert all(record['checks'].values())
    assert 'fixture-only-secret' not in json.dumps(record)
    assert record['scope']['transit_tested'] is False


def test_places_raw_provider_exceptions_are_never_recorded(monkeypatch):
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY', 'fixture-only-secret')
    async def fail(*args):
        raise RuntimeError('fixture-only-secret')
    record = capture_places_smoke(brief(), live=True, executor=fail)
    assert record['status'] == 'failed'
    assert 'fixture-only-secret' not in json.dumps(record)


def test_fixture_writer_output_cannot_be_claimed_as_a_same_model_capture():
    case = json.loads((ROOT/'evals/cases/yulia_missing_hours.json').read_text())
    capture = json.loads((ROOT/'evals/examples/yulia/actual_agent.json').read_text())
    assert capture_model_evaluation(manifest=None, agent_capture=capture, case=case)['status'] == 'blocked'
    record = capture_model_evaluation(manifest={'frozen': True, 'model': 'test-model'}, agent_capture=capture, case=case)
    assert record['reason_code'] == 'MATCHING_MODEL_AGENT_CAPTURE_REQUIRED'


def test_baseline_and_two_rubric_scores_use_the_frozen_model_and_exact_question():
    observed = []
    case = {'case_id': 'test-1', 'question': 'Exact test question?',
            'expected': {'required_source_ids': ['source:provider:1'],
                         'rubric_reference_claims': ['Opening status is unknown.']}}
    capture = {'case_id': case['case_id'], 'question': case['question'],
               'build': {'kind': 'model-backed research', 'model': 'test-model'},
               'actual': {'response': 'Unknown opening status.'}}
    def baseline(**kwargs):
        observed.append(('baseline', kwargs))
        return {'raw_output': 'A model-only answer.', 'model': kwargs['model']}
    def judge(**kwargs):
        observed.append(('judge', kwargs))
        return RubricJudgeResult.model_validate({'scores': {
            'recommendation_correctness': 4, 'calibrated_uncertainty': 4,
            'comparison_usefulness': 3, 'citation_support': 3}, 'rationale': 'Injected unit-test score.'})
    result = capture_model_evaluation(manifest={'frozen': True, 'model': 'test-model'},
        agent_capture=capture, case=case, baseline=baseline, judge=judge)
    assert result['status'] == 'passed'
    assert len(observed) == 3
    assert all(call['model'] == 'test-model' and call['question'] == case['question'] for _, call in observed)
    assert 'answer' not in observed[0][1] and 'allowed_source_ids' not in observed[0][1]


def test_failed_attempt_does_not_destroy_successful_capture(tmp_path):
    path = tmp_path/'capture.json'
    write_record(path, {'status': 'passed', 'value': 'saved evidence'})
    write_record(path, {'status': 'blocked', 'reason_code': 'MISSING_CONFIG'})
    assert json.loads(path.read_text())['status'] == 'passed'
    assert json.loads((tmp_path/'capture.latest_attempt.json').read_text())['status'] == 'blocked'
