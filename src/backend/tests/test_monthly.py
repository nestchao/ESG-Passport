from copy import deepcopy
import pytest
from test_api import workspace, get, OWNER, CLERK, reviewed, approve, png

@pytest.mark.parametrize('period', ['2026-01', '2026-12', '2024-02', '0001-01', '9999-12'])
def test_new_month_empty_and_independent(workspace, period):
    client, sessions, storage, settings = workspace
    assert get(client, '/documents?period=' + period) == []
    assert get(client, '/declarations?period=' + period) == []
    assert get(client, '/questionnaires?period=' + period) == []
    assert get(client, '/shares?period=' + period) == []
    assert get(client, '/profile?period=' + period)['period'] == period
    assert get(client, '/documents')

@pytest.mark.parametrize('period', ['0000-01', '2026-00', '2026-13', '26-01', '2026-1'])
def test_bad_month(workspace, period):
    assert workspace[0].get('/profile?period=' + period, headers=OWNER).status_code == 422

def test_move_archive_restore_and_stale(workspace):
    client, sessions, storage, settings = workspace
    doc = get(client, '/documents/doc-water')
    activity = deepcopy(doc['activities'])
    activity[0].update(period_start='2024-02-01', period_end='2024-02-29')
    body = dict(name='February water', period='2024-02', activities=activity, expected_version=doc['version'])
    moved = client.put('/documents/doc-water', headers=CLERK, json=body)
    assert moved.status_code == 200, moved.text
    moved = moved.json()
    assert moved['period'] == '2024-02' and moved['name'] == 'February water'
    assert not moved['confirmed'] and not moved['archived']
    assert client.put('/documents/doc-water', headers=OWNER, json=body).status_code == 409
    assert not any(d['id'] == doc['id'] for d in get(client, '/documents'))
    assert [d['id'] for d in get(client, '/documents?period=2024-02')] == [doc['id']]
    archived = client.post('/documents/doc-water/archive', headers=CLERK, json={'expected_version': moved['version']})
    assert archived.status_code == 200, archived.text
    archived = archived.json()
    assert archived['archived']
    assert get(client, '/documents?period=2024-02') == []
    assert len(get(client, '/documents?period=2024-02&archived=true')) == 1
    assert client.put('/documents/doc-water/activities', headers=OWNER, json={'confirmed':True, 'activities':activity}).status_code == 409
    restored = client.post('/documents/doc-water/restore', headers=OWNER, json={'expected_version': archived['version']})
    assert restored.status_code == 200, restored.text
    assert not restored.json()['archived'] and not restored.json()['confirmed']

def test_archive_preserves_approved_pack_and_rejects_selection(workspace):
    client, sessions, storage, settings = workspace
    request = reviewed(client)
    pack = approve(client, request)
    original = get(client, '/shares/' + pack['token'], headers={})['snapshot']
    doc = get(client, '/documents/doc-water')
    response = client.post('/documents/doc-water/archive', headers=CLERK, json={'expected_version':doc['version']})
    assert response.status_code == 200, response.text
    assert get(client, '/shares/' + pack['token'], headers={})['snapshot'] == original
    assert client.get('/shares/' + pack['token'] + '/evidence/doc-water').status_code == 200
    request = reviewed(client)
    response = client.post('/questionnaires/request-1/approve-share', headers=OWNER,
        json={'version':request['version'], 'recipient':'Customer', 'selected_evidence_ids':['doc-water']})
    assert response.status_code == 409

def test_upload_month_duplicate_metadata(workspace):
    client = workspace[0]
    kwargs = dict(headers=CLERK, files={'file':('new.png',png(),'image/png')}, data={'type':'water','period':'2026-12'})
    first = client.post('/documents', **kwargs)
    assert first.status_code == 201, first.text
    assert first.json()['period'] == '2026-12'
    second = client.post('/documents', **kwargs)
    assert second.status_code == 409
    assert second.json()['detail']['document_id'] == first.json()['id']
    assert second.json()['detail']['period'] == '2026-12'
    assert second.json()['detail']['archived'] is False

