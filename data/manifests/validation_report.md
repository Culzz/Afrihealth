# Stage-04 Validation Report

_Dataset: `v1__20261019` · built 2026-10-19T23:13:18.547868+00:00_
_Long rows: 14400 · Wide rows: 1404_

## Failure-gate checks (blocking)

| Check | Result |
| --- | --- |
| uniqueness (iso3, year, indicator) | PASS |
| geography ⊆ AU members | PASS |
| temporal scope | PASS |
| plausibility bounds (13 series) | PASS |

## Findings (warnings)

- none

## Provenance summary

- Source: World Bank WDI v2 (CC BY 4.0), country filter: AU members
- Missing data preserved as NaN (zero-fill scan: clean); no imputation performed
- value_status: 'published_wdi' (API does not split reported/modelled; see DATA_DICTIONARY)
- File hashes recorded in data/manifests/dataset_manifest.json
