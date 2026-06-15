# Manager Guide — Verify Overview

## What Verify provides

Verify is a validation campaign management platform. It tracks:

- **Requirements** — what the system must do (imported from CSV/Excel)
- **Tests** — how each requirement is verified (scripts, commands, manual)
- **Campaigns** — scheduled validation runs with pass/fail tracking
- **Evidence** — proof of execution (captured output, files, checksums)
- **Reports** — auditable summaries in text, JSON, or HTML

All data lives in a local SQLite database. No servers, no network, no cloud.

## Key metrics at a glance

| Metric | How to get it |
|--------|---------------|
| Total requirements | `verify req list \| wc -l` |
| Requirements with coverage | `verify req coverage <key>` (per-requirement) |
| Test definitions | `verify test list` |
| Campaigns | `verify campaign list` |
| Campaign pass rate | `verify campaign status <version-id>` |
| Full HTML report | `verify campaign report <version-id> --format html` |
| Evidence integrity | `verify evidence verify <id>` |
| Comparison between runs | `verify campaign compare <v1> <v2>` |

## Visualization dashboard

The TUI provides a real-time terminal dashboard:

```
verify tui
```

Three tabs:
- **Campaigns** — all campaigns, their status, and a summary row
- **Requirements** — browse requirements with keys and domains
- **Test Runs** — recent runs, color-coded by status (green = passed, red = failed)

Navigate with `Tab`, scroll with arrow keys, quit with `Ctrl+C`. No browser, no web server — works entirely in the terminal, even over SSH.

## The validation lifecycle

```
Import requirements  →  Define tests  →  Run campaign  →  Review evidence  →  Report
```

Each requirement must be traced to one or more tests. Each campaign version snapshots the test list before execution. Evidence is captured automatically: stdout/stderr, exit codes, and SHA-256 checksums are recorded without any script modifications.

## Pass rate tracking

After running a campaign:

```
verify campaign status <version-id>
```

Output example:

```
Campaign: Q3 Release Audit  v2
Tests:    15 total
  Passed:  11
  Failed:  3
  Error:   1
  Skipped: 0
  Pending: 0
Pass rate: 73.3%
```

**Re-run only failed tests** for the next iteration:

```
verify campaign rerun <campaign-id> <version-id>
verify campaign version <campaign-id> --notes "Re-run failures"
verify campaign run <new-version-id>
```

**Compare two versions** to see what changed:

```
verify campaign compare <version-a> <version-b>
```

Shows tests whose status changed between runs — useful for regression tracking.

## Reports

Three export formats:

```bash
# Text (terminal-friendly)
verify campaign report <version-id>

# JSON (for external tools)
verify campaign report <version-id> --format json -o report.json

# HTML (standalone, no server needed — includes embedded CSS)
verify campaign report <version-id> --format html -o report.html
```

Reports include pass/fail counts, per-test results, and evidence references. The HTML report is fully self-contained — open it in any browser, email it, attach to a ticket.

## Audit trail

- Every requirement change creates a **new version** (diff available via `verify req diff`)
- Each campaign **version** is an immutable snapshot of which tests were included
- Each test run records the **full command output** and an **exit code**
- Each evidence file has an **SHA-256 checksum** stored in the database
- Evidence can be **GPG-signed** for non-repudiation (`verify evidence sign <id>`)

## Data portability

For auditors or transfer to another machine:

```bash
# Bundle all evidence for a campaign version
verify evidence bundle <version-id> -o evidence.tar.gz

# Full export to USB stick
verify export usb /mnt/usb --include-evidence

# Full export to tar.gz
verify export tar export.tar.gz --include-evidence
```

The database + evidence directory is self-contained. Copy it anywhere and open with `verify --db-path <path>`.
