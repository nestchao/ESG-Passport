"""Public demo must never share sessions or evidence with a private workspace."""
from fastapi.testclient import TestClient
from esg_backend.app import create_app
from esg_backend.config import Settings

KEY='k'*40

def test_public_sandbox_is_synthetic_and_never_reads_production():
    app=create_app(settings=Settings(demo_access_enabled=True,backend_shared_key=KEY,
                                    public_workspace_enabled=True))
    h={'X-Demo-Backend-Key':KEY,'X-Demo-Role':'owner'}
    with TestClient(app) as client:
        assert client.get('/sandbox/profile').status_code==401
        assert client.get('/sandbox/profile',headers={'X-Demo-Role':'owner'}).status_code==401
        assert client.get('/profile',headers=h).status_code==503  # no real Postgres configured
        public=client.get('/sandbox/profile?period=2026-09',headers=h)
        assert public.status_code==200
        assert public.json()['company']['id']=='public-fictional-workspace'
        assert public.json()['company']['synthetic'] is True
        rows=client.get('/sandbox/documents?period=2026-09',headers=h)
        assert rows.status_code==200 and len(rows.json())>=6
        assert all('doc-' in d['id'] for d in rows.json())
        img=client.get('/sandbox/documents/doc-electricity/file',headers=h)
        assert img.status_code==200 and img.headers['content-type'].startswith('image/png')
        assert client.get('/sandbox/shares/not-real',headers=h).status_code==404

def test_public_sandbox_flags_cannot_remove_backend_auth():
    from pytest import raises
    with raises(ValueError,match='Public sandbox requires protected backend'):
        Settings(public_workspace_enabled=True,demo_access_enabled=False).validate_demo_access()
    app=create_app(settings=Settings(demo_access_enabled=True,backend_shared_key=KEY,
                                    public_workspace_enabled=False))
    with TestClient(app) as client:
        assert client.get('/sandbox/profile',headers={'X-Demo-Backend-Key':KEY,'X-Demo-Role':'owner'}).status_code==404
