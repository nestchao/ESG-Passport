from copy import deepcopy
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

OWNER = {'X-Demo-Role': 'owner'}
CLERK = {'X-Demo-Role': 'clerk'}


class TestStorage:
    __test__ = False

    def __init__(self):
        self.files = {}

    def ensure_bucket(self):
        pass

    def upload(self, path, content, content_type):
        assert path not in self.files, 'Original evidence must never be overwritten'
        self.files[path] = bytes(content)

    def download(self, path):
        return self.files[path]

    def delete(self, paths):
        for path in paths:
            self.files.pop(path, None)


@pytest.fixture
def workspace(tmp_path):
    try:
        from esg_backend.app import create_app
        from esg_backend.config import Settings
        from esg_backend.models import Base
        from esg_backend.seed import seed_workspace
    except ImportError:
        pytest.fail('The backend API and explicit workspace seeding are not implemented yet')
    engine = create_engine(f'sqlite:///{tmp_path / "test.db"}', connect_args={'check_same_thread': False})
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(allow_sample_reset=True)
    storage = TestStorage()
    with sessions() as session:
        seed_workspace(session, storage, settings)
        session.commit()
    app = create_app(settings=settings, session_factory=sessions, storage=storage)
    with TestClient(app) as client:
        yield client, sessions, storage, settings
    engine.dispose()


def get(client, path, headers=OWNER):
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, document_id, *, quantity=None):
    doc = get(client, f'/documents/{document_id}')
    activities = deepcopy(doc['activities'])
    if quantity is not None:
        activities[0]['quantity'] = quantity
    response = client.put(f'/documents/{document_id}/activities', headers=CLERK,
                          json={'activities': activities, 'confirmed': True})
    assert response.status_code == 200, response.text
    return response.json()


def reviewed(client):
    response = client.post('/questionnaires/request-1/map', headers=CLERK, json={})
    assert response.status_code == 200, response.text
    for question in response.json()['questions']:
        response = client.put(f'/questions/{question["id"]}/review', headers=CLERK,
                              json={'codes': question['proposed_codes'], 'reviewed': True})
        assert response.status_code == 200, response.text
    return get(client, '/questionnaires/request-1')


def approve_with_ack(client, identifier, body):
    """Test helper: simulate the owner EXPLICITLY acknowledging all listed gaps.

    Production callers must show the issues to a real owner; this helper is
    only for controlled approval-flow regression tests.
    """
    response = client.post(f'/questionnaires/{identifier}/approve-share', headers=OWNER, json=body)
    if response.status_code == 409 and isinstance(response.json().get('detail'), dict):
        review = response.json()['detail'].get('pr9_review')
        if review is not None:
            response = client.post(f'/questionnaires/{identifier}/approve-share', headers=OWNER,
                json={**body, 'pr9_review_hash': review['hash'],
                      'acknowledged_issues': [item['id'] for item in review['items']],
                      'pr9_review_reason': 'The owner reviewed every listed gap in this test.'})
    return response


def approve(client, request, selected=None):
    response = approve_with_ack(client, request['id'],
        {'version': request['version'], 'recipient': 'Meridian Foods',
         'selected_evidence_ids': ['doc-water'] if selected is None else selected})
    assert response.status_code == 200, response.text
    return response.json()


def png():
    output = BytesIO()
    Image.new('RGB', (12, 12), 'green').save(output, format='PNG')
    return output.getvalue()


def test_profile_and_confirmation(workspace):
    client, *_ = workspace
    profile = get(client, '/profile')
    assert profile['readiness']['complete'] == 8
    assert len(profile['metrics']) == 11
    confirm(client, 'doc-electricity')
    metric = next(m for m in get(client, '/profile')['metrics'] if m['code'] == 'E1.2')
    assert float(metric['value']) == 740
    assert metric['badge'] == 'auto'
    assert metric['evidence_ids'] == ['doc-electricity']


