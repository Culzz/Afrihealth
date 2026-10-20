"""Service configuration — paths and settings via environment only."""
from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings

# services/api/app/core/config.py -> parents: core, app, api, services, repo
REPO = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    app_env: str = os.environ.get("API_ENV", "development")
    cors_origins: list[str] = [
        o.strip() for o in os.environ.get(
            "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173"
        ).split(",") if o.strip()
    ]

    data_dir: Path = REPO / "data"
    registry_dir: Path = REPO / "ml" / "registry"
    manifests_dir: Path = REPO / "data" / "manifests"
    docs_dir: Path = REPO / "docs"
    frontend_dist: Path = REPO / "apps" / "web" / "dist"

    class Config:
        env_file = ".env"


settings = Settings()
