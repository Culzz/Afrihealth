"""/api/v1 router — every R1 endpoint of the frozen contract."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from services.api.app.core.config import settings
from services.api.app.schemas import (
    AtlasRow,
    Country,
    ForecastRow,
    Health,
    ReportRequest,
    SeriesRow,
)
from services.api.app.services import loader as L
from services.api.db import session as dbsession

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health", response_model=Health)
def health() -> Health:
    countries = len(L.countries_list())
    return Health(
        status="ok", app_env=settings.app_env,
        dataset_version=L.dataset_version(),
        data_max_year=L.current_model_meta().get("data_max_year", 0) or _data_max_year(),
        model_version=L.current_model_meta().get("model_version", "u5m-lgb-v1"),
        countries=countries,
        db="neon" if L.using_db() else "artifacts",
    )


def _data_max_year() -> int:
    rows = L.atlas_rows(L.atlas_year())
    return int(rows[0]["year"]) if rows else 0


@router.get("/countries", response_model=list[Country])
def countries() -> list[Country]:
    return sorted((Country(**c) for c in L.countries_list()), key=lambda c: c.country)


@router.get("/atlas", response_model=list[AtlasRow])
def atlas(year: int | None = None) -> list[AtlasRow]:
    y = year or L.atlas_year()
    rows = L.atlas_rows(y)
    if not rows:
        raise HTTPException(404, f"year {y} not in dataset")
    return [AtlasRow(**r) for r in rows]


@router.get("/countries/{iso3}/series", response_model=list[SeriesRow])
def series(iso3: str) -> list[SeriesRow]:
    rows = L.series_records(iso3)
    if not rows:
        raise HTTPException(404, f"unknown country {iso3}")
    return [SeriesRow(**r) for r in rows]


@router.get("/countries/{iso3}/forecasts", response_model=list[ForecastRow])
def forecasts(iso3: str) -> list[ForecastRow]:
    rows = L.forecast_records(iso3)
    if not rows:
        raise HTTPException(404, f"no forecasts for {iso3}")
    return [ForecastRow(**r) for r in rows]


@router.get("/models/current")
def current_model() -> dict:
    return L.current_model_meta()


@router.get("/model-card", response_class=PlainTextResponse)
def model_card() -> str:
    return L.model_card_text()


@router.get("/exports/panel.csv")
def export_panel() -> FileResponse:
    path = L.settings.data_dir / "processed" / "panel_wide.csv"
    return FileResponse(path, media_type="text/csv",
                        filename="afrihealth_panel_wide.csv")


@router.get("/db-status")
def db_status() -> dict:
    return {"database": "neon" if L.using_db() else "artifacts",
            "reachable": dbsession.ping() if L.using_db() else None}


@router.post("/reports")
def make_report(req: ReportRequest) -> FileResponse:
    """Reproducible PDF: observed series + forecasts + provenance + limits."""
    iso3 = req.iso3.upper()
    meta = L.current_model_meta()
    data = L.series_records(iso3)
    if not data:
        raise HTTPException(404, f"unknown country {iso3}")
    frows = L.forecast_records(iso3)
    country = frows[0]["country"] if frows else iso3

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdfcanvas

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, h - 2 * cm, f"AfriHealth — U5M report: {country}")
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, h - 2.7 * cm,
                 f"Dataset {L.dataset_version()} · model {meta['model_version']} · "
                 f"population-level decision support, NOT individual or clinical advice")
    y = h - 3.6 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Observed under-five mortality (most recent years)")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for r in data[-8:]:
        u5m = "-" if r["u5m"] is None else f"{r['u5m']:.1f}"
        cov = r["q_driver_coverage_pct"]
        c.drawString(2 * cm, y, f"{r['year']}:  U5M {u5m:>7}  driver coverage {cov:5.1f}%")
        y -= 0.5 * cm
    y -= 0.6 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Forecasts (registered model, intervals, exceedance)")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for fr in frows:
        c.drawString(2 * cm, y,
                     f"{fr['year']} (h={fr['horizon']}): {fr['yhat']:.1f} "
                     f"90% [{fr['lo90']:.1f}, {fr['hi90']:.1f}] "
                     f"P(U5M>70)={fr['p_gt_70']:.2f}")
        y -= 0.5 * cm
    if not frows:
        c.drawString(2 * cm, y, "No registered forecasts for this country.")
        y -= 0.5 * cm
    y -= 0.8 * cm
    c.setFont("Helvetica-Oblique", 8)
    for line in meta.get("limitations", [])[:4]:
        c.drawString(2 * cm, y, f"- {line}")
        y -= 0.4 * cm
    c.setFont("Helvetica", 8)
    c.drawString(2 * cm, 1.5 * cm,
                 f"Sources: World Bank WDI (CC BY 4.0) · every value traceable via "
                 f"dataset version + model version")
    c.showPage(); c.save()
    buf.seek(0)

    tmp = Path(tempfile.gettempdir()) / f"afrihealth_report_{iso3}.pdf"
    tmp.write_bytes(buf.read())
    return FileResponse(tmp, media_type="application/pdf",
                        filename=f"afrihealth_u5m_{iso3}.pdf")
