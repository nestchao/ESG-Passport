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

## Password-free synthetic public demo

With protected demo access enabled on Render, unauthenticated visitors opening
`/` without a query are redirected to **`/demo`**, a separate Next.js client
page. Visitors can also open `/demo` directly without a password, or choose
"Open the public synthetic demo" from the `/login` page. Protected staff
continue using `/login` to access the existing, real workspace.

The public route includes three locally bundled, generated test images from
`src/ai/synthetic_dataset` (electricity, water, waste). The page simulates
OCR review, SEDG questionnaire matching and owner/customer Passport preview
**entirely in volatile browser state**, with no HTTP calls, writes, data
uploads, external LLM usage, real sharing URLs or storage access. OCR values
are sample labels, not fresh AI processing. Waste diversion is merely an
unverified suggestion; the displayed electricity emission factor is explicitly
illustrative. Browser refresh resets edits, and "Reset demo" clears them.

`accessGate` explicitly allows only `/demo` and the three named `/demo-assets`
images. All `/api/backend/*` routes and actual customer share links remain
protected by the existing session and role checks; Supabase credentials are
never provided to the public page. Do **not** remove DEMO_PASSWORD or disable
DEMO_ACCESS_ENABLED in Render. The public demo is not a replacement for real
production authentication, audit, or verified ESG claims.

## Password-free full ESG workspace (public synthetic sandbox)

`PUBLIC_WORKSPACE_ENABLED=true` is applied to both services from the Render Blueprint
environment group. Anonymous visitors to `/` see the **original complete ESG Passport
UI**, not a separate login/demo mockup. The frontend proxies their existing
`/api/backend/*` calls to `/sandbox/*` on the backend, using only its own
server-side shared key. The backend mounts a separate, generated **in-memory
SQLite database and synthetic-only in-memory evidence storage**. This code
path never opens Supabase connections or files and resets on restart; it is
shared among anonymous visitors. Don't enter personal information: the
fictional workspace is communal. Public uploads accept only three SHA-256-verified synthetic PNG fixtures with a matching category/month and a 512 KB cap. Other uploads are rejected.

The production Postgres/Supabase services and authorized real customer shares
remain behind the original signed staff session at `/login`; the real backend
always requires the private server-to-server key. Removing `DEMO_PASSWORD` is
not necessary or recommended. The sandbox displays the normal site and does
not make actual ESG claims. The older `/demo` static experience redirects to
`/` when this option is enabled.

## Local browser OCR scanner (public `/ocr`)

From **Records → Add records → Open Live OCR Scanner**, visitors can recognize
arbitrary PNG, JPEG or PDFs (up to 10 MB, at most three PDF pages) **in their
own browser**. Tesseract.js loads an English WebAssembly OCR model on demand;
PDF.js reads selectable PDF text directly or rasterizes scanned pages before
client-side OCR. The original file is shown in a local object URL and is
never sent to Supabase or the communal synthetic backend by this scanner.
Language/engine data may be downloaded by the visitor's browser.

The scanner conservatively proposes document supplier, dates, quantity and
units for electricity, water, diesel, petrol and waste. It deliberately leaves
unverified waste transfer classification unresolved, exposes the complete
recognized text for correction, and requires explicit review before a
**local JSON export**. No client scan is automatically confirmed or counted
as verified ESG disclosure. The export does **not** create a backend record;
original protected staff uploads retain the existing server-side RapidOCR
save/review process. Public synthetic records still accept only the three
SHA-256-verified sample PNGs, using their precomputed fixture extraction.

The anonymous access gate allows only `/ocr` and the bundled PDF worker
asset required for scanning, in addition to previously approved public
paths; protected real backend and customer-sharing routes are unchanged.
