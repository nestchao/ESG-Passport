"""Explicit setup and verification: python -m esg_backend.cli --help."""
import argparse
import os
import sys
from urllib.parse import quote

import httpx
from sqlalchemy import inspect, select, text

from .config import Settings
from .db import build_engine, make_session_factory
from .models import Base, Company, Document
from .seed import seed_workspace
from .storage import StorageError, SupabaseStorage


class CheckError(RuntimeError):
    pass


def check_database(session, settings):
    session.execute(text('SELECT 1'))
    connection = session.connection()
    expected = set(Base.metadata.tables)
    missing = expected - set(inspect(connection).get_table_names(schema='public'))
    if missing:
        raise CheckError('Application tables are missing. Run alembic upgrade head before seeding or checking.')
    company = session.get(Company, settings.company_id)
    if company is None:
        raise CheckError('Sample workspace is missing. Run python -m esg_backend.cli seed.')
    if (company.name, company.location, company.sector, company.period, company.synthetic) != (
            'Lim Carton Industries', 'Shah Alam', 'Manufacturing', '2026-09', True):
        raise CheckError('Workspace identity differs from the expected synthetic company; inspect it without reseeding.')
    rows = session.execute(text("""
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    """)).all()
    protected = {name: enabled for name, enabled in rows if name in expected}
    if set(protected) != expected or not all(protected.values()):
        raise CheckError('RLS is not enabled on every application table. Apply the security migration.')
    for role in ('anon', 'authenticated'):
        exists = session.scalar(text('SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=:role)'), {'role': role})
        if not exists:
            raise CheckError('Expected Supabase browser roles are missing. Use the configured Supabase database.')
        for table_name in sorted(expected):
            allowed = session.scalar(text("SELECT has_table_privilege(:role, :table_name, 'SELECT')"),
                                     {'role': role, 'table_name': 'public.' + table_name})
            if allowed:
                raise CheckError('Browser roles have application-table SELECT privileges. Apply the security migration.')
    policies = session.execute(text("SELECT tablename, roles FROM pg_policies WHERE schemaname='public'")).all()
    for table_name, roles in policies:
        if table_name in expected and set(roles) & {'public', 'anon', 'authenticated'}:
            raise CheckError('An application RLS policy allows browser roles. Review Supabase policies.')


def check_bucket(storage):
    response = storage._request('GET', '/bucket/' + quote(storage.bucket, safe=''))
    if not response.is_success:
        raise CheckError('Cannot read the evidence bucket. Run init-storage or check the server key.')
    try:
        bucket = response.json()
    except ValueError:
        raise CheckError('Storage returned invalid bucket metadata.') from None
    if not isinstance(bucket, dict) or bucket.get('public') is not False:
        raise CheckError('The evidence bucket must exist and be private.')


def check_browser_access(session, settings):
    key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '').strip()
    if not key:
        raise CheckError('Set SUPABASE_PUBLISHABLE_KEY in the server environment to run --anon-key probes; never pass keys as CLI arguments.')
    if key == settings.supabase_server_key or key.startswith('sb_secret_'):
        raise CheckError('SUPABASE_PUBLISHABLE_KEY must be a browser publishable/anon key, never the server secret.')
    # Legacy anon JWTs and modern publishable keys are both supplied through apikey.
    headers = {'apikey': key}
    if not key.startswith('sb_publishable_'):
        headers['Authorization'] = 'Bearer ' + key
    document = session.scalar(select(Document).where(Document.company_id == settings.company_id).order_by(Document.id))
    if document is None:
        raise CheckError('Seed an evidence document before browser access probes.')
    bucket = quote(settings.storage_bucket, safe='')
    path = quote(document.object_path, safe='/')
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for endpoint in (f'/storage/v1/object/{bucket}/{path}', f'/storage/v1/object/public/{bucket}/{path}'):
            response = client.get(settings.supabase_url + endpoint, headers=headers)
            if response.is_success:
                raise CheckError('A browser key could download private evidence. Review bucket and storage policies.')
            if response.status_code not in (400, 401, 403, 404):
                raise CheckError('Storage denial probe was inconclusive; check connectivity and retry.')
        for table_name in sorted(Base.metadata.tables):
            response = client.get(settings.supabase_url + '/rest/v1/' + quote(table_name),
                                  headers=headers, params={'select': '*', 'limit': '1'})
            if response.status_code in (401, 403):
                continue
            if response.status_code == 200:
                try:
                    if response.json() == []:
                        continue
                except ValueError:
                    pass
            raise CheckError('Browser REST isolation probe failed or was inconclusive. Review table grants and RLS.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Explicit ESG Passport Supabase setup; no command runs automatically at API startup.')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init-storage', help='Create or verify the private evidence bucket.')
    commands.add_parser('seed', help='Create the synthetic workspace once; never overwrite an existing company.')
    check = commands.add_parser('check', help='Read-only database, RLS, grants and private-bucket verification.')
    check.add_argument('--anon-key', action='store_true', help='Also probe using SUPABASE_PUBLISHABLE_KEY from the environment (no key argument).')
    args = parser.parse_args(argv)
    engine = None
    storage = None
    session = None
    try:
        settings = Settings.from_env()
        try:
            settings.validate()
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        storage = SupabaseStorage(settings.supabase_url, settings.supabase_server_key, settings.storage_bucket)
        if args.command == 'init-storage':
            storage.ensure_bucket()
            print('Private evidence bucket ready.')
            return 0
        engine = build_engine(settings.database_url)
        session = make_session_factory(engine)()
        if args.command == 'seed':
            tables = set(inspect(engine).get_table_names(schema='public'))
            if not set(Base.metadata.tables).issubset(tables):
                raise CheckError('Application tables are missing. Run alembic upgrade head first.')
            existed = session.get(Company, settings.company_id) is not None
            seed_workspace(session, storage, settings)
            try:
                session.commit()
            except Exception:
                session.rollback()
                paths = session.info.pop('seed_uploaded_paths', [])
                if paths:
                    try:
                        storage.delete(paths)
                    except Exception:
                        print('Seed commit failed; sample object cleanup also failed. Review the private bucket for orphaned seed objects.', file=sys.stderr)
                raise
            print('Workspace already exists; no records changed.' if existed else 'Synthetic sample workspace seeded.')
        else:
            check_database(session, settings)
            check_bucket(storage)
            if args.anon_key:
                check_browser_access(session, settings)
            print('Checks passed: database, application tables, synthetic workspace, RLS, browser grants/policies and private bucket.'
                  + (' Browser download and REST probes passed.' if args.anon_key else ' Browser HTTP probes were not requested.'))
        return 0
    except (CheckError, StorageError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        # Driver/HTTP exceptions can contain passwords, connection strings or request headers.
        print('Backend setup failed. Check Supabase connectivity, server credentials, database role privileges and applied Alembic migrations. No secret details are printed.', file=sys.stderr)
        return 1
    finally:
        if session is not None:
            session.close()
        if engine is not None:
            engine.dispose()
        if storage is not None:
            storage.client.close()


if __name__ == '__main__':
    raise SystemExit(main())
