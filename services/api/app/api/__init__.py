"""/api/v1 router — every R1 endpoint of the frozen contract."""
from __future__ import annotations

import io
import json
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

router = APIRouter(prefix="/api/v1", tags=["v1"])

DRIVER_COLS = ["dpt_cov", "gdp_pc", "san_basic", "water_basic", "urb_pct"]


@router.get("/health", response_model=Health)
def health() -> Health:
    wide = L.panel_wide()
    manifest = L.dataset_manifest()
    meta = L.model_meta()
    y = L.atlas_year()
    countries = wide[wide["year"] == y]["iso3"].nunique()
    return Health(
        status="ok", app_env=settings.app_env,
        dataset_version=manifest["dataset_version"],
        data_max_year=int(wide["year"].max()),
        model_version=meta["model_version"],
        countries=int(countries),
    )


@router.get("/countries", response_model=list[Country])
def countries() -> list[Country]:
    wide = L.panel_wide()
    latest = L.atlas_year()
    rows = wide[wide["year"] == latest][["iso3", "country", "region"]
                                        ].drop_duplicates("iso3")
    out = [Country(**r) for r in rows.to_dict("records")]
    return sorted(out, key=lambda c: c.country)


@router.get("/atlas", response_model=list[AtlasRow])
def atlas(year: int | None = None) -> list[AtlasRow]:
    wide = L.panel_wide()
    y = year or L.atlas_year()
    if y not in wide["year"].unique():
        raise HTTPException(404, f"year {y} not in dataset")
    sel = wide[wide["year"] == y].drop_duplicates("iso3")
    out = []
    for r in sel.to_dict("records"):
        out.append(AtlasRow(
            iso3=r["iso3"], country=r["country"], region=r["region"], year=int(r["year"]),
            u5m=None if pd.isna(r["u5m"]) else float(r["u5m"]),
            driver_coverage_pct=float(r["q_driver_coverage_pct"]),
            target_missing=bool(r["q_target_missing"]),
            sparse_hwf_missing=bool(r["q_sparse_hwf_missing"]),
        ))
    return out


@router.get("/countries/{iso3}/series", response_model=list[SeriesRow])
def series(iso3: str) -> list[SeriesRow]:
    data = L.series_for(iso3.upper())
    if data.empty:
        raise HTTPException(404, f"unknown country {iso3}")
    out = []
    for r in data.to_dict("records"):
        out.append(SeriesRow(
            year=int(r["year"]),
            u5m=_num(r.get("u5m")),
            dpt_cov=_num(r.get("dpt_cov")),
            gdp_pc=_num(r.get("gdp_pc")),
            san_basic=_num(r.get("san_basic")),
            water_basic=_num(r.get("water_basic")),
            urb_pct=_num(r.get("urb_pct")),
            q_driver_coverage_pct=float(r["q_driver_coverage_pct"]),
        ))
    return out


@router.get("/countries/{iso3}/forecasts", response_model=list[ForecastRow])
def forecasts(iso3: str) -> list[ForecastRow]:
    rows = L.forecasts_for(iso3)
    if not rows:
        raise HTTPException(404, f"no forecasts for {iso3}")
    return [ForecastRow(**r) for r in rows]


@router.get("/models/current")
def current_model() -> dict:
    return L.model_meta()


@router.get("/model-card", response_class=PlainTextResponse)
def model_card() -> str:
    return L.model_card_text()


@router.get("/exports/panel.csv")
def export_panel() -> FileResponse:
    path = L.settings.data_dir / "processed" / "panel_wide.csv"
    return FileResponse(path, media_type="text/csv",
                        filename="afrihealth_panel_wide.csv")


@router.post("/reports")
def make_report(req: ReportRequest) -> FileResponse:
    """Reproducible PDF: observed series + forecasts + provenance + limits."""
    iso3 = req.iso3.upper()
    data = L.series_for(iso3)
    if data.empty:
        raise HTTPException(404, f"unknown country {iso3}")
    frows = L.forecasts_for(iso3)
    meta = L.model_meta()
    manifest = L.dataset_manifest()
    latest = L.atlas_year()

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdfcanvas

    country = data["country"].iloc[0]
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, h - 2 * cm, f"AfriHealth — U5M report: {country}")
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, h - 2.7 * cm,
                 f"Dataset {manifest['dataset_version']} · model {meta['model_version']} · "
                 f"population-level decision support, NOT individual or clinical advice")
    y = h - 3.6 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, "Observed under-five mortality (most recent years)")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for r in data.tail(8).to_dict("records"):
        u5m = "-" if pd.isna(r["u5m"]) else f"{r['u5m']:.1f}"
        cov = r["q_driver_coverage_pct"]
        c.drawString(2 * cm, y, f"{r['year']}:  U5M {u5m:>7}  driver coverage {cov:5.1f}%")
        y -= 0.5 * cm
    y -= 0.6 * cm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(2 * cm, y, f"Forecasts (registered model, intervals, exceedance)")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for fr in frows:
        c.drawString(2 * cm, y,
                     f"{fr['year']} (h={fr['horizon']}): {fr['yhat']:.1f} "
                     f"90% [{fr['lo90']:.1f}, {fr['hi90']:.1f}] "
                     f"P(U5M>70)={fr['p_gt_70']:.2f}")
        y -= 0.5 * cm
    y -= 0.8 * cm
    c.setFont("Helvetica-Oblique", 8)
    for line in meta["limitations"][:4]:
        c.drawString(2 * cm, y, f"- {line}")
        y -= 0.4 * cm
    c.setFont("Helvetica", 8)
    c.drawString(2 * cm, 1.5 * cm,
                 f"Generated {L.dataset_manifest()['built_at'][:10]} · sources: World Bank WDI (CC BY 4.0) "
                 f"· every value traceable via dataset+model versions")
    c.showPage(); c.save()
    buf.seek(0)

    tmp = Path(tempfile.gettempdir()) / f"afrihealth_report_{iso3}.pdf"
    tmp.write_bytes(buf.read())
    return FileResponse(tmp, media_type="application/pdf",
                        filename=f"afrihealth_u5m_{iso3}.pdf")


def _num(v) -> float | None:
    return None if v is None or pd.isna(v) else float(v)
