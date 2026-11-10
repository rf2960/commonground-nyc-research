"""Execute the production renderer with Node and a small DOM recording surface.

No JS build dependency is added to the Python app. These tests verify rendered content
and link attributes; real browser layout checks are a separate integration step.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text()
NODE = shutil.which('node')
pytestmark = pytest.mark.skipif(NODE is None, reason='Node is needed to execute the browser renderer')


def calls():
    return json.loads((ROOT / 'evals/examples/yulia/actual_agent.json').read_text())['actual']['tool_calls']


def render(events):
    implementation = HTML[HTML.index('function researchEvidence'):HTML.index('function byArea')]
    harness = '''
const fs=require('node:fs');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.textContent='';}
 append(...children){this.children.push(...children);}
 setAttribute(key,value){this.attributes[key]=value;}
}
function node(tag,cls,text=''){const el=new Element(tag);el.className=cls;el.textContent=text;return el;}
function parsed(value){try{return typeof value==='string'?JSON.parse(value):value;}catch{return null;}}
'''
    suffix = r'''
const result=researchEvidence(JSON.parse(fs.readFileSync(0,'utf8')));
const text=[],links=[],classes=[];
function visit(el){if(!el)return;text.push(el.textContent);classes.push(el.className);if(el.href)links.push({href:el.href,rel:el.rel,target:el.target});for(const child of el.children)visit(child);}
visit(result);console.log(JSON.stringify({text:text.join('\n'),links,classes,present:!!result}));
'''
    process = subprocess.run([NODE, '-e', harness + implementation + suffix],
                             input=json.dumps(events), text=True, capture_output=True)
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def test_missing_hours_card_shows_status_gaps_routes_and_auditable_sources():
    result = render(calls())
    assert 'Evidence insufficient' in result['text']
    assert 'Opening at meeting time: unknown' in result['text']
    assert 'Cafe Researcher · Round 1 / Transit Researcher · Round 2' in result['text']
    assert 'verify' in result['text'].lower()
    assert 'Exact cafe commute · Columbia University: 20 min / 35 min limit' in result['text']
    assert 'Area-center estimates — not exact cafe routes' in result['text']
    assert 'parent_candidate_id' in result['text'] and 'fact:cafe:r1:' in result['text']
    assert 'source:google-places:' in result['text'] and 'missing:cafe:r1:' in result['text']
    assert all(link['href'].startswith('https://') and link['rel'] == 'noopener noreferrer' for link in result['links'])


def test_center_estimates_cannot_be_displayed_as_verified_cafe_commutes():
    events = deepcopy(calls())
    for event in events:
        if event['agent'] == 'transit_researcher' and event['round'] == 2:
            payload = json.loads(event['result'])
            payload['facts'] = []
            event['result'] = json.dumps(payload)
        if event['name'] == 'evaluate_feasibility':
            event['result'] = '[]'
    text = render(events)['text']
    assert 'Not yet evaluated' in text
    assert 'Exact cafe commute · Columbia University: not verified' in text
    assert 'Area-center estimates — not exact cafe routes' in text


def test_untrusted_source_url_never_becomes_an_active_link():
    events = deepcopy(calls())
    for event in events:
        payload = json.loads(event['result'])
        if isinstance(payload, dict):
            for source in payload.get('sources', []):
                source['url'] = 'javascript:alert(1)'
            event['result'] = json.dumps(payload)
    result = render(events)
    assert not result['links']
    assert 'Source unavailable' in result['text']


def test_provisional_hours_are_visibly_qualified():
    events = deepcopy(calls())
    for event in events:
        payload = json.loads(event['result'])
        if event['agent'] == 'cafe_researcher':
            template = next(f for f in payload['facts'] if f['predicate'] == 'rating')
            payload['facts'].append({**template, 'fact_id': 'fact:cafe:r1:999',
                'predicate': 'open_at_meeting_time', 'value': True, 'provisional': True,
                'valid_for': {**template['valid_for'], 'meeting_time': '2026-10-10T14:00:00-04:00'}})
            payload['missing'] = []
            event['result'] = json.dumps(payload)
    assert 'Regular hours estimate: expected open — not guaranteed' in render(events)['text']


def test_search_failure_has_a_visible_recovery_action_without_venue_invention():
    events = [{'agent': 'cafe_researcher', 'round': 1, 'name': 'search_cafes_in_areas',
               'result': json.dumps({'facts': [], 'sources': [], 'missing': [{
                   'candidate_id': 'area:initial:test', 'field': 'cafe_search_results',
                   'missing_id': 'missing:cafe:r1:001', 'detail': 'Provider failed.',
                   'next_action': 'Retry the bounded search.'}]})}]
    result = render(events)
    assert 'Area search evidence missing' in result['text']
    assert 'Retry the bounded search.' in result['text']
    assert result['classes'].count('evidence-card') == 1


def test_legacy_calls_do_not_generate_research_evidence_cards():
    assert render([{'name': 'search_cafes_in_areas', 'result': '{"cafes": []}'}])['present'] is False
