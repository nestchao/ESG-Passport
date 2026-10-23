# ESG Passport frontend

Next.js workspace connected to the Python API and Supabase database/storage. The UI never falls back to browser fixtures or reads/writes the previous browser demo database.

## Run

Start and configure the backend first using its README. From this frontend folder:

```powershell
if (!(Test-Path ../../.env)) { Copy-Item ../../.env.example ../../.env }
npm install
npm run dev
```

Use frontend `http://127.0.0.1:3000` with the backend on `http://127.0.0.1:8001`. Before running `npm run dev`, set the following in the repository-root `.env` (preserve the existing Supabase settings):

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
FRONTEND_ORIGIN=http://127.0.0.1:3000
```

Start Uvicorn on port 8001 as shown in the backend README. The API fallback remains `http://127.0.0.1:8000` for compatibility only when `NEXT_PUBLIC_API_URL` is absent. The configured value above selects port 8001. Restart the frontend after changing it; Next.js embeds public variables at build time. The backend CORS origins must include the frontend origin. Use Node.js 22 or newer. The Node-only configuration reads the shared root file but exports only `NEXT_PUBLIC_API_URL` to the browser; it never exports Supabase/database secrets or other values from that file. Do not create a frontend `.env.local`. Shell variables take precedence.

For a production preview run `npm run build`, then `npm start`.

## Check

- `npm test`
- `npm run typecheck`
- `npm run build`

## Behavior and access

- The backend provides fictional September 2026 seed records. Quantities from newly uploaded bills are entered and confirmed manually. Matching uses question wording; no live AI or OCR is connected.
- Records, changes, declarations and approved snapshots persist through Supabase on the backend. Original source files use Supabase Storage. Backend configuration or connection failures appear with retry/setup guidance; no fixture data is substituted.
- Internal requests send `X-Demo-Role` for the selected owner, clerk or customer. This is simulated role authorization for a demo, not account authentication. Local direct API calls omit browser credentials. Protected hosted calls use the same-origin proxy with an HttpOnly demo session cookie.
- Internal source previews fetch the role-protected document file as a temporary blob URL. Public pack and selected evidence routes use their share token without a role header. The backend enforces which files the token can access.
- Pack links use the frontend origin and open in another browser against the same backend. With the default localhost addresses, they work only on the same computer while both servers are running. External access requires reachable frontend/API addresses and appropriate backend CORS configuration.
- Workspace help → Restore sample records calls the server's demo reset. It works only when the backend enables reset and affects the server demo workspace.
- The unused browser-only implementation has been removed. Any older browser-stored data is left untouched and is not imported. This application is not a certification or legal assurance system.

## Compare production loading with development

Keep the configured FastAPI backend running. In a separate frontend terminal:

```powershell
npm run build
npm start
```

Stop the development frontend with Ctrl+C first if it owns port 3000. Open http://127.0.0.1:3000 and time the first visit separately from three subsequent visits. Development mode compiles pages on demand; production mode serves the completed build. This does not eliminate Supabase network latency.

Overview loads profile, records and questionnaires together. Declarations and approved-pack history load independently with their own loading/error states. Explicit refresh keeps existing content visible while updating. A source editor can open before its file finishes downloading; confirmation stays disabled until the protected source file loads. No save is considered successful before the backend confirms it.

## Monthly records and archives

Use Reporting month in the header to select any calendar month. The period stays in `?period=YYYY-MM`; switching is guarded when there are unsaved edits. September 2026 remains the initial default. New months start missing, with blank declarations and Unknown policy statuses.

Records has Active and Archived views. Edit record changes its display name, assigned month and quantities without replacing its original source. Save changes leaves it unconfirmed. Confirm & calculate is explicit. Archive removes it from active calculations; Restore returns it unconfirmed. Existing approved packs retain their approved answers and selected original files.

Policies in Place uses four accessible status cards, a known-status count, saved attribution in MYT, and a single attachment section. Prior-month answers are reference only. Existing attached files remain visible even after moving or archiving, so owners can remove an archived attachment before saving.

## Hosted hackathon demo

Follow [the Render setup guide](../../docs/DEPLOY-RENDER.md). Hosted mode uses a shared demo password, an eight-hour signed HttpOnly session and a same-origin /api/backend proxy. Server keys never reach the browser. Both workspace and customer-pack access require the demo session; pack tokens still restrict evidence. Local mode stays unchanged. The frontend start script accepts Render hostname and port arguments.
