# AfriHealth — Platform Blueprint (v2)

> **AI-powered African population health intelligence and early-warning platform.**
> Not a dashboard: a reproducible, geospatial health-intelligence system that integrates
> public health data, evaluates forecasting models against temporal baselines, explains
> predictions, quantifies uncertainty, and exposes the evidence behind regional risk
> assessments through a production web application.

**Status:** blueprint written, Phase 01 (research & data audit) next
**Research core:** data reliability + cross-region forecasting + explainable early warnings
**Product layer:** Scenario Lab + Research Copilot, built on top of the validated core

---

## 1. Locked decisions

| Decision | Choice |
|---|---|
| Primary focus | **Balanced platform** — atlas + forecasting + explainability together |
| Lead outcome | **Under-five mortality** (data audit decides if a second outcome — e.g., malaria — joins it) |
| Geographic scope | **All-Africa, country-level first**; subnational only after validation |
| Success bar | **Both** — defensible research evaluation AND production-grade product |
| Release 1 timeline | **~8 weeks** |
| Frontend | React + TypeScript + Vite + Tailwind (no Streamlit) |
| Backend | FastAPI + Pydantic, PostgreSQL (+PostGIS), Alembic migrations |
| ML | scikit-learn, XGBoost, LightGBM, Optuna, SHAP · temporal validation only |
| Deploy | Docker, managed Postgres, static frontend on CDN host |

## 2. Six capabilities (the product spine)

1. **Health Risk Atlas** — outcomes and risk factors across African countries; subnational where data supports it (later)
2. **Predictive Health Intelligence** — forecast under-5 mortality; probability of exceeding defined risk thresholds
3. **Risk Driver Discovery** — SHAP-explained drivers, regional comparison, emerging patterns
4. **Intervention Scenario Lab** — validated hypothetical-condition exploration, clearly labelled (Release 2)
5. **Early-Warning Intelligence** — unusual-change detection, threshold alerts, uncertainty framing (Release 2)
6. **Evidence & Research Copilot** — grounded Q&A over the platform's own verified data, with citations (Release 3)

## 3. The three-layer intelligence framework (the research identity)

**Layer 1 — Observed health burden:** what reported/modelled data says, with source quality and coverage flags.
**Layer 2 — Predicted future risk:** validated forecasts with intervals + threshold-exceedance probabilities + SHAP explanations.
**Layer 3 — Health-system vulnerability:** where high burden overlaps weak service capacity — a transparent, sensitivity-tested composite, **never** an opaque universal score.

No single "African health risk score." Outcome-specific models, an explicit data-confidence layer, and an emerging-risk monitor instead. Low data quality is displayed, not silently smoothed away.

### Research questions (drive the evaluation plan)

1. Do ML models beat simple forecasting baselines (naive, trend) on U5M?
2. Do socioeconomic + health-system + environmental indicators improve forecasts over health-history-only models?
3. How does performance vary with country-level data availability?
4. Do uncertainty + data-quality indicators reduce overconfidence in rankings?
5. How stable are rankings under alternative normalizations and weights?
6. Can every displayed number be traced to source, version, and method?

## 4. Release plan

### Release 1 — Research-ready MVP (~8 weeks) ← current target
WHO/WB ingestion for U5M + drivers · data catalogue · interactive Africa map (MapLibre) · historical trends & comparisons · 1–2 properly validated forecast models · basic explainability + uncertainty · PDF/CSV exports + provenance · tests · live deployment · model card.

### Release 2 — Predictive intelligence — ✅ SHIPPED (2026-10)
Vulnerability index with sensitivity analysis ✅ (deterministic percentile composite `vuln-v1`: declared weights, per-component data vintages, jackknife leave-one-out deltas shipped inside the artifact · no imputation · 49/54 countries complete) · threshold alerting ✅ (deterministic watchlist from registered exceedance probabilities, "decision support, not surveillance" framing) · alerts ✅ + comparisons ✅ UI · forecast studio in its honest v1 form ✅ (scenario simulator = registered model on counterfactual driver paths, zero-intervention replay test-enforced to equal the registered forecast; auto-brief = templated narrative, no LLM) · registry stays artifact-backed ✅ (32/32 tests green, endpoints verified live).
Deliberately NOT shipped, with reasons: user accounts + saved analyses (needs a real auth provider → moved to R3; no fake security), scheduled reports, second outcome (malaria), Celery/Redis (current workload is deterministic, bounded and sub-second — synchronous endpoints suffice).

### Release 3 — Advanced research platform
Research copilot (RAG over platform evidence, refuses invented statistics) · validated scenario engine · subnational expansion where data supports · expanded environmental modelling.

## 5. Stack adoption by release (over-engineering control)

| Layer | R1 | R2 | R3 |
|---|---|---|---|
| Frontend | React 18, TS, Vite, Tailwind, MapLibre GL JS, Plotly.js | saved analyses UI, alerts UI | copilot UI, scenario lab UI |
| Backend | FastAPI, Pydantic, **public read-only API, no auth** | auth + saved analyses + rate limits | copilot service |
| Database | PostgreSQL **with PostGIS enabled from day 1**, Alembic | vulnerability/scenario tables + Redis | + RAG store |
| Jobs | synchronous endpoints (bounded) | Celery + Redis workers | — |
| ML | XGBoost/LightGBM vs baselines, SHAP, temporal CV | model registry hardening, anomaly detection | scenario engine |
| Ops | Docker Compose, GH Actions CI, structured logs | monitoring budget: error tracking, model drift | — |

## 6. Monorepo layout

