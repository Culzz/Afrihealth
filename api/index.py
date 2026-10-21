"""Vercel serverless entrypoint — wraps the FastAPI app as an ASGI function.

Rewrites send /api/v1/* (and /api/health) here; the original URL path is
preserved, so no root_path gymnastics is needed.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

from services.api.app.main import app  # noqa: E402

# Vercel's Python runtime looks for a module-level ASGI app named after the file.
run = app
