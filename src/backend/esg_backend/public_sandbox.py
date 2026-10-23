"""Separate, disposable synthetic database for anonymous ESG Passport visitors.

This module does not import, instantiate or request Supabase services.
The in-memory database and synthetic evidence are destroyed on restart.
"""
from dataclasses import replace
from hashlib import sha256
from fastapi import HTTPException
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base
from .seed import seed_workspace
from .storage import StorageError


# Approved fictional test images, identified by immutable SHA-256 digests.
# No user-provided or personal document can enter the shared public sandbox.
# These fixtures come from src/ai/synthetic_dataset, but source images are not
# bundled in the backend deployment, so validation uses only their digests.
APPROVED_TEST_IMAGES = {
    '1e990e0dc20d61da66ad52ce2236c76be790cdb698a5f7cc7c396dba17ca5faf': ('electricity', '2026-05'),
    '1acd7151a058030695492421cb8b2a1fc7e7d7740a3d3de01572c0b05dbd0d97': ('water', '2026-03'),
    'c4bc11002caa2ed8ed82317e6214020c54209d776295f8ac26ee21df916e3b0a': ('waste', '2026-03'),
}
MAX_PUBLIC_IMAGE_BYTES = 512 * 1024


def validate_synthetic_upload(content: bytes, category: str, period: str) -> None:
    if len(content) > MAX_PUBLIC_IMAGE_BYTES:
        raise HTTPException(413, 'Public demo images must be 512 KB or smaller.')
    approved = APPROVED_TEST_IMAGES.get(sha256(content).hexdigest())
    if not approved:
        raise HTTPException(403, 'Public demo accepts only the three approved synthetic sample PNGs (electricity-itemised-001-clean.png, water-sidebar-001-clean.png, waste-landscape-001-clean.png). Never upload personal documents.')
    if (category, period) != approved:
        raise HTTPException(422, {'message': f'Sample document category must be {approved[0]} and reporting month {approved[1]}. Select that category and month before uploading.'})

class SyntheticMemoryStorage:
    def __init__(self):
        self.files={}
        self.lock=Lock()
    def ensure_bucket(self):
        pass
    def upload(self,path,content,content_type):
        if len(content)>2*1024*1024:
            raise StorageError('Public synthetic sandbox file exceeds the 2MB limit.')
        with self.lock:
            if path in self.files:raise StorageError('Sandbox file already exists.')
            if len(self.files)>=50:raise StorageError('Public sandbox storage is full; retry after a restart.')
            self.files[path]=bytes(content)
    def download(self,path):
        with self.lock:
            if path not in self.files:raise StorageError('Synthetic file unavailable.')
            return self.files[path]
    def delete(self,paths):
        with self.lock:
            for path in paths:self.files.pop(path,None)


def make_public_app(main_settings):
    # This is intentionally NOT using main_settings.database_url or SupabaseStorage.
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions=sessionmaker(engine,autoflush=False,expire_on_commit=False)
    storage=SyntheticMemoryStorage()
    sandbox_settings=replace(main_settings,company_id='public-fictional-workspace',
                             allow_sample_reset=False,public_workspace_enabled=False,
                             sandbox_instance=True)
    with sessions() as db:
        seed_workspace(db,storage,sandbox_settings)
        db.commit()
    from .app import create_app
    return create_app(settings=sandbox_settings,session_factory=sessions,storage=storage)
