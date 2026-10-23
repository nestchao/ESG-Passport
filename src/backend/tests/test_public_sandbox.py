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


def test_approved_synthetic_png_upload():
    from pathlib import Path
    from PIL import Image
    from io import BytesIO
    app=create_app(settings=Settings(demo_access_enabled=True,backend_shared_key=KEY,public_workspace_enabled=True))
    headers={'X-Demo-Backend-Key':KEY,'X-Demo-Role':'clerk'}
    fixture=Path(__file__).resolve().parents[2]/'ai'/'synthetic_dataset'/'electricity'/'electricity-itemised-001-clean.png'
    content=fixture.read_bytes()
    with TestClient(app) as client:
        fake=BytesIO();Image.new('RGB',(24,24),'white').save(fake,format='PNG')
        result=client.post('/sandbox/documents',headers=headers,data={'type':'electricity','period':'2026-05'},files={'file':('fake.png',fake.getvalue(),'image/png')})
        assert result.status_code==403,result.text
        result=client.post('/sandbox/documents',headers=headers,data={'type':'electricity','period':'2026-04'},files={'file':(fixture.name,content,'image/png')})
        assert result.status_code==422,result.text
        result=client.post('/sandbox/documents',headers=headers,data={'type':'electricity','period':'2026-05'},files={'file':(fixture.name,content,'image/png')})
        assert result.status_code==201,result.text
        doc=result.json()
        assert doc['company_id']=='public-fictional-workspace' and doc['period']=='2026-05' and not doc['confirmed']
        assert doc['extraction']['ocr_engine']=='synthetic_fixture_text_not_live_ocr'
        assert doc['extraction']['activities'][0]['quantity']=='2577'
        assert 'precomputed from the fictional' in str(doc['extraction']['uncertainty_notes'])
        assert client.get('/sandbox/documents/'+doc['id']+'/file',headers=headers).content==content
        assert client.post('/sandbox/documents',headers=headers,data={'type':'electricity','period':'2026-05'},files={'file':(fixture.name,content,'image/png')}).status_code==409
