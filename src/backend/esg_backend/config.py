"""Environment configuration. Secrets remain on the Python server."""
from dataclasses import dataclass, field
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
    demo_access_enabled: bool = False
    backend_shared_key: str = ''
    render_hosted: bool = False
    public_workspace_enabled: bool = False
    sandbox_instance: bool = False
    esg_ocr_mode: str = 'offline'
    esg_compare_models: tuple[str, ...] = ()
    gemini_api_key: str = field(default='', repr=False)
    gemini_ocr_model: str = 'gemini-2.5-flash-lite'
    grafilab_api_key: str = field(default='', repr=False)
    grafilab_base_url: str = 'https://llm.grafilab.ai/v1'
    grafilab_ocr_model: str = 'grafilab/qwen3.5-397b-a17b'

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
            demo_access_enabled=os.getenv('DEMO_ACCESS_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes'),
            backend_shared_key=os.getenv('BACKEND_SHARED_KEY', '').strip(),
            render_hosted=os.getenv('RENDER', '').strip().lower() == 'true',
            public_workspace_enabled=os.getenv('PUBLIC_WORKSPACE_ENABLED', '').strip().lower() == 'true',
            esg_ocr_mode=os.getenv('ESG_OCR_MODE', 'offline').strip().lower(),
            esg_compare_models=tuple(model.strip() for model in os.getenv('ESG_COMPARE_MODELS', '').split(',') if model.strip()),
            gemini_api_key=os.getenv('GEMINI_API_KEY', '').strip(),
            gemini_ocr_model=os.getenv('GEMINI_OCR_MODEL', 'gemini-2.5-flash-lite').strip(),
            grafilab_api_key=os.getenv('GRAFILAB_API_KEY', '').strip(),
            grafilab_base_url=os.getenv('GRAFILAB_BASE_URL', 'https://llm.grafilab.ai/v1').strip(),
            grafilab_ocr_model=os.getenv('GRAFILAB_OCR_MODEL', 'grafilab/qwen3.5-397b-a17b').strip(),
        )

    def validate_demo_access(self) -> None:
        """Fail closed on Render; local direct-API development stays available."""
        if self.render_hosted and not self.demo_access_enabled:
            raise ValueError('Render requires DEMO_ACCESS_ENABLED=true for this simulated-role demo.')
        if self.demo_access_enabled and len(self.backend_shared_key) < 32:
            raise ValueError('Protected demo requires BACKEND_SHARED_KEY with at least 32 characters.')
        if self.demo_access_enabled and self.allow_sample_reset:
            raise ValueError('Protected demo requires ALLOW_SAMPLE_RESET=false.')
        if self.public_workspace_enabled and not self.demo_access_enabled:
            raise ValueError('Public sandbox requires protected backend demo access.')

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
