"""Unit tests for the validation suite (no network, synthetic panels)."""
import pandas as pd

from ml.validation.checks import (
    check_bounds,
    check_geo,
    check_suspicious_zero,
    check_unique,
    check_years,
    run_checks,
)


def make_long(rows):
    return pd.DataFrame(
        rows, columns=["iso3", "year", "indicator_code", "indicator_short", "value"]
    )


def make_wide(rows):
    return pd.DataFrame(
        rows, columns=["iso3", "year", "u5m", "dpt_cov"]
    )


LONG_OK = make_long([
    ("NER", 2020, "SH.DYN.MORT", "u5m", 95.0),
    ("NER", 2021, "SH.DYN.MORT", "u5m", 92.0),
    ("NER", 2020, "SH.IMM.IDPT", "dpt_cov", 80.0),
])
WIDE_OK = make_wide([
    ("NER", 2020, 95.0, 80.0),
    ("NER", 2021, 92.0, 81.0),
])


def test_duplicates_fail():
    long = pd.concat([LONG_OK, LONG_OK.iloc[[0]]], ignore_index=True)
    v = check_unique(long)
    assert v and v[0].check == "uniqueness"


def test_non_au_geo_fails():
    long = make_long([("XYZ", 2020, "SH.DYN.MORT", "u5m", 10.0)])
    v = check_geo(long)
    assert v and v[0].check == "geography" and "XYZ" in v[0].detail


def test_year_out_of_scope_fails():
    wide = make_wide([("NER", 1999, 95.0, 80.0)])
    v = check_years(wide)
    assert v and v[0].check == "temporal_scope"


def test_plausibility_bounds_fail():
    long = make_long([("NER", 2020, "SH.IMM.IDPT", "dpt_cov", 150.0)])  # >100%
    v = check_bounds(long)
    assert v and v[0].check == "plausibility:dpt_cov"


def test_zero_between_positives_warns():
    wide = make_wide([
        ("NER", 2019, 95.0, 80.0),
        ("NER", 2020, 90.0, 0.0),   # zero fill-in smell between 80 and 82
        ("NER", 2021, 88.0, 82.0),
    ])
    v = check_suspicious_zero(wide)
    assert any(w.check == "suspicious_zero:dpt_cov" for w in v)


def test_legit_zero_not_flagged_at_edge():
    wide = make_wide([
        ("NER", 2019, 95.0, 0.0),   # at series edge: no right neighbor >= 1
        ("NER", 2021, 88.0, 82.0),
    ])
    # 2020 row missing => right neighbor lookup fails for 2019 -> no warning
    v = check_suspicious_zero(wide)
    assert v == []


def test_clean_panels_pass():
    failures, _ = run_checks(LONG_OK, WIDE_OK)
    assert failures == []
