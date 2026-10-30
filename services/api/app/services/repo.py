"""R3 persistence: organizations, users, sessions, workspaces, program data,
saved analyses, versioned reports, audit trail.

Design rules:
- Two implementations of one interface: `PgRepo` (Neon Postgres, production)
  and `MemoryRepo` (dict-backed; used by contract tests via dependency
  override). The HTTP contracts are identical; SQL correctness is exercised on
  the live deployment and in staging probes rather than locally (no local
  Postgres on this machine — per docs/DEPLOYMENT.md).
- Every id is a TEXT UUID; timestamps are ISO-8601 TEXT; JSON payloads are
  stored as TEXT JSON. Deliberately simple, portable, easy to audit.
- Connections are NEVER cached (the documented Neon/Vercel quirk): each repo
  call opens and closes a fresh psycopg connection.
- Nothing is trusted from the client without role checks.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from services.api.db import session as dbsession

SESSION_TTL_DAYS = 30
PBKDF2_ITERS = 240_000

ROLES = ("owner", "editor", "viewer")
ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}
# actions allowed by role rank (ranks included in the check)
WRITE = {"editor", "owner"}
READ = {"owner", "editor", "viewer"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid() -> str:
    return str(uuid.uuid4())


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return salt, digest


def verify_password(password: str, salt: bytes, expected: bytes) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return secrets.compare_digest(digest, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RepoError(Exception):
    """Domain-level error surfaced as 400/401/403/404/409 by the router."""


# --------------------------------------------------------------------------- #
# interface                                                                    #
# --------------------------------------------------------------------------- #
class Repo(Protocol):

    # auth
    def create_org_and_user(self, org_name: str, display_name: str,
                            email: str, password: str) -> dict: ...
    def get_user_by_email(self, email: str) -> dict | None: ...
    def create_session(self, user_id: str) -> str: ...
    def get_user_by_session(self, token: str) -> dict | None: ...
    def delete_session(self, token: str) -> None: ...

    # workspaces
    def create_workspace(self, org_id: str, user_id: str, name: str,
                         countries: list[str], description: str) -> dict: ...
    def list_workspaces(self, org_id: str) -> list[dict]: ...
    def get_workspace(self, workspace_id: str) -> dict | None: ...
    def ws_role(self, workspace_id: str, user_id: str) -> str | None: ...

    # program monitoring
    def add_target(self, workspace_id: str, entry: dict) -> dict: ...
    def list_targets(self, workspace_id: str) -> list[dict]: ...
    def delete_target(self, workspace_id: str, target_id: str) -> None: ...
    def add_ws_data(self, workspace_id: str, rows: list[dict],
                    user_id: str) -> int: ...
    def list_ws_data(self, workspace_id: str) -> list[dict]: ...

    # saved analyses
    def add_analysis(self, workspace_id: str, user_id: str,
                     title: str, view_state: dict, notes: str) -> dict: ...
    def list_analyses(self, workspace_id: str) -> list[dict]: ...

    # reports
    def add_report(self, workspace_id: str, user_id: str, spec: dict,
                   computed: dict, narrative: dict) -> dict: ...
    def list_reports(self, workspace_id: str) -> list[dict]: ...
    def get_report(self, workspace_id: str, report_id: str) -> dict | None: ...

    # audit + digest
    def audit(self, org_id: str | None, user_id: str | None, action: str,
              detail: dict) -> None: ...
    def list_audit(self, org_id: str, limit: int = 50) -> list[dict]: ...
    def get_org(self, org_id: str) -> dict | None: ...
    def get_digest_key(self, key: str) -> str | None: ...
    def set_digest_key(self, key: str, value: str) -> None: ...


# --------------------------------------------------------------------------- #
# Postgres (Neon) implementation                                               #
# --------------------------------------------------------------------------- #
def ensure_schema() -> None:
    sql = """
    CREATE TABLE IF NOT EXISTS r3_orgs (
      org_id TEXT PRIMARY KEY, name TEXT NOT NULL,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_users (
      user_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
      display_name TEXT NOT NULL, pw_salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'owner', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_sessions (
      token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
      created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_workspaces (
      ws_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, name TEXT NOT NULL,
      countries TEXT NOT NULL DEFAULT '[]', description TEXT NOT NULL DEFAULT '',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_ws_members (
      ws_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL,
      PRIMARY KEY (ws_id, user_id));
    CREATE TABLE IF NOT EXISTS r3_targets (
      target_id TEXT PRIMARY KEY, ws_id TEXT NOT NULL,
      iso3 TEXT NOT NULL, indicator TEXT NOT NULL, geography TEXT NOT NULL DEFAULT '',
      baseline_year INT, baseline_value REAL, target_value REAL, target_year INT,
      notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_ws_data (
      row_id TEXT PRIMARY KEY, ws_id TEXT NOT NULL,
      iso3 TEXT NOT NULL, indicator TEXT NOT NULL, geography TEXT NOT NULL DEFAULT '',
      year INT NOT NULL, value REAL NOT NULL,
      source TEXT NOT NULL DEFAULT 'org-upload',
      uploaded_by TEXT, uploaded_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_analyses (
      analysis_id TEXT PRIMARY KEY, ws_id TEXT NOT NULL, user_id TEXT,
      title TEXT NOT NULL, view_state TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_reports (
      report_id TEXT PRIMARY KEY, ws_id TEXT NOT NULL, version INT NOT NULL,
      spec TEXT NOT NULL, computed TEXT NOT NULL, narrative TEXT NOT NULL,
      created_by TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_audit (
      audit_id TEXT PRIMARY KEY, org_id TEXT, user_id TEXT,
      action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}', ts TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS r3_digest (
      key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
    """
    with dbsession.connect() as conn, conn.cursor() as cur:
        for stmt in [s.strip() + ";" for s in sql.split(";") if s.strip()]:
            cur.execute(stmt)


class PgRepo:

    # auth --
    def create_org_and_user(self, org_name, display_name, email, password):
        email_norm = email.strip().lower()
        if self.get_user_by_email(email_norm):
            raise RepoError("email_already_registered")
        org_id, user_id = _uid(), _uid()
        salt, digest = hash_password(password)
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_orgs (org_id, name, created_at) VALUES (%s,%s,%s)",
                (org_id, org_name.strip(), now_iso()))
            cur.execute(
                "INSERT INTO r3_users (user_id, org_id, email, display_name, "
                "pw_salt, pw_hash, role, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,'owner',%s)",
                (user_id, org_id, email_norm, display_name.strip(),
                 salt.hex(), digest.hex(), now_iso()))
        return self.get_user_by_email(email_norm)

    def get_user_by_email(self, email):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM r3_users WHERE email = %s",
                        (email.strip().lower(),))
            return cur.fetchone()

    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        exp = (datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)) \
            .isoformat(timespec="seconds")
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_sessions (token_hash, user_id, created_at, expires_at)"
                " VALUES (%s,%s,%s,%s)",
                (token_hash(token), user_id, now_iso(), exp))
        return token

    def get_user_by_session(self, token):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT u.* FROM r3_sessions s JOIN r3_users u ON u.user_id = s.user_id"
                " WHERE s.token_hash = %s AND s.expires_at > %s",
                (token_hash(token), now_iso()))
            return cur.fetchone()

    def delete_session(self, token):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM r3_sessions WHERE token_hash = %s",
                        (token_hash(token),))

    # workspaces --
    def create_workspace(self, org_id, user_id, name, countries, description):
        ws_id = _uid()
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_workspaces (ws_id, org_id, name, countries, "
                "description, created_by, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (ws_id, org_id, name.strip(), json.dumps(countries),
                 description.strip(), user_id, now_iso()))
            cur.execute(
                "INSERT INTO r3_ws_members (ws_id, user_id, role) VALUES (%s,%s,'owner')",
                (ws_id, user_id))
        return self.get_workspace(ws_id)

    def list_workspaces(self, org_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_workspaces WHERE org_id = %s ORDER BY created_at DESC",
                (org_id,))
            return [self._expand_ws(r) for r in cur.fetchall()]

    def get_workspace(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM r3_workspaces WHERE ws_id = %s",
                        (workspace_id,))
            row = cur.fetchone()
        return self._expand_ws(row) if row else None

    def _expand_ws(self, row):
        row = dict(row)
        row["countries"] = json.loads(row.get("countries") or "[]")
        return row

    def ws_role(self, workspace_id, user_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT role FROM r3_ws_members WHERE ws_id = %s AND user_id = %s",
                (workspace_id, user_id))
            return (cur.fetchone() or {}).get("role")

    # program monitoring --
    def add_target(self, workspace_id, entry):
        tid = _uid()
        sql = ("INSERT INTO r3_targets (target_id, ws_id, iso3, indicator, geography,"
               " baseline_year, baseline_value, target_value, target_year, notes,"
               " updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)")
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (
                tid, workspace_id, entry["iso3"].upper(), entry["indicator"],
                entry.get("geography", ""), entry.get("baseline_year"),
                entry.get("baseline_value"), entry.get("target_value"),
                entry.get("target_year"), entry.get("notes", ""), now_iso()))
        return self.get_target(workspace_id, tid)

    def get_target(self, workspace_id, target_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_targets WHERE ws_id = %s AND target_id = %s",
                (workspace_id, target_id))
            return cur.fetchone()

    def list_targets(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_targets WHERE ws_id = %s ORDER BY iso3, indicator",
                (workspace_id,))
            return cur.fetchall()

    def delete_target(self, workspace_id, target_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM r3_targets WHERE ws_id = %s AND target_id = %s",
                        (workspace_id, target_id))

    def add_ws_data(self, workspace_id, rows, user_id):
        sql = ("INSERT INTO r3_ws_data (row_id, ws_id, iso3, indicator, geography,"
               " year, value, source, uploaded_by, uploaded_at)"
               " VALUES (%s,%s,%s,%s,%s,%s,%s,'org-upload',%s,%s)")
        n = 0
        with dbsession.connect() as conn, conn.cursor() as cur:
            for r in rows:
                cur.execute(sql, (
                    _uid(), workspace_id, r["iso3"].upper(), r["indicator"],
                    r.get("geography", ""), int(r["year"]), float(r["value"]),
                    user_id, now_iso()))
                n += 1
        return n

    def list_ws_data(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_ws_data WHERE ws_id = %s ORDER BY uploaded_at DESC"
                " LIMIT 5000", (workspace_id,))
            return cur.fetchall()

    # saved analyses --
    def add_analysis(self, workspace_id, user_id, title, view_state, notes):
        aid = _uid()
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_analyses (analysis_id, ws_id, user_id, title,"
                " view_state, notes, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (aid, workspace_id, user_id, title.strip(),
                 json.dumps(view_state), notes.strip(), now_iso()))
        return self.get_analysis(workspace_id, aid)

    def get_analysis(self, workspace_id, analysis_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_analyses WHERE ws_id = %s AND analysis_id = %s",
                (workspace_id, analysis_id))
            row = cur.fetchone()
        if row:
            row["view_state"] = json.loads(row["view_state"])
        return row

    def list_analyses(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_analyses WHERE ws_id = %s ORDER BY created_at DESC",
                (workspace_id,))
            return [dict(r, view_state=json.loads(r["view_state"]))
                    for r in cur.fetchall()]

    # reports --
    def next_report_version(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM r3_reports WHERE ws_id = %s",
                (workspace_id,))
            return int((cur.fetchone() or {"v": 0})["v"]) + 1

    def add_report(self, workspace_id, user_id, spec, computed, narrative):
        rid = _uid()
        version = self.next_report_version(workspace_id)
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_reports (report_id, ws_id, version, spec, computed,"
                " narrative, created_by, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (rid, workspace_id, version, json.dumps(spec),
                 json.dumps(computed), json.dumps(narrative), user_id, now_iso()))
        return self.get_report(workspace_id, rid)

    def list_reports(self, workspace_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT report_id, ws_id, version, created_by, created_at,"
                " LEFT(spec, 400) AS spec_head FROM r3_reports WHERE ws_id = %s"
                " ORDER BY version DESC", (workspace_id,))
            return cur.fetchall()

    def get_report(self, workspace_id, report_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_reports WHERE ws_id = %s AND report_id = %s",
                (workspace_id, report_id))
            row = cur.fetchone()
        if row:
            row["spec"] = json.loads(row["spec"])
            row["computed"] = json.loads(row["computed"])
            row["narrative"] = json.loads(row["narrative"])
        return row

    # audit + digest --
    def get_org(self, org_id):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM r3_orgs WHERE org_id = %s", (org_id,))
            return cur.fetchone()

    def audit(self, org_id, user_id, action, detail):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_audit (audit_id, org_id, user_id, action, detail, ts)"
                " VALUES (%s,%s,%s,%s,%s,%s)",
                (_uid(), org_id, user_id, action, json.dumps(detail), now_iso()))

    def list_audit(self, org_id, limit=50):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM r3_audit WHERE org_id = %s ORDER BY ts DESC LIMIT %s",
                (org_id, limit))
            return cur.fetchall()

    def get_digest_key(self, key):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT value FROM r3_digest WHERE key = %s", (key,))
            row = cur.fetchone()
        return row["value"] if row else None

    def set_digest_key(self, key, value):
        with dbsession.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO r3_digest (key, value, updated_at) VALUES (%s,%s,%s)"
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,"
                " updated_at = EXCLUDED.updated_at",
                (key, value, now_iso()))


class MemoryRepo:
    """Same contract, dict-backed — selected by tests via dependency override."""

    def __init__(self):
        self.orgs: dict[str, dict] = {}
        self.users_by_email: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.workspaces: dict[str, dict] = {}
        self.members: dict[tuple, str] = {}
        self.targets: dict[str, dict] = {}
        self.data_rows: dict[str, list] = {}
        self.analyses: dict[str, dict] = {}
        self.reports: dict[str, dict] = {}
        self.audits: list[dict] = []
        self.digest: dict[str, str] = {}

    # auth --
    def create_org_and_user(self, org_name, display_name, email, password):
        if self.get_user_by_email(email):
            raise RepoError("email_already_registered")
        org_id, user_id = _uid(), _uid()
        salt, digest = hash_password(password)
        self.orgs[org_id] = {"org_id": org_id, "name": org_name.strip(),
                             "created_at": now_iso()}
        u = {"user_id": user_id, "org_id": org_id, "email": email.strip().lower(),
             "display_name": display_name.strip(), "pw_salt": salt.hex(),
             "pw_hash": digest.hex(), "role": "owner", "created_at": now_iso()}
        self.users[user_id] = u
        self.users_by_email[u["email"]] = u
        return dict(u)

    def get_user_by_email(self, email):
        u = self.users_by_email.get(email.strip().lower())
        return dict(u) if u else None

    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        self.sessions[token_hash(token)] = {
            "user_id": user_id, "created_at": now_iso(),
            "expires_at": (datetime.now(timezone.utc)
                           + timedelta(days=SESSION_TTL_DAYS))
            .isoformat(timespec="seconds")}
        return token

    def get_user_by_session(self, token):
        s = self.sessions.get(token_hash(token))
        if not s or s["expires_at"] <= now_iso():
            return None
        return dict(self.users.get(s["user_id"]) or {})

    def delete_session(self, token):
        self.sessions.pop(token_hash(token), None)

    # workspaces --
    def create_workspace(self, org_id, user_id, name, countries, description):
        ws_id = _uid()
        self.workspaces[ws_id] = {
            "ws_id": ws_id, "org_id": org_id, "name": name.strip(),
            "countries": list(countries), "description": description.strip(),
            "created_by": user_id, "created_at": now_iso()}
        self.members[(ws_id, user_id)] = "owner"
        return self.get_workspace(ws_id)

    def list_workspaces(self, org_id):
        rows = [w for w in self.workspaces.values() if w["org_id"] == org_id]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def get_workspace(self, workspace_id):
        w = self.workspaces.get(workspace_id)
        return dict(w) if w else None

    def ws_role(self, workspace_id, user_id):
        return self.members.get((workspace_id, user_id))

    # program monitoring --
    def add_target(self, workspace_id, entry):
        tid = _uid()
        row = {"target_id": tid, "ws_id": workspace_id,
               "iso3": entry["iso3"].upper(), "indicator": entry["indicator"],
               "geography": entry.get("geography", ""),
               "baseline_year": entry.get("baseline_year"),
               "baseline_value": entry.get("baseline_value"),
               "target_value": entry.get("target_value"),
               "target_year": entry.get("target_year"),
               "notes": entry.get("notes", ""), "updated_at": now_iso()}
        self.targets[tid] = row
        return dict(row)

    def get_target(self, workspace_id, target_id):
        t = self.targets.get(target_id)
        return {**t} if t and t["ws_id"] == workspace_id else None

    def list_targets(self, workspace_id):
        return sorted(
            [t for t in self.targets.values() if t["ws_id"] == workspace_id],
            key=lambda r: (r["iso3"], r["indicator"]))

    def delete_target(self, workspace_id, target_id):
        t = self.targets.get(target_id)
        if t and t["ws_id"] == workspace_id:
            del self.targets[target_id]

    def add_ws_data(self, workspace_id, rows, user_id):
        for r in rows:
            self.data_rows.setdefault(workspace_id, []).append({
                "row_id": _uid(), "ws_id": workspace_id,
                "iso3": r["iso3"].upper(), "indicator": r["indicator"],
                "geography": r.get("geography", ""), "year": int(r["year"]),
                "value": float(r["value"]), "source": "org-upload",
                "uploaded_by": user_id, "uploaded_at": now_iso()})
        return len(rows)

    def list_ws_data(self, workspace_id):
        return list(self.data_rows.get(workspace_id, []))

    # saved analyses --
    def add_analysis(self, workspace_id, user_id, title, view_state, notes):
        aid = _uid()
        row = {"analysis_id": aid, "ws_id": workspace_id, "user_id": user_id,
               "title": title.strip(), "view_state": dict(view_state),
               "notes": notes.strip(), "created_at": now_iso()}
        self.analyses[aid] = row
        return dict(row)

    def list_analyses(self, workspace_id):
        return sorted(
            [a for a in self.analyses.values() if a["ws_id"] == workspace_id],
            key=lambda r: r["created_at"], reverse=True)

    # reports --
    def next_report_version(self, workspace_id):
        return 1 + sum(1 for r in self.reports.values()
                       if r["ws_id"] == workspace_id)

    def add_report(self, workspace_id, user_id, spec, computed, narrative):
        rid = _uid()
        row = {"report_id": rid, "ws_id": workspace_id,
               "version": self.next_report_version(workspace_id),
               "spec": dict(spec), "computed": dict(computed),
               "narrative": dict(narrative), "created_by": user_id,
               "created_at": now_iso()}
        self.reports[rid] = row
        return dict(row)

    def list_reports(self, workspace_id):
        rows = [r for r in self.reports.values() if r["ws_id"] == workspace_id]
        return [{"report_id": r["report_id"], "ws_id": r["ws_id"],
                 "version": r["version"], "created_by": r["created_by"],
                 "created_at": r["created_at"], "spec_head":
                     json.dumps(r["spec"])[:400]} for r in
                sorted(rows, key=lambda r: r["version"], reverse=True)]

    def get_report(self, workspace_id, report_id):
        r = self.reports.get(report_id)
        if not r or r["ws_id"] != workspace_id:
            return None
        return {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in r.items()}

    # audit + digest --
    def get_org(self, org_id):
        return self.orgs.get(org_id)

    def audit(self, org_id, user_id, action, detail):
        self.audits.append({"audit_id": _uid(), "org_id": org_id,
                            "user_id": user_id, "action": action,
                            "detail": dict(detail), "ts": now_iso()})

    def list_audit(self, org_id, limit=50):
        return [a for a in sorted(self.audits, key=lambda a: a["ts"],
                                  reverse=True) if a["org_id"] == org_id][:limit]

    def get_digest_key(self, key):
        return self.digest.get(key)

    def set_digest_key(self, key, value):
        self.digest[key] = value


repo: Repo | None = None


def get_repo() -> Repo:
    """FastAPI dependency: the Postgres repo, with a one-shot schema ensure per
    cold start (CREATE TABLE IF NOT EXISTS ×11 is cheap on the pooled Neon
    connection). The router additionally requires `dbsession.is_enabled()` and
    returns 503 otherwise — the R3 layer is explicit about requiring real
    persistence rather than degrading silently."""
    global repo
    if repo is None:
        repo = PgRepo()
        ensure_schema()
    return repo
