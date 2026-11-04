from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base, get_session

SessionDep = Annotated[Session, Depends(get_session)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends()]


def get_or_404[M: Base](session: Session, model: type[M], id_: int) -> M:
    entity = session.get(model, id_)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__.lower()} {id_} not found")
    return entity


def commit_or_409(session: Session, message: str) -> None:
    """Commit, turning a unique-constraint violation into a readable 409."""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None
