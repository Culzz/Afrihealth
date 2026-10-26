"""Release-2 endpoints: vulnerability composite, alerts, briefs, comparisons,
scenario counterfactuals. Same honesty rules as the frozen R1 contract:
deterministic, artifact/registry-backed, no imputation, explicit limitations.
"""
from __future__ import annotations

from services.api.app.schemas import (
    AlertsResponse,
    AlertRow,
    ComparisonColumn,
    ComparisonResponse,
    ScenarioRequest,
    ScenarioResponse,
    VulnerabilityArtifact,
    VulnerabilityRow,
)
from services.api.app.services import loader as L
from services.api.app.services.scenario import ScenarioError, scenario_forecast

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/v1", tags=["v2"])


@router.get("/vulnerability", response_model=VulnerabilityArtifact)
def vulnerability() -> VulnerabilityArtifact:
    v = L.vulnerability()
    return VulnerabilityArtifact(**v)


@router.get("/vulnerability/{iso3}", response_model=VulnerabilityRow)
def vulnerability_country(iso3: str) -> VulnerabilityRow:  # verbatim row
    row = L.vulnerability_row(iso3)
    if not row:
        raise HTTPException(404, f"unknown country {iso3}")
    return VulnerabilityRow(**row)


@router.get("/alerts", response_model=AlertsResponse)
def alerts() -> AlertsResponse:
    """Deterministic decision-support watchlist — NOT outbreak surveillance."""
    w = L.vulnerability()
    band = {r["iso3"]: (r["band"], r["components"]) for r in w["rows"]}
    rows: list[AlertRow] = []
    for f in L.forecasts():
        if f["year"] != w["year"] + 1 or f["p_gt_70"] is None:
            continue
        iso3 = f["iso3"]
        reasons = [f"P(u5m stays above 70) = {f['p_gt_70']} for {f['year']}"]
        b, comps = band.get(iso3, (None, {}))
        if b in ("high", "elevated"):
            reasons.append(f"vulnerability band: {b}")
        if f.get("drivers_default_missing"):
            reasons.append("forward-year drivers unobserved — model carries "
                           "history forward (assumption, not data)")
        atl = next((a for a in (L.vulnerability()["rows"]) if a["iso3"] == iso3), None)
        weakest = sorted(
            ((k, v) for k, v in (atl["components"] or {}).items()
             if v is not None and k not in ("u5m_observing", "u5m_forecast")),
            key=lambda kv: -kv[1])
        if weakest:
            reasons.append(f"weakest capacity: {weakest[0][0]} vs peers")
            reasons.append((
                "model behaviour, not causation; population-level decision "
                "support, not surveillance"))
        rows.append(AlertRow(
            iso3=iso3, country=f["country"], year=f["year"],
            p_gt_70=f["p_gt_70"], p_gt_50=f["p_gt_50"],
            yhat=f["yhat"], lo90=f["lo90"], hi90=f["hi90"],
            reasons=reasons[:3]))
    rows.sort(key=lambda r: r.p_gt_70, reverse=True)
    rows = rows[:10]
    return AlertsResponse(
        as_of_year=w["year"],
        rule=("top registered h1 forecasts where P(u5m>70) is at least 0.5; "
              "why-rule text is derived from the vuln-v1 composite and driver "
              "coverage flags"),
        honesty_note=("deterministic decision-support watchlist from registered "
                      "forecasts, NOT outbreak surveillance or clinical advice; "
                      "P values are model outputs, not measured event risks"),
        rows=rows)


