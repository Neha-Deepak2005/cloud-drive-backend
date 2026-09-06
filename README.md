# CloudDrive — Backend (FastAPI)

A production-shaped backend for a Google-Drive-style file storage & sharing service. Built with **FastAPI + SQLAlchemy + PostgreSQL (Supabase) + JWT auth + Google OAuth**, matching the project's technical specification.

Live API: [`https://cloud-drive-backend-5at6.onrender.com`](https://cloud-drive-backend-5at6.onrender.com) (interactive docs at `/docs`)
Frontend repo: [cloud-drive-frontend](https://github.com/Neha-Deepak2005/cloud-drive-frontend)
Live app: [`https://cloud-drive-frontend-umber.vercel.app`](https://cloud-drive-frontend-umber.vercel.app)

## Features

- Email/password auth (JWT access + HttpOnly-cookie refresh token) and Google OAuth
- Folder CRUD with nested hierarchy + breadcrumbs
- File upload/download with per-file version history
- Role-based sharing (Owner / Editor / Viewer), enforced server-side on every request
- Public shareable links with optional expiry and password protection
- Search, starred files, soft-delete Trash with restore and permanent delete
- Activity log
- Storage backend is pluggable: local disk (zero-setup dev) or Supabase Storage / S3 (production)
- Rate limiting, bcrypt password hashing, Pydantic input validation

## Tech stack

FastAPI · SQLAlchemy 2.0 · PostgreSQL (Supabase) or SQLite (dev) · Pydantic v2 · python-jose (JWT) · passlib/bcrypt · slowapi (rate limiting) · boto3 (S3-compatible storage)

## Project structure

```
app/
├── main.py            # FastAPI app, router wiring, CORS
├── core/               # config, security (JWT/bcrypt), rate limiter, auth dependency
├── db/                 # SQLAlchemy engine/session/base
├── models/              # ORM models (User, Folder, File, FileVersion, Share, LinkShare, Star, Activity)
├── schemas/             # Pydantic request/response schemas
├── routes/              # auth, folders, files, shares, search, trash, starred, activities
├── services/             storage.py — local-disk / Supabase-S3 storage abstraction
└── utils/                activity logging, per-user-correct serialization
```

## Running locally (zero setup)

Requires Python 3.11+.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults to SQLite + local disk storage - no external accounts needed
uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`). A `smoke_test.py` script is included — with the server running, `python smoke_test.py` exercises every core flow (auth, folders, upload/versioning, sharing, public links, trash) end-to-end.

## Running against Supabase (production-equivalent)

1. Create a free project at [supabase.com](https://supabase.com).
2. **Database**: Project Settings → Database → copy the connection string (URI) into `DATABASE_URL` in `.env`.
3. **Storage**: create a bucket (e.g. `drive-files`) under Storage. Project Settings → Storage → get the S3-compatible connection details and fill in `SUPABASE_S3_*` and set `STORAGE_DRIVER=supabase` in `.env`.
4. Restart the server — tables are created automatically on startup.

## Google OAuth (optional)

Create an OAuth Client ID in [Google Cloud Console](https://console.cloud.google.com/apis/credentials), add your **frontend's** URL + `/auth/google/callback` as an authorized redirect URI, and set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` in `.env`. See the comment in `.env.example` for why the redirect URI points at the frontend, not this backend.

## Deploying (Render)

A `Dockerfile` and `render.yaml` blueprint are included.

1. Push this repo to GitHub.
2. On [render.com](https://render.com): New → Blueprint → point at this repo (or New → Web Service → Docker, root = this repo).
3. Set the environment variables listed in `.env.example` (Supabase connection string, storage keys, `FRONTEND_URL` = your deployed frontend URL, Google OAuth if used).
4. Deploy. Render builds the `Dockerfile` and exposes the API on a `https://*.onrender.com` URL.

## Environment variables

See `.env.example` for the full list with explanations.

## Security notes

JWT access tokens are short-lived and kept client-side in memory only; the refresh token lives in an HttpOnly, SameSite cookie. All folder/file/share endpoints re-check ownership/role server-side on every request — the frontend UI never gates access on its own. Passwords are hashed with bcrypt. Public link passwords are hashed the same way. See `app/core/deps.py` for the permission model.
