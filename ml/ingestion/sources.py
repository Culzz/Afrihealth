"""AfriHealth source adapters (World Bank-first, provenance-controlled).

One module owns every external-source constant + fetch function so that the
audit, the panel builder, and validation can never disagree about geography
or indicator codes. Nothing here imputes, transforms opinions, or zero-fills.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
MANIFESTS = REPO / "data" / "manifests"
PROCESSED = REPO / "data" / "processed"

WB_API = "https://api.worldbank.org/v2"
GHO_API = "https://ghoapi.azureedge.net/api"
YEAR_START, YEAR_END = 2000, 2025
PER_PAGE = 500
RETRIES = 3
RETRY_BACKOFF = 2.0

# African countries by African Union membership (ISO-3). Western Sahara excluded.
AU_ISO3 = [
    "AGO", "DZA", "BEN", "BWA", "BFA", "BDI", "CPV", "CMR", "CAF", "TCD",
    "COM", "COG", "COD", "CIV", "DJI", "EGY", "GNQ", "ERI", "SWZ", "ETH",
    "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "LBY", "MDG",
    "MWI", "MLI", "MRT", "MUS", "SYC", "MAR", "MOZ", "NAM", "NER", "NGA",
    "RWA", "STP", "SEN", "SLE", "SOM", "ZAF", "SSD", "SDN", "TZA", "TGO",
    "TUN", "UGA", "ZMB", "ZWE",
]

# code -> metadata dict (short = column name in the analytical wide panel)
WB_CATALOG: dict[str, dict] = {
    "SH.DYN.MORT": {"short": "u5m", "name": "under5_mortality_per_1000",
                    "role": "outcome", "unit": "per 1,000 live births"},
    "SH.STA.MMRT": {"short": "matmort", "name": "maternal_mortality_per_100k",
                    "role": "candidate_outcome", "unit": "per 100,000 live births"},
    "SH.MLR.INCD.P3": {"short": "malaria", "name": "malaria_incidence_per_1000_at_risk",
                       "role": "candidate_outcome", "unit": "per 1,000 population at risk"},
    "NY.GDP.PCAP.CD": {"short": "gdp_pc", "name": "gdp_per_capita",
                       "role": "driver", "unit": "current US$"},
    "SH.XPD.CHEX.GD.ZS": {"short": "chexp_pctgdp", "name": "health_expenditure_pct_gdp",
                          "role": "driver", "unit": "% of GDP"},
    "SH.MED.PHYS.ZS": {"short": "phys_1k", "name": "physicians_per_1000",
                       "role": "driver", "unit": "per 1,000 people"},
    "SH.MED.NUMW.P3": {"short": "nurses_1k", "name": "nurses_midwives_per_1000",
                       "role": "driver", "unit": "per 1,000 people"},
    "SH.IMM.IDPT": {"short": "dpt_cov", "name": "dpt_immunization_pct",
                    "role": "driver", "unit": "% of children 12-23 months"},
    "SH.IMM.MEAS": {"short": "meas_cov", "name": "measles_immunization_pct",
                    "role": "driver", "unit": "% of children 12-23 months"},
    "SH.STA.BASS.ZS": {"short": "san_basic", "name": "basic_sanitation_pct",
                       "role": "driver", "unit": "% of population"},
    "SH.H2O.BASW.ZS": {"short": "water_basic", "name": "basic_drinking_water_pct",
                       "role": "driver", "unit": "% of population"},
    "SP.URB.TOTL.IN.ZS": {"short": "urb_pct", "name": "urbanization_pct",
                          "role": "driver", "unit": "% of total population"},
}

DRIVERS = [m["short"] for m in WB_CATALOG.values() if m["role"] == "driver"]
SPARSE_DRIVERS = {"phys_1k", "nurses_1k"}  # audit: ~42% coverage, flagged not dropped


def wb_get(path: str, params: dict) -> dict:
    """GET a World Bank API endpoint with retries; returns parsed JSON."""
    url = f"{WB_API}{path}"
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001 - survive source flakiness
            last_err = exc
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"World Bank API failed after {RETRIES} tries: {url} ({last_err})")


def wb_countries() -> pd.DataFrame:
    """Country metadata (AU members only): iso3, name, region."""
    payload = wb_get("/country", {"format": "json", "per_page": 1000})
    rows = payload[1] or []
    frame = pd.DataFrame(
        [{"iso3": r["id"], "country": r["name"], "region": r["region"]["value"]}
         for r in rows]
    )
    return frame[frame["iso3"].isin(AU_ISO3)].reset_index(drop=True)


def wb_indicator_panel(code: str) -> tuple[pd.DataFrame, str | None]:
    """Full country-year panel for one indicator restricted to AU members."""
    def fetch(page: int) -> tuple[dict, list]:
        payload = wb_get(
            f"/country/all/indicator/{code}",
            {"format": "json", "date": f"{YEAR_START}:{YEAR_END}",
             "per_page": PER_PAGE, "page": page},
        )
        return payload[0], payload[1] or []

    meta, all_rows = fetch(1)
    total, pages = meta.get("total", 0), meta.get("pages", 1)
    page = 2
    while page <= pages:
        _, rows = fetch(page)
        all_rows.extend(rows)
        page += 1

    frame = pd.DataFrame(
        [{"iso3": r["countryiso3code"], "year": int(r["date"]), "value": r["value"]}
         for r in all_rows
         if r["value"] is not None and r["countryiso3code"] in AU_ISO3]
    )
    note = None if not frame.empty else "no records returned (empty series)"
    if total == 0 and frame.empty:
        note = f"indicator {code} returned 0 records — check code validity"
    return frame, note


def md_table(headers: list[str], rows: list[list]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)
