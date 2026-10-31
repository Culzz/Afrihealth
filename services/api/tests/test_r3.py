"""Release-3 contract tests.

The R3 layer needs real persistence. There is no local Postgres on this
machine, so these tests run the full HTTP contract against `MemoryRepo` â€” a
dict-backed implementation of the same `Repo` interface the Neon-backed
`PgRepo` implements â€” injected by replacing the repo module global. SQL
correctness is exercised on the live deployment (staging probes documented
in docs/DEPLOYMENT.md).
"""
from __future__ import annotations

import pytest

from services.api.app.services.repo import MemoryRepo
import services.api.app.services.repo as repomod


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    import services.api.app.api.r3 as r3mod
    from types import SimpleNamespace
    repomod.repo = MemoryRepo()
    # fake the DB gate ONLY inside the r3 router (MemoryRepo answers storage
    # calls; other modules' DB behaviour stays untouched for other test files)
    r3mod.dbsession = SimpleNamespace(is_enabled=lambda: True)
    from services.api.app.main import app
    # https base url: the production session cookie is Secure, so requests
    # must come from an https origin or the cookie jar drops them
    return TestClient(app, base_url="https://testserver")


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client, email="mel@ngo.example", password="correct-horse-battery", org="Evidence NGO"):
    r = client.post("/api/v1/auth/register", json={
        "org_name": org, "display_name": "MEL Manager",
        "email": email, "password": password})
    assert r.status_code == 201, r.text
    me = r.json()
    assert me["user"]["org_name"] == org
    token = r.cookies.get("afh_session")
    if not token:  # TestClient keeps cookie automatically; grab header variant
        token = ""
    return me, token


# ---------------------------------------------------------------- auth ------
def test_register_login_me(client):
    me, _ = _register_and_login(client)
    r = client.get("/api/v1/auth/me")            # cookie jar from TestClient
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "mel@ngo.example"


def test_duplicate_email_rejected(client):
    r = client.post("/api/v1/auth/register", json={
        "org_name": "Other Org", "display_name": "Second",
        "email": "mel@ngo.example", "password": "correct-horse-battery"})
    assert r.status_code == 409


def test_login_wrong_password(client):
    r = client.post("/api/v1/auth/login", json={
        "email": "mel@ngo.example", "password": "wrong-incorrect-password"})
    assert r.status_code == 401


def test_me_requires_session(client):
    # second, isolated client without cookies
    from fastapi.testclient import TestClient
    from services.api.app.main import app
    anon = TestClient(app, base_url="https://testserver")
    assert anon.get("/api/v1/auth/me").status_code == 401


def test_logout_invalidates(client):
    from fastapi.testclient import TestClient
    from services.api.app.main import app
    fresh = TestClient(app, base_url="https://testserver")
    email = "logout@x.example"
    fresh.post("/api/v1/auth/register", json={
        "org_name": "Logout Co", "display_name": "L", "email": email,
        "password": "correct-horse-battery"})
    r = fresh.post("/api/v1/auth/login", json={
        "email": email, "password": "correct-horse-battery"})
    assert r.status_code == 200
    t = r.cookies.get("afh_session")
    fresh.post("/api/v1/auth/logout")          # same client → cookie-based logout
    r2 = fresh.get("/api/v1/auth/me", headers=_auth_headers(t))
    assert r2.status_code == 401


def test_passwords_never_stored_in_clear(client):
    repo = repomod.repo
    row = repo.get_user_by_email("mel@ngo.example")
    assert row["pw_salt"] and row["pw_hash"]
    assert "correct-horse-battery" not in row["pw_hash"]


