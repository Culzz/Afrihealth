"""AfriHealth Stage-01 data audit.

Profiles availability of the under-five mortality outcome plus driver and
candidate-outcome indicators for African countries from the World Bank
World Development Indicators API, and discovers WHO GHO indicator candidates.

This audit gates the Release-1 feature set: no modeling decision outranks it.

Run from repo root:
    .venv\\Scripts\\python -m ml.ingestion.audit

Committed outputs:
    data/manifests/wb_indicator_audit.csv   per-indicator machine-readable profile
    data/manifests/audit_report.md          human-readable findings + verdicts
Gitignored outputs (reproducible): data/raw/
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "raw"
MANIFESTS = REPO / "data" / "manifests"

WB_API = "https://api.worldbank.org/v2"
GHO_API = "https://ghoapi.azureedge.net/api"
YEAR_START, YEAR_END = 2000, 2025
PER_PAGE = 500
RETRIES = 3
RETRY_BACKOFF = 2.0
GHO_ROW_CAP = 4000

# African countries by African Union membership (ISO-3). Western Sahara excluded.
AU_ISO3 = [
    "AGO", "DZA", "BEN", "BWA", "BFA", "BDI", "CPV", "CMR", "CAF", "TCD",
    "COM", "COG", "COD", "CIV", "DJI", "EGY", "GNQ", "ERI", "SWZ", "ETH",
    "GAB", "GMB", "GHA", "GIN", "GNB", "KEN", "LSO", "LBR", "LBY", "MDG",
    "MWI", "MLI", "MRT", "MUS", "SYC", "MAR", "MOZ", "NAM", "NER", "NGA", "RWA",
    "STP", "SEN", "SLE", "SOM", "ZAF", "SSD", "SDN", "TZA", "TGO", "TUN",
    "UGA", "ZMB", "ZWE",
]

# code -> (short name, role in the study)
WB_CATALOG = {
    "SH.DYN.MORT": ("under5_mortality_per_1000", "outcome"),
    "SH.STA.MMRT": ("maternal_mortality_per_100k", "candidate_outcome"),
    "SH.MLR.INCD.P3": ("malaria_incidence_per_1000_at_risk", "candidate_outcome"),
    "NY.GDP.PCAP.CD": ("gdp_per_capita", "driver"),
    "SH.XPD.CHEX.GD.ZS": ("health_expenditure_pct_gdp", "driver"),
    "SH.MED.PHYS.ZS": ("physicians_per_1000", "driver"),
    "SH.MED.NUMW.P3": ("nurses_midwives_per_1000", "driver"),
    "SH.IMM.IDPT": ("dpt_immunization_pct", "driver"),
    "SH.IMM.MEAS": ("measles_immunization_pct", "driver"),
    "SH.STA.BASS.ZS": ("basic_sanitation_pct", "driver"),
    "SH.H2O.BASW.ZS": ("basic_drinking_water_pct", "driver"),
    "SP.URB.TOTL.IN.ZS": ("urbanization_pct", "driver"),
}

GHO_SEARCH_TERMS = [
    "under-five mortality",
    "maternal mortality",
    "malaria incidence",
    "physicians density",
    "UHC service coverage",
]


def wb_get(path: str, params: dict) -> dict:
    """GET a World Bank API endpoint with retries; returns parsed JSON."""
    url = f"{WB_API}{path}"
    last_err: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001 - audit must survive source flakiness
            last_err = exc
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"World Bank API failed after {RETRIES} tries: {url} ({last_err})")


def wb_countries() -> pd.DataFrame:
    """Country metadata (AU members only): iso3, name, region."""
    payload = wb_get("/country", {"format": "json", "per_page": 1000})
    rows = payload[1] or []
    frame = pd.DataFrame(
        [
            {
                "iso3": r["id"],
                "country": r["name"],
                "region": r["region"]["value"],
            }
            for r in rows
        ]
    )
    return frame[frame["iso3"].isin(AU_ISO3)].reset_index(drop=True)


def wb_indicator_panel(code: str) -> tuple[pd.DataFrame, str | None]:
    """Full country-year panel for one indicator restricted to AU members."""
    first = wb_get(
        f"/country/all/indicator/{code}",
        {
            "format": "json",
            "date": f"{YEAR_START}:{YEAR_END}",
            "per_page": PER_PAGE,
            "page": 1,
        },
    )
    meta, rows = first[0], first[1] or []
    pages, total = meta.get("pages", 1), meta.get("total", len(rows))
    all_rows = list(rows)
    page = 2
    while page <= pages:
        payload = wb_get(
            f"/country/all/indicator/{code}",
            {
                "format": "json",
                "date": f"{YEAR_START}:{YEAR_END}",
                "per_page": PER_PAGE,
                "page": page,
            },
        )
        all_rows.extend(payload[1] or [])
        page += 1

    frame = pd.DataFrame(
        [
            {
                "iso3": r["countryiso3code"],
                "year": int(r["date"]),
                "value": r["value"],
            }
            for r in all_rows
            if r["value"] is not None and r["countryiso3code"] in AU_ISO3
        ]
    )
    empty = "ok"
    if total == 0:
        empty = "no records returned (empty series)"
    return frame, (None if not frame.empty else empty)


def indicator_metrics(panel: pd.DataFrame) -> dict:
    """Availability metrics for one indicator panel (AU members only)."""
    missing_years = set(range(YEAR_START, YEAR_END + 1)) - set(panel["year"].tolist())
    span_years = max(panel["year"]) - min(panel["year"]) + 1 if not panel.empty else 0
    countries = panel["iso3"].nunique()
    cells_target = len(AU_ISO3) * (YEAR_END - YEAR_START + 1)
    return {
        "rows": len(panel),
        "countries_with_data": countries,
        "auc_coverage_pct": round(100 * len(panel) / cells_target, 1),
        "first_year": int(panel["year"].min()) if not panel.empty else None,
        "last_year": int(panel["year"].max()) if not panel.empty else None,
        "years_span": span_years,
        "median_countries_per_year": float(panel.groupby("year")["iso3"].nunique().median()),
        "recent_year_40plus": int(
            panel.groupby("year")["iso3"].nunique().pipe(
                lambda s: s[s >= 40].index.max()
            )
        )
        if not panel.empty
        else None,
        "zero_years_flagged": len(missing_years),
    }


def md_table(headers: list[str], rows: list[list]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def gho_search_indicator(term: str) -> list[dict]:
    """Search WHO GHO indicator catalog for candidates."""
    try:
        r = requests.get(
            f"{GHO_API}/Indicator",
            params={"$search": term, "$top": 10},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("value", data if isinstance(data, list) else [])
        out = []
        for it in items:
            code = it.get("IndicatorCode") or it.get("Id")
            label = it.get("IndicatorName") or it.get("Title") or ""
            if code:
                out.append({"code": code, "name": label[:110]})
        return out
    except Exception as exc:  # noqa: BLE001
        return [{"code": None, "name": f"SEARCH FAILED ({exc})"}]


def gho_profile(code: str) -> dict | None:
    """Row-count and coverage profile for one GHO indicator code."""
    try:
        all_items: list = []
        skip = 0
        while skip < GHO_ROW_CAP:
            r = requests.get(
                f"{GHO_API}/{code}",
                params={"$format": "json", "$skip": skip, "$top": 500},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            page = data.get("value", data if isinstance(data, list) else [])
            if not page:
                break
            all_items.extend(page)
            skip += len(page)
        frame = pd.DataFrame(
            [
                {"iso3": it.get("SpatialDim"), "year": it.get("TimeDim")}
                for it in all_items
                if it.get("SpatialDim") in (AU_ISO3 or [])
            ]
        )
        if frame.empty:
            return {"code": code, "rows_african": 0, "countries": 0,
                    "first_year": None, "last_year": None}
        return {
            "code": code,
            "rows_african": len(frame),
            "countries": frame["iso3"].nunique(),
            "first_year": int(frame["year"].min()),
            "last_year": int(frame["year"].max()),
        }
    except Exception as exc:  # noqa: BLE001
        return {"code": code, "error": f"fetch failed ({exc.status_code if hasattr(exc, 'status_code') else exc})"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    print("[1/3] Fetching AU country metadata ...")
    countries = wb_countries()
    print(f"      AU countries matched: {len(countries)}")
    countries.to_csv(RAW / "wb_countries.csv", index=False)

    profiles: list[dict] = []
    print("[2/3] Auditing World Bank indicators ...")
    for code, (short, role) in WB_CATALOG.items():
        print(f"      {code} ({role}) ...", flush=True)
        try:
            panel, note = wb_indicator_panel(code)
            panel.to_csv(RAW / f"wb_{code.replace('.', '_')}.csv", index=False)
            m = indicator_metrics(panel)
            verdict = (
                "STRONG"
                if m["rows"] >= 900 and m["countries_with_data"] >= 45
                else "USABLE"
                if m["rows"] >= 400 and m["countries_with_data"] >= 35
                else "WEAK"
            )
            profiles.append({
                "code": code, "short_name": short, "role": role,
                "verdict": verdict, "note": note, **m,
            })
        except Exception as exc:  # noqa: BLE001
            profiles.append({
                "code": code, "short_name": short, "role": role,
                "verdict": "FAILED", "note": str(exc)[:160],
            })

    profile_df = pd.DataFrame(profiles)
    profile_df.to_csv(MANIFESTS / "wb_indicator_audit.csv", index=False)

    print("[3/3] Auditing WHO GHO availability ...")
    gho_rows: list[dict] = []
    for term in GHO_SEARCH_TERMS:
        cands = gho_search_indicator(term)
        for cand in cands[:2]:
            code = cand.get("code")
            if code and code != None and cand.get("name", "").startswith("SEARCH FAILED") is False:
                prof = gho_profile(code)
                gho_rows.append({
                    "search_term": term, **prof,
                    "name": cand.get("name", ""),
                })
            else:
                gho_rows.append({
                    "search_term": term, "code": code,
                    "name": cand.get("name", ""),
                })

    gho_df = pd.DataFrame(gho_rows)
    gho_df.to_csv(MANIFESTS / "who_gho_audit.csv", index=False)

    outcome = profile_df[profile_df["role"] == "outcome"].iloc[0]
    drivers = profile_df[profile_df["role"] == "driver"]
    strong_drivers = drivers[drivers["verdict"].isin(["STRONG", "USABLE"])]
    candidates = profile_df[profile_df["role"] == "candidate_outcome"]

    lines = [
        "# Stage-01 Data Audit Report",
        "",
        f"_Generated: {now} (UTC) · Sources: World Bank WDI v2, WHO GHO_",
        f"_Geographic scope: {len(countries)} African Union member states matched against an expected {len(AU_ISO3)} (ISO-3), years {YEAR_START}–{YEAR_END}_",
        "",
        "## 1. World Bank indicator profile",
        md_table(
            ["Code", "Series", "Role", "Verdict", "Rows", "Countries",
             "Coverage %", "First", "Last", "Median c/yr"],
            [
                [r["code"], r["short_name"], r["role"], r["verdict"],
                 r.get("rows", "-"), r.get("countries_with_data", "-"),
                 r.get("auc_coverage_pct", "-"), r.get("first_year", "-"),
                 r.get("last_year", "-"), r.get("median_countries_per_year", "-")]
                for _, r in profile_df.iterrows()
            ],
        ),
        "",
        f"**Target (under-five mortality):** {outcome['verdict']} — "
        f"{outcome.get('rows')} observations across {outcome.get('countries_with_data')} countries, "
        f"{outcome.get('auc_coverage_pct')}% of possible country-year cells, "
        f"data through {outcome.get('last_year')}.",
        "",
        f"**Driver candidates with adequate coverage:** {len(strong_drivers)}/"
        f"{len(drivers)} → " + ", ".join(strong_drivers["short_name"].tolist()),
        "",
        "## 2. WHO GHO candidates",
        md_table(
            ["Search term", "Code", "Name", "African rows", "Countries", "First", "Last"],
            [
                [r.get("search_term"), r.get("code"), r.get("name"),
                 r.get("rows_african", "-"), r.get("countries", "-"),
                 r.get("first_year", "-"), r.get("last_year", "-")]
                for _, r in gho_df.iterrows()
            ],
        ),
        "",
        "## 3. Candidate second outcomes",
        md_table(
            ["Code", "Series", "Verdict", "Rows", "Countries", "Coverage %",
             "Last year"],
            [
                [r["code"], r["short_name"], r["verdict"], r.get("rows", "-"),
                 r.get("countries_with_data", "-"), r.get("auc_coverage_pct", "-"),
                 r.get("last_year", "-")]
                for _, r in candidates.iterrows()
            ],
        ),
        "",
        "## 4. Verdicts to carry into modeling",
        "",
        f"1. U5M panel: **{outcome['verdict']}** — proceed with outcome-specific forecasting.",
        f"2. Feature set locked to drivers with verdict USABLE+ : see list above; all others dropped before features.py.",
        "3. Second outcome (malaria / maternal) decision deferred to audit review — not forced.",
        "4. WHO GHO treated as enrichment source only (architecture invariant: v1 ships on WB alone if needed).",
        "",
        "## 5. Reproducibility",
        "",
        "- Script: `python -m ml.ingestion.audit` (requests + pandas only)",
        "- Raw snapshots cached under `data/raw/` (gitignored)",
        "- This report and CSVs are committed under `data/manifests/`",
        "- Critical rule honoured: no value was imputed, estimated, or zero-filled anywhere in this audit",
    ]
    report = "\n".join(lines)
    (MANIFESTS / "audit_report.md").write_text(report, encoding="utf-8")
    print("\nAudit complete -> data/manifests/audit_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
