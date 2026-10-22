"""Load artifact content into Neon Postgres (run locally, one-off per version).

    .venv\Scripts\python -m services.api.db.load_neon --url "postgresql://...neon.tech/neondb?sslmode=require"

Idempotent: applies schema then upserts the current artifact set. Preserves
provenance: every observation keeps indicator/unit/source; quality flags are
first-class rows. The API serves the same data from either store.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_SQL = (REPO / "services" / "api" / "db" / "schema.sql").read_text(encoding="utf-8")
UPSERT_OBS = """
INSERT INTO observations (iso3, year, indicator, value, unit, source, source_url)
VALUES (%(iso3)s, %(year)s, %(indicator)s, %(value)s, %(unit)s, %(source)s, %(source_url)s)
ON CONFLICT (iso3, year, indicator) DO UPDATE
SET value = EXCLUDED.value, unit = EXCLUDED.unit, source = EXCLUDED.source,
    source_url = EXCLUDED.source_url
"""
UPSERT_CY = """
INSERT INTO country_year_meta (iso3, year, q_driver_coverage_pct,
                               q_target_missing, q_sparse_hwf_missing)
VALUES (%(iso3)s, %(year)s, %(q_driver_coverage_pct)s, %(q_target_missing)s, %(q_sparse_hwf_missing)s)
ON CONFLICT (iso3, year) DO UPDATE
SET q_driver_coverage_pct = EXCLUDED.q_driver_coverage_pct,
    q_target_missing = EXCLUDED.q_target_missing,
    q_sparse_hwf_missing = EXCLUDED.q_sparse_hwf_missing
"""
UPSERT_FC = """
INSERT INTO forecasts (iso3, year, horizon, yhat, lo90, hi90, p_gt_70, p_gt_50,
                       last_observed_year, last_observed_u5m,
                       drivers_default_missing, sparse_hwf_missing, top_drivers_shap)
VALUES (%(iso3)s, %(year)s, %(horizon)s, %(yhat)s, %(lo90)s, %(hi90)s,
        %(p_gt_70)s, %(p_gt_50)s, %(last_observed_year)s, %(last_observed_u5m)s,
        %(drivers_default_missing)s, %(sparse_hwf_missing)s,
        %(top_drivers_shap)s::jsonb)
ON CONFLICT (iso3, year) DO UPDATE
SET horizon = EXCLUDED.horizon, yhat = EXCLUDED.yhat, lo90 = EXCLUDED.lo90,
    hi90 = EXCLUDED.hi90, p_gt_70 = EXCLUDED.p_gt_70, p_gt_50 = EXCLUDED.p_gt_50,
    last_observed_year = EXCLUDED.last_observed_year,
    last_observed_u5m = EXCLUDED.last_observed_u5m,
    drivers_default_missing = EXCLUDED.drivers_default_missing,
    sparse_hwf_missing = EXCLUDED.sparse_hwf_missing,
    top_drivers_shap = EXCLUDED.top_drivers_shap
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Neon pooled connection string (or set NEON_URL)")
    args = ap.parse_args()
    url = args.url or os.environ.get("NEON_URL", "")
    if not url:
        print("No Neon URL given (--url or NEON_URL env).")
        return 2

    import psycopg

    wide = pd.read_csv(REPO / "data" / "processed" / "panel_wide.csv")
    long_df = pd.read_csv(REPO / "data" / "processed" / "panel_long.csv")
    forecast_rows = json.loads((REPO / "ml" / "registry" / "forecasts.json").read_text(encoding="utf-8"))
    model_meta = json.loads((REPO / "ml" / "registry" / "model_meta.json").read_text(encoding="utf-8"))
    manifest = json.loads((REPO / "data" / "manifests" / "dataset_manifest.json").read_text(encoding="utf-8"))

    obs_records = []
    for r in long_df.to_dict("records"):
        v = r.get("value")
        iso = r.get("iso3")
        if iso is None:
            continue
        obs_records.append({
            "iso3": iso, "year": int(r["year"]), "indicator": r["indicator_short"],
            "value": None if v is None or pd.isna(v) else float(v),
            "unit": r.get("unit"), "source": r.get("source", "unknown"),
            "source_url": r.get("source_url"),
        })

    cy_records = []
    for r in wide.to_dict("records"):
        cy_records.append({
            "iso3": r["iso3"], "year": int(r["year"]),
            "q_driver_coverage_pct": float(r.get("q_driver_coverage_pct") or 0),
            "q_target_missing": bool(r.get("q_target_missing")),
            "q_sparse_hwf_missing": bool(r.get("q_sparse_hwf_missing")),
        })

    countries = (wide[["iso3", "country", "region"]
                       ].drop_duplicates("iso3").to_dict("records"))

    fc_records = []
    for f in forecast_rows:
        g = dict(f)
        g["top_drivers_shap"] = json.dumps(f.get("top_drivers_shap", []))
        fc_records.append(g)

    with psycopg.connect(url, sslmode="require", autocommit=False) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)

        for c in countries:
            cur.execute(
                "INSERT INTO countries (iso3, country, region) VALUES (%s, %s, %s) "
                "ON CONFLICT (iso3) DO UPDATE SET country = EXCLUDED.country, region = EXCLUDED.region",
                (c["iso3"], c["country"], c["region"]))

        cur.executemany(UPSERT_OBS, obs_records)
        cur.executemany(UPSERT_CY, cy_records)
        cur.executemany(UPSERT_FC, fc_records)

        cur.execute(
            "INSERT INTO registry_meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("model_meta", json.dumps(model_meta)))
        cur.execute(
            "INSERT INTO registry_meta (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            ("dataset_manifest", json.dumps(manifest)))

        conn.commit()

    print(f"Loaded: {len(countries)} countries, {len(obs_records)} observations, "
          f"{len(cy_records)} country-year metas, {len(fc_records)} forecasts -> Neon")
    return 0


if __name__ == "__main__":
    import os
    sys.exit(main())
