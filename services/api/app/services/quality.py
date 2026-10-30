"""Data-quality and evidence monitor (R3, feature 1).

Extends the product's existing data-confidence layer and turns it into a
monitoring endpoint teams can review before submitting reports:
- coverage, freshness (years since last observation) and missingness per
  indicator over the recent window;
- suspicious year-over-year changes (larger jumps than plausible for annual
  program data, always flagged for human review — never silently corrected);
- dataset/artifact change tracking: hashes of every registry artifact compared
  against the last-marked snapshot, so teams can see what changed since their
  previous quarterly cycle.

Honesty rules: every flag is evidence-based and traceable to panel_wide.csv +
the dataset manifest; nothing is auto-corrected; suspicious changes are
flagged as "review", not as errors.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.api.app.services import loader as L

RECENT_WINDOW = 10            # last N years drive coverage/freshness
FRESH_LIMIT = 4               # older than this = stale flag
SUSPECT_JUMP_FRAC = 0.35      # |delta| > 35% of previous = review flag

INDICATORS = ["u5m", "dpt_cov", "san_basic", "water_basic", "gdp_pc",
              "urb_pct", "phys_1k", "nurses_1k", "chexp_pctgdp", "meas_cov"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def indicator_quality() -> dict:
    wide = L.panel_wide()
    latest = L.atlas_year()
    lo, hi = latest - RECENT_WINDOW + 1, latest
    per_indicator = []
    for ind in INDICATORS:
        window = wide[(wide["year"] >= lo) & (wide["year"] <= hi)]
        s = window[ind]
        n_cy = len(window)
        if n_cy == 0:
            continue
        coverage_pct = round(100.0 * s.notna().sum() / n_cy, 1)

        # per-country freshness: year of latest observation
        per_country = wide.dropna(subset=[ind]).groupby("iso3")["year"].max()
        stale = int((per_country < hi - FRESH_LIMIT).sum())
        observed = int(per_country.size)

        # suspicious jumps: |y - y-1| > SUSPECT_JUMP_FRAC * |y-1| (both present)
        jump_rows = []
        sub = wide.dropna(subset=[ind]).sort_values(["iso3", "year"])
        prev = sub.groupby("iso3")[ind].shift(1)
        delta = (sub[ind] - prev).abs()
        mask = (prev > 0) & (delta / prev.abs() > SUSPECT_JUMP_FRAC) & (delta > 0)
        flagged = sub[mask]
        for r in flagged.itertuples(index=False):
            jump_rows.append({"iso3": r.iso3, "year": int(r.year),
                              "note": "large year-over-year change — review "
                                      "source revision before comparing"})
        jump_rows = jump_rows[:12]
        per_indicator.append({
            "indicator": ind,
            "window": [lo, hi],
            "coverage_pct": coverage_pct,
            "countries_observed": observed,
            "stale_countries": stale,
            "missingness_pct": round(100.0 - coverage_pct, 1),
            "suspicious_changes": len(jump_rows),
            "suspicious_samples": jump_rows[:4],
            "definition_note": "values are last-observed within the freshness "
                               "window, never imputed; jumps are review flags, "
                               "not corrections",
        })

    wide_provider = wide[wide["iso3"] == "NGA"]   # placeholder: no exceptions
    del wide_provider
    return {"window": [lo, hi], "indicators": per_indicator}


def artifact_state() -> dict:
    reg = L.settings.registry_dir
    files = {}
    for name in ("model_meta.json", "forecasts.json", "vulnerability_v1.json"):
        p = reg / name
        if p.exists():
            files[name] = _sha(p)
    return {
        "dataset_version": L.dataset_version(),
        "model_version": (L.current_model_meta() or {}).get("model_version"),
        "artifacts": files,
    }


def state_snapshot() -> str:
    return json.dumps(artifact_state(), sort_keys=True)


def changes_since(snapshot: str | None) -> dict:
    current = artifact_state()
    if not snapshot:
        changed, what = False, []
        return {"changed": changed, "what": what, "current": current,
                "note": "no previous snapshot marked — this establishes the "
                        "baseline for future change detection"}
    try:
        prev = json.loads(snapshot)
    except json.JSONDecodeError:
        return {"changed": True, "what": ["previous snapshot unreadable"],
                "current": current, "note": "snapshot corrupted — treat as changed"}
    what = []
    if prev.get("dataset_version") != current["dataset_version"]:
        what.append(f"dataset_version {prev.get('dataset_version')} → "
                    f"{current['dataset_version']}")
    if prev.get("model_version") != current.get("model_version"):
        what.append(f"model_version {prev.get('model_version')} → "
                    f"{current.get('model_version')}")
    for name, sha in current["artifacts"].items():
        if prev.get("artifacts", {}).get(name) not in (None, sha):
            what.append(f"{name} content changed (sha256 {sha})")
    return {"changed": bool(what), "what": what, "current": current}
