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


# ------------------------------------------------- Release 2 contract ------

class VulnerabilityRow(BaseModel):
    iso3: str
    country: str
    region: str = ""
    composite: float | None
    band: str | None
    components: dict[str, float | None]
    component_vintages: dict[str, int | None]
    missing_components: list[str]
    complete: bool
    jackknife_max_delta: float | None


class VulnerabilityArtifact(BaseModel):
    composite_version: str
    dataset_version: str
    year: int
    weights: dict[str, float]
    bands: dict[str, str]
    framework_note: str
    rows: list[VulnerabilityRow]


class AlertRow(BaseModel):
    iso3: str
    country: str
    year: int
    p_gt_70: float
    p_gt_50: float
    yhat: float
    lo90: float
    hi90: float
    reasons: list[str]


class AlertsResponse(BaseModel):
    as_of_year: int
    rule: str
    honesty_note: str
    rows: list[AlertRow]


class ComparisonColumn(BaseModel):
    iso3: str
    country: str
    region: str
    u5m_latest: float | None
    u5m_year: int
    trend_10y_pp: float | None
    forecast_2025: float | None
    forecast_2027: float | None
    interval_2025: list[float] | None
    p_gt_70_2025: float | None
    driver_coverage_pct: float | None
    vulnerability_band: str | None
    vulnerabilities: dict[str, float | None]


class ComparisonResponse(BaseModel):
    columns: list[ComparisonColumn]


class ScenarioRequest(BaseModel):
    class Intervention(BaseModel):
        driver: str
        delta: float
    iso3: str
    interventions: list[Intervention]


class ScenarioResponse(BaseModel):
    iso3: str
    target_year: int
    model_version: str | None
    baseline_registered: float | None
    yhat_registered_replay: float
    yhat_scenario: float
    delta: float
    interval_90_scenario: list[float]
    interval_note: str
    interventions_applied: dict[str, dict]
    interventions_unit_note: str
    honesty_note: str
