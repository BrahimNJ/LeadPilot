from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__, models  # noqa: F401  (registers the tables)
from app.db import Base, engine
from app.routers import companies, contacts, deals, health


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Good enough while the schema is young; Alembic migrations come before production data.
    Base.metadata.create_all(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LeadPilot API",
        version=__version__,
        description="A small CRM with an AI copilot for lead scoring and follow-ups.",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(companies.router)
    app.include_router(contacts.router)
    app.include_router(deals.router)
    return app


app = create_app()
