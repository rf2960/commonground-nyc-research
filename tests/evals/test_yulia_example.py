import json
from datetime import datetime
from pathlib import Path

from commonground.research.cafe_agent import AreaObservation, build_cafe_result
from commonground.research.lead import LeadOrchestrator
from commonground.research.models import Coordinates, ResearchBrief, ResearchResult
from evals.runner import evaluate_case, load_case

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/research/fixtures'


def test_yulia_actual_pipeline_capture_passes_golden_checks():
    result = evaluate_case(load_case(ROOT / 'evals/cases/yulia_missing_hours.json'))
    assert result['passed'] is True
    assert result['deterministic_score'] == 1.0
    assert result['actual']['feasibility_statuses'] == {'cafe:gplaces:fixture-yulia': 'EVIDENCE_INSUFFICIENT'}
    assert result['actual']['recommended_cafe_id'] is None


def test_golden_places_evidence_is_reproducible_from_raw_synthetic_response():
    raw = json.loads((FIXTURES / 'yulia_places_missing_hours.json').read_text(encoding="utf-8"))
    brief = ResearchBrief.model_validate_json((FIXTURES / 'yulia_research_brief.json').read_text(encoding="utf-8"))
    observations = tuple(AreaObservation(area.candidate_id, Coordinates(lat=area.lat, lng=area.lng),
                                        datetime.fromisoformat(raw['accessed_at']), tuple(raw['places']))
                         for area in brief.initial_candidates)
    generated = build_cafe_result(brief, LeadOrchestrator.build_initial_tasks(brief)[1], observations)
    stored = json.loads((FIXTURES / 'yulia_round_1_results.json').read_text(encoding="utf-8"))[1]
    assert generated == ResearchResult.model_validate(stored)
    assert raw['synthetic'] is True and raw['live_provider_observation'] is False
