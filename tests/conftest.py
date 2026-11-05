from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers the tables)
from app.ai.offline import OfflineCopilot
from app.db import Base, build_engine, get_session
from app.main import create_app
from app.routers.copilot import get_copilot


@pytest.fixture
def session() -> Iterator[Session]:
    # One in-memory database per test: fast, isolated, no files left behind.
    # Same engine setup as the app (foreign keys on), shared by every thread.
    engine = build_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    # Tests never call a real model, whatever is in the local .env.
    app.dependency_overrides[get_copilot] = OfflineCopilot
    with TestClient(app) as c:
        yield c
