import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__, models  # noqa: F401  (registers the tables)
from app.config import get_settings
from app.db import Base, engine
from app.middleware import request_id_middleware
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
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LeadPilot API",
        version=__version__,
        description="A CRM with an AI copilot for lead scoring and follow-ups.",
        lifespan=lifespan,
    )
    app.middleware("http")(request_id_middleware)
    app.include_router(health.router)
    app.include_router(companies.router)
    app.include_router(contacts.router)
    app.include_router(deals.router)
    app.include_router(activities.router)
    app.include_router(copilot.router)
    return app


app = create_app()
