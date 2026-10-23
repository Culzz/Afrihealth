# Postgres (Neon) session — serverless-friendly single connections.
from __future__ import annotations

import os
from functools import lru_cache

import psycopg

from services.api.app.core.config import settings


@lru_cache(maxsize=8)
def _connect(url: str):
    # Neon + Vercel: the sandbox cuts the classic SSLRequest->TLS upgrade and
    # has no IPv6 egress, so connect with TLS negotiated directly, pinned to
    # an IPv4 address (SNI + verification still use the hostname).
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        import socket
        import urllib.parse
        parts = urllib.parse.urlparse(url)
        infos = socket.getaddrinfo(parts.hostname, 5432, socket.AF_INET,
                                   socket.SOCK_STREAM)
        ipv4 = infos[0][4][0]
        q = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
             if k not in ("sslmode", "sslnegotiation", "hostaddr")]
        q += [("sslmode", "require"), ("sslnegotiation", "direct"),
              ("hostaddr", ipv4)]
        tuned = urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))
        return psycopg.connect(tuned, autocommit=True)
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
