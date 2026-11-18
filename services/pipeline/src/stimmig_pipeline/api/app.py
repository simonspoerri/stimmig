"""FastAPI application."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from . import admin, public

VERSION = os.environ.get("APP_VERSION", "dev")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Stimmig pipeline",
        version="0.1.0",
        description="Votes, claims and charts. `/api/*` needs a bearer token from the identity service; "
        "`/public/v1/*` serves published content only.",
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"]
        )

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        # Liveness: never touches the database.
        return {"status": "ok", "version": VERSION}

    app.include_router(admin.router)
    app.include_router(public.router)
    logging.getLogger("stimmig").info("pipeline started", extra={"version": VERSION})
    return app
