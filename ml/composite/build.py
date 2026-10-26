"""Health-system vulnerability composite (Release 2, layer 3).

A transparent, sensitivity-tested, deterministic composite that flags where
under-five mortality burden meets weak service capacity, for the 54 AU
countries. Every input is a percentile rank; every weight is declared; every
component carries its own data vintage (drivers lag: workforce data stop at
2022 while burden runs to 2024), and a jackknife records each country's
worst sensitivity to dropping a component.

Framework rules (enforced by tests):
- No imputation: values are last-observed within a freshness window, as-is —
  never interpolated; a country without ANY value for a component (since the
  max vintage year) keeps that component genuinely missing and weights are
  renormalised over the rest, with `complete: false`.
- Determinism: identical inputs -> identical output.
- Composite published as ml/registry/vulnerability_v1.json with sha256
  provenance, versioned `vuln-v1`, in the same registry spirit as model cards.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

TARGET_DRIVERS_CAP = ["phys_1k", "nurses_1k", "dpt_cov", "san_basic",
                      "water_basic", "chexp_pctgdp"]

# Declared v1 weights (documented in MODEL_CARD.md). Burden ~40%, capacity ~60%.
WEIGHTS = {
    "u5m_observing": 0.25,     # adverse: current under-five mortality
    "u5m_forecast": 0.15,      # adverse: 2025 registered forecast
    "phys_1k": 0.15,           # capacity deficits (higher raw value = safer)
    "nurses_1k": 0.10,
    "dpt_cov": 0.10,
    "san_basic": 0.10,
    "water_basic": 0.10,
    "chexp_pctgdp": 0.05,
}

# Component extraction policy: newest value per country within the window.
MIN_VINTAGE = 2018          # nothing older than this may enter
CAP_COMPONENTS = ("phys_1k", "nurses_1k", "dpt_cov", "san_basic",
                  "water_basic", "chexp_pctgdp")

REPO = Path(__file__).resolve().parents[2]
PANEL = REPO / "data" / "processed" / "panel_wide.csv"
REGISTRY = REPO / "ml" / "registry"
OUT = REGISTRY / "vulnerability_v1.json"

BANDS = [(0.20, "low"), (0.50, "watch"), (0.80, "elevated"), (1.01, "high")]


def _band(p: float) -> str:
    for hi, name in BANDS:
        if p < hi:
            return name
    return "high"


def _composite_from(parts: dict[str, float]) -> tuple[float | None, list[str]]:
    available = {k: v for k, v in parts.items() if v is not None}
    if not available:
        return None, list(WEIGHTS)
    missing = [k for k in WEIGHTS if k not in available]
    total_w = sum(WEIGHTS[k] for k in available)
    return sum(available[k] * WEIGHTS[k] for k in available) / total_w, missing


def _jackknife(available: dict[str, float], composite: float) -> float | None:
    if len(available) < 2:
        return None
    deltas = []
    for k in list(available):
        subset = {j: v for j, v in available.items() if j != k}
        w2 = sum(WEIGHTS[j] for j in subset)
        if w2 <= 0:
            continue
        c2 = sum(subset[j] * WEIGHTS[j] for j in subset) / w2
        deltas.append(abs(c2 - composite))
    return max(deltas) if deltas else None


def build_vulnerability(forecasts_path: Path | None = None,
                        out_path: Path = OUT) -> dict:
    wide = pd.read_csv(PANEL)
    # Anchor year: the latest year with a real burden cross-section (>= 40
    # countries with observed u5m). Calendar stubs with null targets are skipped.
    counts = wide.groupby("year")["u5m"].apply(lambda s: s.notna().sum())
    latest = int(counts[counts >= 40].index.max())
    fpath = forecasts_path or (REGISTRY / "forecasts.json")
    fdf = pd.DataFrame(json.loads(Path(fpath).read_text()))
    fyear = latest + 1
    fdf = fdf[fdf["year"] == fyear][["iso3", "yhat"]] \
        .rename(columns={"yhat": "u5m_forecast"})
    countries = wide[wide["year"] == latest][["iso3", "country", "region"]] \
        .drop_duplicates("iso3")
    names = countries.set_index("iso3")["country"].to_dict()
    regions = countries.set_index("iso3")["region"].to_dict()

    # ---- component values: per-country latest value since MIN_VINTAGE ------
    values: dict[str, dict[str, float]] = {c: {} for c in WEIGHTS}
    vintages: dict[str, dict[str, int]] = {c: {} for c in WEIGHTS}

    obs = wide[wide["year"] == latest][["iso3", "u5m"]].dropna()
    for iso3, v in obs.itertuples(index=False):
        values["u5m_observing"][iso3] = float(v)
        vintages["u5m_observing"][iso3] = latest

    fc = fdf.dropna()
    for iso3, v in fc.itertuples(index=False):
        values["u5m_forecast"][iso3] = float(v)
        vintages["u5m_forecast"][iso3] = fyear

    hist = wide[wide["year"] >= MIN_VINTAGE].sort_values(["iso3", "year"])
    for c in CAP_COMPONENTS:
        sub = hist[hist[c].notna()]
        for iso3, g in sub.groupby("iso3"):
            last = g.iloc[-1]
            values[c][iso3] = float(last[c])
            vintages[c][iso3] = int(last["year"])

    # ---- percentile ranks over available cross-sections --------------------
    ranks: dict[str, dict[str, float]] = {c: {} for c in WEIGHTS}
    for c in WEIGHTS:
        s = pd.Series(values[c], dtype=float)
        if len(s) >= 2:
            r = s.rank(pct=True, method="average") * 100.0
            if c in CAP_COMPONENTS:
                r = 100.0 - r          # invert capacity: 100 = weakest
            ranks[c] = r.to_dict()

    rows = []
    for iso3, country in names.items():
        parts = {c: ranks[c].get(iso3) for c in WEIGHTS}
        composite, missing = _composite_from(parts)
        avail = {k: v for k, v in parts.items() if v is not None}
        jk = _jackknife(avail, composite) if composite is not None else None
        rows.append({
            "iso3": iso3, "country": country, "region": regions.get(iso3, ""),
            "composite": None if composite is None else round(composite, 1),
            "band": None if composite is None else _band(composite),
            "components": {k: (None if v is None else round(v, 1))
                           for k, v in parts.items()},
            "component_vintages": {k: vintages[k].get(iso3) for k in WEIGHTS},
            "missing_components": missing,
            "complete": not missing,
            "jackknife_max_delta": None if jk is None else round(float(jk), 1),
        })
    rows.sort(key=lambda x: (x["composite"] is None, -(x["composite"] or 0)))

    manifest_p = REPO / "data" / "manifests" / "dataset_manifest.json"
    dataset_version = "unknown"
    if manifest_p.exists():
        dataset_version = json.loads(manifest_p.read_text()).get(
            "dataset_version", "unknown")

    artifact = {
        "composite_version": "vuln-v1",
        "dataset_version": dataset_version,
        "year": latest,
        "weights": WEIGHTS,
        "policy": {
            "components": ("newest observed value per country since "
                           f"{MIN_VINTAGE}, as-is (no interpolation)"),
            "fyear_forecast": fyear,
            "percentile_method": "average ranks over available cross-section",
            "capacity_inversion": ("phys/nurses/dpt/san/water/chexp inverted so "
                                   "100 = weakest recorded capacity"),
        },
        "bands": {"low": "<20", "watch": "20-50", "elevated": "50-80",
                  "high": ">=80"},
        "framework_note": ("population-level decision support, NOT a diagnosis "
                           "or surveillance instrument; the composite describes "
                           "recorded data, not future outcomes"),
        "provenance": {
            "panel": "data/processed/panel_wide.csv",
            "forecasts": "ml/registry/forecasts.json (u5m-lgb-v1)",
        },
        "rows": rows,
    }
    out_path.write_text(json.dumps(artifact, indent=1), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    a = build_vulnerability()
    complete = sum(1 for r in a["rows"] if r["complete"])
    print(f"vulnerability_v1: {len(a['rows'])} countries, year {a['year']}, "
          f"complete components for {complete}")
    print(json.dumps(a["rows"][:2], indent=1)[:900])
    _OUT = OUT.read_bytes()
    import hashlib as _h
    print("sha256:", _h.sha256(_OUT).hexdigest()[:16])
