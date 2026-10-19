# AfriHealth Risk Atlas — Build Plan

> ML-powered atlas that scores every African country on a composite health-risk index,
> tiers countries (Low / Elevated / High / Critical), explains **why** each country sits
> in its tier (SHAP), and simulates policy what-ifs — shipped as a **React + FastAPI
> web app**, a research PDF, and a model card.

**Status:** planned · **Owner:** you + AI pairing · **Window:** 4–6 weeks

---

## 1. Decisions locked

| Decision | Choice | Why |
|---|---|---|
| Prediction target | **Composite Health Risk Index + tiers** | Fits "Risk Atlas"; richer story than a single outcome |
| Data granularity | **Country-year panel, 2000–2023** (~54 countries ≈ 1,200+ rows) | 54 rows alone can't train XGBoost; panel gives 20× data and enables what-ifs |
| Validation | **Temporal split** (train ≤2018, val 2019–2020, test 2021–2023) + leave-one-region-out sanity | Random KFold on panel data leaks country effects; temporal is honest |
| Index sources | Burden indicators only (mortality, disease prevalence) | Keeps drivers (capacity levers) out of the target — no target leakage |
| **App stack** | **React (Vite + Tailwind) frontend · FastAPI backend** | Real web app, strongest recruiter signal; API contract separates ML from UI |
| Deployment | **Single Docker container** (FastAPI serves built React bundle) → Render free tier | One URL, no CORS pain; two-service split is a documented stretch goal |
| Environment | venv + pip (backend) · npm (frontend) | Simple, zero extra tooling |

---

## 2. Data spec

### Source A — World Bank Open Data API (primary, free, no key)
Raw pulls cached to `data/raw/` as CSV. Code list (indicator codes verified at first fetch, snapshotted):

**Burden outcomes → build the Risk Index (never used as features):**
- `SH.DYN.MORT` — under-5 mortality per 1,000
- `SH.STA.MMRT` — maternal mortality per 100k
- `SH.STA.WAST.ZS` — wasting prevalence
- `SH.STA.STNT.ZS` — stunting prevalence
- `SH.TBS.INCD` — TB incidence per 100k
- `SH.DYN.AIDS.ZS` — HIV prevalence
- `SH.MLR.INCD.P3` — malaria incidence per 1,000 at risk

**Capacity drivers → model features (the policy levers):**
- `NY.GDP.PCAP.CD` — GDP per capita
- `SH.XPD.CHEX.GD.ZS` — health expenditure (% GDP)
- `SH.MED.PHYS.ZS` — physicians per 1,000
- `SH.MED.NUMW.P3` — nurses & midwives per 1,000
- `SH.IMM.IDPT` — DPT immunization %
- `SH.IMM.MEAS` — measles immunization %
- `SH.STA.BASS.ZS` — basic sanitation %
- `SH.H2O.SMDW` — safely managed drinking water %
- `SP.URB.TOTL.IN.ZS` — urbanization %

### Source B — WHO GHO API (secondary, enhances drivers)
- `UHC_INDEX_REPORTED` — UHC service coverage index
- Optional extras if data quality is good enough; **v1 must ship on World Bank alone** (de-risking).

### Missing-data policy (documented in the research PDF)
1. Per-country time interpolation for small gaps (flagged)
2. Drop country-years with < 50% driver coverage
3. Missingness map shipped in EDA — this is a *feature* of the story, not an embarrassment

---

## 3. Risk index & tiering

- **Index v1:** min-max normalize each burden indicator (0–100, higher = worse) → weighted mean.
  Weights: equal-weight baseline + sensitivity analysis (PC1-weighted variant reported in appendix).
- **Tiers:** KMeans (k=4) on the index distribution, sanity-checked against quartiles; silhouette score reported. Cluster profiles named Low / Elevated / High / Critical.
- **Neighborhood sanity check:** e.g., Niger vs. Nigeria, Botswana (high HIV burden but strong system) — the atlas must *not* be a GDP map in disguise. SHAP output will prove this.

---

## 4. Modeling plan

| Step | Detail |
|---|---|
| Baselines | Majority-tier + logistic regression (with standardization) |
| Main models | LightGBM + XGBoost, multiclass on tiers **and** regression on the index (regression powers the what-if slider) |
| Tuning | Optuna, ~75 trials, expanding-window time CV (never cross-year random split) |
| Metrics | Macro-F1, per-tier precision/recall, confusion matrix; MAE for regression |
| Explainability | SHAP: global importances + per-country-year waterfall (country deep-dive page) |
| Fairness slice | Error rates by UN sub-region (North vs. West vs. East/Central/Southern Africa) — honest table in the PDF |

**Deliverable gate:** a short decision memo choosing the final model with evidence.
**Serving artifact:** trained model + SHAP TreeExplainer serialized to `artifacts/` — loaded once at app startup.

---

## 5. Web app architecture (React + FastAPI)

```
┌─────────────────────────────  single Docker container (prod)  ─────────────┐
│  FastAPI :8000                                                             │
│  ├── /api/*          Pydantic-typed JSON                                   │
│  ├── /assets/*       React build served as static files (SPA)              │
│  └── ML layer        loads artifacts/ at startup (model + explainer+panel) │
└────────────────────────────────────────────────────────────────────────────┘
```

### API contract (locked before frontend work starts)

| Endpoint | Method | Returns |
|---|---|---|
| `/api/health` | GET | `{status, model_version, data_through}` |
| `/api/atlas/{year}` | GET | `[{iso3, country, region, risk_index, tier, top_drivers:[{feature, value, shap}]}]` |
| `/api/countries/{iso3}` | GET | profile: `series[{year, index, tier}]`, current drivers w/ SHAP, stats |
| `/api/whatif` | POST `{iso3, year, deltas: {"SH.IMM.IDPT": +10}}` | `{index_before, index_after, tier_before, tier_after, driver_delta:[{feature, shap}]}` |
| `/api/model-card` | GET | model card JSON (rendered beautifully on the Methodology page) |

