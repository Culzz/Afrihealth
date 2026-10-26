"""Release-2 endpoint contract tests (artifact mode, no DB)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.api.app.services import loader as L
from services.api.app.services.scenario import scenario_forecast


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from services.api.app.main import app
    return TestClient(app)


# -------- vulnerability artifact invariants --------------------------------
def test_vulnerability_artifact_rules():
    v = L.vulnerability()
    assert v["composite_version"] == "vuln-v1"
    rows = v["rows"]
    assert len(rows) == 54 or len(rows) > 40
    assert abs(sum(v["weights"].values()) - 1.0) < 1e-9
    for r in rows:
        c = r["composite"]
        assert c is None or 0.0 <= c <= 100.0
        # weights renormalise over present components — never imputed
        present = [k for k, val in r["components"].items() if val is not None]
        assert r["missing_components"] == [k for k in r["components"]
                                           if k not in present]
        assert r["complete"] == (len(present) == len(r["components"]))
        bands = {"low", "watch", "elevated", "high"}
        assert r["band"] is None or r["band"] in bands


def test_vulnerability_deterministic(tmp_path: Path):
    from ml.composite.build import build_vulnerability
    a = build_vulnerability(out_path=tmp_path / "one.json")
    b = build_vulnerability(out_path=tmp_path / "two.json")
    assert a["rows"] == b["rows"]


# -------- endpoints --------------------------------------------------------
def test_vulnerability_endpoint(client):
    r = client.get("/api/v1/vulnerability")
    assert r.status_code == 200
    data = r.json()
    assert data["composite_version"] == "vuln-v1"
    assert any(x["band"] == "high" for x in data["rows"])


def test_vulnerability_country_endpoint(client):
    r = client.get("/api/v1/vulnerability/NGA")
    assert r.status_code == 200
    assert r.json()["iso3"] == "NGA"
    assert client.get("/api/v1/vulnerability/XXX").status_code == 404


def test_alerts_endpoint(client):
    r = client.get("/api/v1/alerts")
    assert r.status_code == 200
    data = r.json()
    assert data["rows"], "watchlist must not be empty"
    assert all(x["p_gt_70"] >= 0.5 for x in data["rows"])
    assert data["rows"] == sorted(data["rows"], key=lambda x: x["p_gt_70"], reverse=True)
    for x in data["rows"]:
        assert x["reasons"], "each alert must state its reason"


def test_alerts_is_deterministic(client):
    a = client.get("/api/v1/alerts").json()
    b = client.get("/api/v1/alerts").json()
    assert a == b


def test_comparisons_bundle(client):
    r = client.get("/api/v1/comparisons?iso3=NGA,ETH")
    assert r.status_code == 200
    cols = r.json()["columns"]
    assert [c["iso3"] for c in cols] == ["NGA", "ETH"]
    for c in cols:
        assert c["u5m_latest"] is not None
        assert c["forecast_2025"] is not None
        assert "dpt_cov" in c["vulnerabilities"]


def test_brief_is_templated_narrative(client):
    r = client.get("/api/v1/countries/NGA/brief", )
    assert r.status_code == 200
    text = r.text
    assert "auto-brief" in text
    assert "Observed:" in text and "Forecast" in text
    assert "not causal" not in text  # careful wording check (model card covers limits)


def test_scenario_replays_registered_forecast(client):
    """The counterfactual engine with NO interventions must reproduce the
    registered h1 forecast — a strong internal-consistency check."""
    row = scenario_forecast("NGA", [])
    reg = [f for f in L.forecast_records("NGA") if f["year"] == row["target_year"]][0]
    assert abs(row["yhat_registered_replay"] - reg["yhat"]) < 0.5


def test_scenario_delta_and_interval(client):
    r = client.post("/api/v1/scenarios", json={
        "iso3": "NGA",
        "interventions": [{"driver": "dpt_cov", "delta": 10}],
    })
    assert r.status_code == 200
    data = r.json()
    base = scenario_forecast("NGA", [])
    assert data["delta"] != 0
    assert data["yhat_registered_replay"] == base["yhat_registered_replay"]
    lo, hi = data["interval_90_scenario"]
    assert lo < data["yhat_scenario"] < hi
    assert "NOT a causal" in data["honesty_note"]


def test_scenario_rejects_unknown_driver(client):
    r = client.post("/api/v1/scenarios", json={
        "iso3": "NGA", "interventions": [{"driver": "magic", "delta": 1}]})
    assert r.status_code == 422


def test_scenario_rejects_missing_input(client):
    r = client.post("/api/v1/scenarios", json={
        "iso3": "XXX", "interventions": []})
    assert r.status_code in (404, 422)
