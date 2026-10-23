"""PR #9 approval never invents acknowledgement and its export stays private."""
from copy import deepcopy
from sqlalchemy import select
from test_api import workspace, OWNER, reviewed, get
from esg_backend.models import ApprovedSnapshot
from esg_backend.ai_evidence import existing_question_coverage
from ai.workflow.outcome import export_preparation

REASON = 'Owner reviewed each limitation and agrees to share this partial disclosure.'


def initiate(client, request, selected=None, recipient='Buyer'):
    body = {'version': request['version'], 'recipient': recipient,
            'selected_evidence_ids': ['doc-water'] if selected is None else selected}
    attempt = client.post(f'/questionnaires/{request["id"]}/approve-share', headers=OWNER, json=body)
    assert attempt.status_code == 409, attempt.text
    review = attempt.json()['detail']['pr9_review']
    assert review['items']
    assert len(review['hash']) == 64
    return body, review


def accept(client, request, body, review, ids=None, reason=REASON):
    return client.post(f'/questionnaires/{request["id"]}/approve-share', headers=OWNER,
        json={**body, 'pr9_review_hash': review['hash'],
              'acknowledged_issues': [item['id'] for item in review['items']] if ids is None else ids,
              'pr9_review_reason': reason})


def test_each_gap_requires_explicit_acknowledgement_and_reason(workspace):
    client, *_ = workspace
    request = reviewed(client)
    body, review = initiate(client, request)
    assert all('issue' in item and 'id' in item for item in review['items'])
    incomplete = accept(client, request, body, review, ids=[])
    assert incomplete.status_code == 409
    assert accept(client, request, body, review, reason='yes').status_code == 409
    assert accept(client, request, body, review, ids=[review['items'][0]['id']] * len(review['items'])).status_code == 409 if len(review['items'])>1 else True
    assert get(client, f'/questionnaires/{request["id"]}')['status'] != 'shared'
    assert get(client, '/shares') == []


def test_valid_gap_acknowledgements_produce_audited_private_preparation(workspace):
    client, sessions, *_ = workspace
    request = reviewed(client)
    body, review = initiate(client, request)
    successful = accept(client, request, body, review)
    assert successful.status_code == 200, successful.text
    public = successful.json()['snapshot']
    assert 'pr9_private_preparations' not in public
    assert 'pr9_owner_review' not in public
    assert public['pr9_preparation_review']
    assert all(row['status'] in ('preparation_approved_with_gaps','manual_review_required','preparation_approved')
               for row in public['pr9_preparation_review'])
    with sessions() as db:
        pack = db.scalar(select(ApprovedSnapshot).where(ApprovedSnapshot.token == successful.json()['token']))
        snapshot = deepcopy(pack.snapshot)
        assert set(snapshot['pr9_owner_review']['acknowledged_issues']) == set(item['id'] for item in review['items'])
        assert snapshot['pr9_owner_review']['reason'] == REASON
        for item in snapshot['pr9_private_preparations']:
            outcome = item['approved_preparation']
            assert outcome['approval']['reviewer']
            assert outcome['approval']['acknowledged_requirements']
            assert all(row['is_verified_disclosure'] is False for row in outcome['rows'])
            assert export_preparation(outcome)
    customer = get(client, '/shares/' + successful.json()['token'], headers={})['snapshot']
    assert 'pr9_private_preparations' not in customer
    assert 'pr9_owner_review' not in customer


def test_changed_selection_or_version_invalidates_owner_consent(workspace):
    client, *_ = workspace
    request = reviewed(client)
    body, review = initiate(client, request, selected=['doc-water'])
    stale = accept(client, request, {**body,'selected_evidence_ids':[]}, review)
    assert stale.status_code == 409
    assert stale.json()['detail']['pr9_review']['hash'] != review['hash']
    tampered = accept(client, request, body, {**review,'hash':'0'*64})
    assert tampered.status_code == 409
    assert get(client, f'/questionnaires/{request["id"]}')['status'] != 'shared'