# ---------------------------------------------------------- workspaces ------
def test_workspace_crud_and_isolation(client):
    r = client.post("/api/v1/workspaces", json={
        "name": "Nigeria child health Q4", "countries": ["NGA", "TCD"],
        "description": "quarterly review workspace"})
    assert r.status_code == 201, r.text
    ws = r.json()
    assert ws["countries"] == ["NGA", "TCD"]

    assert client.get("/api/v1/workspaces").status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws['ws_id']}").status_code == 200
    assert client.post("/api/v1/workspaces", json={"name": "x"}).status_code == 201

    # another user (no membership) must get 403, unknown id 404
    other = client.post("/api/v1/auth/register", json={
        "org_name": "Rival", "display_name": "Other", "email": "other@x.example",
        "password": "different-password-1"})
    assert other.status_code == 201
    from fastapi.testclient import TestClient
    from services.api.app.main import app
    rival = TestClient(app, base_url="https://testserver")
    rival.post("/api/v1/auth/login", json={
        "email": "other@x.example", "password": "different-password-1"})
    assert rival.get(f"/api/v1/workspaces/{ws['ws_id']}").status_code == 403
    assert client.get("/api/v1/workspaces/nope").status_code == 404


def test_targets_and_program_progress(client):
    ws = client.post("/api/v1/workspaces", json={
        "name": "targets ws", "countries": ["NGA"]}).json()
    r = client.post(f"/api/v1/workspaces/{ws['ws_id']}/targets", json={
        "iso3": "NGA", "indicator": "u5m", "baseline_year": 2024,
        "baseline_value": 115.6, "target_value": 100.0, "target_year": 2027,
        "notes": "program goal"})
    assert r.status_code == 201, r.text
    tid = r.json()["target_id"]

    rows = client.get(f"/api/v1/workspaces/{ws['ws_id']}/targets").json()
    assert any(x["target_id"] == tid for x in rows)

    prog = client.get(f"/api/v1/workspaces/{ws['ws_id']}/progress").json()
    row = next(x for x in prog["rows"] if x["target_id"] == tid)
    assert row["actual"]["source"] == "national-estimate"
    assert row["progress"]["status"] in ("on-track", "slow-progress", "off-track")
    assert "descriptive" in row["progress"]["note"]

    assert client.delete(
        f"/api/v1/workspaces/{ws['ws_id']}/targets/{tid}").status_code == 200
    assert client.get(f"/api/v1/workspaces/{ws['ws_id']}/targets").json() == []


def test_org_data_upload_stays_separate(client):
    ws = client.post("/api/v1/workspaces", json={
        "name": "org data ws", "countries": ["NGA"]}).json()
    r = client.post(f"/api/v1/workspaces/{ws['ws_id']}/data", json={
        "rows": [
            {"iso3": "NGA", "indicator": "severe_wasting", "year": 2026,
             "value": 4.1, "geography": "Kano State"},
            {"iso3": "NGA", "indicator": "severe_wasting", "year": 2026,
             "value": 2.9, "geography": "Lagos State"},
        ]})
    assert r.status_code == 201
    assert "never merged" in r.json()["note"]
    listed = client.get(f"/api/v1/workspaces/{ws['ws_id']}/data").json()
    assert listed["count"] == 2
    assert listed["sources"] == ["org-upload"]


def test_saved_analyses(client):
    ws = client.post("/api/v1/workspaces", json={
        "name": "analysis ws", "countries": ["ETH"]}).json()
    r = client.post(f"/api/v1/workspaces/{ws['ws_id']}/analyses", json={
        "title": "Atlas vulnerability view Q3",
        "view_state": {"mode": "vuln", "year": 2024, "countries": ["ETH"]},
        "notes": "elevated band, jackknife small"})
    assert r.status_code == 201
    listed = client.get(f"/api/v1/workspaces/{ws['ws_id']}/analyses").json()
    assert listed[0]["title"] == "Atlas vulnerability view Q3"
    assert listed[0]["view_state"]["mode"] == "vuln"


# ---------------------------------------------------------------- reports ---
def _ensure_session(c, email, pw, org="Evidence NGO"):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        c.post("/api/v1/auth/register", json={
            "org_name": org, "display_name": "MEL", "email": email,
            "password": pw})