def test_manual_answer_uses_request_month_and_scoped_invalidation(workspace):
    client = workspace[0]
    requests = []
    for period in ['2026-01','2026-12']:
        response = client.post('/questionnaires', headers=CLERK, json={'customer':'Monthly buyer','period':period,'questions':['Water use?']})
        assert response.status_code == 201, response.text
        request = response.json()
        question = request['questions'][0]
        response = client.put('/questions/' + question['id'] + '/review', headers=OWNER,
            json={'codes':[], 'reviewed':True,'manual_answer':'Monthly declaration'})
        assert response.status_code == 200, response.text
        assert response.json()['manual_declaration']['period'] == period
        requests.append(get(client, '/questionnaires/' + request['id']))
    doc = get(client, '/documents/doc-water')
    response = client.post('/documents/doc-water/archive',headers=CLERK,json={'expected_version':doc['version']})
    assert response.status_code == 200
    for request in requests:
        after = get(client, '/questionnaires/' + request['id'])
        assert after['version'] == request['version'] and after['questions'][0]['reviewed']

def test_archived_evidence_rejected_in_new_declaration(workspace):
    client = workspace[0]
    doc = get(client, '/documents/doc-water')
    response = client.post('/documents/doc-water/archive', headers=OWNER,json={'expected_version':doc['version']})
    assert response.status_code == 200
    response = client.put('/declarations/G1.1',headers=OWNER,json={'period':'2026-09','answer':{'directors':2},'evidence_ids':['doc-water']})
    assert response.status_code == 409

def test_cross_month_reference_invalidates_reference_month(workspace):
    client = workspace[0]
    response = client.put('/declarations/G1.1',headers=OWNER,json={'period':'2026-12','answer':{'directors':2},'evidence_ids':['doc-water']})
    assert response.status_code == 200, response.text
    response = client.post('/questionnaires',headers=CLERK,json={'customer':'December','period':'2026-12','questions':['Board directors?']})
    assert response.status_code == 201
    request = response.json()
    question = request['questions'][0]
    assert client.put('/questions/' + question['id'] + '/review',headers=CLERK,json={'codes':['G1.1'],'reviewed':True}).status_code == 200
    before = get(client, '/questionnaires/' + request['id'])
    doc = get(client, '/documents/doc-water')
    assert client.post('/documents/doc-water/archive',headers=CLERK,json={'expected_version':doc['version']}).status_code == 200
    after = get(client, '/questionnaires/' + request['id'])
    assert after['version'] > before['version'] and not after['questions'][0]['reviewed']
    assert get(client, '/declarations?period=2026-12')[0]['complete'] is False

def test_service_accepts_independent_month():
    from types import SimpleNamespace
    from esg_backend.service import Workspace
    work = Workspace(None, None, SimpleNamespace(company_id='test'))
    work._company = SimpleNamespace(period='2026-09')
    work.period('2026-01')

@pytest.mark.parametrize('period,start,end', [('2026-01','2026-01-01','2026-01-31'),('2026-12','2026-12-01','2026-12-31'),('2024-02','2024-02-01','2024-02-29')])
def test_move_valid_calendar_months(workspace, period, start, end):
    client = workspace[0]
    doc = get(client, '/documents/doc-water')
    activities = deepcopy(doc['activities'])
    activities[0].update(period_start=start, period_end=end)
    response = client.put('/documents/doc-water',headers=OWNER,json={'name':doc['name'],'period':period,'activities':activities,'expected_version':doc['version']})
    assert response.status_code == 200, response.text
    assert response.json()['period'] == period

def test_invalid_atomic_move_leaves_record_unchanged(workspace):
    client = workspace[0]
    before = get(client, '/documents/doc-water')
    response = client.put('/documents/doc-water',headers=CLERK,json={'name':'Changed','period':'2026-12','activities':before['activities'],'expected_version':before['version']})
    assert response.status_code == 422
    assert get(client, '/documents/doc-water') == before

