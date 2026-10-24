# Postgres (Neon) session — serverless-friendly single connections.
from __future__ import annotations

import psycopg

from services.api.app.core.config import settings


def _connect(url: str):
    # Primary path (works on Vercel AND locally): resolve the pooled endpoint
    # to IPv4 (the sandbox has no IPv6 egress), then negotiate TLS *directly*
    # (the sandbox cuts the classic SSLRequest->TLS upgrade). SNI and server
    # verification still use the hostname. If anything fails (e.g. non-Neon),
    # fall back to the standard connection.
    import socket
    import urllib.parse
    try:
        parts = urllib.parse.urlparse(url)
        if parts.scheme.startswith("postgres") and parts.hostname:
            infos = socket.getaddrinfo(parts.hostname, 5432, socket.AF_INET,
                                       socket.SOCK_STREAM)
            ipv4 = infos[0][4][0]
            q = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
                 if k not in ("sslmode", "sslnegotiation", "hostaddr")]
            q += [("sslmode", "require"), ("sslnegotiation", "direct"),
                  ("hostaddr", ipv4)]
            tuned = urllib.parse.urlunparse(
                parts._replace(query=urllib.parse.urlencode(q)))
            return psycopg.connect(tuned, autocommit=True)
    except (socket.gaierror, OSError, psycopg.Error):
        pass
    return psycopg.connect(url, sslmode="require", autocommit=True)


def connect(url: str | None = None):
    return _connect(url or settings.database_url)


def is_enabled() -> bool:
    return bool(settings.database_url)


def ping() -> bool:
    if not is_enabled():
        return False
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone()[0] == 1
    except Exception:
        return False
