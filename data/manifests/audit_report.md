# Stage-01 Data Audit Report

_Generated: 2026-10-19T22:49:00+00:00 (UTC) · Sources: World Bank WDI v2, WHO GHO_
_Geographic scope: 54 African Union member states matched against an expected 54 (ISO-3), years 2000–2025_

## 1. World Bank indicator profile
| Code | Series | Role | Verdict | Rows | Countries | Coverage % | First | Last | Median c/yr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SH.DYN.MORT | under5_mortality_per_1000 | outcome | STRONG | 1350 | 54 | 96.2 | 2000 | 2024 | 54.0 |
| SH.STA.MMRT | maternal_mortality_per_100k | candidate_outcome | STRONG | 1296 | 54 | 92.3 | 2000 | 2023 | 54.0 |
| SH.MLR.INCD.P3 | malaria_incidence_per_1000_at_risk | candidate_outcome | STRONG | 1225 | 49 | 87.3 | 2000 | 2024 | 49.0 |
| NY.GDP.PCAP.CD | gdp_per_capita | driver | STRONG | 1372 | 54 | 97.7 | 2000 | 2025 | 53.0 |
| SH.XPD.CHEX.GD.ZS | health_expenditure_pct_gdp | driver | STRONG | 1256 | 54 | 89.5 | 2000 | 2023 | 52.0 |
| SH.MED.PHYS.ZS | physicians_per_1000 | driver | USABLE | 606 | 54 | 43.2 | 2000 | 2023 | 24.5 |
| SH.MED.NUMW.P3 | nurses_midwives_per_1000 | driver | USABLE | 582 | 54 | 41.5 | 2000 | 2023 | 26.5 |
| SH.IMM.IDPT | dpt_immunization_pct | driver | STRONG | 1339 | 54 | 95.4 | 2000 | 2024 | 54.0 |
| SH.IMM.MEAS | measles_immunization_pct | driver | STRONG | 1339 | 54 | 95.4 | 2000 | 2024 | 54.0 |
| SH.STA.BASS.ZS | basic_sanitation_pct | driver | STRONG | 1318 | 54 | 93.9 | 2000 | 2024 | 53.0 |
| SH.H2O.BASW.ZS | basic_drinking_water_pct | driver | STRONG | 1313 | 54 | 93.5 | 2000 | 2024 | 52.0 |
| SP.URB.TOTL.IN.ZS | urbanization_pct | driver | STRONG | 1404 | 54 | 100.0 | 2000 | 2025 | 54.0 |

**Target (under-five mortality):** STRONG — 1350 observations across 54 countries, 96.2% of possible country-year cells, data through 2024.

**Driver candidates with adequate coverage:** 9/9 → gdp_per_capita, health_expenditure_pct_gdp, physicians_per_1000, nurses_midwives_per_1000, dpt_immunization_pct, measles_immunization_pct, basic_sanitation_pct, basic_drinking_water_pct, urbanization_pct

## 2. WHO GHO candidates
| Search term | Code | Name | African rows | Countries | First | Last |
| --- | --- | --- | --- | --- | --- | --- |
| under-five mortality | nan | SEARCH FAILED (502 Server Error: Bad Gateway for url: https://ghoapi.azureedge.net/api/Indicator?%24search=under-five+mortality&%24top=10) | - | - | - | - |
| maternal mortality | nan | SEARCH FAILED (502 Server Error: Bad Gateway for url: https://ghoapi.azureedge.net/api/Indicator?%24search=maternal+mortality&%24top=10) | - | - | - | - |
| malaria incidence | nan | SEARCH FAILED (502 Server Error: Bad Gateway for url: https://ghoapi.azureedge.net/api/Indicator?%24search=malaria+incidence&%24top=10) | - | - | - | - |
| physicians density | nan | SEARCH FAILED (502 Server Error: Bad Gateway for url: https://ghoapi.azureedge.net/api/Indicator?%24search=physicians+density&%24top=10) | - | - | - | - |
| UHC service coverage | nan | SEARCH FAILED (502 Server Error: Bad Gateway for url: https://ghoapi.azureedge.net/api/Indicator?%24search=UHC+service+coverage&%24top=10) | - | - | - | - |

## 3. Candidate second outcomes
| Code | Series | Verdict | Rows | Countries | Coverage % | Last year |
| --- | --- | --- | --- | --- | --- | --- |
| SH.STA.MMRT | maternal_mortality_per_100k | STRONG | 1296 | 54 | 92.3 | 2023 |
| SH.MLR.INCD.P3 | malaria_incidence_per_1000_at_risk | STRONG | 1225 | 49 | 87.3 | 2024 |

## 4. Verdicts to carry into modeling

1. U5M panel: **STRONG** — proceed with outcome-specific forecasting.
2. Feature set locked to drivers with verdict USABLE+ : see list above; all others dropped before features.py.
3. Second outcome (malaria / maternal) decision deferred to audit review — not forced.
4. WHO GHO treated as enrichment source only (architecture invariant: v1 ships on WB alone if needed).

## 5. Reproducibility

- Script: `python -m ml.ingestion.audit` (requests + pandas only)
- Raw snapshots cached under `data/raw/` (gitignored)
- This report and CSVs are committed under `data/manifests/`
- Critical rule honoured: no value was imputed, estimated, or zero-filled anywhere in this audit