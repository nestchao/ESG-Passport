from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from test_api import workspace
from esg_backend.app import create_app
from esg_backend.config import Settings

KEY = 'backend-demo-key-' + 'x' * 32


def test_protected_backend_requires_key_even_with_owner_or_pack_token(workspace):
    _, sessions, storage, settings = workspace
    protected = replace(settings, demo_access_enabled=True, backend_shared_key=KEY, allow_sample_reset=False)
    with TestClient(create_app(settings=protected, session_factory=sessions, storage=storage)) as client:
        for path in ['/documents', '/shares/invalid-token', '/shares/invalid-token/evidence/doc-water', '/docs', '/openapi.json']:
            denied = client.get(path, headers={'X-Demo-Role': 'owner'})
            assert denied.status_code == 401
            assert denied.json() == {'detail': 'Demo access required.'}
        assert client.get('/documents', headers={'X-Demo-Role': 'owner', 'X-Demo-Backend-Key': 'wrong'}).status_code == 401
        assert client.get('/documents', headers={'X-Demo-Role': 'owner', 'X-Demo-Backend-Key': KEY}).status_code == 200
        assert client.get('/documents', headers={'X-Demo-Backend-Key': KEY}).status_code == 401
        assert client.get('/health').status_code == 200
        assert client.post('/health').status_code == 401


def test_shared_key_does_not_replace_role_or_pack_checks(workspace):
    _, sessions, storage, settings = workspace
    with TestClient(create_app(settings=replace(settings, demo_access_enabled=True, backend_shared_key=KEY, allow_sample_reset=False),
                               session_factory=sessions, storage=storage)) as client:
        headers = {'X-Demo-Backend-Key': KEY, 'X-Demo-Role': 'clerk'}
        assert client.post('/questionnaires/request-1/approve-share', headers=headers,
                           json={'version': 1, 'recipient': 'Buyer', 'selected_evidence_ids': []}).status_code == 403
        assert client.get('/shares/invalid-token', headers=headers).status_code == 404


def test_demo_security_configuration_fails_closed_before_database_setup(monkeypatch):
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.delenv('DEMO_ACCESS_ENABLED', raising=False)
    settings = Settings.from_env()
    with pytest.raises(ValueError, match='DEMO_ACCESS_ENABLED'):
        create_app(settings=settings)
    with pytest.raises(ValueError, match='BACKEND_SHARED_KEY'):
        create_app(settings=Settings(demo_access_enabled=True, backend_shared_key='short'))


def test_demo_environment_flags(monkeypatch):
    monkeypatch.setenv('DEMO_ACCESS_ENABLED', 'true')
    monkeypatch.setenv('BACKEND_SHARED_KEY', KEY)
    settings = Settings.from_env()
    assert settings.demo_access_enabled is True
    assert settings.backend_shared_key == KEY
