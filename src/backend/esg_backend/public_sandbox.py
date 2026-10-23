"""Separate, disposable synthetic database for anonymous ESG Passport visitors.

This module does not import, instantiate or request Supabase services.
The in-memory database and synthetic evidence are destroyed on restart.
"""
from dataclasses import replace
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base
from .seed import seed_workspace
from .storage import StorageError

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
                             allow_sample_reset=False,public_workspace_enabled=False)
    with sessions() as db:
        seed_workspace(db,storage,sandbox_settings)
        db.commit()
    from .app import create_app
    return create_app(settings=sandbox_settings,session_factory=sessions,storage=storage)
