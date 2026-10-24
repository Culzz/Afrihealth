"""Data façade — Neon Postgres when DATABASE_URL is set, artifacts otherwise.

The DB and the committed artifacts hold the SAME versioned data (the loader
script `services.api.db.load_neon` pushes artifact content into Postgres), so
responses are identical either way. Tests and local dev run artifact-only.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from services.api.app.core.config import settings


# ---------------------------------------------------------------- artifacts --
@lru_cache(maxsize=4)
def panel_wide() -> pd.DataFrame:
    return pd.read_csv(settings.data_dir / "processed" / "panel_wide.csv")


@lru_cache(maxsize=4)
def dataset_manifest() -> dict:
    return json.loads((settings.manifests_dir / "dataset_manifest.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def model_meta() -> dict:
    return json.loads((settings.registry_dir / "model_meta.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def forecasts() -> list[dict]:
    return json.loads((settings.registry_dir / "forecasts.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def model_card_text() -> str:
    return (settings.docs_dir / "MODEL_CARD.md").read_text(encoding="utf-8")


def atlas_year() -> int:
    wide = panel_wide()
    have = wide[wide["u5m"].notna()]["year"]
    return int(have.max())


def series_for(iso3: str) -> pd.DataFrame:
    wide = panel_wide()
    return wide[wide["iso3"] == iso3].sort_values("year")


def forecasts_for(iso3: str) -> list[dict]:
    return [f for f in forecasts() if f["iso3"] == iso3.upper()]


# ------------------------------------------------------------------ dispatch --
def _db():
    """Lazy import so artifact-only environments never need psycopg."""
    from services.api.db import read as R
    from services.api.db.session import connect
    return R, connect(settings.database_url)


def using_db() -> bool:
    return bool(settings.database_url)


def dataset_version() -> str:
    if using_db():
        R, conn = _db()
        with conn:
            m = R.manifest(conn)
        if m:
            return m["dataset_version"]
    return dataset_manifest()["dataset_version"]


def current_model_meta() -> dict:
    if using_db():
        R, conn = _db()
        with conn:
            m = R.model_meta(conn)
        if m:
            return m
    return model_meta()


def countries_list() -> list[dict]:
    if using_db():
        R, conn = _db()
        with conn:
            rows = R.countries(conn)
        if rows:
            return rows
    wide = panel_wide()
    latest = atlas_year()
    rows = wide[wide["year"] == latest][["iso3", "country", "region"]
                                        ].drop_duplicates("iso3")
    return rows.to_dict("records")


def atlas_rows(year: int) -> list[dict]:
    if using_db():
        R, conn = _db()
        with conn:
            rows = R.atlas_rows(conn, year)
        if rows:
            return [{
                "iso3": r["iso3"], "country": r["country"], "region": r["region"],
                "year": int(r["year"]),
                "u5m": None if r["u5m"] is None else float(r["u5m"]),
                "driver_coverage_pct": float(r["q_driver_coverage_pct"]),
                "target_missing": bool(r["q_target_missing"]),
                "sparse_hwf_missing": bool(r["q_sparse_hwf_missing"]),
            } for r in rows]
    wide = panel_wide()
    sel = wide[wide["year"] == year].drop_duplicates("iso3")
    out = []
    for r in sel.to_dict("records"):
        out.append({
            "iso3": r["iso3"], "country": r["country"], "region": r["region"],
            "year": int(r["year"]),
            "u5m": None if pd.isna(r["u5m"]) else float(r["u5m"]),
            "driver_coverage_pct": float(r["q_driver_coverage_pct"]),
            "target_missing": bool(r["q_target_missing"]),
            "sparse_hwf_missing": bool(r["q_sparse_hwf_missing"]),
        })
    return out


def series_records(iso3: str) -> list[dict]:
    iso3 = iso3.upper()
    if using_db():
        R, conn = _db()
        with conn:
            rows = R.series(conn, iso3)
        if rows:
            return rows
    data = series_for(iso3)
    out = []
    for r in data.to_dict("records"):
        rec = {"year": int(r["year"]), "q_driver_coverage_pct": float(r["q_driver_coverage_pct"])}
        for col in ("u5m", "dpt_cov", "gdp_pc", "san_basic", "water_basic", "urb_pct"):
            v = r.get(col)
            rec[col] = None if v is None or pd.isna(v) else float(v)
        out.append(rec)
    return out


def forecast_records(iso3: str) -> list[dict]:
    iso3 = iso3.upper()
    if using_db():
        R, conn = _db()
        with conn:
            rows = R.forecasts_conn(conn, iso3)
        if rows:
            return rows
    return [f for f in forecasts() if f["iso3"] == iso3]
