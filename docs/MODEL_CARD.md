# AfriHealth — Model Card (template, populated after Wk-5 evaluation)

## Model details
- **Model:** TBD (candidate: gradient-boosted trees vs. baselines) · **Version:** TBD
- **Task:** forecast annual under-5 mortality (per 1,000 live births) for African countries
- **Training window:** TBD (e.g., 2000–2018) · **Feature set:** TBD (see DATA_DICTIONARY)
- **Validation:** rolling-origin temporal evaluation — **no random splits**

## Intended use
Population-level decision support for researchers/policy analysts exploring
"where risk is heading and why." Public-good analytics at country granularity.

## Out of scope / prohibited
Individual or clinical prediction · outbreak surveillance replacement ·
resource-allocation decisions without human expert review · causal intervention claims.

## Performance
- vs. baseline: TBD (MAE/RMSE/WAPE) · by region: TBD · interval coverage: TBD
- Known weak coverage: TBD (linked from data-confidence layer)

## Limitations & failure modes
- Country-level only; no district inference
- Sparse/imputed inputs raise uncertainty — surfaced via quality flags
- SHAP = model behaviour, **not** causation
- Modelled estimates (not raw reports) dominate U5M series — interpreted accordingly

## Monitoring & update policy
Data refresh per source cadence; model re-registered on dataset_version change;
automatic rollback trigger if acceptance checks fail (defined Wk 5+).
