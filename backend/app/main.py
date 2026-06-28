"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import routes_health, routes_pipeline, routes_webhook
from app.config import get_settings
from app.db.session import init_models

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: ensure tables exist. In prod, Alembic owns the schema.
    if not settings.is_production:
        await init_models()
    yield


app = FastAPI(
    title="Multi-Agent Code Generator",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router)
app.include_router(routes_pipeline.router)
app.include_router(routes_webhook.router)


@app.get("/")
async def root() -> dict:
    return {"service": "multi-agent-codegen", "docs": "/docs"}
