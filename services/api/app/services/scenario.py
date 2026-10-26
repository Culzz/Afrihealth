"""Counterfactual scenario simulation on the registered u5m-lgb-v1 model.

Honest-inference contract:
- Uses the SAME leak-safe feature recipe as training (`ml.features`): target
  lags are history, drivers are year t-1 values.
- Applies interventions to the t-1 driver values (they are what the model sees
  for a t forecast), as raw deltas (e.g. dpt_cov +10 percentage points).
- Single horizon only (h=1 is the only empirically validated horizon).
- The model treats missing values natively; interventions never invent data —
  a driver that is missing as input stays missing unless the user supplies it.
- Output is a MODEL-BEHAVIOUR quantity: "what the model would predict if these
  inputs changed" — explicitly NOT a causal effect estimate.
"""
from __future__ import annotations

import json
from functools import lru_cache

from services.api.app.services import loader as L

INTERVENABLE = ("dpt_cov", "san_basic", "water_basic", "gdp_pc", "chexp_pctgdp",
                "phys_1k", "nurses_1k", "meas_cov", "urb_pct")


@lru_cache(maxsize=1)
def _model():
    import joblib
    return joblib.load(L.settings.registry_dir / "model_v1.pkl")


class ScenarioError(ValueError):
    pass


def scenario_forecast(iso3: str,
                      interventions: list[dict] | None = None) -> dict:
    iso3 = iso3.upper()
    meta = L.current_model_meta()
    feats = list(meta.get("features") or [])
    if not feats:
        raise ScenarioError("model registry does not expose a feature list")

    # --- feature row exactly as ml.features.build_table would build it -------
    wide = L.panel_wide()
    c = wide[wide["iso3"] == iso3].sort_values("year")
    if c.empty:
        raise ScenarioError(f"unknown country {iso3}")

    base_year = L.atlas_year() + 1          # forecast target year
    vals: dict[str, object] = {"iso3": iso3, "year": base_year}

    u5m = dict(zip(c["year"], c["u5m"]))
    for lag in (1, 2, 3):
        vals[f"u5m_lag{lag}"] = u5m.get(base_year - lag)

    region = str(c.iloc[-1]["region"] or "")
    vals["region_afr"] = 1.0 if ("sub-saharan" in region.lower()
                                 or "africa" in region.lower()) else 0.0
    vals["region_mena"] = 1.0 if "middle east" in region.lower() or "mena" \
        in region.lower() else 0.0

    drivers = {d: dict(zip(c["year"], c[d])) for d in
               ("dpt_cov", "gdp_pc", "chexp_pctgdp", "phys_1k", "nurses_1k",
                "meas_cov", "san_basic", "water_basic", "urb_pct")}
    applied: dict[str, dict] = {}
    for iv in interventions or []:
        name = str(iv.get("driver", "")).strip()
        if name not in INTERVENABLE:
            raise ScenarioError(
                f"driver '{name}' is not interventable (allowed: {INTERVENABLE})")
        delta = float(iv.get("delta", 0))
        t1v = drivers[name].get(base_year - 1)
        if t1v is None:
            raise ScenarioError(
                f"{name} has no observed value at {base_year - 1} for {iso3}; "
                "scenarios cannot invent missing inputs (no-imputation rule)")
        if name == "gdp_pc":
            delta = t1v * delta / 100.0            # gdp_pc delta is a percent
        vals[f"{name}_p1"] = t1v + delta
        applied[name] = {"base": t1v, "delta": delta,
                         "scenario_value": t1v + delta}

    # drivers without interventions keep their observed t-1 values
    for d, series in drivers.items():
        vals.setdefault(f"{d}_p1", series.get(base_year - 1))

    x = {k: vals.get(k) for k in feats}
    import pandas as pd
    row = pd.DataFrame([x], columns=feats)
    yhat_baseline = float(_model().predict(row)[0])

    for name, info in applied.items():
        vals[f"{name}_p1"] = info["base"]
    row_base = pd.DataFrame([{k: vals.get(k) for k in feats}], columns=feats)
    yhat_reg = float(_model().predict(row_base)[0])

    unc = meta.get("uncertainty") or {}
    q90 = float(unc.get("q90h1", 0)) or (float(unc.get("sigma", 0)) * 0.3)

    return {
        "iso3": iso3, "target_year": base_year,
        "model_version": meta.get("model_version"),
        "baseline_registered": next((f["yhat"] for f in L.forecast_records(iso3)
                                     if f["year"] == base_year), None),
        "yhat_registered_replay": round(yhat_reg, 2),
        "yhat_scenario": round(yhat_baseline, 2),
        "delta": round(yhat_baseline - yhat_reg, 2),
        "interval_90_scenario": [round(yhat_baseline - q90, 1),
                                 round(yhat_baseline + q90, 1)],
        "interval_note": "empirical h=1 90% half-width applied to the scenario point",
        "interventions_applied": applied,
        "interventions_unit_note": "percents for coverage; absolute values for phys/nurses; % change for gdp_pc",
        "honesty_note": ("model-inferred counterfactual for horizon 1 only — "
                        "describes registered model behaviour, NOT a causal "
                        "estimate; policies take years to move drivers"),
    }
