"""Read layer over Neon Postgres — mirrors the artifact loader's contract."""
from __future__ import annotations

import pandas as pd
from psycopg.rows import dict_row

from services.api.app.core.config import settings
from services.api.db.session import connect

DRIVERS = ["dpt_cov", "gdp_pc", "san_basic", "water_basic", "urb_pct"]


def atlas_year(conn) -> int:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT MAX(year) AS max_year FROM observations WHERE indicator = 'u5m' AND value IS NOT NULL")
        return int(cur.fetchone()["max_year"])


def countries(conn) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT iso3, country, region FROM countries
            WHERE iso3 IN (SELECT DISTINCT iso3 FROM country_year_meta
                           WHERE year = (SELECT MAX(year) FROM country_year_meta))
            ORDER BY country
            """)
        return [dict(r) for r in cur.fetchall()]


def atlas_rows(conn, year: int) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT cy.iso3, c.country, c.region, cy.year,
                   o.value AS u5m, cy.q_driver_coverage_pct,
                   cy.q_target_missing, cy.q_sparse_hwf_missing
            FROM country_year_meta cy
            JOIN countries c USING (iso3)
            LEFT JOIN observations o
                   ON o.iso3 = cy.iso3 AND o.year = cy.year AND o.indicator = 'u5m'
            WHERE cy.year = %s
            ORDER BY c.country
            """, (year,))
        return [dict(r) for r in cur.fetchall()]


def series(conn, iso3: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cols = ", ".join(
            f"MAX(o.value) FILTER (WHERE o.indicator = '{d}') AS {d}" for d in DRIVERS)
        cur.execute(
            f"""
            SELECT cy.year,
                   MAX(o.value) FILTER (WHERE o.indicator = 'u5m') AS u5m,
                   {cols},
                   cy.q_driver_coverage_pct
            FROM country_year_meta cy
            LEFT JOIN observations o ON o.iso3 = cy.iso3 AND o.year = cy.year
            WHERE cy.iso3 = %s
            GROUP BY cy.year, cy.q_driver_coverage_pct
            ORDER BY cy.year
            """, (iso3.upper(),))
        return [dict(r) for r in cur.fetchall()]


def forecasts_conn(conn, iso3: str) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT f.iso3, c.country, f.year, f.horizon, f.yhat, f.lo90, f.hi90,
                   f.p_gt_70, f.p_gt_50, f.last_observed_year,
                   f.drivers_default_missing, f.top_drivers_shap
            FROM forecasts f JOIN countries c USING (iso3)
            WHERE f.iso3 = %s ORDER BY f.year
            """, (iso3.upper(),))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["top_drivers_shap"] = d.pop("top_drivers_shap") or []
            rows.append(d)
        return rows


def meta(conn) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT key, value FROM registry_meta")
        return {r["key"]: r["value"] for r in cur.fetchall()}


def manifest(conn) -> dict:
    return meta(conn).get("dataset_manifest", {})


def model_meta(conn) -> dict:
    return meta(conn).get("model_meta", {})

