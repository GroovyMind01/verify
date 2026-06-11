"""Shared test fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from verify.shared.models import Base


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    """Create an in-memory SQLite engine for tests."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Create a session tied to the in-memory database."""
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def session_factory(db_engine: Engine) -> sessionmaker:
    """Return a sessionmaker that creates independent sessions for services."""
    return sessionmaker(bind=db_engine)


@pytest.fixture
def temp_evidence_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for evidence storage."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file with requirements."""
    csv_path = tmp_path / "requirements.csv"
    csv_path.write_text(
        "key,title,description,domain\n"
        "REQ-001,Login Page,Must authenticate users,security\n"
        "REQ-002,API Rate Limit,Must enforce rate limits,api\n"
        "REQ-003,Pod Security,Must run as non-root,kubernetes\n"
    )
    return csv_path
