"""FastAPI app. Run with `uv run uvicorn navigator_api.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from navigator_api.routes import evidence, health, maps, parcels
from navigator_api.settings import Settings
from navigator_api.sources.base import SiteSource
from navigator_api.sources.mock import MockSiteSource


def build_source(settings: Settings) -> SiteSource:
    if settings.site_source == "mock":
        return MockSiteSource(
            settings.golden_dir, settings.mock_generated_dir, settings.mock_evidence_dir
        )
    raise NotImplementedError("SITE_SOURCE=pipeline arrives with the pipeline")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="Buildable PGH API", version="0.1.0")
    app.state.source = build_source(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    for module in (health, parcels, maps, evidence):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()
