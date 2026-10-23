# ESG Passport backend

FastAPI persists the synthetic monthly workspace in Supabase Postgres and stores original PNG/JPEG/PDF evidence in a private Supabase Storage bucket. Calculations use decimal arithmetic and confirmed activity revisions. Offline RapidOCR extracts *candidate* quantities and billing dates from supported images and single-page PDFs into the existing record editor; human correction and confirmation remain required. The PR #9 deterministic AI workflow assists bilingual questionnaire mapping, evidence coverage, calculation provenance and explicit owner gap acknowledgement. There is no external LLM service, independent evidence assurance or automatic certification.

This is a local prototype. The role switch / `X-Demo-Role` header is a demonstration of owner, clerk and customer permissions, not real authentication. Keep local direct access bound to `127.0.0.1`. The [protected Render hackathon deployment](../../docs/DEPLOY-RENDER.md) adds a server key and shared website password; real-user deployment still requires identity, authorization and tenant isolation. Browser roles receive no direct database table privileges. Only the Python server receives the database password and Supabase server key.

Python 3.12 is required by the offline RapidOCR dependency. The Render backend and GitHub Actions checks use the same version; the frontend continues to use Node 22.

## Windows setup

From the repository root, in PowerShell:

```powershell
cd src\backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path ../../.env)) { Copy-Item ../../.env.example ../../.env }
```

Recommended local addresses are frontend `http://127.0.0.1:3000` and backend `http://127.0.0.1:8001`. Set these entries in the repository-root `.env` before starting the services:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
FRONTEND_ORIGIN=http://127.0.0.1:3000
```

The frontend's fallback API address remains port 8000 for compatibility when `NEXT_PUBLIC_API_URL` is absent. The explicit value above selects port 8001; the Uvicorn command must use the same port. Restart Next.js after changing this value.

Edit the repository-root `.env` with your Supabase project URL, server secret/service-role key and Postgres session-pooler connection string. Both the backend and Alembic read this exact file regardless of your working directory. Explicit process environment variables take precedence. There are no separate backend or frontend `.env` files. Do not paste secrets into chat or source code.

For `DATABASE_URL`, use the Supabase dashboard's connection string. The session pooler is useful where direct IPv6 is unavailable (typically port 5432, user `postgres.<project-ref>`); use its exact host and username. A direct database connection also works where supported. Percent-encode special characters in the password. The backend normalizes Postgres URLs to Psycopg 3 and requires TLS by default. SQLite is only available through explicit test dependency injection; configuration rejects it for the running server.

Use a database role that can apply migrations, enable RLS and revoke browser grants. The server's database role must be able to read and write the protected application tables; use a trusted server role with appropriate RLS bypass or server policies. Supabase `anon` and `authenticated` roles must retain no application table access or permissive application policies. The server storage key must manage the private evidence bucket. No secret is needed in browser code.

From `src/backend` after creating the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m esg_backend.cli init-storage
.\.venv\Scripts\python.exe -m esg_backend.cli seed
.\.venv\Scripts\python.exe -m esg_backend.cli check
.\.venv\Scripts\python.exe -m uvicorn esg_backend.app:app --host 127.0.0.1 --port 8001
```

API startup never migrates, seeds or creates the bucket. `init-storage` explicitly creates/verifies a private bucket and enforces a maximum 10 MB upload limit. `seed` requires migrated tables, creates six distinct sample PNG originals and never overwrites an existing company. An existing workspace returns immediately; it does not reset activities, declarations, factors, requests or approvals. New seed uploads use immutable UUID paths and are cleaned up on seed failure. If compensation itself fails, inspect the private bucket for orphaned objects before retrying. Database transactions and storage writes are separate services, so interrupted processes can leave orphans.

The starting company is fictional Lim Carton Industries, Shah Alam, Manufacturing, September 2026. Electricity has 1,000 kWh pending confirmation. Diesel has 100 L, purchased water 10 m3, and waste 100 kg generated / 80 kg diverted / 20 kg disposed, all confirmed. Six explicit owner declarations include both policies in place and policies not in place. Fuel conversion factors are estimated mineral-fuel proxies and never count as complete disclosures. The provisional Peninsular grid factor is 0.740 kg CO2e/kWh. These are monthly, partial-year records with no annual extrapolation.

