# RecipeLens: one Railway service

The Railway service builds the Flutter web client and Flask backend together.
One HTTPS origin serves the UI, REST API, Socket.IO, and local OCR. Vercel is
not required. SQLite and permanent uploads share a volume mounted at `/data`.

## Configuration

Source: `SaiKiran6305/kitchenowl-recipelens`, deployment branch containing the
Sprint 2 changes. Repository root: `/`. Dockerfile:
`deploy/railway/Dockerfile`. Leave the custom start command empty: Docker's CMD
runs `deploy/railway/start.sh`. Use the existing health URL:
`/api/health/8M4F88S8ooi4sMbLBfkkV7ctWwgibW6V` with a 300-second startup timeout.
Use one replica. The image pins Flutter to the repository's SDK submodule
revision, installs locked dependencies, and includes Tesseract English and Poppler.

Set these variables through Railway, never in Git:

| Variable | Value |
| --- | --- |
| `JWT_SECRET_KEY` | Generated random secret of at least 32 characters; keep stable |
| `PORT` | `8080` |
| `STORAGE_PATH` | `/data` |
| `FRONT_URL` | Generated Railway HTTPS origin |
| `OPEN_REGISTRATION` | `False` |
| `RECIPELENS_MODEL` | Empty, for local-only extraction |

Attach a volume at `/data` **before** starting. The startup script refuses to run
without the mount or a valid JWT secret. It runs database migrations after the
volume is mounted, then starts uWSGI's HTTP listener on Railway's assigned port.
Flutter files are served from `/var/www/web/kitchenowl` with a client-route
fallback. The Flutter API uses the same origin, so no backend URL build variable
or cross-origin API proxy is needed.

Keep the default one-process setup: SQLite and in-process Socket.IO sessions
are not configured for multiple replicas. Back up the volume before changing
the application database schema or deployment branch.

## Billing

Use existing trial credits unless a paid plan and budget are explicitly approved.
Trial expiry can stop the app near the report deadline; check the actual
remaining time and credit in Railway before the demo. No subscription upgrade
is performed by these files. If switching to paid hosting later, set an approved
Compute hard usage limit in Workspace Usage; Agent usage limits and email alerts
do not cap application compute. A workspace cap also affects unrelated services.

## Demo

1. Open the Railway HTTPS domain. Complete initial administrator onboarding
   before sharing the URL; create a household and sign in.
2. In Postman, set `base_url` to the origin and use the authenticated user's
   bearer token and household ID.
3. POST a clear printed PNG/JPEG or single-page PDF as multipart `file` to
   `/api/household/<id>/recipe/scan`: expect HTTP 200 with OCR text.
4. POST the same page to `/api/household/<id>/recipe/scan/draft`: expect fields,
   validation status, and review warnings. Nothing is saved automatically.
5. Upload an unsupported file: expect HTTP 400. Remove authentication: expect
   HTTP 401. Confirm the recipe list is unchanged after scan requests.
6. Restart the service and verify users, households, recipes, and saved images
   remain available from the volume.

Sprint 1/2 do not include a Flutter OCR upload screen. The web client provides
KitchenOwl account/household access; use Postman for the new OCR endpoints.
The live deployment is complete only after Railway reports SUCCESS and the
health, frontend, login, OCR, validation, and persistence checks pass.