def test_stale_activity_and_restore_do_not_mutate(workspace):
    client = workspace[0]
    doc = get(client, '/documents/doc-water')
    archived = client.post('/documents/doc-water/archive',headers=OWNER,json={'expected_version':doc['version']}).json()
    assert client.post('/documents/doc-water/restore',headers=CLERK,json={'expected_version':doc['version']}).status_code == 409
    restored = client.post('/documents/doc-water/restore',headers=CLERK,json={'expected_version':archived['version']}).json()
    response = client.put('/documents/doc-water/activities',headers=CLERK,json={'activities':doc['activities'],'confirmed':True,'expected_version':doc['version']})
    assert response.status_code == 409
    assert get(client, '/documents/doc-water') == restored

def test_upload_does_not_change_company_default_month(workspace):
    from esg_backend.models import Company
    client, sessions, _, settings = workspace
    assert client.post('/documents',headers=CLERK,files={'file':('water.png',png(),'image/png')},data={'type':'water','period':'2026-01'}).status_code == 201
    with sessions() as db:
        assert db.get(Company,settings.company_id).period == '2026-09'

def test_archive_requires_workspace_role(workspace):
    client = workspace[0]
    assert client.post('/documents/doc-water/archive',json={'expected_version':1}).status_code == 401
    assert client.post('/documents/doc-water/archive',headers={'X-Demo-Role':'customer'},json={'expected_version':1}).status_code == 403

def test_new_event_month_and_legacy_workspace_label(workspace):
    client = workspace[0]
    doc = get(client, '/documents/doc-water')
    assert client.post('/documents/doc-water/archive',headers=CLERK,json={'expected_version':doc['version']}).status_code == 200
    events = get(client, '/activity-log')
    event = next(item for item in events if item['action'] == 'document_archived')
    assert event['period'] == '2026-09'
    assert all('period' in event for event in events)

def test_duplicate_archived_file_identifies_existing_record(workspace):
    client = workspace[0]
    kwargs = dict(headers=CLERK,files={'file':('same.png',png(),'image/png')},data={'type':'water','period':'2026-01'})
    doc = client.post('/documents',**kwargs).json()
    assert client.post('/documents/' + doc['id'] + '/archive',headers=OWNER,json={'expected_version':doc['version']}).status_code == 200
    duplicate = client.post('/documents',**kwargs)
    assert duplicate.status_code == 409
    assert duplicate.json()['detail'] == {'message':'This file has already been uploaded. Open its existing record.','document_id':doc['id'],'period':'2026-01','archived':True}

def test_archive_migration_preserves_legacy_records_and_backfills_audit():
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    config.set_main_option('script_location',str(Path(__file__).parents[1] / 'migrations'))
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config,'0002_questionnaire_updated_at')
        connection.execute(text("INSERT INTO companies (id,name,location,sector,period,synthetic,version) VALUES ('legacy','Legacy','KL','Paper','2026-09',0,17)"))
        connection.execute(text("INSERT INTO documents (id,company_id,name,type,period,mime_type,file_hash,object_path,confirmed,activity_revision,version,uploaded_by,uploaded_at) VALUES ('legacy-doc','legacy','Original','water','2026-09','image/png','legacy-hash','immutable/original',1,4,8,'Owner','2026-09-01')"))
        for identifier, target in [('doc-event','legacy-doc'),('workspace-event','legacy')]:
            connection.execute(text("INSERT INTO activity_events (id,company_id,actor,role,action,target,time,summary) VALUES (:id,'legacy','Owner','owner','legacy',:target,'2026-09-01','History')"),{'id':identifier,'target':target})
        command.upgrade(config,'head')
        document = connection.execute(text('SELECT version,activity_revision,object_path,confirmed,archived_at,archived_by FROM documents')).one()
        assert tuple(document) == (8,4,'immutable/original',1,None,None)
        assert connection.scalar(text('SELECT version FROM companies')) == 17
        periods = dict(connection.execute(text('SELECT id,period FROM activity_events')).all())
        assert periods == {'doc-event':'2026-09','workspace-event':None}
    engine.dispose()
