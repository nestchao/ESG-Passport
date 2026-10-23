# ESG Passport

Evidence-backed monthly ESG profiles and owner-approved customer questionnaire packs.

## Application

- **Frontend:** Next.js and Tailwind in `src/frontend`.
- **Backend:** FastAPI in `src/backend`.
- **Persistence:** Supabase Postgres and private Supabase Storage.
- **Current scope:** one fictional company, September 2026, simulated roles, manual bill review and wording-based question suggestions. No live AI or production authentication.

The frontend now calls the API. It does not fall back to browser fixtures when the API is unavailable. Earlier browser-local records remain untouched and are not imported.

## Start locally

1. Follow [backend setup](src/backend/README.md): create a Python environment, configure the repository-root `.env`, apply Alembic migrations, initialize private Storage and explicitly seed sample records.
2. Run the backend on `http://127.0.0.1:8001`, matching the example environment configuration.
3. In a second terminal:

```powershell
cd src\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The example root environment sets `NEXT_PUBLIC_API_URL=http://127.0.0.1:8001`; the frontend falls back to port 8000 only when that setting is absent. Restart Next.js after changes. Match `FRONTEND_ORIGIN` in the backend to the exact frontend address and port.

Keep only two environment files at the repository root: `.env` for your private local values and `.env.example` as the committed template. Copy the template only when `.env` does not already exist. The backend and Alembic read this root file explicitly; Next.js exports only its `NEXT_PUBLIC_API_URL` value. Shell environment variables take precedence. Restart both services after changing the file.

Supabase credentials are backend-only settings in this shared file. Use a dedicated synthetic hackathon project. This milestone keeps the API bound to localhost; customer links can be opened in another browser while both local services run. Hosted sharing and real accounts require the later deployment/authentication work.

## Verify

- Backend: from `src/backend`, run `.venv\Scripts\python.exe -m pytest tests -q --basetemp=.pytest-tmp`.
- Frontend: from `src/frontend`, run `npm test`, `npm run typecheck` and `npm run build`.
- Supabase: after setup, run `python -m esg_backend.cli check`; add `--anon-key` with `SUPABASE_PUBLISHABLE_KEY` configured to run browser-access HTTP probes.

Unit/integration tests inject isolated SQLite and fake storage; they do not claim that the hosted Supabase project has been verified. The running API accepts Supabase Postgres configuration only.

Original evidence stays immutable. Corrections and declarations create revisions. New data invalidates draft answers, and owner approval freezes the selected answers, factor versions and evidence. No certification or compliance claim is made.
## AI module

The offline [AI workflow](src/ai/workflow/README.md) provides reviewed evidence intake,
bilingual SEDG requirement forms, matching/coverage checks, guarded Scope 2
calculations and preparation exports. It is not yet connected to the live backend
or review UI. Scope 1 and fuel-to-energy calculations remain explicit gaps.

The [synthetic generator](src/ai/synthetic_generator/README.md) and four-category
[synthetic dataset](src/ai/synthetic_dataset/README.md) are public team-created
fixtures. Supplemental fictional staff records are in
`src/ai/workflow/fixtures/staff_records`. They remain self-declared and unverified.
The [OCR comparison](src/ai/comparison/README.md) reports the bounded synthetic pilot.

Install application dependencies from the root requirements with uv targeting an
explicit project environment. The offline synthetic generator requires a separate
approved environment: its Pillow 13 pin conflicts with the backend's Pillow <13
range. Use its own requirements file; do not combine both dependency sets.
Private research, real reference records, credentials and development notes remain
ignored under `src/ai/.local/` and `docs/reference/`.

## Project folders and licence

`docs/` holds competition documentation, `runpod/` deployment notes, `src/`
application code, `submission/` deliverables and `tests/` AI regression checks.
Project code uses Apache License 2.0; see LICENSE. Third-party materials retain
their respective licences and notices.
