"""Release-3 endpoints: organization accounts, workspaces, program monitoring,
saved analyses, evidence-to-report engine, data-quality monitor, change digest.

Security model (real, minimal, documented):
- passwords: PBKDF2-SHA256, 240k iterations, per-user random salt (str.secrets)
- sessions: random 256-bit tokens; only sha256(token) is stored
- transport: cookie HttpOnly + SameSite=Lax (https in production) or
  Authorization: Bearer for programmatic access
- roles: per-workspace owner/editor/viewer; every mutation writes an audit row
- limitation (recorded in docs): no email verification / SSO yet — registration
  trusts the entered email; invite flows come with an email provider (R3+)

In-memory login throttling is best-effort on serverless (per-instance).
"""
from __future__ import annotations

import io
import time
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from services.api.app.services import loader as L
from services.api.app.services import quality as Q
from services.api.app.services import report as REP
from services.api.app.services.repo import (
    MemoryRepo,
    PgRepo,
    RepoError,
    Repo,
    get_repo,
    now_iso,
    verify_password,
    WRITE,
    ROLE_RANK,
)
from services.api.db import session as dbsession

router = APIRouter(prefix="/api/v1", tags=["v3"])

COOKIE = "afh_session"
_login_fails: dict[str, tuple[float, int]] = {}


# ---------------------------------------------------------------- schemas ---
class RegisterReq(BaseModel):
    org_name: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=10, max_length=200)


