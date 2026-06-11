# Verify

Validation campaign management platform — CLI-first, air-gapped, single-user.

Track requirements, define tests, run validation campaigns, collect evidence, and generate reports — all from the terminal with a local SQLite database.

## Install

```bash
git clone <repo-url> && cd verify
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Requires Python >= 3.10. Dependencies: `click`, `sqlalchemy`, `openpyxl`, `tabulate`, `rich`, `textual`.

## Quick start

```bash
# Initialize the data directory
verify init

# Import requirements
verify req import examples/kubernetes-requirements.csv

# Create a test definition
verify test create --name "Pod Security Scan" --domain kubernetes

# Run a validation campaign
verify campaign create "Q3 Audit"
verify campaign version <campaign-id> -t <test-id>

# Check status
verify campaign status <version-id>

# Full-text search
verify req search "privileged"
```

**Data directory** — default `~/.local/share/verify/` (override with `VERIFY_HOME`):
```
~/.local/share/verify/
├── verify.db          SQLite database
├── evidence/          Collected artifacts
├── backups/           Database backups
├── exports/           Report exports
└── templates/         Custom report templates
```

**Database** — `VERIFY_DB_PATH` overrides just the DB file. `VERIFY_HOME` overrides the entire data directory.

## Commands

```
verify req          Manage requirements
verify test         Manage test definitions
verify campaign     Manage validation campaigns
verify evidence     Manage evidence and artifacts
verify report       Generate reports (HTML, JSON, text)
verify dashboard    Launch terminal UI
verify init         Initialize data directory
verify export       Export data for physical transfer
verify help         Offline documentation
verify example      Worked examples (kubernetes, webui, api)
verify completion   Shell completion setup
```

### Requirements

```bash
# Import from CSV or Excel (--update to upsert)
verify req import specs.csv
verify req import specs.csv --update
verify req import specs.xlsx --format excel --sheet "Security"

# List all (filter by domain, archived hidden by default)
verify req list
verify req list --domain security

# Show details
verify req show REQ-001

# Full-text search (FTS5 with Porter stemming)
verify req search "non-root container"

# Coverage: which tests cover this requirement
verify req coverage REQ-001

# Version diff
verify req diff REQ-001 1 2

# Set decomposition parent (requirement hierarchy)
verify req set-parent REQ-002 REQ-001

# Archive (soft-delete)
verify req archive REQ-008

# Export to Markdown
verify req export -o requirements.md

# Rebuild full-text search index
verify req rebuild-fts
```

### Test Definitions

```bash
# Create
verify test create --name "Login Smoke Test" --domain webui --tags "smoke,auth"

# List
verify test list
verify test list --domain kubernetes

# Show
verify test show <test-id>

# Map to requirement
verify test map <test-id> REQ-001 --claim full

# Import from CSV
verify test import tests.csv
```

### Campaigns

```bash
# Create
verify campaign create "Security Audit" --description "PCI compliance round"

# List
verify campaign list

# Show (includes version history)
verify campaign show <campaign-id>

# Create a version snapshot
verify campaign version <campaign-id> -t <test-id-1> -t <test-id-2> --notes "First run"

# Check status
verify campaign status <version-id>

# Generate report (text, json, html)
verify campaign report <version-id>
verify campaign report <version-id> --format json -o report.json
verify campaign report <version-id> --format html -o report.html

# Re-run failed tests only
verify campaign rerun <campaign-id> <previous-version-id>

# Compare two versions
verify campaign compare <version-a> <version-b>

# Set due date
verify campaign set-due-date <campaign-id> 2026-12-31

# Set milestone
verify campaign set-milestone <version-id> "Gate Review"
```

### Evidence

```bash
# Collect an artifact (symlinks rejected, SHA-256 checksum auto-computed)
verify evidence collect <test-run-id> ./screenshot.png --type screenshot
verify evidence collect <test-run-id> ./output.log --type log --meta '{"tool":"pytest"}'

