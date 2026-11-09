import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, models  # noqa: F401  (registers the tables)
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.demo import seed_demo
from app.middleware import (
    body_limit_middleware,
    request_id_middleware,
    security_headers_middleware,
)
from app.routers import activities, companies, contacts, copilot, deals, health


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # One line per log record on stdout: Cloud Run sends it to Cloud Logging as is.
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Tables are created at startup until Alembic migrations are introduced.
    Base.metadata.create_all(engine)
    if get_settings().seed_demo:
        with SessionLocal() as session:
            if seed_demo(session):
                logging.getLogger("leadpilot").info("demo data added")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LeadPilot API",
        version=__version__,
        description="A CRM with an AI copilot for lead scoring and follow-ups.",
        lifespan=lifespan,
    )
    settings = get_settings()
    app.middleware("http")(body_limit_middleware(settings.max_body_bytes))
    # Added last = runs first: the request ID wraps everything else.
    app.middleware("http")(security_headers_middleware)
    app.middleware("http")(request_id_middleware)
    if origins := settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    app.include_router(health.router)
    app.include_router(companies.router)
    app.include_router(contacts.router)
    app.include_router(deals.router)
    app.include_router(activities.router)
    app.include_router(copilot.router)
    return app


app = create_app()
