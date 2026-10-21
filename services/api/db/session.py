# Postgres (Neon) session — serverless-friendly single connections.
from __future__ import annotations

import os
from functools import lru_cache

import psycopg

from services.api.app.core.config import settings


@lru_cache(maxsize=8)
def _connect(url: str):
    # Neon requires/recommends TLS; pooler endpoints serve serverless clients.
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