# List
verify evidence list --test-run <test-run-id>
verify evidence list --campaign-version <version-id>

# Verify file integrity
verify evidence verify <evidence-id>

# GPG-sign evidence
verify evidence sign <evidence-id> --key my-key-id

# Preview text content
verify evidence preview <evidence-id>

# Run a command and capture output as evidence
verify evidence run <test-run-id> -- pytest tests/ -v

# Bundle all evidence for a campaign version
verify evidence bundle <version-id> -o audit.tar.gz
```

### Dashboard

```bash
verify dashboard          # Launch TUI (Tab to switch views, q to quit)
verify --db-path /tmp/my.db dashboard
```

### Air-gap helpers

```bash
verify init                          # Create data directory
verify help concepts                 # Core concepts documentation
verify help workflow                 # End-to-end workflow guide
verify help csv-format               # CSV import format reference
verify help storage                  # Storage layout
verify example kubernetes            # Worked example (also: webui, api)
verify export usb /mnt/usb           # Export DB + evidence to directory
verify completion bash               # Print shell completion script
```

## Architecture

```
verify/
├── cli/            Click commands (main, requirements, campaigns, evidence, tests, help, export, tui)
├── requirements/   Requirement model + CSV/Excel import + FTS5 search + versioning
├── definitions/    TestDefinition model + mapping service
├── campaigns/      Campaign, CampaignVersion, TestRun models + lifecycle service
├── evidence/       Evidence model + secure file-based artifact store
├── reporting/      JSON, text (tabulate), HTML report generation
└── shared/         Base models, DB engine, Alembic migrations, security hardening
```

All IDs are UUIDs. SQLite with WAL mode, foreign keys enforced, trusted schema disabled.

## Environment

| Variable | Purpose | Default |
|----------|---------|---------|
| `VERIFY_HOME` | Data directory (evidence, backups, exports, templates) | `~/.local/share/verify` |
| `VERIFY_DB_PATH` | Database file location (overrides VERIFY_HOME/db) | `$VERIFY_HOME/verify.db` |
| `XDG_DATA_HOME` | Fallback base for VERIFY_HOME | `~/.local/share` |

## Security

- **Symlink rejection** — evidence collection refuses to follow symlinks
- **Path traversal prevention** — all evidence files validated against base directory
- **SHA-256 checksums** — auto-computed on evidence collection, verified on demand
- **Restrictive permissions** — DB and evidence files set to owner-only (0o600/0o700)
- **GPG signing** — detach-sign evidence artifacts for non-repudiation
- **SQLite hardening** — `trusted_schema=OFF`, foreign keys enforced, WAL mode
- **Input validation** — JSON payload size/depth limits, null byte rejection
- **Safe file copy** — uses low-level `open()` to avoid symlink traversal races

## Development

```bash
# Dev install with all optional deps
.venv/bin/pip install -e ".[dev]"

# Run tests (in-memory SQLite, 28 tests)
.venv/bin/python -m pytest -v

# Lint
.venv/bin/ruff check .

# Build standalone binary
bash scripts/build-binary.sh
```

Alembic migrations run automatically on first `verify` invocation. The initial migration is in `alembic/versions/`.

## Data model

| Table | Purpose |
|-------|---------|
| `requirements` | Imported specs with version chains + decomposition hierarchy + FTS5 index |
| `test_definitions` | Reusable test specifications with steps, tags, domain |
| `requirement_test_mappings` | Links tests to requirements with coverage claims |
| `campaigns` | Top-level validation campaign (due_date, is_template) |
| `campaign_versions` | Immutable snapshots with test runs and milestones |
| `test_runs` | Per-test execution records (pending/running/passed/failed/error/skipped) |
| `evidence` | Artifacts collected during test runs (with SHA-256 checksums) |
| `requirements_fts` | FTS5 virtual table for full-text search |
