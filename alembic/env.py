from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import verify.campaigns.models  # noqa: F401
import verify.definitions.models  # noqa: F401
import verify.evidence.models  # noqa: F401
import verify.requirements.models  # noqa: F401
from alembic import context
from verify.shared.database import get_db_path
from verify.shared.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db_path = get_db_path()

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = f"sqlite+pysqlite:///{db_path}"

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
