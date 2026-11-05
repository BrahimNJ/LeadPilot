from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import __version__
from app.db import get_session

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    version: str
    database: str


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    # Someone opening the bare URL lands on the interactive docs, not on a 404.
    return RedirectResponse("/docs")


@router.get("/health")
def health(session: Annotated[Session, Depends(get_session)]) -> Health:
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unreachable"
    status = "ok" if database == "ok" else "degraded"
    return Health(status=status, version=__version__, database=database)
