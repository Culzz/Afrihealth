"""AfriHealth FastAPI application (Release 1).

Serves the frozen /api/v1 contract plus the built React bundle in production.
Run from repo root:
    .venv\\Scripts\\python -m uvicorn services.api.app.main:app --port 8000
OpenAPI docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

from services.api.app.api import router
from services.api.app.core.config import settings

app = FastAPI(
    title="AfriHealth API",
    version="1.0.0",
    description=(
        "Population-level health intelligence for African countries. "
        "Decision support, not individual or clinical advice."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)
from services.api.app.api.r2 import router as r2_router  # noqa: E402
from services.api.app.api.r3 import router as r3_router  # noqa: E402
app.include_router(r2_router)
app.include_router(r3_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    dist = settings.frontend_dist
    if (dist / "index.html").exists():
        return RedirectResponse(url="/index.html")
    return RedirectResponse(url="/docs")


@app.get("/api/health", include_in_schema=False)
def plain_health() -> dict:
    return {"status": "ok"}


# Serve the built frontend in production (single-container deploy)
if settings.frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dist),
                               html=True), name="web")
