import json
from pathlib import Path

import pytest

from commonground.research.models import ResearchResult, Source


def source():
    path = Path(__file__).parent / 'fixtures' / 'round_1_results.json'
    return json.loads(path.read_text())[0]['sources'][0]


@pytest.mark.parametrize('url', [
    'https://example.com/?key=secret',
    'https://example.com/?access_token=secret',
    'https://user:secret@example.com/data',
])
def test_common_credential_urls_are_rejected(url):
    with pytest.raises(ValueError, match='credentials'):
        Source.model_validate({**source(), 'url': url})


def test_nested_key_credentials_are_rejected():
    with pytest.raises(ValueError, match='credential'):
        Source.model_validate({**source(), 'request_summary': {'nested': {'key': 'secret'}}})


def test_duplicate_missing_ids_are_rejected_before_writer():
    payload = json.loads((Path(__file__).parent / 'fixtures' / 'round_1_results.json').read_text())[0]
    gap = {'missing_id': 'missing:transit:r1:001', 'candidate_id': payload['candidate_ids_considered'][0],
           'field': 'research_result', 'reason_code': 'PROVIDER_ERROR', 'detail': 'Fixture gap.',
           'retryable': False, 'next_action': 'Verify provider.'}
    payload['missing'] = [gap, gap]
    with pytest.raises(ValueError, match='missing IDs'):
        ResearchResult.model_validate(payload)
