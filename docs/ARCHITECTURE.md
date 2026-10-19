# AfriHealth — Architecture

Status: v0.1 (Wk 1)

## System diagram (R1 target)

```
World Bank / WHO GHO APIs
        │  (scheduled pulls → immutable snapshots + manifests)
        ▼
  ml/ingestion ─ ml/validation ─ ml/features
        │                (schema, unit, missingness checks)
        ▼
PostgreSQL (+PostGIS)  ◄──── Alembic migrations
        │
        ▼
services/api (FastAPI + Pydantic)  ◄── reads registered artifacts from ml/registry
        │   /api/v1: catalogue · atlas · series · forecast · explain · model card · exports
        ▼
apps/web (React + TS, Vite)  → MapLibre atlas · Plotly charts · uncertainty UI
```

## Invariants

- **ML code never imports services/** and vice versa; they meet only at artifacts (models + panel data) and the DB.
- Forecasts are versioned against (dataset_version, model_version) — no orphan predictions.
- Missing data is flagged, never zero-filled; imputation labelled with method + test.
- Geography joins on ISO codes only.

## Repository conventions

- Monorepo: `apps/web`, `services/api`, `ml/`, `pipelines/`, `research/`, `infra/`, `docs/`
- Modular monolith (api + separate worker when Celery lands in R2) — no microservices fleet
- Python: ruff + pytest + mypy-lite expectations; Node: eslint + vitest (+ Playwright later)
- CI gates: lint, tests, docker build

## Deployment (R1)

- **Frontend:** static build on CDN host (e.g., Vercel/Render/Cloudflare) — decided Wk 8 against pricing + fit
- **API:** containerized FastAPI (single service; bounded synchronous jobs)
- **DB:** managed PostgreSQL with PostGIS + backups (e.g., Neon/Render) — decided Wk 8
- **Artifacts:** small committed registry snapshots; heavier artifacts → object storage R2
- Secrets via environment only; CORS pinned to frontend origin

## Risk register (engineering)

| Risk | Mitigation |
|---|---|
| React depth vs. 8-wk clock | API contract frozen Wk 6; pages data-viz heavy, patterns repeat |
| PostGIS overhead unnecessary for R1 country-level | Enable extension day 1 but only use it if/if subnational arrives |
| Sparse WHO series breaks plan | Wk-1 audit gates the feature set; World Bank-first fallback (documented) |
| Optuna sycophancy (tuning against test data) | Optuna only inside rolling-origin CV; test year untouched until final |
