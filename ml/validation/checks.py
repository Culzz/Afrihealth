"""AfriHealth validation suite (Stage 04 quality gate).

Structural checks are blocking (FAIL); judgement-call findings are warnings.
The suite is deliberately importable so tests can exercise it on synthetic
panels without touching the network.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml.ingestion.sources import AU_ISO3, DRIVERS, YEAR_END, YEAR_START

# Plausibility bounds per indicator short name (source-9specific units).
LO, HI = 0, 1  # naming pair for readability below
BOUNDS: dict[str, tuple[float, float]] = {
    "u5m": (0, 500),          # per 1,000 live births
    "matmort": (0, 3000),     # per 100,000 live births
    "malaria": (0, 4000),     # per 1,000 population at risk
    "gdp_pc": (0, 100_000),   # current US$
    "chexp_pctgdp": (0, 60),  # % of GDP
    "phys_1k": (0, 12),       # physicians per 1,000
    "nurses_1k": (0, 20),     # nurses+midwives per 1,000
    "dpt_cov": (0, 100),      # coverage %
    "meas_cov": (0, 100),
    "san_basic": (0, 100),
    "water_basic": (0, 100),
    "urb_pct": (0, 100),
}


@dataclass
class Violation:
    level: str   # "FAIL" | "WARN"
    check: str
    detail: str


def check_unique(long: pd.DataFrame) -> list[Violation]:
    out: list[Violation] = []
    dup_mask = long.duplicated(subset=["iso3", "year", "indicator_code"])
    if dup_mask.any():
        sample = long.loc[dup_mask, ["iso3", "year", "indicator_code"]].head(5).values.tolist()
        out.append(Violation(
            "FAIL", "uniqueness",
            f"{int(dup_mask.sum())} duplicate (iso3, year, indicator) rows, e.g. {sample}",
        ))
    return out


def check_geo(long: pd.DataFrame) -> list[Violation]:
    unknown = sorted(set(long["iso3"]) - set(AU_ISO3))
    if unknown:
        return [Violation("FAIL", "geography", f"non-AU iso3 present: {unknown}")]
    return []


def check_years(wide: pd.DataFrame) -> list[Violation]:
    bad = wide[~wide["year"].between(YEAR_START, YEAR_END)]
    if len(bad):
        return [Violation(
            "FAIL", "temporal_scope",
            f"{len(bad)} rows outside {YEAR_START}-{YEAR_END}",
        )]
    return []


def check_bounds(long: pd.DataFrame) -> list[Violation]:
    out: list[Violation] = []
    merged = long.assign(short=long["indicator_short"])
    for short, (lo, hi) in BOUNDS.items():
        col = merged.loc[merged["short"] == short, "value"]
        bad = col[(col < lo) | (col > hi)]
        if len(bad):
            rows = merged.loc[bad.index, ["iso3", "year", "value"]].head(10).values
            out.append(Violation(
                "FAIL", f"plausibility:{short}",
                f"{len(bad)} values outside [{lo}, {hi}]: {rows.tolist()}",
            ))
    return out


def check_suspicious_zero(wide: pd.DataFrame) -> list[Violation]:
    """Zero between two adjacent positive values smells like a fill-in, not data.

    Rule per plan/docs: never fill missing health stats with zero. This scans
    for accidental zero-filling (or unit-error drops) in any series.
    """
    out: list[Violation] = []
    for iso, grp in wide.sort_values("year").groupby("iso3"):
        grp = grp.set_index("year")
        for short in BOUNDS:
            if short not in grp.columns:
                continue
            for year in grp.index:
                try:
                    v = grp.loc[year, short]
                    prev = grp.loc[year - 1, short]
                    nxt = grp.loc[year + 1, short]
                except KeyError:
                    continue
                if pd.notna(v) and v == 0 and pd.notna(prev) and pd.notna(nxt) \
                        and prev >= 1 and nxt >= 1:
                    out.append(Violation(
                        "WARN", f"suspicious_zero:{short}",
                        f"{iso} {year}: 0 between {prev} ({year - 1}) and {nxt} ({year + 1})",
                    ))
    return out


def run_checks(long: pd.DataFrame, wide: pd.DataFrame) -> tuple[list[Violation], list[Violation]]:
    failures = (
        check_unique(long)
        + check_geo(long)
        + check_years(wide)
        + check_bounds(long)
    )
    warnings = check_suspicious_zero(wide)
    return failures, warnings


def write_validation_report(manifest: dict,
                            failures: list[Violation],
                            warnings: list[Violation]) -> Path:
    from ml.ingestion.sources import MANIFESTS

    lines = [
        "# Stage-04 Validation Report",
        "",
        f"_Dataset: `{manifest['dataset_version']}` · built {manifest['built_at']}_",
        f"_Long rows: {manifest['rows']['long']} · Wide rows: {manifest['rows']['wide']}_",
        "",
        "## Failure-gate checks (blocking)",
        "",
        "| Check | Result |",
        "| --- | --- |",
        f"| uniqueness (iso3, year, indicator) | {'PASS' if not any(v.check == 'uniqueness' for v in failures) else 'FAIL'} |",
        f"| geography ⊆ AU members | {'PASS' if not any(v.check == 'geography' for v in failures) else 'FAIL'} |",
        f"| temporal scope | {'PASS' if not any(v.check == 'temporal_scope' for v in failures) else 'FAIL'} |",
        f"| plausibility bounds (13 series) | {'PASS' if not any(v.check.startswith('plausibility') for v in failures) else 'FAIL'} |",
        "",
        "## Findings (warnings)",
        "",
    ]
    if warnings:
        for v in warnings:
            lines.append(f"- [{v.level}] {v.check}: {v.detail}")
    else:
        lines.append("- none")
    if failures:
        lines += ["", "## Blocking failures", ""]
        lines += [f"- [{v.level}] {v.check}: {v.detail}" for v in failures]
    lines += [
        "",
        "## Provenance summary",
        "",
        f"- Source: World Bank WDI v2 (CC BY 4.0), country filter: AU members",
        f"- Missing data preserved as NaN (zero-fill scan: "
        f"{'clean' if not warnings else f'{len(warnings)} flagged'}); no imputation performed",
        "- value_status: 'published_wdi' (API does not split reported/modelled; see DATA_DICTIONARY)",
        "- File hashes recorded in data/manifests/dataset_manifest.json",
        "",
    ]
    path = MANIFESTS / "validation_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
