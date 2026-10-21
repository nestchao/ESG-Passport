# ESG Passport frontend

Next.js frontend for the ESG Passport workspace. No separate service, Python runtime, API URL or AI key is required.

## Run

From this frontend folder:

```powershell
npm install
npm run dev
```

Open http://127.0.0.1:3000. For a production preview: run `npm run build`, then `npm start`.

## Check

- `npm test`
- `npm run typecheck`
- `npm run build`

## Local UI behavior

- Includes synthetic September bills, declarations and two questionnaires.
- All interactions use browser-side fixtures; no OCR, live AI, server API, authentication or real sharing is provided.
- Uploaded files stay local. Enter their quantities manually; automatic extraction is not connected, so no extraction action is exposed.
- Browser storage retains edits and preview snapshots on this browser and origin. If storage is unavailable, the demo lasts for the current page session.
- Demo links work only in the same browser and origin. They are not secure or externally accessible customer links.
- The role switch demonstrates Owner, clerk and customer screens. It is not an access-control boundary.
- Use Workspace help → Restore sample records to start over.
- Browser arithmetic illustrates the UI; this build is not a reporting or compliance system.
