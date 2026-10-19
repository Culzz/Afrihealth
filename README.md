# AfriHealth Risk Atlas 🌍

> **Work in progress.** Composite health-risk profiles for every African country —
> WHO / World Bank data → gradient-boosted models → SHAP-explained risk tiers →
> what-if policy simulator. **React + FastAPI web app** · research PDF · model card.

**The full build plan lives in [`PLAN.md`](PLAN.md).**

## Status

| Phase | State |
|---|---|
| 1 — Data foundation (World Bank/WHO fetchers, panel dataset) | 🔜 next |
| 2 — Risk index + tiering | planned |
| 3 — Modeling + Optuna + SHAP | planned |
| 4 — FastAPI (typed API) + React app (atlas map · deep-dive · what-if) | planned |
| 5 — Research PDF + model card | planned |
| 6 — Docker deploy + story | planned |

## Architecture

```
World Bank / WHO APIs  →  ML pipeline (index, tiers, XGBoost + SHAP)
                       →  artifacts/ (model + explainer + panel.csv)
                       →  FastAPI (Pydantic-typed /api endpoints + static React build)
                       →  React + Tailwind + Plotly.js  →  🌐 live on Render
```

## Stack

**ML:** Python · Pandas · NumPy · Scikit-learn · XGBoost · LightGBM · Optuna · SHAP
**API:** FastAPI · Pydantic · Uvicorn
**Frontend:** React (Vite) · Tailwind CSS · Plotly.js

## Quickstart

**Backend** (once Phase 1 lands — Python 3.11+):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m src.data.build_dataset   # fetch + build the country-year panel
uvicorn backend.app.main:app --reload   # http://localhost:8000/docs
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 → proxies /api to :8000
```

## Ethics framing

This project is **country-level decision support** for policy exploration —
not individual medical diagnosis. All model limitations are documented in the
model card (`reports/MODEL_CARD.md`) and served by the app's `/api/model-card`.
