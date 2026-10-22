"""Vercel serverless entrypoint — wraps the FastAPI app as an ASGI function.

Rewrites send /api/v1/* here; the original URL path is preserved, so no
root_path gymnastics is needed. Import failures surface as a visible
diagnostic response (cloud logs hide tracebacks on this plan).
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

app = None  # top-level ASGI app; set in both branches below

try:
    from services.api.app.main import app as _real_app
    app = _real_app
except Exception:  # pragma: no cover - diagnostics only
    import fastapi
    from fastapi.responses import JSONResponse

    _tb = traceback.format_exc()

    app = fastapi.FastAPI()

    @app.get("/{_p:path}")
    @app.get("/")
    def _diag(_p: str = "") -> JSONResponse:
        return JSONResponse({"import_error": _tb}, status_code=500)
