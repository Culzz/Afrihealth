# AfriHealth — Deployment

## Release 1 runtime shape

One container serves both the FastAPI API and the built React bundle:

```
uvicorn (python 3.11)
├── /api/v1/*        → FastAPI routers
└── /*               → apps/web/dist (static, built in the Node stage)
```

**Deviation from the original plan, documented deliberately:** Release 1 ships
*without a live Postgres layer*. The API reads only immutable, sha256-hashed
artifacts (`data/processed/panel_wide.csv` + `data/manifests/dataset_manifest.json`
+ `ml/registry/*`). Rationale: provenance and audit-first — every value the
service returns is version-pinned. The DB-backed ingestion cadence (scheduled
refresh, per-source lake tables, drift alarms) is the first item of Release 1.5.

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

`.github/workflows/ci.yml` runs on every push/PR:

1. **python-tests** — full pytest (`tests/` data-quality + feature-leakage,
   `services/api/tests/` API contract) on Python 3.11.
2. **web-build** — `tsc && vite build` on Node 20 with npm cache.

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
