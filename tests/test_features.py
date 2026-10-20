"""Leakage and integrity tests for feature construction (synthetic, no network)."""
import numpy as np
import pandas as pd

from ml.ingestion.sources import DRIVERS
from ml.features.features import build_table, features_matrix, all_features


def wide_fixture() -> pd.DataFrame:
    rows = []
    for iso3, base in (("NER", 110.0), ("DZA", 40.0)):
        for year in range(2005, 2010):
            drift = -1.5 * (year - 2005)
            row = {
                "iso3": iso3, "country": iso3,
                "region": "Sub-Saharan Africa (excluding high income)",
                "year": year,
                "u5m": base + drift,
                "dpt_cov": 70.0 + 0.5 * (year - 2005),
                "urb_pct": 30.0,
            }
            # give every remaining driver a constant value so the table builds
            for d in DRIVERS:
                row[d] = 500.0
            rows.append(row)
    wide = pd.DataFrame(rows)
    # planted gap: NER in 2007 has no observed u5m (NaN in the panel, as built)
    wide.loc[(wide["iso3"] == "NER") & (wide["year"] == 2007), "u5m"] = np.nan
    return wide


def test_lag_uses_raw_prior_year():
    wide = wide_fixture()
    table = build_table(wide)
    row = table[(table["iso3"] == "NER") & (table["year"] == 2009)].iloc[0]
    raw = wide.set_index(["iso3", "year"])
    assert row["u5m_lag1"] == raw.loc[("NER", 2008), "u5m"]


def test_missing_year_propagates_as_nan():
    table = build_table(wide_fixture())
    row = table[(table["iso3"] == "NER") & (table["year"] == 2008)].iloc[0]
    # 2007 u5m was never imputed/zero-filled -> lag1 for 2008 is NaN, not 0
    assert pd.isna(row["u5m_lag1"])
    # and the year with no target is absent from the modeling table
    assert ((table["iso3"] == "NER") & (table["year"] == 2007)).sum() == 0


def test_driver_is_one_year_behind_target():
    table = build_table(wide_fixture())
    row = table[(table["iso3"] == "NER") & (table["year"] == 2009)].iloc[0]
    raw = wide_fixture().set_index(["iso3", "year"])
    assert row["dpt_cov_p1"] == raw.loc[("NER", 2008), "dpt_cov"]


def test_no_same_year_feature_columns():
    table = build_table(wide_fixture())
    _, _, cols = features_matrix(table)
    leakage_names = {"target", "u5m"} | {d for d in DRIVERS}  # same-year columns
    offending = [c for c in cols if c in leakage_names]
    assert not offending, f"same-year leakage features present: {offending}"
    # every feature must be history (_lagN), prior-year (_p1), a region, or year index
    for c in cols:
        ok = (c == "year" or c.startswith("region_")
              or "_lag" in c or "_p1" in c)
        assert ok, f"unclassified feature column: {c}"