def test_role_checks_are_server_enforced(workspace):
    client, *_ = workspace
    assert client.get('/documents').status_code == 401
    assert client.get('/documents', headers={'X-Demo-Role': 'customer'}).status_code == 403
    assert client.get('/documents', headers={'X-Demo-Role': 'boss'}).status_code == 403
    assert client.put('/declarations/G1.1', headers=CLERK,
                      json={'period': '2026-09', 'answer': {'directors': 3}}).status_code == 403
    assert client.post('/questionnaires/request-1/approve-share', headers=CLERK,
                       json={'version': 1, 'recipient': 'Buyer', 'selected_evidence_ids': []}).status_code == 403


def test_file_validation_and_duplicate_detection(workspace):
    client, _, storage, _ = workspace
    before = len(storage.files)
    response = client.post('/documents', headers=CLERK, data={'type': 'electricity'},
                           files={'file': ('bill.png', png(), 'image/png')})
    assert response.status_code == 201, response.text
    doc = response.json()
    assert not doc['confirmed']
    assert len(storage.files) == before + 1
    assert client.get(f'/documents/{doc["id"]}/file', headers=CLERK).content == png()
    duplicate = client.post('/documents', headers=CLERK, data={'type': 'electricity'},
                            files={'file': ('renamed.png', png(), 'image/png')})
    assert duplicate.status_code == 409
    assert len(storage.files) == before + 1
    bad = client.post('/documents', headers=CLERK, data={'type': 'water'},
                      files={'file': ('bill.png', b'not an image', 'image/png')})
    assert bad.status_code == 422
    assert len(storage.files) == before + 1


def test_invalid_activities_leave_previous_confirmation_unchanged(workspace):
    client, *_ = workspace
    original = get(client, '/documents/doc-water')
    for change in [{'quantity': '-1'}, {'unit': 'kWh'}, {'quantity': 'NaN'},
                   {'period_end': '2026-08-01'}, {'period_start': '2026-08-01'},
                   {'category': 'diesel', 'unit': 'L'}]:
        rows = deepcopy(original['activities'])
        rows[0].update(change)
        response = client.put('/documents/doc-water/activities', headers=CLERK,
                              json={'activities': rows, 'confirmed': True})
        assert response.status_code == 422, (change, response.text)
    assert get(client, '/documents/doc-water')['activities'] == original['activities']


def test_cross_month_requires_allocation(workspace):
    client, *_ = workspace
    doc = get(client, '/documents/doc-water')
    rows = doc['activities']
    rows[0].update(period_start='2026-08-15', estimated=True, allocated_period='2026-09',
                   assumptions='September portion based on daily meter readings', quantity='5')
    response = client.put('/documents/doc-water/activities', headers=OWNER,
                          json={'activities': rows, 'confirmed': True})
    assert response.status_code == 200, response.text
    metric = next(m for m in get(client, '/profile')['metrics'] if m['code'] == 'E3.1')
    assert float(metric['value']) == 5000
    assert metric['badge'] == 'estimated'


def test_stale_approval_and_unreviewed_questions_rejected(workspace):
    client, *_ = workspace
    response = client.post('/questionnaires/request-1/approve-share', headers=OWNER,
                           json={'version': 1, 'recipient': 'Buyer', 'selected_evidence_ids': []})
    assert response.status_code == 409
    request = reviewed(client)
    question = request['questions'][0]
    client.put(f'/questions/{question["id"]}/review', headers=OWNER,
               json={'codes': question['codes'], 'reviewed': True})
    response = client.post('/questionnaires/request-1/approve-share', headers=OWNER,
                           json={'version': request['version'], 'recipient': 'Buyer', 'selected_evidence_ids': []})
    assert response.status_code == 409


def test_new_upload_invalidates_reviewed_answers_and_stale_approval(workspace):
    client, *_ = workspace
    confirm(client, 'doc-electricity')
    request = reviewed(client)
    response = client.post('/documents', headers=CLERK, data={'type': 'electricity'},
                           files={'file': ('additional.png', png(), 'image/png')})
    assert response.status_code == 201, response.text
    after = get(client, '/questionnaires/request-1')
    assert after['version'] > request['version']
    assert all(not question['reviewed'] for question in after['questions'])
    response = client.post('/questionnaires/request-1/approve-share', headers=OWNER,
                           json={'version': request['version'], 'recipient': 'Buyer', 'selected_evidence_ids': []})
    assert response.status_code == 409


