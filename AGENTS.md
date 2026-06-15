# AGENTS.md

## Project: Verify

Validation campaign management platform — CLI-first, air-gapped, single-user.

## Commands

```bash
# Dev install
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Run all tests (28 tests, in-memory SQLite)
.venv/bin/python -m pytest -v

# Lint
.venv/bin/ruff check .
.venv/bin/ruff check . --fix

# CLI entry point (auto-runs Alembic migrations then creates missing tables)
.venv/bin/verify --help
.venv/bin/verify --db-path /tmp/test.db req list

# Run the full example workflow
.venv/bin/python examples/run_all.py

# Build standalone binary
bash scripts/build-binary.sh
```

## Architecture

- **Package by feature**: `requirements/`, `definitions/`, `campaigns/`, `evidence/`, `reporting/`, `cli/`, `shared/`
- **Persistence**: SQLite via SQLAlchemy 2.0 with WAL mode, foreign keys enforced, `trusted_schema=OFF`
- **DB path**: `VERIFY_DB_PATH` → `$VERIFY_HOME/verify.db` → `$XDG_DATA_HOME/verify/verify.db` → `~/.local/share/verify/verify.db`
- **Data directory**: `VERIFY_HOME` → `$XDG_DATA_HOME/verify` → `~/.local/share/verify` (contains evidence/, backups/, exports/, templates/)
- **UUID PKs**: all tables use string UUIDs (`str(uuid.uuid4())`), not auto-increment ints
- **Service layer**: each feature has a `Protocol` interface and `...Impl` class, wired to CLI via `ctx.meta["session_factory"]`
- **`init_db()` runs at CLI startup**: Alembic migrations → `create_all` (idempotent) → FTS5 virtual table creation
- **Migrations**: Alembic auto-upgrades on first `init_db()` call; initial migration in `alembic/versions/`

## CLI context propagation

Session factory is stored in `ctx.meta["session_factory"]` by the `main` group. All child commands access it via `ctx.meta["session_factory"]` because Click's `ctx.meta` is inherited across the parent chain.

```python
# In main.py:
ctx.meta["session_factory"] = get_session_factory()

# In any command:
service = RequirementServiceImpl(ctx.meta["session_factory"])
```

## Service session pattern

All service constructors wrap the factory with `make_service_session()` which sets `expire_on_commit=False`. This allows returning ORM objects from service methods without `DetachedInstanceError`:

```python
class SomeServiceImpl:
    def __init__(self, session_factory) -> None:
        self._session_factory = lambda: make_service_session(session_factory)

    def some_method(self) -> SomeModel:
        with self._session_factory() as session:
            obj = session.execute(...).scalar_one()
            session.commit()
            session.expunge(obj)   # Detach before session closes
            return obj
```

Always `expunge()` returned objects and always use `with self._session_factory() as session:` context manager.

## Cross-package model imports (CRITICAL)

Feature model files reference models from other packages. Use `TYPE_CHECKING` guards with string-based forward references to avoid circular imports:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from verify.definitions.models import TestDefinition

