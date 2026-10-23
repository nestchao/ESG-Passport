"""Smoke real synthetic bills through offline OCR and existing backend APIs.

The synthetic labels are intended targets, not ground-truth verification of
real commercial bills. All HTTP tests use isolated SQLite and fake storage.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from esg_backend.bill_ocr import extract_upload, parse_bill_text
from test_api import workspace, OWNER, CLERK, get

DATASET = Path(__file__).resolve().parents[2] / 'ai' / 'synthetic_dataset'


def activity_target(label):
    return next((item for item in label['expected_fields'] if item.get('role') == 'activity'), None)


def activity_category(label):
    activity = activity_target(label)
    return ('petrol' if activity and activity['field'] == 'petrol_consumption'
            else 'diesel' if activity and activity['field'] == 'diesel_consumption'
            else label['category'])


def test_all_synthetic_annotations_are_conservatively_parsed():
    """Check all 360 labelled intended transcripts without running image OCR."""
    seen = {'electricity': 0, 'fuel': 0, 'water': 0, 'waste': 0}
    for path in sorted(DATASET.glob('*/*.json')):
        label = json.loads(path.read_text(encoding='utf-8'))
        kind = activity_category(label)
        result = parse_bill_text([row['text'] for row in label['intended_lines']],
                                 kind, label['period']['start'][:7])
        target = activity_target(label)
        seen[label['category']] += 1
        if label['category'] == 'waste':
            # Waste transfer is NOT synonymous with disposal or recovery.
            assert result['activities'] == [], path.name
            assert 'Transfer weights' in ' '.join(result['uncertainty_notes']), path.name
        else:
            assert len(result['activities']) == 1, path.name
            candidate = result['activities'][0]
            assert Decimal(candidate['quantity']) == Decimal(target['value']), path.name
            assert candidate['unit'] == target['unit'], path.name
            assert candidate['category'] == kind, path.name
            assert candidate['period_start'] == target['period']['start'], path.name
            assert candidate['period_end'] == target['period']['end'], path.name
    assert seen == {'electricity': 90, 'fuel': 90, 'water': 90, 'waste': 90}


@pytest.mark.parametrize('name,kind', [
    ('electricity/electricity-payment-stub-001-photo', 'electricity'),
    ('water/water-sidebar-001-photo', 'water'),
    ('fuel/fuel-pump-001-photo', 'petrol'),
    ('waste/waste-thermal-001-photo', 'waste'),
])
def test_photographed_synthetic_bills_never_invent_values(name, kind):
    label = json.loads((DATASET / (name + '.json')).read_text(encoding='utf-8'))
    result = extract_upload((DATASET / (name + '.png')).read_bytes(),
                            'image/png', kind, label['period']['start'][:7])
    expected = activity_target(label)
    if kind == 'waste':
        assert result['activities'] == []
        assert result['ocr_status'] == 'manual_entry_required'
    else:
        assert len(result['activities']) == 1, (name, result)
        candidate = result['activities'][0]
        assert Decimal(candidate['quantity']) == Decimal(expected['value'])
        assert candidate['unit'] == expected['unit']
        assert result['period_start'] == expected['period']['start']
        assert result['period_end'] == expected['period']['end']


def test_synthetic_may_electricity_end_to_end_owner_share(workspace):
    client, *_ = workspace
    path = DATASET / 'electricity/electricity-itemised-001-photo.png'
    source = path.read_bytes()
    uploaded = client.post('/documents', headers=CLERK,
                           data={'type': 'electricity', 'period': '2026-05'},
                           files={'file': (path.name, source, 'image/png')})
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document['confirmed'] is False and document['activities'] == []
    candidates = document['extraction']['activities']
    assert len(candidates) == 1
    assert candidates[0]['quantity'] == '2577'
    before = get(client, '/profile?period=2026-05')
    assert next(row for row in before['metrics'] if row['code'] == 'E1.2')['value'] is None
    confirmed = client.put(f"/documents/{document['id']}/activities", headers=CLERK,
        json={'activities': candidates, 'confirmed': True,
              'expected_version': document['version']})
    assert confirmed.status_code == 200, confirmed.text
    after = get(client, '/profile?period=2026-05')
    metric = next(row for row in after['metrics'] if row['code'] == 'E1.2')
    assert metric['value'] == '1906.98'
    assert document['id'] in metric['evidence_ids']

    made = client.post('/questionnaires', headers=CLERK, json={
        'customer': 'Synthetic Buyer', 'period': '2026-05',
        'questions': ['How much Scope 2 electricity emission did your company produce in May 2026?'],
    })
    assert made.status_code == 201, made.text
    identifier = made.json()['id']
    mapped = client.post(f'/questionnaires/{identifier}/map', headers=CLERK, json={})
    assert mapped.status_code == 200, mapped.text
    question = mapped.json()['questions'][0]
    assert 'E1.2' in question['proposed_codes']
    review = client.put(f"/questions/{question['id']}/review", headers=CLERK,
        json={'codes': ['E1.2'], 'reviewed': True})
    assert review.status_code == 200, review.text
    request = get(client, f'/questionnaires/{identifier}')
    body = {'version': request['version'], 'recipient': 'Synthetic Buyer',
            'selected_evidence_ids': [document['id']]}
    challenge = client.post(f'/questionnaires/{identifier}/approve-share',
                            headers=OWNER, json=body)
    assert challenge.status_code == 409, challenge.text
    pr9 = challenge.json()['detail']['pr9_review']
    assert pr9['items']
    rejection = client.post(f'/questionnaires/{identifier}/approve-share', headers=OWNER,
        json={**body, 'pr9_review_hash': pr9['hash'], 'acknowledged_issues': [],
              'pr9_review_reason': 'I examined the remaining evidence limitations.'})
    assert rejection.status_code == 409
    completed = client.post(f'/questionnaires/{identifier}/approve-share', headers=OWNER,
        json={**body, 'pr9_review_hash': pr9['hash'],
              'acknowledged_issues': [item['id'] for item in pr9['items']],
              'pr9_review_reason': 'Owner reviewed each unresolved limitation for this synthetic disclosure.'})
    assert completed.status_code == 200, completed.text
    snapshot = completed.json()['snapshot']
    assert snapshot['pr9_preparation_review']
    assert 'pr9_private_preparations' not in snapshot
    assert document['id'] in snapshot['selected_evidence_ids']
    token = completed.json()['token']
    customer = get(client, f'/shares/{token}', headers={})
    assert customer['snapshot']['selected_evidence_ids'] == [document['id']]
    assert 'pr9_private_preparations' not in customer['snapshot']
    original = client.get(f"/shares/{token}/evidence/{document['id']}")
    assert original.status_code == 200
    assert original.content == source
