# AfriHealth — Data Dictionary & Provenance Rules

Status: living document · starts Wk 1, grows with the pipeline

## Provenance contract (every observation carries)

| Field | Meaning |
|---|---|
| `source_id` → `data_sources` | organization + dataset + exact indicator id |
| `source_url` | landmark URL of the record |
| `retrieved_at` | pull timestamp |
| `geo_id` | ISO3 country (+ admin level for future subnational) |
| `period` | year / reporting period, source-defined |
| `value`, `unit`, `definition` | as published; transformed values keep both forms |
| `value_status` | `reported` / `estimated` / `imputed` / `derived` |
| `quality_flags` | missingness, sparsity, revision pending |
| `dataset_version` | immutable snapshot hash |

## Hard rules

1. **Never zero-fill** missing health statistics; a zero ≠ an unreported observation.
2. Imputation = documented method, tested, labelled `imputed`, uncertainty reflected.
3. Geography matched on ISO codes only — never display names.
4. Source values are immutable: refreshes add new versions, they don't overwrite history.
5. Units and indicator definitions travel with every transformed series.

## Core entities (R1 schema)

| Table | Purpose |
|---|---|
| `countries` | ISO3 id, names, UN subregion, geometry metadata |
| `indicators` | id, definition, unit, source, update cadence |
| `data_sources` | URL, licensing, retrieval history |
| `dataset_versions` | immutable snapshot hash, changelog |
| `observations` | the panel: country × indicator × year × value × provenance |
| `model_versions` | artifact ref, feature list, training window, metrics, card link |
| `forecasts` | prediction per (model_version, dataset_version, country, horizon) with intervals |

## Seed indicator list (audit verifies availability Wk 1)

| Code | Indicator | Role |
|---|---|---|
| `SH.DYN.MORT` (WB) / WHO GHO equivalent | Under-5 mortality per 1,000 | **Outcome (target)** |
| `NY.GDP.PCAP.CD` | GDP per capita | driver |
| `SH.XPD.CHEX.GD.ZS` | Health expenditure % GDP | driver |
| `SH.MED.PHYS.ZS` | Physicians per 1,000 | driver |
| `SH.MED.NUMW.P3` | Nurses & midwives per 1,000 | driver |
| `SH.IMM.IDPT` | DPT immunization % | driver |
| `SH.IMM.MEAS` | Measles immunization % | driver |
| `SH.STA.BASS.ZS` | Basic sanitation % | driver |
| `SH.H2O.SMDW` | Safely managed drinking water % | driver |
| `SP.URB.TOTL.IN.ZS` | Urbanization % | driver |
| WHO GHO `UHC_INDEX_REPORTED` | UHC service coverage | driver |
| `SH.STA.MMRT` (WB) | Maternal mortality | exploratory (2nd-outcome candidate) |
| `SH.MLR.INCD.P3` (WB) | Malaria incidence /1,000 at risk | exploratory (2nd-outcome candidate) |