def test_report_engine_full_workflow(client):
    _ensure_session(client, "reports@x.example", "strong-report-password")
    ws = client.post("/api/v1/workspaces", json={
        "name": "Report engine ws", "countries": ["NGA", "TCD", "ZAF"]}).json()
    r = client.post(f"/api/v1/workspaces/{ws['ws_id']}/reports", json={
        "countries": ["NGA", "TCD"],
        "indicators": ["u5m", "dpt_cov"],
        "period_text": "Quarter 4 2026 review"})
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["version"] == 1
    n = rep["narrative"]
    # honesty invariants
    assert "MODELLED" in str(rep["computed"]["analysis"]) or any(
        "MODELLED" in str(e) for e in n["evidence"] + n["findings"])
    assert n["limitations"], "limitations block is mandatory"
    assert "no causal" in " ".join(n["limitations"]).lower()
    assert n["findings"], "findings must cite the analysis"
    assert all("E" in e["id"] for e in n["evidence"])
    findings_txt = " ".join(f["text"] for f in n["findings"])
    assert "caused" not in findings_txt.lower()     # no causal claims
    # second version increments
    r2 = client.post(f"/api/v1/workspaces/{ws['ws_id']}/reports", json={
        "countries": ["NGA"], "period_text": "Quarter 1 2027"})
    assert r2.json()["version"] == 2
    listed = client.get(f"/api/v1/workspaces/{ws['ws_id']}/reports").json()
    assert [x["version"] for x in listed] == [2, 1]


def test_report_pdf_render(client):
    _ensure_session(client, "pdf@x.example", "strong-pdf-password-1")
    ws = client.post("/api/v1/workspaces", json={
        "name": "pdf ws", "countries": ["NGA"]}).json()
    rep = client.post(f"/api/v1/workspaces/{ws['ws_id']}/reports", json={
        "countries": ["NGA"]}).json()
    r = client.get(f"/api/v1/workspaces/{ws['ws_id']}/reports/{rep['report_id']}"
                   "?format=pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_report_pdf_nonascii_workspace_name(client):
    """Live regression: the em-dash in a real workspace name broke the
    Content-Disposition header (headers are latin-1-encoded), NOT the drawn
    text. The ASCII 'pdf ws' name above never caught it."""
    _ensure_session(client, "pdf2@x.example", "strong-pdf2-password")
    ws = client.post("/api/v1/workspaces", json={
        "name": "Nigeria child health — Q4 review", "countries": ["NGA"]}).json()
    rep = client.post(f"/api/v1/workspaces/{ws['ws_id']}/reports", json={
        "countries": ["NGA"]}).json()
    r = client.get(f"/api/v1/workspaces/{ws['ws_id']}/reports/{rep['report_id']}"
                   "?format=pdf")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_report_requires_selection(client):
    r = client.post("/api/v1/workspaces" "/no-such-ws" "/reports",
                    json={"countries": []})
    assert r.status_code in (404, 422, 503)


# ---------------------------------------------------- quality + digest ------
def test_quality_monitor(client):
    r = client.get("/api/v1/quality")
    assert r.status_code == 200
    data = r.json()
    assert any(i["indicator"] == "u5m" for i in data["indicators"])
    u5m = next(i for i in data["indicators"] if i["indicator"] == "u5m")
    assert u5m["coverage_pct"] > 80
    assert "never imputed" in u5m["definition_note"]


def test_quality_changes_and_cron(client):
    first = client.get("/api/v1/quality/changes").json()
    assert first["current"]["dataset_version"]
    assert "baseline" in first["note"]
    r = client.get("/api/v1/cron/digest")
    assert r.status_code == 200 and r.json()["ok"] is True
    second = client.get("/api/v1/quality/changes").json()
    assert second["changed"] is False
    assert isinstance(second["what"], list)


def test_audit_trail_records_mutations(client):
    ws = client.post("/api/v1/workspaces", json={
        "name": "audit ws", "countries": []}).json()
    client.post(f"/api/v1/workspaces/{ws['ws_id']}/analyses", json={
        "title": "t1", "view_state": {}})
    audit = client.get(f"/api/v1/workspaces/{ws['ws_id']}/audit").json()
    actions = [a["action"] for a in audit["audit"]]
    assert "workspace.create" in actions
    assert "analysis.save" in actions