# Then use string forward refs in Mapped annotations:
test_definition: Mapped["TestDefinition"] = relationship()
```

**Never import models directly across feature packages at runtime** — only within `if TYPE_CHECKING` blocks.

**Exception**: `init_db()` in `verify/shared/database.py` imports all model modules at runtime to ensure SQLAlchemy's registry can resolve string-based relationship references before `create_all()`.

## Security module (`verify/shared/security.py`)

All file operations must go through the security module:

- `secure_copy()` — copy without following symlinks
- `resolve_safe_path()` — prevent path traversal
- `sanitize_filename()` — strip dangerous chars from filenames
- `ensure_safe_directory()` — create dirs with 0o700 permissions
- `set_safe_permissions()` — set 0o600 on files, 0o700 on dirs
- `compute_sha256()` / `verify_checksum()` — file integrity
- `safe_json_parse()` — parse with size/depth limits
- `is_symlink()` — symlink detection
- `validate_string()` / `validate_id()` — input validation

## Domain model details

- `Requirement` — two self-referencing FKs: `parent_id` for version chains, `decomposition_parent_id` for requirement hierarchy. `requirement_type`: `"spec"`, `"sub"`, `"derived"`. `archived` for soft delete. `attributes` is JSON blob.
- `RequirementTestMapping` — dedicated model with `coverage_claim` metadata (`"full"`, `"partial"`, `"indirect"`)
- `Campaign` — `due_date` (datetime), `is_template` (bool)
- `CampaignVersion` — immutable snapshot; `milestone` (string); `created_at` uses `timezone.utc`
- `TestRun.status` — free-form string: `pending`, `running`, `passed`, `failed`, `error`, `skipped`
- `Evidence` — `checksum` (SHA-256 string), `evidence_type` free-form; DB column `metadata` mapped to attribute `metadata_`
- `requirements_fts` — FTS5 virtual table with Porter tokenizer, separate from Alembic (created in `init_db()`)

## FTS5 Search

The full-text search index is a separate virtual table (`requirements_fts`). It's not managed by Alembic — created in `init_db()` via raw SQL. Must be rebuilt after imports (auto-called by `import_from_csv` and `import_from_excel`).

Query escaping: FTS5 interprets special chars (`-`, `*`, `(`, `)`) as operators. The `search()` method wraps each term in double quotes to treat them as literals.

## Test execution model

Tests are executable — each `TestDefinition` can carry an `exec_command` (shell command). Execution is handled by `CampaignServiceImpl.run_test()`:

```
User writes script (Python, bash, binary)
    ↓ prints to stdout/stderr, exits with code
verify test exec <id>    ← ad-hoc, auto-creates campaign
verify campaign run <id>  ← batch, runs all pending
    ↓
CampaignServiceImpl.run_test()
    1. subprocess.run(command, shell=True, capture_output=True)
    2. stores full output in test_run.output
    3. creates Evidence record with SHA-256 checksum
    4. writes evidence file to <VERIFY_HOME>/evidence/<run-id>/
    5. sets test_run.status: exit 0→passed, non-zero→failed, timeout→error
    ↓
Result displayed + evidence auto-collected
```

**Evidence is automatic** — stdout/stderr capture, SHA-256 checksums, and file storage are all handled by `run_test()`. The user's test script only needs to print output and exit with the right code. Extra artifacts (screenshots, logs) must be collected manually with `verify evidence collect`.

**Ad-hoc execution** (`exec_test()`) auto-creates an "Ad-hoc" campaign + version + test run on the fly. No prior setup needed. The user can also override the command at runtime via `--exec`.

## Testing

- In-memory SQLite: `create_engine("sqlite://")` — note `sqlite://`, NOT `sqlite+pysqlite:///`
- Fixtures: `db_engine` (engine lifecycle), `db_session` (per-test session with rollback), `session_factory` (sessionmaker for service use), `temp_evidence_dir`, `sample_csv`
- Services get `session_factory` (not `db_session`) so they create their own independent sessions
- Tests run against in-memory DB, never touches disk

## Dependencies

| Package | Purpose |
|---------|---------|
| `click>=8.1` | CLI framework |
| `sqlalchemy>=2.0` | ORM + DB engine |
| `openpyxl>=3.1` | Excel import |
| `tabulate>=0.9` | Text table formatting |
| `rich>=13.0` | Colored terminal output, Markdown rendering |
| `textual>=0.52` | TUI dashboard |
| `alembic>=1.18` | Database migrations (dev dep) |
| `pytest>=7.4` | Testing (dev dep) |
| `ruff>=0.4` | Linting (dev dep) |

## Conventions

- Ruff: line length 100, rules `E,F,I,N,W,UP`, no custom ignores
- Python `>=3.10` (union syntax `X | None` is allowed)
- All `NOT NULL` model columns use `nullable=False` explicitly
- `SystemExit(2)` for `NotFoundError`, `SystemExit(1)` for other errors
- CLI helper functions per module: `_get_service()`, `_get_store()`, etc.
- `.gitignore` covers: `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, `build/`, `*.db`
