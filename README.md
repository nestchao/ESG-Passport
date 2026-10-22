# ESG Passport

Evidence-backed monthly ESG profiles and owner-approved customer questionnaire packs.

## Application

- **Frontend:** Next.js and Tailwind in `src/frontend`.
- **Backend:** FastAPI in `src/backend`.
- **Persistence:** Supabase Postgres and private Supabase Storage.
- **Current scope:** one fictional company, September 2026, simulated roles, manual bill review and wording-based question suggestions. No live AI or production authentication.

The frontend now calls the API. It does not fall back to browser fixtures when the API is unavailable. Earlier browser-local records remain untouched and are not imported.

## Start locally

1. Follow [backend setup](src/backend/README.md): create a Python environment, configure the backend `.env`, apply Alembic migrations, initialize private Storage and explicitly seed sample records.
2. Run the backend on `http://127.0.0.1:8000`.
3. In a second terminal:

```powershell
cd src\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The frontend defaults to port 8000 for its API; use `src/frontend/.env.local` with `NEXT_PUBLIC_API_URL` if needed and restart Next.js. Match `FRONTEND_ORIGIN` in the backend to the exact frontend address and port.

Supabase credentials belong only in the backend environment. Use a dedicated synthetic hackathon project. This milestone keeps the API bound to localhost; customer links can be opened in another browser while both local services run. Hosted sharing and real accounts require the later deployment/authentication work.

## Verify

- Backend: from `src/backend`, run `.venv\Scripts\python.exe -m pytest tests -q --basetemp=.pytest-tmp`.
- Frontend: from `src/frontend`, run `npm test`, `npm run typecheck` and `npm run build`.
- Supabase: after setup, run `python -m esg_backend.cli check`; add `--anon-key` with `SUPABASE_PUBLISHABLE_KEY` configured to run browser-access HTTP probes.

Unit/integration tests inject isolated SQLite and fake storage; they do not claim that the hosted Supabase project has been verified. The running API accepts Supabase Postgres configuration only.

Original evidence stays immutable. Corrections and declarations create revisions. New data invalidates draft answers, and owner approval freezes the selected answers, factor versions and evidence. No certification or compliance claim is made.