class LoginReq(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    user_id: str
    org_id: str
    email: str
    display_name: str
    role: str
    org_name: str


class MeOut(BaseModel):
    user: UserOut


class WorkspaceReq(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    countries: list[str] = []
    description: str = ""


class TargetReq(BaseModel):
    iso3: str = Field(min_length=3, max_length=3)
    indicator: str = Field(min_length=1, max_length=60)
    geography: str = ""
    baseline_year: int | None = None
    baseline_value: float | None = None
    target_value: float | None = None
    target_year: int | None = None
    notes: str = ""


class DataRowsReq(BaseModel):
    class Row(BaseModel):
        iso3: str = Field(min_length=3, max_length=3)
        indicator: str = Field(min_length=1, max_length=60)
        geography: str = ""
        year: int = Field(ge=1990, le=2100)
        value: float
    rows: list[Row] = Field(max_length=2000)


class AnalysisReq(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    view_state: dict = {}
    notes: str = ""


class ReportReq(BaseModel):
    countries: list[str] = Field(max_length=8)
    indicators: list[str] = []
    period_text: str = ""
    org_notes: str = ""


# ---------------------------------------------------------------- helpers ---
def _require_db() -> None:
    if not dbsession.is_enabled():
        raise HTTPException(
            503, "workspace persistence requires the database (DATABASE_URL); "
                 "the artifact deployment serves the read-only R1/R2 API")


def _auth(token: str) -> dict:
    if not token:
        raise HTTPException(401, "sign in to use workspaces")
    repo = get_repo()
    user = repo.get_user_by_session(token)
    if not user:
        raise HTTPException(401, "invalid or expired session")
    return user


def _token_from(cookie_value: str | None,
                authorization: str | None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return cookie_value or ""


async def _current_user(request: Request,
                        afh_session: str | None = Cookie(None),
                        authorization: str | None = Header(None)) -> dict:
    return _auth(_token_from(afh_session, authorization))


def _org_user(row: dict) -> UserOut:
    org = get_repo().get_org(row["org_id"]) or {}
    return UserOut(user_id=row["user_id"], org_id=row["org_id"],
                   email=row["email"], display_name=row["display_name"],
                   role=row.get("role", "owner"),
                   org_name=org.get("name", ""))


def _ws_access(user: dict, ws_id: str, need: str) -> tuple[Repo, dict]:
    """need in {read, write}: raises 404/403 accordingly; returns repo+ws."""
    repo = get_repo()
    ws = repo.get_workspace(ws_id)
    if not ws:
        raise HTTPException(404, "workspace not found")
    role = repo.ws_role(ws_id, user["user_id"])
    if role is None:
        raise HTTPException(403, "you are not a member of this workspace")
    if need == "write" and role not in WRITE:
        raise HTTPException(403, "viewer role cannot modify the workspace")
    return repo, ws


# -------------------------------------------------------------------- auth --
@router.post("/auth/register", response_model=MeOut, status_code=201)
def register(req: RegisterReq, response: Response):
    _require_db()
    repo = get_repo()
    try:
        user = repo.create_org_and_user(req.org_name, req.display_name,
                                        req.email, req.password)
    except RepoError as e:
        raise HTTPException(409, f"{e}: this email already has an account")
    token = repo.create_session(user["user_id"])
    repo.audit(user["org_id"], user["user_id"], "auth.register",
               {"email": user["email"]})
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=True, max_age=60 * 60 * 24 * 30)
    return MeOut(user=_org_user(user))


@router.post("/auth/login", response_model=MeOut)
def login(req: LoginReq, response: Response):
    _require_db()
    repo = get_repo()
    now = time.time()
    slot = _login_fails.get(req.email, (0.0, 0))
    if slot[1] >= 8 and now - slot[0] < 300:
        raise HTTPException(429, "too many failed attempts — retry in a few minutes")
    user = repo.get_user_by_email(req.email)
    if not user or not verify_password(req.password,
                                       bytes.fromhex(user["pw_salt"]),
                                       bytes.fromhex(user["pw_hash"])):
        _login_fails[req.email] = (now, slot[1] + 1 if now - slot[0] < 300 else 1)
        raise HTTPException(401, "invalid email or password")
    _login_fails.pop(req.email, None)
    token = repo.create_session(user["user_id"])
    repo.audit(user["org_id"], user["user_id"], "auth.login", {})
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=True, max_age=60 * 60 * 24 * 30)
    return MeOut(user=_org_user(user))


@router.post("/auth/logout")
def logout(response: Response, afh_session: str | None = Cookie(None),
           authorization: str | None = Header(None)):
    if dbsession.is_enabled() and (afh_session or authorization):
        try:
            get_repo().delete_session(_token_from(afh_session, authorization))
        except Exception:
            pass
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/auth/me", response_model=MeOut)
def me(afh_session: str | None = Cookie(None), authorization: str | None = Header(None)):
    _require_db()
    user = _auth(_token_from(afh_session, authorization))
    return MeOut(user=_org_user(user))


# --------------------------------------------------------------- workspaces --
@router.post("/workspaces", status_code=201)
def create_workspace(req: WorkspaceReq, user: dict = Depends(_current_user)):
    repo = get_repo()
    countries = [c.upper() for c in req.countries]
    ws = repo.create_workspace(user["org_id"], user["user_id"], req.name,
                               countries, req.description)
    repo.audit(user["org_id"], user["user_id"], "workspace.create",
               {"ws_id": ws["ws_id"], "name": req.name})
    return ws


@router.get("/workspaces")
def list_workspaces(user: dict = Depends(_current_user)):
    repo = get_repo()
    return repo.list_workspaces(user["org_id"])


@router.get("/workspaces/{ws_id}")
def get_workspace(ws_id: str, user: dict = Depends(_current_user)):
    repo, ws = _ws_access(user, ws_id, "read")
    return ws


# program monitoring ----------------------------------------------------------
@router.get("/workspaces/{ws_id}/progress")
def progress(ws_id: str, user: dict = Depends(_current_user)):
    """Per-target progress: latest actual (org-uploaded data first, else the
    national estimate for platform indicators) vs baseline → target trajectory
    with explicit source labels. Planning aid, never a causal estimate."""
    repo, _ = _ws_access(user, ws_id, "read")
    targets = repo.list_targets(ws_id)
    data = repo.list_ws_data(ws_id)
    wide = L.panel_wide()
    out = []
    for t in targets:
        iso, ind = t["iso3"], t["indicator"]
        org_rows = [d for d in data if d["iso3"] == iso
                    and d["indicator"] == ind
                    and (not t.get("geography")
                         or d.get("geography", "") == t["geography"])]
        entry = {"target_id": t["target_id"], "iso3": iso,
                 "indicator": ind, "geography": t.get("geography", ""),
                 "baseline_year": t.get("baseline_year"),
                 "baseline_value": t.get("baseline_value"),
                 "target_value": t.get("target_value"),
                 "target_year": t.get("target_year")}
        if org_rows:
            latest = max(org_rows, key=lambda r: r["year"])
            src = "org-upload"
        elif ind == "u5m":
            obs = wide[(wide["iso3"] == iso) & wide["u5m"].notna()]
            if obs.empty:
                entry["progress"] = {"status": "no-evidence"}
                out.append(entry)
                continue
            latest = {"year": int(obs.iloc[-1]["year"]),
                      "value": float(obs.iloc[-1]["u5m"])}
            src = "national-estimate"
        else:
            known = {"dpt_cov": "dpt_cov", "san_basic": "san_basic",
                     "water_basic": "water_basic", "gdp_pc": "gdp_pc",
                     "urb_pct": "urb_pct", "phys_1k": "phys_1k",
                     "nurses_1k": "nurses_1k", "chexp_pctgdp": "chexp_pctgdp",
                     "meas_cov": "meas_cov"}
            col = known.get(ind)
            if col is None:
                entry["progress"] = {"status": "no-evidence",
                                     "note": "indicator not tracked by the "
                                             "platform and no org upload"}
                out.append(entry)
                continue
            obs = wide[(wide["iso3"] == iso) & wide[col].notna()]
            if obs.empty:
                entry["progress"] = {"status": "no-evidence"}
                out.append(entry)
                continue
            latest = {"year": int(obs.iloc[-1]["year"]),
                      "value": float(obs.iloc[-1][col])}
            src = "national-estimate"
        status, actual, actual_year = latest.get("status"), latest["value"], \
            latest["year"]
        entry["actual"] = {"value": actual, "year": actual_year, "source": src}
        if t.get("baseline_value") is not None and t.get("target_value") is not None \
                and t["target_value"] != t["baseline_value"]:
            frac = (actual - t["baseline_value"]) / \
                   (t["target_value"] - t["baseline_value"])
            entry["progress"] = {
                "toward_target_pct": round(max(0.0, min(1.0, frac)) * 100.0, 1),
                "status": "on-track" if frac >= 0.5 else
                          ("off-track" if frac < 0.2 else "slow-progress"),
                "note": "fraction of the observed baseline→target movement "
                        "covered to date; language is descriptive",
            }
        else:
            entry["progress"] = {"status": "incomplete-target",
                                 "note": "set baseline_value and target_value "
                                         "to track movement"}
        out.append(entry)
    return {"rows": out,
            "note": "org-uploaded actuals are compared as-is; national "
                    "estimates are labelled; no interpolation across years"}
@router.post("/workspaces/{ws_id}/targets", status_code=201)
def add_target(ws_id: str, req: TargetReq, user: dict = Depends(_current_user)):
    repo, ws = _ws_access(user, ws_id, "write")
    row = repo.add_target(ws_id, req.model_dump())
    repo.audit(user["org_id"], user["user_id"], "target.add",
               {"ws_id": ws_id, "iso3": req.iso3, "indicator": req.indicator})
    return row


@router.get("/workspaces/{ws_id}/targets")
def list_targets(ws_id: str, user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "read")
    return repo.list_targets(ws_id)


@router.delete("/workspaces/{ws_id}/targets/{target_id}")
def delete_target(ws_id: str, target_id: str,
                  user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "write")
    repo.delete_target(ws_id, target_id)
    repo.audit(user["org_id"], user["user_id"], "target.delete",
               {"ws_id": ws_id, "target_id": target_id})
    return {"ok": True}


@router.post("/workspaces/{ws_id}/data", status_code=201)
def add_data(ws_id: str, req: DataRowsReq, user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "write")
    n = repo.add_ws_data(ws_id, [r.model_dump() for r in req.rows],
                         user["user_id"])
    repo.audit(user["org_id"], user["user_id"], "data.upload",
               {"ws_id": ws_id, "rows": n})
    return {"rows_added": n,
            "note": "organization-supplied program data stored with its own "
                    "provenance (source=org-upload); it is never merged with "
                    "national estimates"}


@router.get("/workspaces/{ws_id}/data")
def list_data(ws_id: str, user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "read")
    rows = repo.list_ws_data(ws_id)
    return {"rows": rows,
            "count": len(rows),
            "sources": sorted({r["source"] for r in rows})}


# saved analyses ---------------------------------------------------------------
@router.post("/workspaces/{ws_id}/analyses", status_code=201)
def add_analysis(ws_id: str, req: AnalysisReq,
                 user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "write")
    row = repo.add_analysis(ws_id, user["user_id"], req.title,
                            req.view_state, req.notes)
    repo.audit(user["org_id"], user["user_id"], "analysis.save",
               {"ws_id": ws_id, "title": req.title})
    return row


@router.get("/workspaces/{ws_id}/analyses")
def list_analyses(ws_id: str, user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "read")
    return repo.list_analyses(ws_id)


# --------------------------------------------------- evidence-to-report ------
@router.post("/workspaces/{ws_id}/reports", status_code=201)
def generate_report(ws_id: str, req: ReportReq,
                    user: dict = Depends(_current_user)):
    repo, ws = _ws_access(user, ws_id, "write")
    spec = req.model_dump()
    spec["workspace_name"] = ws["name"]
    try:
        built = REP.build_report(spec, repo.list_ws_data(ws_id))
    except ValueError as e:
        raise HTTPException(422, str(e))
    row = repo.add_report(ws_id, user["user_id"], built["spec"],
                          built["computed"], built["narrative"])
    repo.audit(user["org_id"], user["user_id"], "report.generate",
               {"ws_id": ws_id, "version": row["version"]})
    return row


@router.get("/workspaces/{ws_id}/reports")
def list_reports(ws_id: str, user: dict = Depends(_current_user)):
    repo, _ = _ws_access(user, ws_id, "read")
    return repo.list_reports(ws_id)


@router.get("/workspaces/{ws_id}/reports/{report_id}")
def get_report(ws_id: str, report_id: str, format: str = "json",
               user: dict = Depends(_current_user)):
    repo, ws = _ws_access(user, ws_id, "read")
    row = repo.get_report(ws_id, report_id)
    if not row:
        raise HTTPException(404, "report not found")
    if format == "pdf":
        return _render_pdf(user, ws, row)
    return row


def _render_pdf(user: dict, ws: dict, row: dict) -> Response:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as pdfcanvas

    def san(s: str) -> str:
        """Standard Type-1 Helvetica is latin-1 only: transliterate the chars
        the narrative templates use (em dashes, smart quotes, box glyphs)."""
        for k, v in {"—": "-", "–": "-", "“": '"', "”": '"', "“": '"',
                     "‘": "'", "’": "'", "·": "-", "★": "*", "☐": "[ ]",
                     "≥": ">=", "→": "->", "±": "+-", "×": "x"}.items():
            s = s.replace(k, v)
        return s.encode("latin-1", "replace").decode("latin-1")

    buf = io.BytesIO()
    w, h = A4
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    n = row["narrative"]
    comp = row["computed"]

    y = h - 2.0 * cm
    c.setFont("Helvetica-Bold", 15)
    org = user.get("display_name", "AfriHealth")
    c.drawString(2 * cm, y, san(f"AfriHealth Intelligence — {ws['name']}"))
    y -= 0.9 * cm
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, y, san(f"Organization: {org} · Report v{row['version']} · "
                            f"generated {row['created_at'][:16]}Z UTC"))
    y -= 0.7 * cm
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawString(2 * cm, y, "Population-level decision support — not clinical, "
                            "individual or surveillance guidance. No causal claims.")
    y -= 1.1 * cm

    def para(size, lines):
        nonlocal y
        c.setFont("Helvetica", size)
        for ln in lines:
            if y < 2 * cm:
                c.showPage(); y = h - 2 * cm
                c.setFont("Helvetica", size)
            c.drawString(2 * cm, y, san(ln))
            y -= size * 0.52 * cm * 0.9 + 2

    import textwrap
    def wrap(t, width=100):
        return textwrap.wrap(t, width) or [""]

    para(12.5, ["Executive summary"])
    para(9, wrap(n.get("summary", "")))
    y -= 6
    para(12.5, ["Validate — evidence flags"])
    for it in comp.get("validate", []):
        flags = "; ".join(it["flags"])
        para(9, wrap(f"• {it['iso3']}: {flags}"))
    if not comp.get("validate"):
        para(9, ["No blocking data issues in the current selection."])
    y -= 6
    para(12.5, ["Findings"])
    for f in n.get("findings", []):
        for ln in wrap(("★ " if f.get("kind") == "disparity" else "• ") +
                       f.get("text", ""), 97):
            para(9, [ln])
        y -= 3
    y -= 4
    para(12.5, ["Evidence"])
    for ev in n.get("evidence", []):
        for ln in wrap(f"[{ev['id']}] {ev['country']}: {ev['text']}", 97):
            para(8.5, [ln])
        y -= 2
    y -= 4
    para(12.5, ["Limitations"])
    for lim in n.get("limitations", []):
        for ln in wrap("• " + lim, 97):
            para(9, [ln])
        y -= 2
    y -= 4
    para(12.5, ["Review checklist"])
    for ck in n.get("checklist", []):
        for ln in wrap("☐ " + ck, 97):
            para(9, [ln])

    c.showPage()
    c.save()
    buf.seek(0)
    import re
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", ws["name"]).strip("_").lower() or "report"
    filename = f"afrihealth_{slug}_v{row['version']}.pdf"
    return Response(
        content=buf.getvalue(), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"})


# ------------------------------------------------------------ quality + digest
@router.get("/quality")
def quality():
    return {**Q.indicator_quality(), "artifacts": Q.artifact_state()}


@router.get("/quality/changes")
def quality_changes(mark: bool = False):
    prev = None
    if dbsession.is_enabled():
        prev = get_repo().get_digest_key("dataset_state")
    out = Q.changes_since(prev)
    out["as_of"] = now_iso()
    if mark and dbsession.is_enabled():
        get_repo().set_digest_key("dataset_state", Q.state_snapshot())
        out["marked"] = True
    return out


@router.get("/workspaces/{ws_id}/audit")
def list_audit(ws_id: str, user: dict = Depends(_current_user)):
    repo, ws = _ws_access(user, ws_id, "read")
    return {"audit": repo.list_audit(user["org_id"]),
            "note": "org-wide audit trail; every mutation is recorded"}


@router.get("/cron/digest")
def cron_digest():
    """Monthly Vercel cron target: mark the dataset/artifact snapshot so teams'
    change monitoring have a fresh diff baseline. Idempotent + safe."""
    if not dbsession.is_enabled():
        return {"ok": False, "note": "no database configured"}
    repo = get_repo()
    prev = repo.get_digest_key("dataset_state")
    out = Q.changes_since(prev)
    repo.set_digest_key("dataset_state", Q.state_snapshot())
    return {"ok": True, "marked": True, "changed": out["changed"],
            "what": out["what"]}
