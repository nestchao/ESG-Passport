"""Environment configuration. Secrets remain on the Python server."""
from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


def load_environment() -> None:
    """Use one repository-root file, independent of the working directory.

    Explicit process environment variables always take precedence.
    """
    load_dotenv(dotenv_path=ROOT_ENV_FILE, override=False)


@dataclass(frozen=True)
class Settings:
    database_url: str = ''
    supabase_url: str = ''
    supabase_server_key: str = ''
    storage_bucket: str = 'esg-evidence'
    frontend_origin: str = 'http://127.0.0.1:3000'
    company_id: str = 'lim-carton'
    allow_sample_reset: bool = False

    @classmethod
    def from_env(cls) -> 'Settings':
        load_environment()
        return cls(
            database_url=os.getenv('DATABASE_URL', '').strip(),
            supabase_url=os.getenv('SUPABASE_URL', '').strip().rstrip('/'),
            supabase_server_key=os.getenv('SUPABASE_SERVER_KEY', '').strip(),
            storage_bucket=os.getenv('SUPABASE_STORAGE_BUCKET', 'esg-evidence').strip(),
            frontend_origin=os.getenv('FRONTEND_ORIGIN', 'http://127.0.0.1:3000').strip().rstrip('/'),
            allow_sample_reset=os.getenv('ALLOW_SAMPLE_RESET', 'false').strip().lower() in ('1', 'true', 'yes'),
        )

    def validate(self) -> None:
        missing = [name for name, value in (
            ('DATABASE_URL', self.database_url), ('SUPABASE_URL', self.supabase_url),
            ('SUPABASE_SERVER_KEY', self.supabase_server_key), ('SUPABASE_STORAGE_BUCKET', self.storage_bucket),
        ) if not value]
        if missing:
            raise ValueError('Missing backend settings: ' + ', '.join(missing) + '. Copy .env.example and configure your Supabase project.')
        if not self.database_url.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')):
            raise ValueError('DATABASE_URL must be a Supabase Postgres connection string; use the session pooler when direct IPv6 is unavailable.')
        parsed = urlsplit(self.supabase_url)
        if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('SUPABASE_URL must be your HTTPS Supabase project URL.')
        origin = urlsplit(self.frontend_origin)
        if origin.scheme not in ('http', 'https') or not origin.netloc or origin.path or origin.query or origin.fragment:
            raise ValueError('FRONTEND_ORIGIN must be a single HTTP(S) origin, for example http://127.0.0.1:3000.')
