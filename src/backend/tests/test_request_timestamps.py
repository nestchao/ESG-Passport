from datetime import datetime
from test_api import workspace, get, approve, confirm, OWNER, CLERK


def test_updated_at_tracks_mutations(workspace):
    client, *_ = workspace
    request = get(client, '/questionnaires/request-1')
    created = request['created_at']
    previous = datetime.fromisoformat(request['updated_at'])
    assert previous.utcoffset().total_seconds() == 0
    assert get(client, '/questionnaires/request-1')['updated_at'] == request['updated_at']

    def changed():
        nonlocal previous
        current = get(client, '/questionnaires/request-1')
        timestamp = datetime.fromisoformat(current['updated_at'])
        assert timestamp > previous
        assert current['created_at'] == created
        previous = timestamp
        return current

    response = client.post('/questionnaires/request-1/map', headers=CLERK, json={})
    assert response.status_code == 200
    changed()
    for question in response.json()['questions']:
        response = client.put(f'/questions/{question["id"]}/review', headers=CLERK,
                              json={'codes': question['proposed_codes'], 'reviewed': True})
        assert response.status_code == 200
        changed()
    response = client.put('/questionnaires/request-1', headers=CLERK, json={'status': 'ready_for_owner'})
    assert response.status_code == 200, response.text
    request = changed()
    pack = approve(client, request)
    changed()
    confirm(client, 'doc-electricity')
    changed()
    assert get(client, f'/shares/{pack["token"]}', headers={})['snapshot'] == pack['snapshot']


def test_created_updated_at_is_utc(workspace):
    client, *_ = workspace
    response = client.post('/questionnaires', headers=CLERK, json={
        'customer': 'New buyer', 'period': '2026-09', 'questions': ['Water consumption?']})
    assert response.status_code == 201, response.text
    request = response.json()
    assert datetime.fromisoformat(request['updated_at']).utcoffset().total_seconds() == 0
    assert request['updated_at'] >= request['created_at']


def test_model_timestamp_changes_on_content_update(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from esg_backend.models import Base, Company, Questionnaire
    from esg_backend.service import row
    engine = create_engine(f'sqlite:///{tmp_path / "model.db"}')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Company(id='test'))
        request = Questionnaire(company_id='test', customer='Before')
        db.add(request)
        db.commit()
        initial = row(request)
        assert datetime.fromisoformat(initial['updated_at']).utcoffset().total_seconds() == 0
        request.customer = 'After'
        db.commit()
        assert row(request)['updated_at'] > initial['updated_at']
        assert row(request)['created_at'] == initial['created_at']
    engine.dispose()


def test_migration_backfills_existing_requests(tmp_path):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text, inspect
    engine = create_engine(f'sqlite:///{tmp_path / "migration.db"}')
    config = Config(str(Path(__file__).parents[1] / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0001_esg_foundation')
        connection.execute(text("INSERT INTO companies VALUES ('c', 'Buyer', '', '', '2026-09', 1, 1)"))
        connection.execute(text("INSERT INTO questionnaires VALUES ('q', 'c', 'Buyer', '2026-09', NULL, 'draft', 1, '2026-09-01 12:34:56.123456')"))
        command.upgrade(config, 'head')
        assert 'updated_at' in {c['name'] for c in inspect(connection).get_columns('questionnaires')}
        result = connection.execute(text('SELECT created_at, updated_at FROM questionnaires')).one()
        assert result.created_at == result.updated_at
        column = next(c for c in inspect(connection).get_columns('questionnaires') if c['name'] == 'updated_at')
        assert not column['nullable']
        command.downgrade(config, '0001_esg_foundation')
        assert connection.execute(text('SELECT customer FROM questionnaires')).scalar_one() == 'Buyer'
    engine.dispose()
