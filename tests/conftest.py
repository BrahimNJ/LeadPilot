import os
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers the tables)
from app.ai.offline import OfflineCopilot
from app.config import get_settings
from app.db import Base, build_engine, get_session
from app.main import create_app
from app.routers.copilot import get_copilot


@pytest.fixture
def session() -> Iterator[Session]:
    # TEST_DATABASE_URL runs the suite on another database, such as PostgreSQL in CI.
    # Otherwise each test gets its own in-memory SQLite database, shared by every thread.
    url = os.environ.get("TEST_DATABASE_URL")
    engine = build_engine(url) if url else build_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
    engine.dispose()


@pytest.fixture
def client_with(session: Session, monkeypatch: pytest.MonkeyPatch) -> Callable[..., TestClient]:
    """Build a client for an app created with these environment variables."""

    def build(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        try:
            app = create_app()
        finally:
            get_settings.cache_clear()
        app.dependency_overrides[get_session] = lambda: session
        # A 500 must come back as a response here, as it does for a real client.
        return TestClient(app, raise_server_exceptions=False)

    return build


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    # Tests never call a real model, whatever is in the local .env.
    app.dependency_overrides[get_copilot] = OfflineCopilot
    with TestClient(app) as c:
        yield c
