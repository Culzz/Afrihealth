"""Feature construction for under-five mortality forecasting (Stage 05).

Leakage policy (test-enforced):
- Target: u5m at year t.
- History features: u5m lags 1..3 (suffix `_lagN`) — strictly years < t.
- Driver features: value at year t-1 (suffix `_p1`) — strictly years < t.
- No feature may touch data from year t. NaNs are preserved, never imputed
  (XGBoost/LightGBM treat missing values natively; "no hidden imputation" rule).
"""
from __future__ import annotations

import pandas as pd

from ml.ingestion.sources import DRIVERS

TARGET = "u5m"
LAGS = (1, 2, 3)
REGION_BUCKETS = ("afr", "mena")


def history_only_features() -> list[str]:
    return [f"{TARGET}_lag{lag}" for lag in LAGS] + ["year"]


def driver_features() -> list[str]:
    return [f"{d}_p1" for d in DRIVERS]


def all_features() -> list[str]:
    return (
        history_only_features()
        + [f"region_{b}" for b in REGION_BUCKETS]
        + driver_features()
    )


def _region_bucket(region: object) -> str:
    text = str(region or "").lower()
    if "middle east" in text or "mena" in text:
        return "mena"
    if "sub-saharan" in text or "africa" in text:
        return "afr"
    return "other"


def build_table(wide: pd.DataFrame) -> pd.DataFrame:
    """One row per (iso3, target year): the supervised modeling table."""
    df = wide.sort_values(["iso3", "year"]).copy()
    df["region_bucket"] = df["region"].map(_region_bucket)
    df["target"] = df[TARGET]

    # History-only features: strictly prior-year target values
    for lag in LAGS:
        df[f"{TARGET}_lag{lag}"] = df.groupby("iso3")[TARGET].shift(lag)

    # Drivers as known one year earlier (t-1); NaNs preserved, never filled
    for d in DRIVERS:
        if d in df.columns:
            df[f"{d}_p1"] = df.groupby("iso3")[d].shift(1)

    base_cols = ["iso3", "country", "region_bucket", "year", "target"]
    keep = base_cols + history_only_features() + driver_features()
    keep = list(dict.fromkeys(keep))  # dedupe, preserve order
    out = df[keep].reset_index(drop=True)

    dummies = pd.get_dummies(out["region_bucket"], prefix="region",
                             prefix_sep="_", dtype=float)
    out = pd.concat([out.drop(columns=["region_bucket"]), dummies], axis=1)

    # Ensure both region columns exist even in tiny synthetic fixtures
    for col in (f"region_{b}" for b in REGION_BUCKETS):
        if col not in out.columns:
            out[col] = 0.0

    out = out[out["target"].notna()].reset_index(drop=True)
    return out


def features_matrix(
    table: pd.DataFrame, use_drivers: bool = True
) -> tuple[pd.DataFrame, "pd.Series", list[str]]:
    """X/y split honoring the leakage-safe feature list.\n"""
    cols = list(all_features()) if use_drivers else list(history_only_features()) + [
        f"region_{b}" for b in REGION_BUCKETS
    ]
    cols = [c for c in cols if c in table.columns]
    X = table[cols]
    y = table["target"]
    return X, y, cols
