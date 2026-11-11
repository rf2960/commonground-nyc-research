"""Opt-in, redacted delivery captures for Yulia's Places and model evidence.

These commands never fabricate a successful live/model run when configuration is
missing. They write a machine-readable blocked/failed/passed record and exit nonzero
unless the requested capture actually succeeds. Unit tests inject all paid boundaries.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable

from commonground.research.cafe_agent import run_cafe_task
from commonground.research.models import ResearchBrief, ResearchTask
from commonground.research.runner import ResearchContext
from evals.baseline import capture_no_tools_baseline
from evals.rubric_judge import judge_writer_answer
from evals.runner import load_case

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE = ROOT / 'evals/cases/yulia_missing_hours.json'


def _record(kind: str, status: str, **values) -> dict[str, Any]:
    return {'schema_version': 'yulia-delivery-v1', 'kind': kind, 'status': status,
            'captured_at': datetime.now(timezone.utc).isoformat(), **values}


def capture_places_smoke(
    brief: ResearchBrief, *, live: bool = False, executor=run_cafe_task,
) -> dict[str, Any]:
    """Make at most one inherited nearby-search request; never route any travelers."""
    if not live:
        return _record('places_smoke', 'blocked', reason_code='LIVE_OPT_IN_REQUIRED',
                       live_provider_observation=False)
    key = os.environ.get('GOOGLE_MAPS_API_KEY', '').strip()
    if not key:
        return _record('places_smoke', 'blocked', reason_code='MAPS_KEY_NOT_CONFIGURED',
                       live_provider_observation=False)
    if brief.meeting_time <= datetime.now(timezone.utc):
        return _record('places_smoke', 'blocked', reason_code='FUTURE_MEETING_TIME_REQUIRED',
                       live_provider_observation=False)
    target = brief.initial_candidates[0]
    task = ResearchTask(
        task_id=f'task:{brief.session_id}:r1:cafe:1', research_id=brief.research_id,
        round=1, agent='cafe_researcher', objective='One-area live Places smoke; no transit claim.',
        candidate_ids=(target.candidate_id,), allowed_tools=('search_cafes_in_areas',),
    )
    context = ResearchContext(messages=[], allowed_tools=task.allowed_tools, max_turns=1)
    try:
        result = asyncio.run(executor(context, brief, task))
        serialized = result.model_dump_json()
        if key in serialized:
            return _record('places_smoke', 'failed', reason_code='OUTPUT_REDACTION_FAILED',
                           live_provider_observation=False)
        source_ids = {source.source_id for source in result.sources}
        cafes = {fact.candidate_id for fact in result.facts if fact.candidate_id.startswith('cafe:gplaces:')}
        checks = {
            'one_area_only': result.candidate_ids_considered == (target.candidate_id,),
            'provider_response_received': any(f.predicate == 'cafe_search_results' for f in result.facts),
            'all_facts_cited': all(set(f.source_ids) <= source_ids for f in result.facts),
            'regular_hours_are_provisional': all(f.provisional for f in result.facts
                if f.predicate == 'open_at_meeting_time' and f.valid_for.get('basis') == 'regular_schedule'),
            'missing_hours_are_explicit': all(
                any(f.candidate_id == cafe and f.predicate == 'open_at_meeting_time' for f in result.facts)
                or any(g.candidate_id == cafe and g.field == 'open_at_meeting_time' for g in result.missing)
                for cafe in cafes),
            'no_transit_claims': not any(f.predicate == 'transit_duration_minutes' for f in result.facts),
        }
        passed = all(checks.values())
        return _record('places_smoke', 'passed' if passed else 'failed',
            live_provider_observation=bool(source_ids), checks=checks,
            scope={'area_id': target.candidate_id, 'max_requests': 1, 'radius_meters': 800,
                   'max_records': 10, 'transit_tested': False,
                   'traveler_records': 'Brief controls only; no live route claim.'},
            result=result.model_dump(mode='json'))
    except Exception:
        return _record('places_smoke', 'failed', reason_code='SAFE_PROVIDER_FAILURE',
                       live_provider_observation=False)


def capture_model_evaluation(
    *, manifest: dict[str, Any] | None, agent_capture: dict[str, Any],
    case: dict[str, Any], baseline: Callable = capture_no_tools_baseline,
    judge: Callable = judge_writer_answer,
) -> dict[str, Any]:
    """Require an actual frozen model capture before claiming a same-model baseline.

    A fixed-data Writer capture has no model identity and cannot satisfy this gate.
    Manifest and capture model IDs must match; the same user question is used verbatim.
    """
    if not manifest or manifest.get('frozen') is not True or not manifest.get('model'):
        return _record('model_evaluation', 'blocked', reason_code='FROZEN_MODEL_MANIFEST_REQUIRED')
    build = agent_capture.get('build', {})
    if build.get('kind') != 'model-backed research' or build.get('model') != manifest['model']:
        return _record('model_evaluation', 'blocked', reason_code='MATCHING_MODEL_AGENT_CAPTURE_REQUIRED')
    if agent_capture.get('case_id') != case['case_id'] or agent_capture.get('question') != case['question']:
        return _record('model_evaluation', 'blocked', reason_code='CAPTURE_CASE_OR_QUESTION_MISMATCH')
    answer = agent_capture.get('actual', {}).get('response')
    if not isinstance(answer, str) or not answer.strip():
        return _record('model_evaluation', 'blocked', reason_code='ACTUAL_AGENT_RESPONSE_REQUIRED')
    expected_claims = case.get('expected', {}).get('rubric_reference_claims')
    if not expected_claims:
        return _record('model_evaluation', 'blocked', reason_code='RUBRIC_REFERENCE_REQUIRED')
    try:
        location = manifest.get('vertex_location', 'global')
        baseline_capture = baseline(case_id=case['case_id'], question=case['question'],
            model=manifest['model'], vertex_location=location)
        judge_model = manifest.get('judge_model') or manifest['model']
        judge_args = dict(question=case['question'], expected_claims=expected_claims,
            allowed_source_ids=case['expected']['required_source_ids'],
            model=judge_model, vertex_location=location)
        agent_score = judge(answer=answer, **judge_args)
        baseline_score = judge(answer=baseline_capture['raw_output'], **judge_args)
        return _record('model_evaluation', 'passed', case_id=case['case_id'],
            question=case['question'], expected_claims=expected_claims,
            allowed_source_ids=case['expected']['required_source_ids'],
            model=manifest['model'], judge_model=judge_model,
            agent_capture_build=build, baseline=baseline_capture,
            agent_rubric=agent_score.model_dump(mode='json'),
            baseline_rubric=baseline_score.model_dump(mode='json'),
            scores={'agent': agent_score.normalized_score, 'baseline': baseline_score.normalized_score},
            caveat='One owner example; this is not a 50-case hill-climbing result.')
    except Exception:
        return _record('model_evaluation', 'failed', reason_code='SAFE_MODEL_CAPTURE_FAILURE')


def write_record(path: Path, record: dict[str, Any]) -> None:
    """Keep successful captures intact if a later attempt is blocked or fails."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get('status') == 'passed' and record.get('status') != 'passed':
            path = path.with_name(path.stem + '.latest_attempt' + path.suffix)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    places = sub.add_parser('places-smoke')
    places.add_argument('--live', action='store_true', help='Permit at most one paid Places request.')
    places.add_argument('--meeting-time', help='Future ISO time with explicit UTC offset.')
    places.add_argument('--output', type=Path, default=ROOT/'evals/examples/yulia/live_places_smoke.json')
    model = sub.add_parser('model-eval')
    model.add_argument('--manifest', type=Path)
    model.add_argument('--agent-capture', type=Path, default=ROOT/'evals/examples/yulia/actual_agent.json')
    model.add_argument('--output', type=Path, default=ROOT/'evals/examples/yulia/model_evaluation.json')
    args = parser.parse_args()
    case = load_case(DEFAULT_CASE)
    try:
        if args.command == 'places-smoke':
            raw = json.loads((ROOT/case['fixtures']['brief_path']).read_text(encoding="utf-8"))
            raw['question'] = 'One-area live Places smoke; collect cafe evidence only, without transit verification.'
            if args.meeting_time:
                raw['meeting_time'] = args.meeting_time
            brief = ResearchBrief.model_validate(raw)
            record = capture_places_smoke(brief, live=args.live)
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest else None
            capture = json.loads(args.agent_capture.read_text(encoding="utf-8"))
            record = capture_model_evaluation(manifest=manifest, agent_capture=capture, case=case)
    except Exception:
        record = _record(args.command, 'blocked', reason_code='INVALID_INPUT_OR_CAPTURE')
    write_record(args.output, record)
    if args.command == 'model-eval' and record['status'] == 'passed':
        write_record(args.output.parent/'no_tools_baseline.json',
                     {'status': 'passed', **record['baseline']})
        write_record(args.output.parent/'rubric_scores.json', {
            key: value for key, value in record.items() if key != 'baseline'
        })
    # Only status/reason/checks are printed; raw provider or model failures are not.
    print(json.dumps({key: record[key] for key in ('kind', 'status', 'reason_code', 'checks') if key in record}))
    return 0 if record['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
