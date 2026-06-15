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

## The full workflow

Verify follows a simple 5-step lifecycle. **Evidence, status tracking, and output capture are all automatic** — your test script only needs to print results and exit with the right code.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. IMPORT    │    │ 2. DEFINE    │    │ 3. EXECUTE   │    │ 4. INSPECT   │    │ 5. REPORT    │
│ requirements │───▶│ executable   │───▶│ tests        │───▶│ evidence +   │───▶│ campaign     │
│ from CSV     │    │ tests        │    │ (ad-hoc or   │    │ status       │    │ results      │
│              │    │              │    │  campaign)   │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Step 1 — Import requirements

```bash
verify req import examples/kubernetes-requirements.csv
```

Load your specification into Verify. Each row becomes a requirement with a unique key, domain, and description. Re-import is idempotent (duplicates are skipped). Use `--update` to refresh existing rows.

### Step 2 — Define executable tests

```bash
verify test create --name "Pod Security Check" --domain kubernetes \
  --exec 'python3 examples/kubernetes/test_pod_security.py'
```

Link the test to the requirement it validates:

```bash
verify test map <test-id> K8S-001
```

**What makes a test executable:** any script or binary that:
- Prints diagnostic output to stdout/stderr
- Exits with code 0 (pass) or non-zero (fail)

You write the test in whatever language you want — Python, bash, Go, a compiled binary. Verify handles everything else automatically.

### Step 3 — Execute

**Option A: Ad-hoc (no setup needed)**

```bash
verify test exec <test-id>
verify test exec <test-id> --exec './my_script.sh --env staging'   # override command
```

`verify test exec` runs a single test immediately. It auto-creates a minimal campaign behind the scenes — you don't need to set up anything. Perfect for the "write → run → fix → re-run" development loop.

**Option B: Campaign (batch run)**

```bash
verify campaign create "Q3 Audit"
verify campaign version <campaign-id> -t <test-id-1> -t <test-id-2>
verify campaign run <version-id>                    # runs all pending tests
verify campaign run <version-id> --verbose          # shows per-test output
```

Use campaigns when you want to group multiple tests, run them together, track pass rates over time, and generate reports.

**What happens automatically when a test runs:**
1. The command is executed via subprocess
2. stdout + stderr are captured
3. An evidence file is created at `<VERIFY_HOME>/evidence/<test-run-id>/<uuid>_<name>.txt`
4. A SHA-256 checksum is computed and stored
5. Test run status is set: exit 0 → `passed`, non-zero → `failed`, timeout → `error`
6. The full output is stored in the database for instant display

**You never write evidence-collection code in your test scripts.** Just `print()` and `sys.exit()`.

### Step 4 — Inspect results

```bash
# Per-test output
verify test run <test-run-id>                    # run + see output
verify test exec <test-id>                       # run + see output

# Campaign-level status
verify campaign status <version-id>              # pass/fail counts
verify evidence list --campaign-version <vid>    # all evidence files
verify evidence preview <evidence-id>            # view a specific output

# Coverage — which tests cover which requirements
verify req coverage REQ-001
```

### Step 5 — Report

```bash
verify campaign report <version-id>                # text table
verify campaign report <version-id> --format json -o report.json
verify campaign report <version-id> --format html -o report.html
```

### Evidence model — what you need to know

| What | Who manages it | Where |
|------|---------------|-------|
| stdout/stderr from test execution | **Automatic** — captured by Verify | DB (`test_runs.output`) + evidence file |
| SHA-256 checksum | **Automatic** — computed on capture | DB (`evidence.checksum`) + metadata JSON |
| Test run status (passed/failed) | **Automatic** — set from exit code | DB (`test_runs.status`) |
| Extra artifacts (screenshots, logs, PDFs) | **You** — `verify evidence collect` | `<VERIFY_HOME>/evidence/<run-id>/` |

The only manual evidence step: if your test script produces files (a screenshot, a log file, a PDF report), attach them with:

```bash
verify evidence collect <test-run-id> ./screenshot.png --type screenshot
```

## Data directory

Default `~/.local/share/verify/` (override with `VERIFY_HOME`):

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

# Attach a shell command to an existing test
verify test set-exec <test-id> 'python3 -m pytest tests/test_auth.py -v'

# Import from CSV
verify test import tests.csv

# Run a single test (executes attached command, captures output as evidence)
verify test run <test-run-id>
```

### Executable tests

Test definitions can carry a shell command (`exec_command`). When you run the test, the command is executed, stdout/stderr is captured as evidence, and the test run status is set automatically (`passed` for exit code 0, `failed` otherwise).

**Creating an executable test:**

```bash
# With --exec at creation time
verify test create --name "Auth Tests" --domain api \
  --exec 'python3 -m pytest tests/test_auth.py -v'

# Or attach a command to an existing test
verify test set-exec <test-id> 'curl -sf https://api.example.com/health'
```

**Running tests:**

```bash
# Run a single test run
verify test run <test-run-id>

# Run ALL pending tests in a campaign version
verify campaign run <version-id>
```

The output is automatically stored as evidence (type `command_output`) with SHA-256 checksums.

**Custom test scripts** — any executable works: Python scripts, shell scripts, compiled binaries. The exit code determines pass/fail.

```bash
# Create a custom test script
cat > /tmp/check_pods.sh << 'EOF'
#!/bin/bash
non_root=$(kubectl get pods -A -o json | jq '[.items[].spec.containers[] | select(.securityContext.runAsNonRoot != true)] | length')
if [ "$non_root" -gt 0 ]; then
    echo "FAIL: $non_root pods running as root"
    exit 1
fi
echo "OK: all pods run as non-root"
exit 0
EOF
chmod +x /tmp/check_pods.sh

# Attach and run
verify test set-exec <test-id> '/tmp/check_pods.sh'
verify test run <test-run-id>
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

# Execute all pending tests in a version
verify campaign run <version-id>

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
