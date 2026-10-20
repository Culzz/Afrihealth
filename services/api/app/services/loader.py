"""Artifact loader — reads ONLY versioned, committed artifacts.

Dataset + registry artifacts are immutable versioned files; the API never
calls external sources live. DB layer arrives with ingestion cadence work
(R1.5); documented deviation in docs/DEPLOYMENT.md.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

from services.api.app.core.config import settings


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
