# AfriHealth SRS — Software Requirements Specification

Status: DRAFT (finalized in Wk 1) · Version: 0.1

## 1. Purpose

Population-level health-intelligence platform for African countries: explore observed
health burden, inspect validated forecasts with uncertainty, understand drivers,
and export evidence-traceable reports. Explicitly out of scope: individual diagnosis,
outbreak surveillance replacement, clinical guidance.

## 2. Stakeholders / personas

- **Public-health researcher** — compares countries/outcomes, validates claims, downloads methods-backed reports
- **NGO / programme analyst** — identifies regions where burden overlaps weak service capacity, tests assumptions in the Scenario Lab (R2+)
- **Epidemiology / policy team** — monitors emerging trends and early-warning flags (R2+)
- **Developer / reviewer** (max: recruiters) — verifies reproducibility, model card, tests, provenance trail

## 3. User stories (Wk 1 filler)

- As a researcher, I see each country's U5M series with source + coverage flags so I know what I'm looking at.
- As a researcher, I can generate a U5M forecast with intervals and compare it with a naive baseline.
- As a researcher, I can inspect SHAP drivers of any forecast, labelled as model behaviour not causation.
- As any user, I can export a report that cites sources, dataset version, model version, and limitations.
- As a low-bandwidth user, pages degrade gracefully with loading/empty/error states.

## 4. Functional requirements by capability (R1 slice)

| Capability | R1 requirement |
|---|---|
| Atlas | Country-level U5M map (MapLibre) + filter by year + data-confidence layer |
| Forecasting | ≥1 validated model + naive baseline; intervals; horizon constrained to what data supports |
| Explainability | SHAP global + per-country; ablation summary; causation disclaimer |
| Exports | PDF (ReportLab via services) + CSV; provenance embedded |
| Catalogue | indicators/countries/data_sources browsable via API + UI |
| Copilot / Scenario Lab / Alerts | **Out of scope R1** (R3 / R2 / R2) |

## 5. Non-functional requirements

- Temporal (no-leakage) validation only; leakage covered by tests
- API typed with Pydantic; OpenAPI docs; stable `/api/v1` contract
- Responsive + accessible; works with sparse-data regions shown honestly
- Reproducibility: dataset manifests, model registry, seeds pinned
- Performance: no API request does unbounded work; exports bounded

## 6. Research questions this SRS serves

1. Do ML models beat baselines for U5M forecasting? 2. Do added socioeconomic/system indicators help? 3. How does performance vary with data availability? 4. Do uncertainty + quality displays reduce overconfidence? 5. How stable are rankings? 6. Is every displayed number independently verifiable?

## 7. Quality gates / acceptance criteria (R1)

E2E user journey works on real API · leakage test green · model card complete ·
live URL · docs current · logged deviations from SRS recorded in Wk-8 review.
