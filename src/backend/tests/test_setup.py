from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from PIL import Image
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from esg_backend.config import Settings
from esg_backend.models import Activity, Base, Company, Declaration, Document, FactorVersion, Question
from esg_backend.seed import seed_workspace


class MemoryStorage:
    def __init__(self, fail_at=None):
        self.files = {}
        self.attempts = 0
        self.fail_at = fail_at

    def ensure_bucket(self):
        pass

    def upload(self, path, content, content_type):
        self.attempts += 1
        assert path not in self.files
        self.files[path] = content
        if self.attempts == self.fail_at:
            raise RuntimeError('Simulated response loss after write')

    def delete(self, paths):
        for path in paths:
            self.files.pop(path, None)


@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_seed_has_distinct_matching_png_originals_and_does_not_overwrite(session):
    storage = MemoryStorage()
    settings = Settings()
    seed_workspace(session, storage, settings)
    session.commit()
    documents = session.scalars(select(Document)).all()
    assert len(documents) == len(storage.files) == 6
    assert len({d.file_hash for d in documents}) == 6
    for doc in documents:
        content = storage.files[doc.object_path]
        assert sha256(content).hexdigest() == doc.file_hash
        assert Image.open(BytesIO(content)).format == 'PNG'
        assert doc.name.endswith('.png') and doc.object_path.startswith('lim-carton/seed/')
        activity = session.scalar(select(Activity).where(Activity.document_id == doc.id))
        assert doc.activity_revision == activity.revision == 1
        assert doc.extraction == doc.original_extraction
        assert str(int(activity.quantity)) == doc.original_extraction['activities'][0]['quantity']
    assert sum(d.confirmed for d in documents) == 5
    assert len(session.scalars(select(Declaration).where(Declaration.complete.is_(True))).all()) == 6
    assert len(session.scalars(select(Question)).all()) == 7
    assert session.get(FactorVersion, 'diesel-energy-v1').estimated
    session.get(Company, settings.company_id).name = 'Edited owner company'
    documents[0].extraction = {'manual': 'keep'}
    session.commit()
    originals = deepcopy(storage.files)
    seed_workspace(session, storage, settings)
    session.commit()
    assert storage.files == originals
    assert session.get(Company, settings.company_id).name == 'Edited owner company'
    assert documents[0].extraction == {'manual': 'keep'}


def test_seed_failure_compensates_upload_including_response_loss(session):
    storage = MemoryStorage(fail_at=3)
    with pytest.raises(RuntimeError):
        seed_workspace(session, storage, Settings())
    assert storage.files == {}
    assert session.get(Company, 'lim-carton') is None
    assert session.scalars(select(Document)).all() == []


def test_seed_caller_owns_commit(session):
    storage = MemoryStorage()
    seed_workspace(session, storage, Settings())
    assert session.in_transaction()
    session.rollback()
    assert session.get(Company, 'lim-carton') is None


def test_cli_missing_config_is_actionable_and_does_not_traceback(monkeypatch, capsys):
    from esg_backend.cli import main
    monkeypatch.setattr(Settings, 'from_env', classmethod(lambda cls: cls()))
    assert main(['seed']) == 1
    result = capsys.readouterr()
    assert 'Missing backend settings' in result.err
    assert 'Traceback' not in result.err


def test_bucket_check_is_read_only_and_rejects_public_bucket():
    import httpx
    from esg_backend.cli import CheckError, check_bucket
    from esg_backend.storage import SupabaseStorage
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'public': False, 'file_size_limit': 10485760})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        storage = SupabaseStorage('https://sample.supabase.co', 'server-only', 'evidence', client)
        check_bucket(storage)
    assert len(requests) == 1 and requests[0].method == 'GET'
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={'public': True}))) as client:
        with pytest.raises(CheckError, match='private'):
            check_bucket(SupabaseStorage('https://sample.supabase.co', 'server-only', 'evidence', client))


def test_browser_probe_needs_environment_key_and_rejects_server_key(session, monkeypatch):
    from esg_backend.cli import CheckError, check_browser_access
    monkeypatch.delenv('SUPABASE_PUBLISHABLE_KEY', raising=False)
    with pytest.raises(CheckError, match='environment'):
        check_browser_access(session, Settings())
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_secret_not-a-browser-key')
    with pytest.raises(CheckError, match='never the server secret'):
        check_browser_access(session, Settings())
