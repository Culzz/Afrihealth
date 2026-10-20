"""API contract tests (httpx TestClient, offline, real committed artifacts)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root on path

from fastapi.testclient import TestClient  # noqa: E402

from services.api.app.main import app  # noqa: E402

client = TestClient(app, base_url="http://test")


def test_health_reports_dataset_and_model():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_version"] == "u5m-lgb-v1"
    assert body["data_max_year"] >= 2024
    assert body["countries"] >= 50


def test_countries_listing_compliant():
    r = client.get("/api/v1/countries")
    assert r.status_code == 200
    names = {c["iso3"] for c in r.json()}
    assert {"NGA", "NER", "ZAF"} <= names


def test_atlas_defaults_to_latest_year():
    r = client.get("/api/v1/atlas")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 50
    assert rows[0]["year"] == max(x["year"] for x in rows)


def test_atlas_404_on_unknown_year():
    r = client.get("/api/v1/atlas", params={"year": 1999})
    assert r.status_code == 404


def test_series_full_shape():
    r = client.get("/api/v1/countries/NGA/series")
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]["year"] < rows[-1]["year"]
    assert all("q_driver_coverage_pct" in row for row in rows)


def test_series_unknown_country_404():
    r = client.get("/api/v1/countries/ZZZ/series")
    assert r.status_code == 404


def test_forecasts_carry_intervals_and_exceedance():
    r = client.get("/api/v1/countries/NGA/forecasts")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 3
    for row in rows:
        assert row["lo90"] <= row["yhat"] <= row["hi90"]
        assert 0.0 <= row["p_gt_70"] <= 1.0
        assert len(row["top_drivers_shap"]) == 5


def test_model_card_is_markdown():
    r = client.get("/api/v1/model-card")
    assert r.status_code == 200
    assert r.text.startswith("# AfriHealth")


def test_report_pdf_generated():
    r = client.post("/api/v1/reports", json={"iso3": "NGA"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
