# Render hackathon deployment

Deploy the synthetic demo using the root render.yaml Blueprint. It creates two Free web services that watch main. Supabase remains the database and private evidence store.

## Prepare

- Rotate the Supabase database password and server key exposed in earlier screenshots, and update your private local .env. Never commit secrets.
- Review and merge the tested changes into GitHub main. A push only to Boon does not update the deployment branch.
- Create a Render account, connect GitHub, and choose New > Blueprint with this repository and main.
- Confirm both service plans say Free. No new database or persistent disk is needed. Keep existing data; do not reset or reseed.

## Fill the environment prompts

API service only:

- DATABASE_URL: rotated Supabase Postgres session-pooler connection string. Percent-encode special password characters.
- SUPABASE_URL: HTTPS Supabase project URL.
- SUPABASE_SERVER_KEY: rotated server/secret key, not the publishable key.
- FRONTEND_ORIGIN: actual frontend HTTPS origin, without a path.

Frontend service only:

- BACKEND_INTERNAL_URL: actual API public HTTPS Render URL, without /api/backend or another path. Despite the name, this uses public HTTPS; the server key protects direct API access.
- DEMO_PASSWORD: a strong unique password of at least 16 characters. Share privately with judges.

If Render has not assigned service URLs during the initial form, use https://example.invalid temporarily for the two URL fields. After creating resources, replace them with the actual URLs and redeploy both services. The app cannot connect until placeholders are replaced.

The Blueprint generates BACKEND_SHARED_KEY once in a shared environment group linked to both services. It generates DEMO_SESSION_SECRET for the frontend too. Keep them private. It enables DEMO_ACCESS_ENABLED on both services, sets NEXT_PUBLIC_API_URL=/api/backend on the frontend, and disables ALLOW_SAMPLE_RESET on the API. Do not upload your full .env to the frontend or put secrets in NEXT_PUBLIC_ variables.

## Service settings

Frontend: root src/frontend, Node 22, build npm ci && npm run build, start npm run start -- --hostname 0.0.0.0 --port $PORT, health path /login.

Backend: repository root (no rootDir), Python 3.12 pinned by root .python-version. Build with pip install -r src/backend/requirements.txt; start with cd src/backend && uvicorn esg_backend.app:app --host 0.0.0.0 --port $PORT; health path /health. The backend imports sibling src/ai/workflow, so rootDir: src/backend prevents the build and runtime from accessing required AI files. Use buildFilter paths for src/backend/** and src/ai/workflow/** instead.

These are Render Linux commands. Keep $PORT as written. Both services use Auto-Deploy On Commit and branch main. The login page is public; protected pages and API proxy require a session. GET /health is the API's only unauthenticated route.

No migrations or seeds run at startup. No migration is added by this change. For future schema changes, verify the local environment targets the intended Supabase project, then explicitly run python -m alembic current, python -m alembic upgrade head, and python -m esg_backend.cli check from the configured backend environment before deploying dependent code.

## Verify before sharing

1. Wait for both services to show Live. API /health should return status ok. For 503, inspect private logs and configuration without sharing secrets.
2. Open the website in a private browser. Test wrong password, correct login and logout.
3. Check December 2026 and another month; existing records and approved packs should remain in their months.
4. Upload a fresh synthetic file. Enter category, quantity, unit and dates; save and explicitly confirm. Test a valid file near 10 MiB too.
5. Correct, archive and restore a record; restoration must require reconfirmation. Save an owner declaration.
6. Review a request as clerk, hand it off, and approve as owner. Open its share link in another private session and enter the demo password. Only selected evidence should download.
7. After logout, workspace APIs and customer files must require login. Direct API /documents must return 401 even with an Owner role header. The backend server key must not appear in browser requests.
8. Restart services and verify Supabase records, files and packs persist.

## Update later versions

1. Edit and test locally on your development branch.
2. Push and review Application checks in GitHub Actions: frontend tests, TypeScript, production build and isolated backend tests. CI needs no Supabase secrets.
3. Merge tested changes into main. Render rebuilds the service whose root directory changed. Services deploy independently; keep API changes backward compatible.
4. Wait for Live and check the same website URL. No new service, database or bucket is needed.

On Commit deploys are not blocked by CI. To enforce checks later, select After CI Checks Pass for both services and change autoDeployTrigger in render.yaml to checksPass as well.

For environment changes, update Render values and choose the save option that redeploys. Editing your laptop .env does not update Render. Frontend public variables require a rebuild; restarting alone retains the current deployment's environment snapshot.

For a failed version, inspect deployment logs and use Render's previous-deployment rollback where appropriate. Application rollback does not reverse database migrations or data edits.

## Demo limits

Free services sleep after 15 idle minutes and share account usage allowances. Open the website and an API-backed screen before presenting, allowing both services to wake. Retry after a waking-backend connection error. Do not promise fixed latency.

Everyone with the shared password can use the simulated roles. This is for synthetic hackathon data, not individual production accounts. Customer share links also require the demo password.

Local development stays frontend 3000 and backend 8001, with DEMO_ACCESS_ENABLED=false by default. Your private .env is unchanged.

References: https://render.com/docs/blueprint-spec and https://render.com/docs/deploys and https://render.com/docs/free

Render automatically provides the frontend RENDER_EXTERNAL_URL used to check login/save origins behind HTTPS termination. If you later use a custom domain, set frontend DEMO_PUBLIC_ORIGIN to that exact HTTPS origin and redeploy. Leave it unset for the normal Render address. Changing DEMO_SESSION_SECRET invalidates existing demo sessions.

### Passwordless homepage with Supabase + Gemini / Grafilab OCR

The homepage `/` and `/live` now open **without visitor passwords**.
Next.js proxies requests to FastAPI using the protected **server-only**
`BACKEND_SHARED_KEY`; the private Supabase database/Storage credentials and
Gemini/Grafilab API keys never enter the browser. `/login` redirects to `/`.

Only fictional hackathon data is appropriate because the shared live
workspace is publicly readable and editable with simulated roles. The
frontend allows permanent deletion through the existing FastAPI endpoint,
blocks sample reset, and enforces best-effort per-instance request limits on
writes and OCR uploads. Public visitors can permanently delete shared
fictional records. These
controls are not production security or abuse prevention. Keep
`DEMO_ACCESS_ENABLED=true` and the private backend shared key configured;
**do not** disable the backend access key to remove the browser password.

For new Blueprint deployments, `PUBLIC_LIVE_WORKSPACE_ENABLED=true` is set
in the shared environment group and the frontend health check uses `/demo`
to ensure a 200 response with no auth. `DEMO_PASSWORD` and
`DEMO_SESSION_SECRET` are not required by the passwordless frontend.
Remove any old manual secrets from Render only if no other workflows rely on
them. After updating the Blueprint, ensure the new environment value has
deployed to the frontend and verify that GET `/` returns 200.

The backend calls Gemini OCR on public uploads only when `ESG_OCR_MODE`
and the provider credentials are correctly set **on Render backend**.
Grafilab may be used as a fallback; offline OCR may still be used if both
remote providers fail. Verify the OCR engine/model on a synthetic upload
before claiming a real Gemini/Grafilab success.

The public `/demo` page stays browser-only with fake sample data and never
calls Supabase; `/ocr` stays browser-based too.