def _trend_pp(iso3: str, years: int = 10) -> float | None:
    s = L.series_for(iso3).dropna(subset=["u5m"])
    s = s[s["year"] >= L.atlas_year() - years]
    if len(s) < 2:
        return None
    import pandas as pd
    import numpy as np
    x = pd.Series(s["year"].values, dtype=float)
    y = pd.Series(s["u5m"].values, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    return round(slope * (11 - 1), 1)


@router.get("/comparisons", response_model=ComparisonResponse)
def comparisons(iso3: str) -> ComparisonResponse:
    """Side-by-side bundle for up to 4 countries (comma-separated codes)."""
    codes = [c.strip().upper() for c in iso3.split(",") if c.strip()][:4]
    if not codes:
        raise HTTPException(422, "provide ?iso3=NGA,ETH")
    cols: list[ComparisonColumn] = []
    fc = {f["iso3"]: f for f in L.forecasts()}
    for code in codes:
        name = L.vulnerability_row(code)
        atlas_year = L.atlas_year()
        latest_series = next(
            (r for r in reversed(L.series_records(code))
             if r.get("u5m") is not None), None)
        f25 = fc.get(code)
        f27 = next((f for f in L.forecast_records(code) if f["year"] ==
                    atlas_year + 3), None)
        cols.append(ComparisonColumn(
            iso3=code,
            country=name["country"] if name else code,
            region=name["region"] if name else "",
            u5m_latest=latest_series["u5m"] if latest_series else None,
            u5m_year=latest_series["year"] if latest_series else atlas_year,
            trend_10y_pp=_trend_pp(code),
            forecast_2025=f25["yhat"] if f25 else None,
            forecast_2027=f27["yhat"] if f27 else None,
            interval_2025=[f25["lo90"], f25["hi90"]] if f25 else None,
            p_gt_70_2025=f25["p_gt_70"] if f25 else None,
            driver_coverage_pct=latest_series["q_driver_coverage_pct"] if latest_series else None,
            vulnerability_band=name["band"] if name else None,
            vulnerabilities=name["components"] if name else {},
        ))
    return ComparisonResponse(columns=cols)


@router.get("/countries/{iso3}/brief", response_class=PlainTextResponse)
def brief(iso3: str) -> str:
    """Deterministic auto-briefing: template narrative from registered data."""
    iso3 = iso3.upper()
    series = [r for r in L.series_records(iso3) if r.get("u5m") is not None]
    if not series:
        raise HTTPException(404, f"no observed series for {iso3}")
    frows = L.forecast_records(iso3)
    meta = L.current_model_meta()
    vul = L.vulnerability_row(iso3)
    first, last = series[0], series[-1]
    change = (last["u5m"] - first["u5m"])
    pct = change / first["u5m"] * 100.0
    trend = _trend_pp(iso3)
    lines = []
    name = frows[0]["country"] if frows else iso3
    lines.append(f"{name} — auto-brief (template narrative; "
                 f"dataset {L.dataset_version()})")
    lines.append("")
    lines.append(
        f"Observed: under-five mortality fell from {first['u5m']} in "
        f"{first['year']} to {last['u5m']} in {last['year']} "
        f"({pct:+.1f}%; avg trend {trend:+.1f} pp over the last decade).")
    if frows:
        f1 = frows[0]
        lo = min(f["lo90"] for f in frows)
        hi = max(f["hi90"] for f in frows)
        lines.append(
            f"Forecast ({meta.get('model_version')}): {f1['yhat']} in "
            f"{f1['year']}; 2025-27 range spans {lo}-{hi} across the 90% "
            f"intervals; the model keeps P(u5m>70) at {f1['p_gt_70']} in "
            f"{f1['year']}.")
        top = (f1.get("top_drivers_shap") or [])[:2]
        if top:
            words = ", ".join(f"{d['feature']} ({d['shap']:+.1f})" for d in top)
            lines.append(f"Main model drivers: {words}. Attribution describes "
                         "model behaviour, not causation.")
        if f1.get("drivers_default_missing"):
            lines.append("Note: forward-year drivers are unobserved for later "
                         "horizons — the model carries history forward "
                         "(assumption, not data).")
    if vul:
        weakest = sorted(((k, v) for k, v in vul["components"].items()
                          if v is not None and k not in
                          ("u5m_observing", "u5m_forecast")),
                         key=lambda kv: -kv[1])
        lines.append(
            f"Vulnerability ({vul and 'vuln-v1'}): composite "
            f"{vul['composite']} ({vul['band']}); weakest recorded capacity "
            f"vs peers: {weakest[0][0] if weakest else 'n/a'}. Complete data: "
            f"{'yes' if vul['complete'] else 'no — ' + ', '.join(vul['missing_components'])}.")
    cov = last.get("q_driver_coverage_pct")
    lines.append(f"Data confidence: {cov}% of expected drivers observed in the "
                 f"latest year; missing values stay flagged, never filled.")
    lines.append("")
    lines.append("Limits: population-level decision support — not clinical or "
                 "surveillance guidance; horizon-1 is the only empirically "
                 "validated horizon.")
    return "\n".join(lines) + "\n"


@router.post("/scenarios", response_model=ScenarioResponse)
def scenarios(req: ScenarioRequest) -> ScenarioResponse:
    try:
        out = scenario_forecast(req.iso3,
                                [i.model_dump() for i in req.interventions])
        return ScenarioResponse(**out)
    except ScenarioError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001 — surfaces model-load problems honestly
        raise HTTPException(501,
                            f"scenario runtime unavailable: {e!r}"[:300])