```
afrihealth-risk-atlas/
├── apps/web/            # React + TS (atlas, forecasts, comparisons, scenarios, alerts, copilot)
├── services/api/        # FastAPI (api/ core/ db/ models/ schemas/ services/)
├── ml/                  # ingestion, validation, features, training, evaluation,
│                        # forecasting, explainability, registry
├── pipelines/           # jobs/ schedules/ (Celery arrives in R2)
├── research/            # notebooks, experiments, paper
├── data/                # raw/ (gitignored), processed/, manifests/, samples/
├── docs/                # SRS, ARCHITECTURE, DATA_DICTIONARY, MODEL_CARD, SECURITY, DEPLOYMENT
├── infra/               # Dockerfile.api, docker-compose.yml (CI/CD in .circleci)
└── tests/               # cross-cutting integration tests
```

## 7. Release 1 — 8-week build calendar

| Wk | Stage(s) | Milestone | Exit gate |
|---|---|---|---|
| 1 | 01–03 | SRS finalized; **data audit** (WHO GHO + World Bank U5M/driver availability & missingness profile); monorepo + Docker Compose + local Postgres/PostGIS running | Audit report decides feature set; `docker compose up` works |
| 2 | 04 | Source adapters + immutable snapshots + manifest; geocoding via ISO codes; missingness/quality flags | Reproducible validated dataset with documented limitations |
| 3 | 04–05 | Migrations; baselines (naive, trend) with rolling-origin evaluation | Baseline table in `research/experiments/` |
| 4 | 05 | XGBoost/LightGBM lag models; Optuna with time-aware CV; ablation (Q2 answered) | ≥1 model beats baseline OR explicit fallback decision |
| 5 | 05 | SHAP global/local; prediction intervals; regional error breakdown (Q3); model registry v1 + model card draft | Registered artifacts with metrics + limitations |
| 6 | 06 | FastAPI: catalogue, atlas, series, forecast, explainability, model-card, export endpoints; integration tests | Documented typed API, tests green |
| 7 | 07 | React: app shell, **atlas map**, forecast view, explainability view; loading/empty/error/low-data states; mobile check | End-to-end on real API |
| 8 | 08–09 | E2E + leakage tests; security sweep; deploy (frontend CDN + api + managed Postgres); monitoring basics; README + demo | LIVE URL; runbook; Stage 10 (paper) kicks off |

## 8. R1 data scope (pending audit — codes verified against APIs in Wk 1)

**Outcome (target):** under-5 mortality (WHO GHO / World Bank `SH.DYN.MORT`).
**Driver candidates:** GDP/capita (`NY.GDP.PCAP.CD`), health expenditure % GDP (`SH.XPD.CHEX.GD.ZS`), physicians/1,000 (`SH.MED.PHYS.ZS`), nurses (`SH.MED.NUMW.P3`), DPT immunization (`SH.IMM.IDPT`), measles (`SH.IMM.MEAS`), basic sanitation (`SH.STA.BASS.ZS`), water (`SH.H2O.SMDW`), urbanization (`SP.URB.TOTL.IN.ZS`), UHC service coverage (WHO GHO `UHC_INDEX_REPORTED`), plus rainfall/temperature where justified (CHIRPS, later).
**Panel:** country × year (~54 countries × 20+ years). **Provenance is a first-class entity** (source, id, URL, retrieval timestamp, reported/estimated/imputed flag).
**Critical rules:** never fill missing health values with zero; every imputation documented and tested; geographic joins only on ISO codes, never display names.

## 9. R1 API contract (locked Wk 6, versioned under /api/v1)

| Endpoint | Method | Returns |
|---|---|---|
| `/api/v1/health` | GET | app + data-freshness status |
| `/api/v1/countries` · `/api/v1/indicators` | GET | catalogue with metadata + coverage |
| `/api/v1/atlas` | GET | country-year U5M observables + data-confidence layer |
| `/api/v1/countries/{iso3}/series` | GET | historical series + quality flags |
| `/api/v1/countries/{iso3}/forecast` | GET | forecast, intervals, model version, SHAP summary |
| `/api/v1/models/{model_id}` | GET | registry record: window, metrics, limitations |
| `/api/v1/reports` | POST | PDF/CSV export generation (bounded synchronous in R1) |

(R1 = read-only public API; auth arrives in R2 with saved analyses.)

## 10. Initial database scope (R1)

`countries`, `indicators`, `data_sources`, `dataset_versions`, `observations` (+ provenance FKs), `model_versions`, `forecasts` — versioned against dataset AND model.
R2 adds: `alerts`, `saved_analyses`, `report_jobs`, `users`, `risk_assessments`, `scenarios`.

## 11. Safeguards (non-negotiable, build-time, not paperwork)

1. No clinical/individual claims — population-level decision support only
2. No fabricated precision — suppress or qualify under-inadequate coverage
3. SHAP ≠ causation — labelled explicitly everywhere
4. No hidden imputation — estimates labelled; missing ≠ zero
5. Rankings expose construction, weights, sensitivity
6. Alert ≠ outbreak confirmation — automated flags distinguished from official warnings
7. Model card + prohibited uses recorded per model version
8. Human review required for any real resource-allocation use
9. Source licensing respected; national data rules honoured
10. Minimal user data; secrets never in Git or browser bundles

## 12. Definition of done — Release 1

- [ ] `docker compose up` runs web + api + db reproducibly; CI green in CircleCI
- [ ] Wk-1 audit report governs every modeling claim; no code contradicts the audit
- [ ] ≥1 model beats temporal baseline (or documented fallback) + leakage test passes
- [ ] Every number in UI traceable: source → dataset version → model version
- [ ] React app: atlas + forecast + explainability views, responsive, real API only
- [ ] Exports (PDF/CSV) include methods, limitations, provenance
- [ ] Model card + data documentation published
- [ ] LIVE URL + demo in README; rollback and restore documented