`check` is read-only: it verifies database reachability, every application table, the seeded company identity, RLS on all application tables, absence of browser SELECT privileges or browser policies, and private bucket metadata. It does not create or repair anything. Optionally set `SUPABASE_PUBLISHABLE_KEY` to the project's browser publishable/legacy anon key and run:

```powershell
.\.venv\Scripts\python.exe -m esg_backend.cli check --anon-key
```

The flag takes no key argument. Probes use a seeded document path read by the trusted server, verify browser denial for both public and private download routes, and verify REST cannot return application rows. A passing check without this flag does not claim to have run HTTP browser probes. No check prints credentials or driver exception details.

`FRONTEND_ORIGIN` must match the actual local frontend origin, including port; the default is `http://127.0.0.1:3000`. OpenAPI is available at [local API docs](http://127.0.0.1:8001/docs) while the server runs. `ALLOW_SAMPLE_RESET=false` is the default; enable it only when deliberately testing the sample-reset endpoint against a disposable synthetic workspace.

## Tests

Tests use injected SQLite and in-memory storage, without Supabase credentials. They do not replace live Supabase security checks. Runtime installation excludes pytest; install development requirements to run tests. From `src/backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=./.pytest-tmp
```

Use a writable workspace path for pytest's temporary directory. After configuring a real Supabase project, run the explicit setup and `check --anon-key` sequence above to verify persistence and access isolation against the live services.

## Monthly reporting and reversible archive migration

From src/backend, explicitly apply `python -m alembic upgrade head` before starting the updated API. Revision 0003_monthly_archive adds nullable archive metadata and audit-event reporting months, preserving existing document versions and source paths. No reset or reseed is needed. Legacy events with no resolvable record/request target remain workspace-level.

GET /profile, /documents, /declarations, /questionnaires and /shares accept `period=YYYY-MM` (default 2026-09). GET /documents additionally accepts `archived=true` for archived rows only; the default is active rows. Activity history stays company-wide. Reporting selection never changes Company.period globally.

Uploads accept a multipart period. PUT /documents/{id} accepts name, period, activities and expected_version atomically and leaves the record unconfirmed. POST /documents/{id}/archive and /restore require expected_version. Owner and clerk may use these endpoints; customers cannot. The existing PUT activities endpoint also accepts expected_version, and the frontend always sends it. Stale versions return 409. For legacy client compatibility this field remains optional on that existing endpoint only.

Duplicate-file 409 responses include the existing document ID, assigned period and archive state. Archived files remain available internally and through previously approved token routes, but cannot be added to a new declaration/approval. Edits invalidate affected monthly drafts and periods with declarations referencing the changed evidence. Approved snapshots are never rewritten.

## Protected hosted demo

On Render, DEMO_ACCESS_ENABLED=true and BACKEND_SHARED_KEY (at least 32 characters) are required; invalid demo protection fails startup. ALLOW_SAMPLE_RESET must remain false. Every route except GET /health requires X-Demo-Backend-Key from the frontend server proxy. Existing role checks and pack-token/evidence checks still apply. See [the Render guide](../../docs/DEPLOY-RENDER.md) for setup and automatic updates.

## Delete a record (Owner only)

Records offers **Archive** (reversible) and **Delete** (permanent) separately.
The Owner can delete an active or archived record only after typing `DELETE` in
the confirmation dialog. The API requires the record's current version:
`DELETE /documents/{document_id}` with JSON `{"expected_version": <version>}`.
This permanently removes the original object and all activity revisions,
invalidates current questionnaire drafts and calculations, and keeps an audit
event recording the actor and reporting month. Deletion is rejected if an
approved customer Passport or any historical owner declaration references
the record. Use Archive to retain historical/audited evidence.

For this prototype the Owner role is simulated. Real-world permanent deletion
requires production identity and retention-policy controls before rollout.

## Waste weighbridge OCR (unclassified transfer weight)

A waste transfer/weighbridge ticket can include a NET / BERAT BERSIH weight
without proving it is waste **generated**, **diverted** or **disposed**.
Offline OCR stores a `waste_transfer_candidate` with net mass, unit, point
date and source line while leaving the ESG waste activity category blank. The
existing Records editor pre-fills that unclassified quantity for human review.
The user must select the applicable category using additional evidence, and
the record reporting month must match the source date before confirmation.
GROSS and TARE are not used as the reported quantity; where all three weights
are readable the net amount is checked against gross-minus-tare. Original
documents and first-pass OCR are retained. Existing unconfirmed records with
previously failed OCR can be reopened for read-only candidate recovery.
