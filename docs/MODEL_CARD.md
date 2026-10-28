# AfriHealth — Model Card

## Model details
- **Model:** LightGBM (gradient-boosted trees), registry id `u5m-lgb-v1`
- **Task:** forecast annual under-five mortality (per 1,000 live births) for African Union countries
- **Training window:** country-years with label present (2000-2024, n=1350) · features: 15 (history lags + drivers at t-1 + region)
- **Validation:** expanding-window temporal folds; Optuna never saw years >= 2019; holdout 2021-2024 untouched during tuning
- **Dataset version:** `v1__20261019` (sha256-hashed manifest)

## Intended use
Population-level decision support for public-health researchers/policy analysts:
"where is under-five mortality heading and what does the model think drives it?"

## Out of scope / prohibited
Individual or clinical prediction · outbreak surveillance replacement ·
resource-allocation decisions without human expert review · causal claims from
SHAP or from scenario-style feature perturbations.

## Performance (holdout 2021-2024, n=216 country-years)
- **MAE 3.49, RMSE 19.29, WAPE 0.06**
- vs. baselines: naive_last MAE 5.06, drift 5.45 → selected model improves
  MAE by ~31%; history-only ablation 3.78 → drivers add +0.29 MAE improvement
- Unknown/failure case: countries with long data gaps — forecasts fall back to
  carried-forward history and are flagged `drivers_default_missing`/`last_observed_year`.

## Uncertainty
- Intervals: empirical residual quantiles from the holdout
  (sigma 19.02, q90 2.96), widened by sqrt(horizon)
- Exceedance probabilities P(u5m > 70, 50) accompany every forecast

## Limitations & failure modes
- Country-level only; no district inference.
- WB modeling estimates dominate recent U5M series - treat forecasts, not raw reports, as the artefact.
- Sparse workforce features (physicians, nurses; ~42% coverage) are weak-confidence inputs.
- Drivers "carried forward" beyond tensor end are assumptions, clearly flagged per row.

## Monitoring & update policy
- Re-register on dataset_version change; automatic metric regression check against
  the Week-4 gate (MAE must stay <= naive baseline) before promotion.
- Known weaknesses evolve with the data audit each cycle.

---

# Companion artifact: vulnerability composite `vuln-v1`

- **What it is:** a deterministic, transparent composite that ranks the 54 AU
  countries by the joint presence of under-five mortality burden and weak
  recorded service capacity. Published as `ml/registry/vulnerability_v1.json`
  with a sha256 block; served verbatim via `GET /api/v1/vulnerability`.
- **Inputs (weights sum to 1):** observed u5m 0.25 · registered 2025 forecast
  0.15 · capacity deficits 0.60 split across physicians 0.15, nurses 0.10,
  DPT coverage 0.10, basic sanitation 0.10, basic water 0.10, health
  expenditure share 0.05.
- **Construction:** every component is a percentile rank over available
  cross-sections (100 = most adverse); capacity series are inverted so 100 =
  weakest. Per-country component values are the newest observation since 2018,
  **as-is** — never interpolated — and each carries a recorded vintage year
  (burden runs to 2024; workforce/expenditure lag to 2022-2023).
- **Missing data:** never imputed. A country lacking a component has weights
  renormalised over the rest and ships `complete: false` with the missing list
  (49/54 complete in the published artifact).
- **Sensitivity:** each row records `jackknife_max_delta` — the maximum change
  in its composite when any single component is dropped (published artifact
  range ≈ 0.7-3.3 points). Bands: low <20 · watch 20-50 · elevated 50-80 ·
  high >=80.
- **Out of scope:** the composite is NOT a surveillance or diagnostic
  instrument; thresholds are ordinal flags for triage of attention, not
  clinical or mandated categories.

# Companion capability: scenario layer (model-behaviour counterfactuals)

- **What it is:** `POST /api/v1/scenarios` runs the registered `u5m-lgb-v1`
  model on a counterfactual feature row: the t-1 driver values perturbed by the
  requested deltas (e.g. DPT coverage +15 pp, basic sanitation +20 pp).
- **Internal-consistency contract (test-enforced):** with zero interventions,
  the engine reproduces the registered forecast within ±0.5 — the replay is the
  same feature builder, the same pickle, the same prediction path.
- **Honest limits:** single horizon (h=1) only; intervals reuse the empirical
  h=1 90% half-width around the scenario point; the output is described as
  **model behaviour, not a causal estimate** — no counterfactual claim is made
  about real-world policy effects. Drivers that are unobserved at t-1 are
  rejected (422) rather than invented, consistent with the no-imputation rule.
- **Not an official section of the frozen R1 card:** Prometheus rules, drift
  monitors and SHAP dashboards apply to the forecast model; the scenario layer
  inherits the same dataset version and re-registration cadence.
