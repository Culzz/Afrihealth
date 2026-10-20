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
