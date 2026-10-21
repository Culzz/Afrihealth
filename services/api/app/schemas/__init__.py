"""Pydantic response schemas — the frozen /api/v1 contract."""
from __future__ import annotations

from pydantic import BaseModel


class Health(BaseModel):
    status: str
    app_env: str
    dataset_version: str
    data_max_year: int
    model_version: str
    countries: int
    db: str = "artifacts"


class Country(BaseModel):
    iso3: str
    country: str
    region: str


class AtlasRow(BaseModel):
    iso3: str
    country: str
    region: str
    year: int
    u5m: float | None
    driver_coverage_pct: float
    target_missing: bool
    sparse_hwf_missing: bool


class SeriesRow(BaseModel):
    year: int
    u5m: float | None
    dpt_cov: float | None
    gdp_pc: float | None
    san_basic: float | None
    water_basic: float | None
    urb_pct: float | None
    q_driver_coverage_pct: float


class ShapDriver(BaseModel):
    feature: str
    shap: float


class ForecastRow(BaseModel):
    iso3: str
    country: str
    year: int
    horizon: int
    yhat: float
    lo90: float
    hi90: float
    p_gt_70: float
    p_gt_50: float
    last_observed_year: int
    drivers_default_missing: bool
    top_drivers_shap: list[ShapDriver]


class ReportRequest(BaseModel):
    iso3: str
