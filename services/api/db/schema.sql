-- AfriHealth R1.5 — Neon/Postgres schema (idempotent, artifact-equivalent).
CREATE TABLE IF NOT EXISTS countries (
  iso3    text PRIMARY KEY,
  country text NOT NULL,
  region  text NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
  iso3      text NOT NULL REFERENCES countries,
  year      int  NOT NULL,
  indicator text NOT NULL,
  value     double precision,
  unit      text,
  source    text NOT NULL,
  source_url text,
  PRIMARY KEY (iso3, year, indicator)
);
CREATE INDEX IF NOT EXISTS obs_indicator_year ON observations (indicator, year);
CREATE INDEX IF NOT EXISTS obs_series ON observations (iso3, year);

-- Country-year quality flags from panel_wide (provenance-first: kept even
-- when values are absent — missing data is never filled, always flagged).
CREATE TABLE IF NOT EXISTS country_year_meta (
  iso3                   text NOT NULL REFERENCES countries,
  year                   int  NOT NULL,
  q_driver_coverage_pct  double precision NOT NULL DEFAULT 0,
  q_target_missing       boolean NOT NULL DEFAULT true,
  q_sparse_hwf_missing   boolean NOT NULL DEFAULT false,
  PRIMARY KEY (iso3, year)
);

CREATE TABLE IF NOT EXISTS forecasts (
  iso3                     text NOT NULL REFERENCES countries,
  year                     int  NOT NULL,
  horizon                  int  NOT NULL,
  yhat                     double precision NOT NULL,
  lo90                     double precision NOT NULL,
  hi90                     double precision NOT NULL,
  p_gt_70                  double precision NOT NULL,
  p_gt_50                  double precision NOT NULL,
  last_observed_year       int NOT NULL,
  last_observed_u5m        double precision,
  drivers_default_missing  boolean NOT NULL,
  sparse_hwf_missing       boolean NOT NULL,
  top_drivers_shap         jsonb NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (iso3, year)
);

CREATE TABLE IF NOT EXISTS registry_meta (
  key   text PRIMARY KEY,
  value jsonb NOT NULL
);
