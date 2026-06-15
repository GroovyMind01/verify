# User Guide — Day-to-Day Operation

## Quick reference

| Task | Command |
|------|---------|
| Initialize data dir | `verify init` |
| Import requirements | `verify req import file.csv` |
| List requirements | `verify req list` |
| Search requirements | `verify req search "query"` |
| Create executable test | `verify test create --name "..." --domain ... --exec 'script.py'` |
| List tests | `verify test list` |
| Map test to requirement | `verify test map <test-id> <req-key>` |
| Run a single test (ad-hoc) | `verify test exec <test-id>` |
| Run with override | `verify test exec <test-id> --exec './other.sh'` |
| Create campaign | `verify campaign create "Campaign Name"` |
| Create campaign version | `verify campaign version <campaign-id> -t <test-id>` |
| Run campaign | `verify campaign run <version-id>` |
| Campaign status | `verify campaign status <version-id>` |
| Re-run failed tests | `verify campaign rerun <campaign-id> <prev-version-id>` |
| Compare versions | `verify campaign compare <v1> <v2>` |
| List evidence | `verify evidence list --test-run <run-id>` |
| Preview evidence | `verify evidence preview <evidence-id>` |
| Bundle evidence | `verify evidence bundle <version-id> -o bundle.tar.gz` |
| Generate report | `verify campaign report <version-id> --format html -o report.html` |
| Dashboard (TUI) | `verify tui` |
| Offline help | `verify help concepts`, `verify help workflow` |

## Typical workday flow

### Morning — check ongoing campaigns

```bash
verify campaign list
verify campaign status <version-id>
```

### Prepare validation

```bash
# Import updated requirements
verify req import requirements.csv --update

# Check if all requirements have coverage
verify req coverage REQ-001
verify req coverage REQ-002

# Search for specific requirements
verify req search "pod security"
```

### Run tests with the "write → run → fix" loop

```bash
# Write a test script (see validation-guide.md)
# Make it executable, then define it in Verify:
verify test create --name "Pod Security Check" --domain kubernetes \
    --exec 'python3 test_pod_security.py'

# Run it immediately — ad-hoc mode:
verify test exec <test-id>

# Fix the script, re-run (auto-creates new run):
verify test exec <test-id>
```

### Run a campaign

```bash
# Create campaign and add tests
verify campaign create "Sprint 24 Validation"
verify campaign version <campaign-id> -t <test-1> -t <test-2> -t <test-3>

# Execute all pending tests
verify campaign run <version-id> --verbose
```

### End of sprint — report

```bash
# Text report for team review
verify campaign report <version-id>

# HTML report for stakeholders
verify campaign report <version-id> --format html -o sprint24-report.html

# Export evidence archive for audit
verify evidence bundle <version-id> -o sprint24-evidence.tar.gz

# Full database export
verify export tar verify-backup.tar.gz --include-evidence
```

## Import formats

### CSV format

```csv
key,title,domain,description,parent
K8S-001,"Pod must run as non-root",kubernetes,"Containers must set runAsNonRoot=true",
```

Use `--update` to refresh existing keys. See `verify help csv-format` for details.

### Excel format

```bash
verify req import specs.xlsx --format excel --sheet "Sheet1"
```

## Test definition management

### Set or change the exec command

```bash
# On creation
verify test create --name "API Health" --domain api \
    --exec 'curl -sf http://localhost:8080/health'

# Change later
verify test set-exec <test-id> 'curl -sf http://localhost:8080/health'

# Run with override (does not change the stored command)
verify test run <run-id> --exec 'curl -sf http://localhost:8080/v2/health'
verify test exec <test-id> --exec 'curl -sf http://localhost:8080/v2/health'
```

## Evidence review

```bash
# See what evidence exists for a test run
verify evidence list --test-run <run-id>

# Preview text evidence
verify evidence preview <evidence-id>

# Check file hasn't been tampered with
verify evidence verify <evidence-id>

# GPG-sign for non-repudiation
verify evidence sign <evidence-id>

# Attach additional files
verify evidence collect <run-id> ./screenshot.png --type screenshot
```

## Data locations

| What | Default path | Override |
|------|-------------|----------|
| SQLite database | `~/.local/share/verify/verify.db` | `VERIFY_DB_PATH` or `--db-path` |
| Evidence files | `~/.local/share/verify/evidence/` | `VERIFY_HOME` |
| Reports | `~/.local/share/verify/exports/` | part of `VERIFY_HOME` |

## Shell completion

```bash
source <(verify completion bash)    # Bash
source <(verify completion zsh)     # Zsh
eval (verify completion fish)       # Fish
```

## TUI dashboard

```bash
verify tui
```

Keyboard: `Tab` to switch tabs, `↑`/`↓` to scroll, `Ctrl+C` to quit.
