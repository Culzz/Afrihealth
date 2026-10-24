# AfriHealth — Deployment

## Live (R1.5): Vercel + Neon Postgres

**Production URL:** https://afrihealth-nine.vercel.app

- **Frontend:** static React build of `apps/web/dist` served by Vercel.
- **API:** `api/index.py` serverless function (`@vercel/python`) — FastAPI app
  with a `_sub`-style sys.path bootstrap; `vercel.json` uses the classic
  `builds` + `routes` schema (`/api/*` → the Python function, `/*` → statics).
- **Database:** Neon Postgres (pooled endpoint). 54 countries, 14,400
  observations, 1,404 country-year quality-flag rows, 162 forecasts, loaded
  from the committed artifacts via `python -m services.api.db.load_neon --url ...`.
- **Env var:** `DATABASE_URL` is set at project level in Vercel. When present
  the loader façade (`services/api/app/services/loader.py`) reads from Neon;
  otherwise it serves the same committed, sha256-versioned artifacts. Tests
  and local dev never require the DB.
- **Health/verify:** `GET /api/v1/health` (reports `db: "neon"` when connected),
  `GET /api/v1/db-status` for a one-shot connectivity diagnostic (reports each
  connection variant and the resolved IPv4).

Connection quirk, documented deliberately: Vercel's Python sandbox cuts the
classic PostgreSQL `SSLRequest`→TLS renegotiation and has no IPv6 egress, so
`services/api/db/session.py` resolves the pooled endpoint to IPv4 and passes
`sslnegotiation=direct&hostaddr=<ipv4>` (SNI + certificate verification still
use the hostname) as the **primary** path, falling back to a standard
`sslmode=require` connection. Note for serverless: connections are
**per-request and never cached** — a psycopg `Connection` used inside `with`
is closed on exit, so caching one would hand every subsequent caller a dead
handle (that regression shipped and was caught live on 2026-10-24).

## Release 1 runtime shape

One container serves both the FastAPI API and the built React bundle:

```
uvicorn (python 3.11)
├── /api/v1/*        → FastAPI routers
└── /*               → apps/web/dist (static, built in the Node stage)
```

**Historical note (Release 1):** R1 shipped *without a live Postgres layer* —
the API read only immutable, sha256-hashed artifacts
(`data/processed/panel_wide.csv` + `data/manifests/dataset_manifest.json`
+ `ml/registry/*`). R1.5 added Neon behind the same façade; the fallback
keeps every guarantee below true in artifact mode.

## Build & run

```bash
docker compose -f infra/docker-compose.yml up --build
# → http://localhost:8000        (React app)
# → http://localhost:8000/docs   (OpenAPI)
# → http://localhost:8000/api/v1/health
```

The image build isoffline-friendly: npm `ci`, pinned base images
(`python:3.11-slim`, `node:20-alpine`), no postinstall network fetches.

## Local (no Docker) — exact dev loop

```bash
# backend
.venv\Scripts\python -m uvicorn services.api.app.main:app --reload --port 8000

# frontend (Vite dev server proxies /api → :8000)
cd apps/web && npm run dev        # http://localhost:5173
```

CORS origins are env-driven: `CORS_ALLOWED_ORIGINS` (comma-separated,
defaults to the local Vite ports).

## CI

`.circleci/config.yml` runs on every push/PR (CircleCI connects to the same
GitHub repo):

1. **python-tests** — full pytest (`tests/` data-quality + feature-leakage,
   `services/api/tests/` API contract) on Python 3.11 inside `cimg/python`.
2. **web-build** — `npm ci` + `tsc && vite build` on Node 20 inside `cimg/node`
   with an npm cache keyed on `package-lock.json`.

## Environment contract

| Variable | Used by | Default |
| --- | --- | --- |
| `API_ENV` | container metadata | `development` |
| `CORS_ALLOWED_ORIGINS` | FastAPI CORS | local Vite ports |
| `VITE_API_BASE_URL` | React build | `''` (same-origin) |

## Registry update flow (production)

`ml/registry/*` artifacts are immutable; a model refresh means: rerun
`python -m ml.training.train` → `python -m ml.registry.register` → commit the
new `model_meta.json`/`forecasts.json`/`model_v1.pkl` → rebuild the image.
The model card's promotion gate (MAE must beat naive baseline) is checked in
the training memo before anything is registered.
