# AfriHealth 🌍

> **AI-powered African population health intelligence — LIVE**
> https://afrihealth-nine.vercel.app
> Reproducible, geospatial platform that integrates WHO / World Bank evidence,
> validates forecasting models against temporal baselines, explains predictions
> with SHAP, quantifies uncertainty, and exposes the evidence behind regional
> risk assessments through a production web app.

**Start here:** [`PLAN.md`](PLAN.md) — platform blueprint, releases, and build calendar.

## Week-1 audit in one line

Under-five mortality verified as a **STRONG** target — 1,350 observations, 54 countries,
96.2% of possible country-year cells, data through 2024, with **9/9 World Bank driver
series usable**. WHO GHO returned 502 on every query during the audit, confirming the
architecture invariant: **v1 ships on World Bank alone.**

## Week-2 build in one line

The audit's verdicts are now a **versioned dataset**: `ml/ingestion/build_panel.py`
assembles `panel_long.csv` (tidy observations with source, unit, value status) and
`panel_wide.csv` (one row per country-year with `q_` quality flags — driver
coverage, target-missing, sparse-workforce flags). Seven unit tests guard the
validation suite; the build writes a sha256 hashed manifest and refuses to pass
if any blocking check fails.

## Week-3 build in one line

The Week-3 baseline suite nailed the yardstick: naive_last **MAE 4.42** over 648
rolling-origin country-year evaluations. Week 4 then beat it — tuned LightGBM
**MAE 3.49 (−31%)** on the locked 2021–24 holdout, and the ablation answered the
research question: history-only 3.78 → full drivers 3.49, so the driver series
carry real signal, not decoration. Week 5 registered `u5m-lgb-v1` with
uncertainty-aware forecasts for 2025–27 and per-country SHAP; Week 6 exposed it
as a typed FastAPI; Week 7 gave it a React face; Week 8 packaged it in Docker
with CI.

## Status overview

| Phase | State |
|---|---|
| Blueprint + monorepo scaffold | ✅ done |
| Wk 1 — Data audit (WHO/WB U5M + drivers) | ✅ done — [`data/manifests/audit_report.md`](data/manifests/audit_report.md) |
| Wk 2 — Ingestion + validation pipeline | ✅ done — `panel_long.csv` + `panel_wide.csv` (1,404 country-years), manifest + gate report |
| Wk 3 — Baselines (the yardstick) | ✅ done — naive_last MAE 4.42, drift 4.64 over 648 rolling-origin evals |
| Wk 4 — Model training + ablation | ✅ done — LightGBM **MAE 3.49 vs naive 5.06 (−31%)** on locked 2021–24 holdout |
| Wk 5 — Registry + SHAP + uncertainty | ✅ done — `u5m-lgb-v1`: 162 forecasts (2025–27 × 54 countries), empirical 90% intervals, exceedance probs, SHAP |
| Wk 6 — FastAPI (typed /api/v1) | ✅ done — 9 contract tests green |
| Wk 7 — React atlas + country deep-dive | ✅ done — Plotly choropleth, forecast bands, SHAP bars |
| Wk 8 — Deploy + hardening | ✅ done — single-container Docker, compose, CircleCI CI |
| **R1.5 — Neon Postgres + Vercel** | ✅ shipped — live DB-backed API verified end-to-end (health/atlas/series/forecasts all 200 on `db:neon`) |
| **UI v2 — editorial redesign** | ✅ shipped — vintage-paper + glass design system, photo landing page, mobile-first (see `apps/web/README.md`) |

## Live deployment

- **Web + API:** https://afrihealth-nine.vercel.app
- **Database:** Neon Postgres (`ep-odd-mud-b75f15hv-pooler`) — 54 countries, 14,400
  observations, 1,404 country-year quality-flag rows, 162 forecasts, loaded via
  `services/api/db/load_neon.py`
- The API reads **Neon when `DATABASE_URL` is set**, and falls back to the committed,
  sha256-versioned artifacts everywhere else — tests and local dev never need a DB.
- Deployment quirk (documented in `services/api/db/session.py`): Vercel's Python
  sandbox cuts the classic PostgreSQL SSL-upgrade handshake and has no IPv6 egress,
  so the session pins Neon's proxy to an IPv4 address and negotiates TLS directly
  (`sslnegotiation=direct`); verified `SELECT 1` end-to-end.

## The three-layer framework

1. **Observed burden** — reported/modelled data with source quality flags
2. **Predicted risk** — validated forecasts with intervals and explanations
3. **Health-system vulnerability** — transparent, sensitivity-tested composite (R2)

No opaque universal risk score. Every displayed number is traceable to
source → dataset version → model version.

## Frontend design, in one paragraph

The UI is an editorial, vintage-paper experience: a warm off-white canvas with
subtle grain, **Fraunces** serif display type over **Instrument Sans** body text,
deep-green/terracotta accents, and frosted **iOS-style glassmorphism** panels.
A photo-led landing page opens the story (Wikimedia Commons imagery, CC BY-SA,
credited in the footer), and the map/forecast pages keep the data-first density.
Icons are Lucide; Plotly (~4 MB) is loaded **lazily** only on pages that draw
charts, so the landing page ships ~64 KB gzipped JS and paints fast. Layout is
mobile-first (single column → 2/3-col grids) with fluid `clamp()` typography.
See [`apps/web/README.md`](apps/web/README.md) for the full system.

## Stack as actually shipped

React + TypeScript + Vite (Plotly.js, lazily loaded) · Fraunces + Instrument Sans ·
Lucide icons · FastAPI + Pydantic · Neon Postgres
(psycopg 3) · scikit-learn · XGBoost · LightGBM · Optuna · SHAP · ReportLab ·
Vercel · Docker · CircleCI.

Documented deviations from the original blueprint: Tailwind → plain-CSS design
system (deterministic builds); MapLibre → Plotly's built-in African choropleth
(no tile dependency). The database is Neon Postgres served from Vercel — the
original PostGIS single-container plan became a serverless stack.

## Quickstart

```bash
# local dev loop (artifact mode, no DB needed)
python -m uvicorn services.api.app.main:app --reload --port 8000
cd apps/web && npm install && npm run dev   # http://localhost:5173

# single-container production (API + built web)
docker compose -f infra/docker-compose.yml up --build

# refresh Neon content from artifacts (once per dataset/model version)
python -m services.api.db.load_neon --url "postgresql://...pooler...neon.tech/neondb?sslmode=require"

# deploy to Vercel (project already linked)
vercel deploy --prod --yes --force
```

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
