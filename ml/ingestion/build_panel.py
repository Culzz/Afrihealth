"""Build the validated, versioned country-year analytical panel (Stage 04).

Reads the audit's cached raw snapshots (refetching only if missing), assembles
long + wide panels with provenance and quality flags, validates everything,
and writes a dataset manifest with file hashes.

Run from repo root:
    .venv\\Scripts\\python -m ml.ingestion.build_panel

Outputs:
    data/processed/panel_long.csv   tidy observations + provenance (committed)
    data/processed/panel_wide.csv   one row per country-year + q_ flags (committed)
    data/manifests/dataset_manifest.json      version, hashes, provenance summary
    data/manifests/validation_report.md       gate report (FAIL => exit 1)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml.ingestion.sources import (
    DRIVERS,
    PROCESSED,
    MANIFESTS,
    RAW,
    SPARSE_DRIVERS,
    WB_API,
    WB_CATALOG,
    YEAR_END,
    YEAR_START,
    wb_countries,
    wb_indicator_panel,
)
from ml.validation.checks import run_checks, write_validation_report

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def raw_paths(code: str) -> tuple[Path, Path]:
    safe = code.replace(".", "_")
    return RAW / f"wb_{safe}.csv", RAW / "wb_countries.csv"


def _code_panel(code: str) -> pd.DataFrame:
    """Indicator long rows from cache; refetch only when the cache is missing."""
    path, _ = raw_paths(code)
    meta = WB_CATALOG[code]
    if path.exists():
        df = pd.read_csv(path)
    else:
        df, note = wb_indicator_panel(code)
        if note:
            raise RuntimeError(f"fetch failed for {code}: {note}")
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
    df["indicator_code"] = code
    df["indicator_short"] = meta["short"]
    return df.dropna(subset=["value"])


def build_long(countries: pd.DataFrame) -> pd.DataFrame:
    frames = [_code_panel(code) for code in WB_CATALOG]
    long = pd.concat(frames, ignore_index=True)
    long = long.merge(countries, on="iso3", how="inner")  # inner: drop non-AU strays
    long["role"] = long["indicator_short"].map(
        {m["short"]: m["role"] for m in WB_CATALOG.values()}
    )
    long["unit"] = long["indicator_short"].map(
        {m["short"]: m["unit"] for m in WB_CATALOG.values()}
    )
    long["value_name"] = long["indicator_short"].map(
        {m["short"]: m["name"] for m in WB_CATALOG.values()}
    )
    long["source"] = "World Bank WDI v2"
    long["source_url"] = long["indicator_code"].map(
        lambda c: f"{WB_API}/country/all/indicator/{c}"
    )
    return long


def q_flags(wide: pd.DataFrame) -> pd.DataFrame:
    """Quality flags — absence is information, never silently zero-filled."""
    present = wide[DRIVERS].notna().sum(axis=1)
    wide["q_driver_coverage_pct"] = (100 * present / len(DRIVERS)).round(1)
    wide["q_target_missing"] = wide["u5m"].isna()
    wide["q_sparse_hwf_missing"] = wide[list(SPARSE_DRIVERS)].isna().all(axis=1)
    return wide


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    t0 = datetime.now(timezone.utc)
    print("[1/4] Loading source snapshots ...")
    cached_countries = raw_paths("x")[1]
    if cached_countries.exists():
        countries = pd.read_csv(cached_countries)
    else:
        countries = wb_countries()
        cached_countries.parent.mkdir(parents=True, exist_ok=True)
        countries.to_csv(cached_countries, index=False)
    print(f"      countries: {len(countries)}")

    print("[2/4] Assembling long + wide panels ...")
    long = build_long(countries)
    wide = (
        long.pivot_table(index=["iso3", "country", "region", "year"],
                         columns="indicator_short", values="value")
        .reset_index()
    )
    wide.columns.name = None
    wide = wide[wide["year"].between(YEAR_START, YEAR_END)]
    wide = q_flags(wide)
    long = long.sort_values(["iso3", "year", "indicator_code"]).reset_index(drop=True)
    wide = wide.sort_values(["iso3", "year"]).reset_index(drop=True)

    print("[3/4] Writing processed panels + manifest ...")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    long_path = PROCESSED / "panel_long.csv"
    wide_path = PROCESSED / "panel_wide.csv"
    long.to_csv(long_path, index=False)
    wide.to_csv(wide_path, index=False)

    version = f"v1__{t0:%Y%m%d}"
    manifest = {
        "dataset_version": version,
        "built_at": t0.isoformat(),
        "generation_command": "python -m ml.ingestion.build_panel",
        "sources": [
            {
                "organization": "World Bank",
                "dataset": "World Development Indicators (WDI) v2 API",
                "url": f"{WB_API}/country/all/indicator/<code>",
                "license": "CC BY 4.0 (attribution required)",
            }
        ],
        "years": {
            "start": YEAR_START,
            "end": YEAR_END,
            "note": "Several drivers end 2023-2024; forecasts must respect per-indicator availability.",
        },
        "rows": {"long": int(len(long)), "wide": int(len(wide))},
        "coverage_by_indicator": {
            WB_CATALOG[c]["short"]: {
                "code": c,
                "role": WB_CATALOG[c]["role"],
                "unit": WB_CATALOG[c]["unit"],
                "obs": int(long[long.indicator_code == c].shape[0]),
                "countries": int(long[long.indicator_code == c].iso3.nunique()),
            }
            for c in WB_CATALOG
        },
        "quality_flags": {
            "q_driver_coverage_pct": "share of the 9 driver series present for that country-year",
            "q_target_missing": "under-five mortality absent for that country-year (kept as NaN, never zero-filled)",
            "q_sparse_hwf_missing": "both sparse health-workforce series missing (physicians, nurses)",
        },
        "notes": [
            "WB v2 API does not distinguish reported vs modelled estimates; all values "
            "carry value_status='published_wdi' and series-level modelled status lives in docs/DATA_DICTIONARY.md.",
            "phys_1k and nurses_1k are sparse (Wk-1 audit: ~42%); downstream models must treat them as weak-confidence features.",
            "WHO GHO was 502-down during the Wk-1 audit; this dataset is WB-only by design.",
        ],
        "files": {
            "panel_long.csv": sha256_file(long_path),
            "panel_wide.csv": sha256_file(wide_path),
        },
    }
    manifest_path = MANIFESTS / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("[4/4] Running validation gate ...")
    failures, warnings = run_checks(long, wide)
    write_validation_report(manifest, failures, warnings)
    if failures:
        print(f"VALIDATION FAILED: {len(failures)} blocking issues, {len(warnings)} warnings")
        return 1
    print(f"Validation passed: 0 blocking issues, {len(warnings)} warnings")
    print(f"Panel v1: {len(wide)} country-years, {len(long)} observations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
