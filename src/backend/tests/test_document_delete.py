"""Deletion is intentionally distinct from audit-preserving Archive/Restore.

All test operations use an isolated SQLite DB and fake in-memory storage;
never send a DELETE request to the user's live Supabase instance.
"""
import pytest
from sqlalchemy import select

from test_api import workspace, OWNER, CLERK, get, reviewed, approve, png
from esg_backend.models import Activity, ActivityEvent, Document
from esg_backend.storage import StorageError


def delete(client, doc, *, headers=OWNER, expected_version=None):
    return client.request('DELETE', f'/documents/{doc["id"]}', headers=headers,
        json={'expected_version': doc['version'] if expected_version is None else expected_version})


def test_owner_deletes_active_record_revisions_and_object_with_audit(workspace):
    client, sessions, storage, _ = workspace
    doc = get(client, '/documents/doc-water')
    # Keep both first and updated activity revisions, then remove all of them.
    revision = client.put(f'/documents/{doc["id"]}/activities', headers=CLERK,
        json={'activities': doc['activities'], 'confirmed': True,
              'expected_version': doc['version']})
    assert revision.status_code == 200, revision.text
    doc = revision.json()
    with sessions() as db:
        row = db.get(Document, doc['id'])
        path = row.object_path
        assert db.scalars(select(Activity).where(Activity.document_id == doc['id'])).first() is not None
    assert path in storage.files
    result = delete(client, doc)
    assert result.status_code == 200, result.text
    assert result.json() == {'deleted': True, 'id': doc['id'], 'period': '2026-09'}
    assert path not in storage.files
    assert client.get(f'/documents/{doc["id"]}', headers=OWNER).status_code == 404
    assert client.get(f'/documents/{doc["id"]}/file', headers=OWNER).status_code == 404
    assert all(record['id'] != doc['id'] for record in get(client, '/documents'))
    with sessions() as db:
        assert db.get(Document, doc['id']) is None
        assert not db.scalars(select(Activity).where(Activity.document_id == doc['id'])).all()
        event = db.scalar(select(ActivityEvent).where(ActivityEvent.action == 'document_deleted',
            ActivityEvent.target == doc['id']))
        assert event.actor and event.period == doc['period']
        assert path not in event.summary
    # Removal also releases the duplicate digest for a later, intentional upload.
    new = client.post('/documents', headers=CLERK,
        files={'file': ('same-bill.png', png(), 'image/png')},
        data={'type':'water', 'period':'2026-09'})
    assert new.status_code == 201, new.text


def test_archived_record_can_be_deleted_but_clerk_cannot(workspace):
    client, _, storage, _ = workspace
    doc = get(client, '/documents/doc-water')
    assert delete(client, doc, headers=CLERK).status_code == 403
    assert delete(client, doc, headers={}).status_code == 401
    assert client.get(f'/documents/{doc["id"]}', headers=OWNER).status_code == 200
    archived = client.post(f'/documents/{doc["id"]}/archive', headers=CLERK,
        json={'expected_version': doc['version']})
    assert archived.status_code == 200, archived.text
    archived = archived.json()
    result = delete(client, archived)
    assert result.status_code == 200, result.text
    assert all(row['id'] != doc['id'] for row in get(client, '/documents?period=2026-09&archived=true'))


def test_stale_version_blocks_delete_without_storage_change(workspace):
    client, sessions, storage, _ = workspace
    doc = get(client, '/documents/doc-water')
    original_objects = dict(storage.files)
    stale = delete(client, doc, expected_version=doc['version']+1)
    assert stale.status_code == 409
    assert get(client, f'/documents/{doc["id"]}')['version'] == doc['version']
    assert storage.files == original_objects


def test_approved_customer_pack_blocks_permanent_delete_including_archived(workspace):
    client, sessions, storage, _ = workspace
    pack = approve(client, reviewed(client), selected=['doc-water'])
    original = get(client, '/shares/' + pack['token'], headers={})['snapshot']
    doc = get(client, '/documents/doc-water')
    response = delete(client, doc)
    assert response.status_code == 409 and 'approved' in response.text.lower()
    archived = client.post(f'/documents/{doc["id"]}/archive', headers=CLERK,
        json={'expected_version':doc['version']}).json()
    assert delete(client, archived).status_code == 409
    assert get(client, '/shares/' + pack['token'], headers={})['snapshot'] == original
    assert client.get(f'/shares/{pack["token"]}/evidence/{doc["id"]}').status_code == 200


def test_owner_declaration_references_block_deletion_across_months(workspace):
    client, sessions, storage, _ = workspace
    saved = client.put('/declarations/G1.1', headers=OWNER, json={
        'period':'2026-12', 'answer':{'directors': 2}, 'evidence_ids':['doc-water']})
    assert saved.status_code == 200, saved.text
    doc = get(client, '/documents/doc-water')
    assert delete(client, doc).status_code == 409
    assert get(client, f'/documents/{doc["id"]}')['id'] == doc['id']


def test_storage_failure_rolls_back_record_deletion(workspace, monkeypatch):
    client, _, storage, _ = workspace
    doc = get(client, '/documents/doc-water')
    before = dict(storage.files)
    def fail_delete(paths):
        raise StorageError('Simulated storage outage')
    monkeypatch.setattr(storage, 'delete', fail_delete)
    response = delete(client, doc)
    assert response.status_code == 503
    assert get(client, f'/documents/{doc["id"]}')['id'] == doc['id']
    assert storage.files == before
    assert not any(x['action']=='document_deleted' for x in get(client, '/activity-log'))


def test_deletion_invalidates_existing_unapproved_question_review(workspace):
    client, _, _, _ = workspace
    request = reviewed(client)
    doc = get(client, '/documents/doc-water')
    assert delete(client, doc).status_code == 200
    updated = get(client, f'/questionnaires/{request["id"]}')
    assert updated['version'] > request['version']
    assert updated['status'] == 'draft'
    assert all(not question['reviewed'] for question in updated['questions'])


def test_database_commit_failure_restores_original_storage(workspace, monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import SQLAlchemyError
    client, sessions, storage, _ = workspace
    doc = get(client, '/documents/doc-water')
    original = dict(storage.files)
    saved_commit = Session.commit
    monkeypatch.setattr(Session, 'commit', lambda self: (_ for _ in ()).throw(SQLAlchemyError('Simulated database failure')))
    try:
        response = delete(client, doc)
        assert response.status_code == 503, response.text
    finally:
        monkeypatch.setattr(Session, 'commit', saved_commit)
    assert storage.files == original
    assert get(client, f'/documents/{doc["id"]}')['id'] == doc['id']
    assert not any(item['action'] == 'document_deleted' for item in get(client, '/activity-log'))


def test_delete_cors_preflight_is_allowed_from_frontend(workspace):
    client, sessions, storage, settings = workspace
    response = client.options('/documents/doc-water', headers={
        'Origin':settings.frontend_origin,
        'Access-Control-Request-Method':'DELETE',
        'Access-Control-Request-Headers':'Content-Type,X-Demo-Role'})
    assert response.status_code == 200, response.text
    assert response.headers['access-control-allow-origin'] == settings.frontend_origin
    assert 'DELETE' in response.headers['access-control-allow-methods']
