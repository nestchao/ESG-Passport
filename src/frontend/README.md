# ESG Passport frontend

Next.js workspace connected to the Python API and Supabase database/storage. The UI never falls back to browser fixtures or reads/writes the previous browser demo database.

## Run

Start and configure the backend first using its README. From this frontend folder:

```powershell
if (!(Test-Path ../../.env)) { Copy-Item ../../.env.example ../../.env }
npm install
npm run dev
```

Open http://127.0.0.1:3000. `NEXT_PUBLIC_API_URL` defaults to `http://127.0.0.1:8000`. Change it in the repository-root `.env` if necessary and restart the frontend; Next.js embeds public variables at build time. The backend CORS origins must include the frontend origin. Use Node.js 22 or newer. The Node-only configuration reads the shared root file but exports only `NEXT_PUBLIC_API_URL` to the browser; it never exports Supabase/database secrets or other values from that file. Do not create a frontend `.env.local`. Shell variables take precedence.

For a production preview run `npm run build`, then `npm start`.

## Check

- `npm test`
- `npm run typecheck`
- `npm run build`

## Behavior and access

- The backend provides fictional September 2026 seed records. Quantities from newly uploaded bills are entered and confirmed manually. Matching uses question wording; no live AI or OCR is connected.
- Records, changes, declarations and approved snapshots persist through Supabase on the backend. Original source files use Supabase Storage. Backend configuration or connection failures appear with retry/setup guidance; no fixture data is substituted.
- Internal requests send `X-Demo-Role` for the selected owner, clerk or customer. This is simulated role authorization for a demo, not account authentication. No browser credentials are sent.
- Internal source previews fetch the role-protected document file as a temporary blob URL. Public pack and selected evidence routes use their share token without a role header. The backend enforces which files the token can access.
- Pack links use the frontend origin and open in another browser against the same backend. With the default localhost addresses, they work only on the same computer while both servers are running. External access requires reachable frontend/API addresses and appropriate backend CORS configuration.
- Workspace help → Restore sample records calls the server's demo reset. It works only when the backend enables reset and affects the server demo workspace.
- The previous browser-only demo data is left untouched and unused. This application is not a certification or legal assurance system.