- **Pydantic response models for every endpoint** — this is the recruiter-visible rigor
- Dev mode: Vite dev server proxies `/api` → `localhost:8000`; prod: same origin, zero CORS issues

### Frontend pages (React Router)

1. **🗺️ Atlas** — Plotly choropleth by tier, year slider (2000–2023), tooltips: index + top 3 drivers; trend strip
2. **🏳️ Country Deep-Dive** — profile card, 20-year risk trajectory, SHAP waterfall of current drivers
3. **🔮 What-If Simulator** — policy sliders (DPT +10pp, sanitation +10pp…) → predicted tier shift + SHAP delta. Framed as a *policy sandbox*, not diagnosis
4. **📚 Methodology** — model card, data sources, limitations, disclaimers (country-level decision support, not individual medical advice)

UI discipline: Tailwind + one accent palette per risk tier; skeleton loaders while API resolves; fully responsive (recruiters open links on phones).

### Deployment
- **Dockerfile (multi-stage):** `node:20` builds `frontend/dist` → copied into `python:3.11-slim` image → FastAPI `StaticFiles` mounts it → one service on Render free tier
- Dev runs as two terminals (`uvicorn` + `vite`); prod is one URL
- Frontend `API_BASE` via env var so the same bundle can point anywhere

---

## 6. Research PDF + model card (ReportLab, generated by script)

- **Paper:** Abstract → Intro (why Africa-wide, why decision support) → Data & Methods → Results (figures from matplotlib) → SHAP findings → Fairness analysis → Limitations → Future work
- **Model card:** intended use / out-of-scope, data provenance, metrics, fairness notes, limitations, update cadence — served as JSON by the API *and* as `reports/MODEL_CARD.md`
- Built via `reports/build_pdf.py` → reproducible artifact, not a one-off Word doc

---

## 7. Week-by-week

| Week | Milestone | Gate |
|---|---|---|
| 1 | Scaffold; WB fetcher + panel builder; missingness report; EDA starts | `python -m src.data.build_dataset` reproduces `panel.csv` |
| 2 | Risk index + tiers; baselines; first XGBoost with temporal eval | Index passes neighborhood sanity check |
| 3 | Optuna tuning; LightGBM vs XGBoost; SHAP; decision memo; artifacts serialized | Final model picked; API contract frozen |
| 4 | FastAPI (all 5 endpoints, Pydantic models, tests) + React scaffold + **Atlas map page live** | Swagger UI passes manual checks; map renders real data |
| 5 | Deep-dive + what-if + methodology pages; UI polish; ReportLab PDF + model card | All 4 pages working; PDF generated |
| 6 | Dockerize → deploy to Render; buffer; README + demo GIF + story post | LIVE URL in README |

---

## 8. Repo layout

```
afrihealth-risk-atlas/
├── backend/
│   └── app/
│       ├── main.py            # FastAPI entrypoint + static mount
│       ├── core/config.py     # settings, artifact paths
│       ├── ml/predictor.py    # loads model + explainer once
│       └── routers/           # atlas.py, countries.py, whatif.py, model_card.py
├── frontend/
│   ├── src/
│   │   ├── pages/             # Atlas.jsx, Country.jsx, WhatIf.jsx, Methodology.jsx
│   │   ├── components/        # ChoroplethMap, TrendChart, Waterfall, RiskBadge, TierLegend
│   │   └── api/client.js      # fetch wrapper + types
│   ├── index.html, vite.config.js, tailwind.config.js
├── src/                       # ML pipeline (pure Python, no HTTP)
│   ├── data/                  # fetch_worldbank.py, build_dataset.py
│   ├── features/              # build_index.py (index + tiers)
│   ├── models/                # train.py, tune_optuna.py, explain_shap.py
│   └── visualization/         # charts.py (figures for PDF)
├── artifacts/                 # trained model, SHAP explainer, panel.csv (committed — small)
├── data/                      # raw/ (gitignored) + processed/
├── notebooks/                 # 01_eda.ipynb, 02_modeling.ipynb
├── reports/                   # figures/, build_pdf.py, MODEL_CARD.md
├── tests/                     # index construction, dataset builder, API responses
├── Dockerfile
├── requirements.txt           # backend + pipeline deps
├── PLAN.md
└── README.md
```

---

## 9. Definition of done

- [ ] One command reproduces the dataset from cached raw pulls
- [ ] Temporal validation only — zero leakage, verified with a test
- [ ] API runs offline from committed artifacts; Pydantic-typed responses
- [ ] React app: all 4 pages, responsive, skeleton loaders
- [ ] Dockerized, deployed, live demo URL + README demo GIF
- [ ] pytest green on index + dataset builder + API
- [ ] Honest Limitations section in both PDF and model card
- [ ] Model card complete (intended use, out-of-scope, metrics, fairness)

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| WHO API flaky / sparse | World Bank-first design; v1 ships on WB alone |
| Indicator code changes | Cache raw JSON/CSV; pin snapshot; fetcher validates codes |
| Overfitting on small panel | Temporal CV, small model capacity, no metric overclaiming |
| "It's just a GDP map" critique | SHAP evidence that capacity levers ≠ wealth alone; neighborhood sanity checks |
| What-if scope creep | Locked spec: tier-shift prediction from fixed feature deltas, no causal claims |
| React learning curve mid-project | API contract frozen in week 3; pages are data-viz heavy, not CRUD — Tailwind + Plotly.js patterns repeat across pages |
| Two-service deploy complexity | Single-container default; service split documented as stretch |
