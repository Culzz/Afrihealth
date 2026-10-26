"""Vercel serverless entrypoint — wraps the FastAPI app as an ASGI function.

Rewrites send /api/v1/* here; the original URL path is preserved, so no
root_path gymnastics is needed. Import failures surface as a visible
diagnostic response (cloud logs hide tracebacks on this plan).
"""
import ctypes
import glob
import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

# LightGBM needs libgomp; the slim serverless image ships without it. We vendor
# the GCC runtime library (freely redistributable, GCC Runtime_license_exception)
# and load it globally so the symbols resolve when lightgbm imports later.
for _g in glob.glob(os.path.join(os.path.dirname(__file__), "vendor", "libgomp.so*")):
    try:
        ctypes.CDLL(_g, mode=ctypes.RTLD_GLOBAL)
    except OSError:
        pass  # graceful: scenario requests then degrade to an honest 501

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
