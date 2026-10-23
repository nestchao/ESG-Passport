"""New AI evidence logic works through the existing questionnaire API only."""
from test_api import workspace, OWNER, CLERK, get, approve_with_ack


def test_existing_review_response_adds_advisory_without_changing_answer(workspace):
    client, *_ = workspace
    created = client.post('/questionnaires', headers=CLERK, json={
        'customer': 'AI Evidence Integration Test', 'period': '2026-09',
        'questions': ['How much water did your company withdraw during September 2026?'],
    })
    assert created.status_code == 201, created.text
    identifier = created.json()['id']
    matched = client.post(f'/questionnaires/{identifier}/map', headers=CLERK, json={})
    assert matched.status_code == 200, matched.text
    question = matched.json()['questions'][0]
    assert 'AI evidence readiness' not in question.get('uncertainty', '')
    assert 'E3.1' in question['proposed_codes']

    reviewed = client.put(f'/questions/{question["id"]}/review', headers=CLERK,
                          json={'codes': ['E3.1'], 'reviewed': True})
    assert reviewed.status_code == 200, reviewed.text
    result = get(client, f'/questionnaires/{identifier}')
    q = result['questions'][0]
    assert q['reviewed'] is True
    assert q['codes'] == ['E3.1']
    assert 'AI evidence readiness' in q['uncertainty']
    assert 'water_source_applicability_unconfirmed' in q['uncertainty']
    assert 'partial_period_coverage' not in q['uncertainty']
    assert q['answer'] == reviewed.json()['answer']
    assert result['status'] == 'draft'
    repeat = get(client, f'/questionnaires/{identifier}')
    assert repeat['version'] == result['version']
    assert repeat['questions'][0]['uncertainty'] == q['uncertainty']


def test_scope2_warnings_survive_existing_owner_approval_snapshot(workspace):
    client, *_ = workspace
    created = client.post('/questionnaires', headers=CLERK, json={
        'customer': 'Grid provenance review', 'period': '2026-09',
        'questions': ['Please disclose Scope 2 emissions from purchased electricity during September 2026'],
    })
    assert created.status_code == 201, created.text
    identifier = created.json()['id']
    matched = client.post(f'/questionnaires/{identifier}/map', headers=CLERK, json={})
    assert matched.status_code == 200, matched.text
    question = matched.json()['questions'][0]
    assert 'E1.2' in question['proposed_codes']
    saved = client.put(f'/questions/{question["id"]}/review', headers=CLERK,
                       json={'codes': ['E1.2'], 'reviewed': True})
    assert saved.status_code == 200, saved.text
    request = get(client, f'/questionnaires/{identifier}')
    note = request['questions'][0]['uncertainty']
    assert 'factor_review_decision_not_recorded' in note
    assert 'grid_region_not_recorded' in note
    assert 'AI evidence readiness' in note
    approved = approve_with_ack(client, identifier,
        {'version': request['version'], 'recipient': 'Buyer',
         'selected_evidence_ids': []})
    assert approved.status_code == 200, approved.text
    exported = approved.json()['snapshot']['questions'][0]
    assert exported['uncertainty'] == note
    assert exported['reviewed'] is True
    assert exported['evidence_ids'] == []
    review = approved.json()['snapshot']['pr9_preparation_review'][0]
    assert review['question_id'] == question['id']
    assert review['status'] == 'preparation_approved_with_gaps'
    assert review['unresolved_count'] > 0
    assert len(review['acknowledged_requirement_ids']) > 0
    assert 'pr9_private_preparations' not in approved.json()['snapshot']
    assert 'document_sha256' not in str(review)


def test_pr9_fingerprint_rejects_changed_shared_snapshot(workspace):
    from copy import deepcopy
    from sqlalchemy import select
    from esg_backend.models import ApprovedSnapshot
    from test_api import reviewed, approve
    client, sessions, *_ = workspace
    pack = approve(client, reviewed(client))
    assert len(pack['snapshot']['preparation_snapshot_sha256']) == 64
    token = pack['token']
    assert client.get(f'/shares/{token}').status_code == 200
    with sessions() as session:
        saved = session.scalar(select(ApprovedSnapshot).where(ApprovedSnapshot.token == token))
        changed = deepcopy(saved.snapshot)
        changed['recipient'] = 'Changed after approval'
        saved.snapshot = changed
        session.commit()
    assert client.get(f'/shares/{token}').status_code == 409
    assert client.get(f'/shares/{token}/evidence/doc-water').status_code == 409
