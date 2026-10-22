# ESG Passport backend

FastAPI persists the synthetic monthly workspace in Supabase Postgres and stores original PNG/JPEG/PDF evidence in a private Supabase Storage bucket. Calculations use decimal arithmetic and confirmed activity revisions. Automatic OCR and live AI are not connected: extracted fields require manual entry and human confirmation; questionnaire suggestions use deterministic wording matching.

This is a local prototype. The role switch / `X-Demo-Role` header is a demonstration of owner, clerk and customer permissions, not real authentication. Keep the API bound to `127.0.0.1`; add real identity, authorization and tenant isolation before a network deployment. Browser roles receive no direct database table privileges. Only the Python server receives the database password and Supabase server key.

## Windows setup

From the repository root, in PowerShell:

```powershell
cd src\backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `src/backend/.env` with your Supabase project URL, server secret/service-role key and Postgres session-pooler connection string. Do not paste keys into chat or frontend files. Explicit process environment variables take precedence over this file. Keep one backend configuration; a repository-root `.env` also works if no nearer backend file exists.

For `DATABASE_URL`, use the Supabase dashboard's connection string. The session pooler is useful where direct IPv6 is unavailable (typically port 5432, user `postgres.<project-ref>`); use its exact host and username. A direct database connection also works where supported. Percent-encode special characters in the password. The backend normalizes Postgres URLs to Psycopg 3 and requires TLS by default. SQLite is only available through explicit test dependency injection; configuration rejects it for the running server.

Use a database role that can apply migrations, enable RLS and revoke browser grants. The server's database role must be able to read and write the protected application tables; use a trusted server role with appropriate RLS bypass or server policies. Supabase `anon` and `authenticated` roles must retain no application table access or permissive application policies. The server storage key must manage the private evidence bucket. No secret is needed in browser code.

From `src/backend` with the virtual environment active:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m esg_backend.cli init-storage
.\.venv\Scripts\python.exe -m esg_backend.cli seed
.\.venv\Scripts\python.exe -m esg_backend.cli check
.\.venv\Scripts\python.exe -m uvicorn esg_backend.app:app --host 127.0.0.1 --port 8000
```

API startup never migrates, seeds or creates the bucket. `init-storage` explicitly creates/verifies a private bucket and enforces a maximum 10 MB upload limit. `seed` requires migrated tables, creates six distinct sample PNG originals and never overwrites an existing company. An existing workspace returns immediately; it does not reset activities, declarations, factors, requests or approvals. New seed uploads use immutable UUID paths and are cleaned up on seed failure. If compensation itself fails, inspect the private bucket for orphaned objects before retrying. Database transactions and storage writes are separate services, so interrupted processes can leave orphans.

The starting company is fictional Lim Carton Industries, Shah Alam, Manufacturing, September 2026. Electricity has 1,000 kWh pending confirmation. Diesel has 100 L, purchased water 10 m3, and waste 100 kg generated / 80 kg diverted / 20 kg disposed, all confirmed. Six explicit owner declarations include both policies in place and policies not in place. Fuel conversion factors are estimated mineral-fuel proxies and never count as complete disclosures. The provisional Peninsular grid factor is 0.740 kg CO2e/kWh. These are monthly, partial-year records with no annual extrapolation.

`check` is read-only: it verifies database reachability, every application table, the seeded company identity, RLS on all application tables, absence of browser SELECT privileges or browser policies, and private bucket metadata. It does not create or repair anything. Optionally set `SUPABASE_PUBLISHABLE_KEY` to the project's browser publishable/legacy anon key and run:

```powershell
.\.venv\Scripts\python.exe -m esg_backend.cli check --anon-key
```

The flag takes no key argument. Probes use a seeded document path read by the trusted server, verify browser denial for both public and private download routes, and verify REST cannot return application rows. A passing check without this flag does not claim to have run HTTP browser probes. No check prints credentials or driver exception details.

`FRONTEND_ORIGIN` must match the actual local frontend origin, including port; the default is `http://127.0.0.1:3000`. OpenAPI is available at [local API docs](http://127.0.0.1:8000/docs) while the server runs. `ALLOW_SAMPLE_RESET=false` is the default; enable it only when deliberately testing the sample-reset endpoint against a disposable synthetic workspace.

## Tests

Tests use injected SQLite and in-memory storage, without network credentials. They do not replace live Supabase security checks. From `src/backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=./.pytest-tmp
```

Use a writable workspace path for pytest's temporary directory. After configuring a real Supabase project, run the explicit setup and `check --anon-key` sequence above to verify persistence and access isolation against the live services.