def test_snapshot_and_selected_evidence_are_immutable(workspace):
    client, *_ = workspace
    pack = approve(client, reviewed(client))
    token = pack['token']
    before = get(client, f'/shares/{token}', headers={})['snapshot']
    evidence = client.get(f'/shares/{token}/evidence/doc-water')
    assert evidence.status_code == 200
    confirm(client, 'doc-water', quantity='99')
    assert get(client, f'/shares/{token}', headers={})['snapshot'] == before
    assert client.get(f'/shares/{token}/evidence/doc-water').content == evidence.content
    assert client.get(f'/shares/{token}/evidence/doc-electricity').status_code == 404
    assert client.get('/shares/invalid-token').status_code == 404
    assert client.get('/documents/doc-water/file').status_code == 401


def test_missing_and_incomplete_declarations_never_become_zero(workspace):
    client, *_ = workspace
    response = client.put('/declarations/S1.1', headers=OWNER,
                          json={'period': '2026-09', 'answer': {}})
    assert response.status_code == 200, response.text
    metric = next(m for m in get(client, '/profile')['metrics'] if m['code'] == 'S1.1')
    assert metric['value'] is None
    assert metric['badge'] == 'missing'
    response = client.put('/declarations/G1.1', headers=OWNER,
                          json={'period': '2026-09', 'answer': {'directors': -1}})
    assert response.status_code == 422


def test_restart_keeps_database_and_storage(workspace):
    from esg_backend.app import create_app
    client, sessions, storage, settings = workspace
    confirm(client, 'doc-electricity')
    pack = approve(client, reviewed(client))
    with TestClient(create_app(settings=settings, session_factory=sessions, storage=storage)) as restarted:
        assert get(restarted, '/documents/doc-electricity')['confirmed']
        assert get(restarted, f'/shares/{pack["token"]}', headers={})['recipient'] == 'Meridian Foods'
        assert restarted.get(f'/shares/{pack["token"]}/evidence/doc-water').status_code == 200


def test_seed_is_explicit_and_idempotent(workspace):
    from esg_backend.seed import seed_workspace
    client, sessions, storage, settings = workspace
    confirm(client, 'doc-water', quantity='11')
    before = len(storage.files)
    with sessions() as session:
        seed_workspace(session, storage, settings)
        session.commit()
    assert len(storage.files) == before
    assert float(get(client, '/documents/doc-water')['activities'][0]['quantity']) == 11


def test_manual_owner_answer_and_handoff(workspace):
    client, *_ = workspace
    request = reviewed(client)
    question = request['questions'][-1]
    response = client.put(f'/questions/{question["id"]}/review', headers=CLERK,
                          json={'codes': [], 'reviewed': True, 'manual_answer': 'Owner statement'})
    assert response.status_code == 403
    response = client.put(f'/questions/{question["id"]}/review', headers=OWNER,
                          json={'codes': [], 'reviewed': True, 'manual_answer': 'Not measured for this period.'})
    assert response.status_code == 200, response.text
    response = client.put('/questionnaires/request-1', headers=CLERK, json={'status': 'ready_for_owner'})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'ready_for_owner'
    pack = approve(client, response.json())
    assert pack['snapshot']['questions'][-1]['badge'] == 'declared'


def test_reset_is_gated(workspace):
    from esg_backend.app import create_app
    from dataclasses import replace
    client, sessions, storage, settings = workspace
    assert client.post('/demo/reset', headers=CLERK).status_code == 403
    with TestClient(create_app(settings=replace(settings, allow_sample_reset=False),
                              session_factory=sessions, storage=storage)) as disabled:
        assert disabled.post('/demo/reset', headers=OWNER).status_code == 403
    response = client.post('/demo/reset', headers=OWNER)
    assert response.status_code == 200, response.text
    assert len(get(client, '/documents')) == 6
    assert get(client, '/profile')['readiness']['complete'] == 8


