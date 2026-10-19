# AfriHealth 🌍

> **AI-powered African population health intelligence**
> Reproducible, geospatial platform that integrates WHO / World Bank evidence,
> validates forecasting models against temporal baselines, explains predictions
> with SHAP, quantifies uncertainty, and exposes the evidence behind regional
> risk assessments through a production web app.

**Start here:** [`PLAN.md`](PLAN.md) — platform blueprint, releases, and build calendar.

## Status

| Phase | State |
|---|---|
| Blueprint + monorepo scaffold | ✅ done |
| Wk 1 — Data audit (WHO/WB U5M + drivers) | 🔜 next |
| Wk 2 — Ingestion + validation pipeline | planned |
| Wk 3–5 — Forecasting research core | planned |
| Wk 6 — FastAPI (typed /api/v1) | planned |
| Wk 7 — React atlas + forecast + explainability | planned |
| Wk 8 — Deploy + hardening | planned |

## The three-layer framework

1. **Observed burden** — reported/modelled data with source quality flags
2. **Predicted risk** — validated forecasts with intervals and explanations
3. **Health-system vulnerability** — transparent, sensitivity-tested composite (R2)

No opaque universal risk score. Every displayed number is traceable to
source → dataset version → model version.

## Stack (Release 1)

React + TypeScript + Vite + Tailwind · MapLibre GL JS · Plotly.js ·
FastAPI · Pydantic · PostgreSQL + PostGIS · Alembic ·
scikit-learn · XGBoost · LightGBM · Optuna · SHAP · Docker · GitHub Actions

## Quickstart (once Week 1 scaffolding lands)

```bash
docker compose -f infra/docker-compose.yml up   # web + api + postgres/postgis
```

Modern detail: `services/api` docs at `/api/docs`; web at the frontend dev URL.

## Documentation

- [`docs/SRS.md`](docs/SRS.md) — product + research scope
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system + deployment
- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — entities, provenance rules, indicators
- [`docs/MODEL_CARD.md`](docs/MODEL_CARD.md) — responsible-AI record
- [`docs/SECURITY.md`](docs/SECURITY.md) — safeguards + security design
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — operations runbook

## Ethics framing

Population-level decision support for public-health research and policy exploration —
**not** individual diagnosis, outbreak surveillance, or clinical guidance. All ten
safeguards in [`PLAN.md`](PLAN.md) §11 are enforced in product behaviour.
