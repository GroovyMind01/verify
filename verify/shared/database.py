"""Database engine and session management.

Uses a configurable SQLite path. No server process required.
"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from verify.shared.models import Base
from verify.shared.security import ensure_safe_directory, set_safe_permissions

_engine: Engine | None = None
_session_factory: sessionmaker | None = None
_migrations_run: bool = False


def get_verify_home() -> Path:
    """Resolve the Verify data directory.

    Priority:
    1. VERIFY_HOME environment variable
    2. $XDG_DATA_HOME/verify
    3. $HOME/.local/share/verify
    """
    import os

    env_home = os.environ.get("VERIFY_HOME")
    if env_home:
        return Path(env_home)

    data_home = os.environ.get("XDG_DATA_HOME")
    if data_home:
        return Path(data_home) / "verify"

    home = os.environ.get("HOME", "/tmp")
    return Path(home) / ".local" / "share" / "verify"


def get_db_path() -> Path:
    """Resolve the database file path.

    Priority:
    1. VERIFY_DB_PATH environment variable
    2. $VERIFY_HOME/verify.db (or XDG fallback)
    """
    import os

    env_path = os.environ.get("VERIFY_DB_PATH")
    if env_path:
        return Path(env_path)

    return get_verify_home() / "verify.db"


def get_evidence_dir() -> Path:
    """Resolve the evidence storage directory."""
    return get_verify_home() / "evidence"


def get_backups_dir() -> Path:
    """Resolve the backup storage directory."""
    return get_verify_home() / "backups"


def get_exports_dir() -> Path:
    """Resolve the export directory."""
    return get_verify_home() / "exports"


def get_templates_dir() -> Path:
    """Resolve the templates directory."""
    return get_verify_home() / "templates"


def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Apply security and performance pragmas to new SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA trusted_schema=OFF")
    cursor.close()


def get_engine() -> Engine:
    """Return the singleton SQLite engine."""
    global _engine
    if _engine is None:
        db_path = get_db_path()
        ensure_safe_directory(db_path.parent)
        _engine = create_engine(
            f"sqlite+pysqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        event.listen(_engine, "connect", _set_sqlite_pragmas)
        set_safe_permissions(db_path)
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the singleton session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine())
    return _session_factory


def run_migrations() -> None:
    """Run Alembic migrations if available (once per process)."""
    global _migrations_run
    if _migrations_run:
        return
    _migrations_run = True

    import logging
    import os

    # Configure before alembic imports anything
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    for name in ("alembic", "alembic.runtime", "alembic.runtime.migration"):
        log = logging.getLogger(name)
        log.setLevel(logging.WARNING)
        log.handlers = []
        log.addHandler(logging.NullHandler())
        log.propagate = False
    os.environ.setdefault("ALEMBIC_LOG_LEVEL", "WARNING")

    try:
        from alembic.config import Config

        from alembic import command

        alembic_cfg = Config()
        candidates = [
            Path(__file__).parent.parent.parent / "alembic.ini",
            Path.home() / ".local" / "share" / "verify" / "alembic.ini",
        ]
        for candidate in candidates:
            if candidate.exists():
                alembic_cfg = Config(str(candidate))
                break
        else:
            return

        alembic_cfg.set_main_option("script_location", str(
            Path(__file__).parent.parent.parent / "alembic"
        ))

        db_path = get_db_path()
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            f"sqlite+pysqlite:///{db_path}"
        )

        # Suppress all output during migration
        import io
        import sys
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        command.upgrade(alembic_cfg, "head")
        sys.stderr = old_stderr
    except ImportError:
        pass
    except Exception:
        pass
    finally:
        # Restore normal logging after first migration
        logging.getLogger("alembic").setLevel(logging.NOTSET)
        logging.getLogger("alembic.runtime.migration").setLevel(logging.NOTSET)


def init_db() -> None:
    """Create all tables if they do not exist.

    Imports all model modules first so SQLAlchemy can resolve
    string-based forward references in relationships.
    """
    import verify.campaigns.models  # noqa: F401
    import verify.definitions.models  # noqa: F401
    import verify.evidence.models  # noqa: F401
    import verify.requirements.models  # noqa: F401

    engine = get_engine()

    run_migrations()

    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(text(
            "CREATE VIRTUAL TABLE IF NOT EXISTS requirements_fts USING fts5("
            "    requirement_id, key, title, description,"
            "    tokenize='porter unicode61'"
            ")"
        ))
        conn.commit()


def get_session() -> Session:
    """Return a new session. Caller is responsible for closing it."""
    return get_session_factory()()


def make_service_session(factory) -> Session:
    """Create a session suitable for service use (expire_on_commit disabled).

    This lets service methods return ORM objects after commit without
    triggering DetachedInstanceError on attribute access.
    """
    session = factory()
    session.expire_on_commit = False
    return session