def test_failed_upload_attempts_cleanup_even_after_storage_response_loss(workspace):
    from esg_backend.storage import StorageError
    client, _, storage, _ = workspace
    before = set(storage.files)
    original = storage.upload
    def lost_response(path, content, content_type):
        original(path, content, content_type)
        raise StorageError('Response lost after remote storage wrote the object')
    storage.upload = lost_response
    response = client.post('/documents', headers=OWNER, data={'type': 'electricity'},
                           files={'file': ('new.png', png(), 'image/png')})
    assert response.status_code == 503
    assert set(storage.files) == before
    assert len(get(client, '/documents')) == 6


def test_upload_commit_failure_removes_uploaded_object(workspace, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    client, _, storage, _ = workspace
    before = set(storage.files)
    original = Session.commit
    def failed_commit(self):
        raise SQLAlchemyError('Simulated unavailable database')
    monkeypatch.setattr(Session, 'commit', failed_commit)
    response = client.post('/documents', headers=OWNER, data={'type': 'electricity'},
                           files={'file': ('new.png', png(), 'image/png')})
    assert response.status_code == 503
    assert set(storage.files) == before
    monkeypatch.setattr(Session, 'commit', original)
    assert len(get(client, '/documents')) == 6


def test_reset_commit_failure_cleans_only_new_seed_objects(workspace, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    client, _, storage, _ = workspace
    before = set(storage.files)
    original = Session.commit
    monkeypatch.setattr(Session, 'commit', lambda self: (_ for _ in ()).throw(SQLAlchemyError('Commit failed')))
    response = client.post('/demo/reset', headers=OWNER)
    assert response.status_code == 503
    assert set(storage.files) == before
    monkeypatch.setattr(Session, 'commit', original)
    assert len(get(client, '/documents')) == 6


def test_unselected_source_metadata_not_exposed_in_customer_snapshot(workspace):
    client, *_ = workspace
    confirm(client, 'doc-electricity')
    request = reviewed(client)
    response = approve_with_ack(client, 'request-1',
        {'version': request['version'], 'recipient': 'Buyer', 'selected_evidence_ids': []})
    assert response.status_code == 200
    snapshot = response.json()['snapshot']
    assert snapshot['evidence'] == []
    for question in snapshot['questions']:
        assert question['evidence_ids'] == []
        for metric in question['metrics']:
            assert metric['evidence_ids'] == []
            assert all(not item.get('evidence_id') for item in metric.get('confirmation_history', []))
            assert all(not item.get('evidence_ids') for item in metric.get('components', []))


def count_selects(workspace, path):
    from sqlalchemy import event
    client, sessions, *_ = workspace
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    engine = sessions.kw['bind']
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        result = get(client, path)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    return result, statements


def test_document_queries_do_not_scale_with_document_count(workspace):
    from esg_backend.models import Document, Activity
    client, sessions, *_ = workspace
    before, initial = count_selects(workspace, '/documents')
    with sessions() as session:
        source = session.get(Document, 'doc-water')
        activity = session.scalar(select(Activity).where(Activity.document_id == source.id))
        for index in range(12):
            session.add(Document(id=f'scale-doc-{index}', company_id=source.company_id,
                name='More water', type='water', period=source.period, file_hash=f'scale-{index}',
                object_path=f'scale/{index}', activity_revision=2))
            session.flush()
            for revision in (1, 2):
                session.add(Activity(company_id=source.company_id, document_id=f'scale-doc-{index}',
                    revision=revision, category='water', quantity=revision, unit='m3',
                    period_start=activity.period_start, period_end=activity.period_end))
        session.commit()
    after, scaled = count_selects(workspace, '/documents')
    assert len(after) == len(before) + 12
    extra = next(d for d in after if d['id'] == 'scale-doc-0')
    assert [a['revision'] for a in extra['history']] == [1, 2]
    assert [a['revision'] for a in extra['activities']] == [2]
    assert 'object_path' not in extra and 'file_hash' not in extra
    assert len(scaled) == len(initial) <= 3


def test_questionnaire_queries_do_not_scale_with_request_count(workspace):
    from esg_backend.models import Questionnaire, Question
    client, sessions, *_ = workspace
    before, initial = count_selects(workspace, '/questionnaires')
    with sessions() as session:
        for index in range(8):
            session.add(Questionnaire(id=f'scale-request-{index}', company_id='lim-carton',
                customer='Scaling customer', period='2026-09'))
            session.flush()
            for position in (2, 0, 1):
                session.add(Question(questionnaire_id=f'scale-request-{index}',
                    position=position, text=f'Water {position}'))
        session.commit()
    after, scaled = count_selects(workspace, '/questionnaires')
    assert len(after) == len(before) + 8
    extra = next(r for r in after if r['id'] == 'scale-request-0')
    assert [q['position'] for q in extra['questions']] == [0, 1, 2]
    assert len(scaled) == len(initial) <= 7


def test_profile_reads_only_current_activity_revisions(workspace):
    from sqlalchemy import event
    from esg_backend.models import Activity
    client, sessions, *_ = workspace
    loaded = []
    def capture(session, instance):
        if isinstance(instance, Activity):
            loaded.append(instance.revision)
    with sessions() as session:
        current = session.scalar(select(Activity).where(Activity.document_id == 'doc-water'))
        session.add(Activity(company_id=current.company_id, document_id=current.document_id,
            revision=0, category='water', quantity=99999, unit=current.unit,
            period_start=current.period_start, period_end=current.period_end))
        session.commit()
    event.listen(sessions.class_, 'loaded_as_persistent', capture)
    try:
        profile, statements = count_selects(workspace, '/profile')
    finally:
        event.remove(sessions.class_, 'loaded_as_persistent', capture)
    assert 0 not in loaded
    assert len(statements) <= 5
    assert next(m for m in profile['metrics'] if m['code'] == 'E3.1')['value'] == '10000'


def test_company_reuse_is_local_and_lock_always_refreshes(workspace):
    from esg_backend.models import Company
    from esg_backend.service import Workspace
    from sqlalchemy import event, update
    _, sessions, storage, settings = workspace
    with sessions() as session:
        work = Workspace(session, storage, settings)
        first = work.company()
        seen = []
        def capture(orm_state):
            if orm_state.is_select:
                seen.append(orm_state.statement)
        event.listen(session, 'do_orm_execute', capture)
        assert work.company() is first
        assert len(seen) == 0
        session.execute(update(Company).where(Company.id == first.id).values(version=9),
                        execution_options={'synchronize_session': False})
        locked = work.company(lock=True)
        assert locked.version == 9
        assert seen[-1]._for_update_arg is not None
        assert seen[-1].get_execution_options()['populate_existing']
        work.company(lock=True)
        assert len(seen) == 2
        session.rollback()
    with sessions() as session:
        assert Workspace(session, storage, settings).company().version == 1



def test_current_activity_batch_uses_captured_document_revision(workspace):
    from sqlalchemy import update
    from esg_backend.models import Document, Activity
    from esg_backend.service import Workspace
    _, sessions, storage, settings = workspace
    with sessions() as session:
        work = Workspace(session, storage, settings)
        doc = work.document('doc-water')
        captured_revision = doc.activity_revision
        original = session.scalar(select(Activity).where(Activity.document_id == doc.id, Activity.revision == captured_revision))
        session.execute(update(Document).where(Document.id == doc.id).values(activity_revision=captured_revision + 1).execution_options(synchronize_session=False))
        session.add(Activity(company_id=doc.company_id, document_id=doc.id, revision=captured_revision + 1,
            category='water', quantity=999, unit='m3', period_start=original.period_start, period_end=original.period_end))
        session.flush()
        result = work.serialize_documents([doc], include_history=False)[0]
        assert [entry['revision'] for entry in result['activities']] == [captured_revision]
        assert result['activities'][0]['quantity'] == format(original.quantity, 'f')
