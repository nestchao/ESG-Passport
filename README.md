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
2. Run the backend on `http://127.0.0.1:8001` with root NEXT_PUBLIC_API_URL set to the same address.
3. In a second terminal:

```powershell
cd src\frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The frontend defaults to port 8000 for its API; set `NEXT_PUBLIC_API_URL` in the repository-root `.env` if needed and restart Next.js. Match `FRONTEND_ORIGIN` in the backend to the exact frontend address and port.

Keep only two environment files at the repository root: `.env` for your private local values and `.env.example` as the committed template. Copy the template only when `.env` does not already exist. The backend and Alembic read this root file explicitly; Next.js exports only its `NEXT_PUBLIC_API_URL` value. Shell environment variables take precedence. Restart both services after changing the file.

Supabase credentials are backend-only settings in this shared file. Use a dedicated synthetic hackathon project. Local customer links work while both services run. For the protected synthetic hackathon deployment, follow [the Render setup guide](docs/DEPLOY-RENDER.md). Real user accounts remain deferred.

## Verify

- Backend: from `src/backend`, run `.venv\Scripts\python.exe -m pytest tests -q --basetemp=.pytest-tmp`.
- Frontend: from `src/frontend`, run `npm test`, `npm run typecheck` and `npm run build`.
- Supabase: after setup, run `python -m esg_backend.cli check`; add `--anon-key` with `SUPABASE_PUBLISHABLE_KEY` configured to run browser-access HTTP probes.

Unit/integration tests inject isolated SQLite and fake storage; they do not claim that the hosted Supabase project has been verified. The running API accepts Supabase Postgres configuration only.

Original evidence stays immutable. Corrections and declarations create revisions. New data invalidates draft answers, and owner approval freezes the selected answers, factor versions and evidence. No certification or compliance claim is made.

## Hosted hackathon demo

[Deploy on Render and enable automatic updates](docs/DEPLOY-RENDER.md). The Blueprint creates two free services with a shared demo gate. It watches main; pushing only to Boon does not update the hosted demo. No automatic migrations, resets or seeding run.

## Integrated offline AI and OCR (test branch)

The offline [PR #9 AI workflow](src/ai/workflow/README.md) is connected to
existing questionnaire mapping, evidence coverage, preliminary preparation,
and owner review. New image/single-page PDF uploads run offline RapidOCR to
suggest consumption values; clerks must verify them before confirming.

Owner **Approve & Share** requires explicit acknowledgement and a reason for
**each** outstanding PR #9 limitation. Unresolved measurements remain gaps,
not verified disclosures. The approved internal PR #9 audit/preparation is
kept private, and public packs include only selected evidence and disclosed
limitations. Existing demo protections on Render still apply: these are not
production authentication or independent assurance.

Run full backend and frontend tests after merging this branch with main. This
branch does not change the project's synthetic-only demonstration scope.
The [synthetic dataset](src/ai/synthetic_dataset/README.md),
[generator](src/ai/synthetic_generator/README.md), and
[OCR comparison](src/ai/comparison/README.md) are research/test material,
not runtime data sources. The generator requires separate dependencies.
