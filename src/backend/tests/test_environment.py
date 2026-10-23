"""Regression coverage for the single root environment file, using fake values only."""
import os
import pytest
from esg_backend import config

ENV_KEYS = ('DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_SERVER_KEY', 'SUPABASE_STORAGE_BUCKET',
            'FRONTEND_ORIGIN', 'ALLOW_SAMPLE_RESET')


def test_backend_reads_root_environment_from_any_working_directory(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    environment = root / '.env'
    environment.write_text('DATABASE_URL=postgresql://test-only:fake@localhost/postgres\n'
                           'SUPABASE_SERVER_KEY=test-only-secret\n', encoding='utf8')
    unrelated = tmp_path / 'elsewhere'
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(config, 'ROOT_ENV_FILE', environment, raising=False)
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    result = config.Settings.from_env()
    if not result.database_url.startswith('postgresql://test-only:'):
        pytest.fail('Backend did not read the configured root environment file')
    if result.supabase_server_key != 'test-only-secret':
        pytest.fail('Backend did not read the server-only setting')


def test_process_environment_has_precedence_over_file(tmp_path, monkeypatch):
    environment = tmp_path / '.env'
    environment.write_text('DATABASE_URL=postgresql://file-only:fake@localhost/postgres\n', encoding='utf8')
    monkeypatch.setattr(config, 'ROOT_ENV_FILE', environment, raising=False)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://process-only:fake@localhost/postgres')
    result = config.Settings.from_env()
    if not result.database_url.startswith('postgresql://process-only:'):
        pytest.fail('A file unexpectedly overrode the process environment')


def test_shared_loader_does_not_search_for_nested_environment_files(tmp_path, monkeypatch):
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / '.env').write_text('SUPABASE_SERVER_KEY=nested-test-only\n', encoding='utf8')
    monkeypatch.setattr(config, 'ROOT_ENV_FILE', tmp_path / 'missing.env', raising=False)
    monkeypatch.delenv('SUPABASE_SERVER_KEY', raising=False)
    monkeypatch.chdir(nested)
    loader = getattr(config, 'load_environment', None)
    if loader is None:
        pytest.fail('Backend and migrations need an explicit shared root environment loader')
    loader()
    if os.getenv('SUPABASE_SERVER_KEY') is not None:
        pytest.fail('A nested environment file was loaded unexpectedly')
