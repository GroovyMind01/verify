# Improvements

Ideas for evolving Verify — ranked by impact, respecting the air-gapped, single-user, CLI-first constraints.  
Priority legend: ★★★ = now, ★★☆ = soon, ★☆☆ = later.

---

## CLI & UX

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **TUI dashboard** — terminal UI with panes: requirement tree, test run matrix, evidence viewer. Use `textual` or `urwid`. Navigate with keyboard, no mouse. Feels like `lazygit` for validation. | Biggest UX jump. Zero dependencies beyond Python. Works over SSH, tmux, serial console. |
| ★★★ | **Shell completion** — `verify --install-completion` generates bash/zsh/fish completions. Click supports this natively. | 10 minutes to add, saves hours of `--help`. |
| ★★☆ | **Colored output** — pass/fail in green/red, domain badges, progress bars for long imports. Click + `rich` library. | Instant readability. No parsing needed. |
| ★★☆ | **`verify init`** — guided setup wizard that creates a directory structure: `evidence/`, `templates/`, `hooks/`, `verify.db`. | Onboarding in air-gapped envs where docs aren't open. |
| ★★☆ | **Non-interactive mode / exit codes** — `--quiet` + meaningful exit codes (`0`=all pass, `1`=failures, `2`=errors, `3`=warnings). | CI-friendly. Scriptable. Essential for automation. |
| ★☆☆ | **Custom output formats** — `--format csv`, `--format jsonl`, `--format template.j2` for Jinja2 templates. | Pipes into `jq`, `mlr`, spreadsheets. |
| ★☆☆ | **Subcommands for test definitions** — `verify test create|list|show|map` so users don't need Python for test CRUD. | Currently test definitions are API-only. CLI parity matters. |

---

## Requirement Management

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Hierarchical requirements** — parent/child decomposition beyond version chains. A `parent_id` that means "this requirement is a sub-requirement of", vs the current version-chain `parent_id`. Add a `requirement_type` column: `"spec"`, `"sub"`, `"derived"`. | Real specs have trees. Version chains and decomposition trees are different things. |
| ★★★ | **Full-text search** — SQLite FTS5 on `title` + `description`. `verify req search "non-root container"`. | Obvious when you have 500+ requirements. No external indexer needed. |
| ★★☆ | **Import from Markdown** — parse `## REQ-001` sections from a spec document. | Air-gapped teams write specs in Markdown, not CSV. |
| ★★☆ | **Import from ReqIF** — parse the XML-based ReqIF format (DOORS, Jama, Polarion export). | Industry standard interchange. Python `lxml` is fine offline. |
| ★★☆ | **Rich attributes** — define a per-domain JSON Schema for `attributes`. Validate on import. Render known fields (severity, priority, owner) in list/show. | Without schema, the JSON column is a black hole. With it, it's a feature. |
| ★★☆ | **Bulk operations** — `verify req import --update` to upsert by key, `verify req tag KEY --add security` for quick tagging. | Common workflows are painful one-at-a-time. |
| ★★☆ | **Diff between versions** — `verify req diff REQ-001 v1 v3` shows what changed. | Required for audits. Version chains without diffs are half the value. |
| ★☆☆ | **Export** — `verify req export --format csv|markdown|reqif` to share with other tools. | Import without export is a roach motel. |
| ★☆☆ | **Soft delete / archival** — `status: archived` instead of hard delete. Filter out by default. | Traceability means never losing history. |

---

## Test Management

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **CLI for test definitions** — `verify test create`, `verify test list --domain kubernetes`, `verify test map TEST_ID --to REQ_KEY`. | Current gap: tests need Python scripts. CLI unlocks ad-hoc use. |
| ★★☆ | **Test suites / templates** — group tests into reusable suites. `verify test suite create "PCI Checklist"` then `verify campaign version ... --suite SUITE_ID`. | Running the same 40 tests every quarter. |
| ★★☆ | **Parameterized tests** — a test with `{{variable}}` placeholders resolved at campaign version time. E.g. `"Check pod {{name}} security context"` with `name: "nginx"`. | Avoids copy-paste for similar checks across namespaces/envs. |
| ★★☆ | **Test dependencies** — `depends_on: [TEST_A, TEST_B]` so execution order is explicit. Block child if parent fails. | Basic workflow. Simple DAG, not a full orchestrator. |
| ★★☆ | **Auto-assign executor** — when creating a campaign version, assign test runs to executors from a pool or by tag. | Without this, every run starts unassigned. |
| ★☆☆ | **Test import** — import test definitions from CSV, same as requirements. `verify test import tests.csv`. | Symmetry with req import. |
| ★☆☆ | **Execution scripts** — attach a shell script to a test definition. `verify test run TEST_RUN_ID` executes it and captures output as evidence. | One-command execution. Air-gapped CI in a box. |

---

## Campaigns

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Campaign due dates and milestones** — `--due 2026-06-30`, `verify campaign milestone VERSION_ID "Gate Review"`. | Schedules exist even in air-gapped envs. |
| ★★☆ | **Campaign comparison** — `verify campaign compare V1 V2` to see what changed between versions (tests added/removed, status diffs). | Regression hunting. |
| ★★☆ | **Re-run failed** — `verify campaign version CAMPAIGN_ID --retry-failed VERSION_ID`. Creates a new version with only the failed tests. | The most common action after a campaign run. |
| ★★☆ | **Blocking / waiving tests** — mark a test run as `"blocked"` (external dependency) or `"waived"` (accepted risk) with mandatory rationale. | `failed` vs `waived` are very different signals. |
| ★☆☆ | **Campaign templates** — save a campaign + test selection as a template. `verify campaign create --from-template "Quarterly Audit"`. | Repeatable processes. |
| ★☆☆ | **Time tracking** — total clock time per campaign version, per test run. `started_at` / `completed_at` already exist, just surface them. | Useful for estimating future efforts. |

---

## Evidence

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Checksums** — store `sha256` of each evidence file on collection. `verify evidence verify CHECKSUM_ID` re-checks integrity. | Tamper detection in regulated environments. |
| ★★☆ | **Evidence signing** — GPG-sign evidence metadata. `verify evidence sign EVIDENCE_ID --key ~/.gnupg/verify.asc`. | Non-repudiation for audits. GPG is air-gap native. |
| ★★☆ | **Inline evidence preview** — `verify evidence show EVIDENCE_ID` prints the file content (for text files) or hex dump (for binaries). | Don't leave the terminal to check a log file. |
| ★★☆ | **Auto-capture** — `verify campaign run VERSION_ID` executes test scripts and auto-collects stdout/stderr as evidence. | Single command = run + collect. |
| ★★☆ | **Evidence packaging** — `verify evidence bundle CAMPAIGN_VERSION_ID --output audit.tar.gz` creates a self-contained archive (evidence + DB dump + report). | Share results with a reviewer who doesn't have Verify. |
| ★☆☆ | **Evidence retention policies** — `verify evidence prune --older-than 90d --campaign CAMPAIGN_ID`. | Disk fills up. |
| ★☆☆ | **Structured evidence** — allow JSON evidence with JSON Schema validation. `verify evidence collect --schema compliance.schema.json`. | Machine-readable evidence enables automated pass/fail decisions. |

---

## Reporting

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **HTML report** — single-file, self-contained HTML with inline CSS/JS. No server. Open with `file://`. Table sorting, filtering, collapsible sections. | The report you actually send to stakeholders. |
| ★★★ | **Traceability matrix** — `verify report matrix CAMPAIGN_VERSION_ID` outputs a grid: requirements × test definitions, with status in each cell. | The canonical validation deliverable. Required by DO-178, ISO 26262, IEC 62304. |
| ★★☆ | **PDF export** — pipe HTML report through `weasyprint` or keep it markdown → `pandoc` → PDF. | Some auditors demand PDF. Pandoc is a single binary. |
| ★★☆ | **Trend report** — `verify report trend --campaign CAMPAIGN_ID` shows pass rate over time across versions. | Is quality improving? One chart answers it. |
| ★★☆ | **Custom templates** — `verify report VERSION_ID --template audit.md.j2` renders a Jinja2 template with the summary dict. | Every org has a report format. Template it. |
| ★☆☆ | **Variance report** — highlight requirements whose test results changed between two campaign versions. | Finds regressions and fixes at a glance. |
| ★☆☆ | **Export to xUnit/JUnit XML** — for ingestion by CI systems (Jenkins, GitLab). | Bridges air-gapped Verify with networked CI. |

---

## Database & Storage

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Database migrations** — Alembic. `verify db migrate` and auto-migrate on startup. | Right now `create_all` only adds new tables, never alters. First schema change breaks existing DBs. |
| ★★★ | **SQLite WAL mode** — `PRAGMA journal_mode=WAL`. Concurrent reads while writing. | Reads won't block writes. Free performance. |
| ★★☆ | **Backup & restore** — `verify db backup --output verify-2026-06-11.db` (just copies the file). `verify db restore FILE`. | SQLite makes this trivial. Still needs a command. |
| ★★☆ | **Data directory convention** — `~/.local/share/verify/` with subdirs: `verify.db`, `evidence/`, `backups/`, `exports/`, `templates/`. Respect `VERIFY_HOME`. | Predictable paths. No scattered files. |
| ★☆☆ | **SQLCipher / encryption** — optional encrypted database via `sqlcipher3` or `pysqlcipher3`. `verify --db-path secrets.db --passphrase "..."`. | Some air-gapped envs still require encryption at rest. |
| ★☆☆ | **Export for sync** — `verify db export --format jsonl > portable.jsonl` for moving data between air-gapped machines via USB. | The air-gap data transfer problem. JSON Lines is universal. |

---

## Web UI

Deliberately last — CLI-first stays. But a read-only dashboard is high-value.

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Read-only dashboard** — `verify serve` starts a local HTTP server on `localhost:8765`. Single HTML page with campaign status, coverage heatmap, recent evidence. All assets baked into the binary (no CDN, no npm). Use `htmx` + server-side rendering. | Zero-dependency sharing within a team. No auth needed (localhost only). |
| ★★☆ | **Evidence browser** — browse collected screenshots/logs in the web view. Click to expand. | The one thing terminals can't do: images and formatted output. |
| ★★☆ | **Drill-down navigation** — click a campaign → see versions → click a version → see test runs → click a run → see evidence. | Navigation that's tedious in CLI. |
| ★☆☆ | **Basic write operations** — update test run status, add notes, collect evidence via drag-and-drop. | Reduces context-switching to terminal. Still secondary to CLI. |
| ★☆☆ | **Authentication** — optional HTTP basic auth for shared access. `verify serve --auth user:pass`. | When localhost-only isn't enough. Keep it simple. |

**Design constraint:** The web UI must work offline. Every asset (CSS, JS, fonts) is embedded. Zero CDN calls. The server is a single Python file with no JavaScript build step. Think Grafana dashboards but with 1% of the complexity.

---

## Air-gap Specific

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Self-contained documentation** — `verify help TOPIC` or `man verify`. Embed this in the tool itself, not just online. | No internet = no docs unless they ship with the tool. |
| ★★★ | **Offline examples** — `verify example kubernetes` prints a worked example to stdout. | Learn by doing, not by reading a URL. |
| ★★☆ | **Single binary distribution** — PyInstaller or Nuitka to produce a single `verify` binary. No Python, no venv, no pip. Copy one file. | The gold standard for air-gapped deployment. |
| ★★☆ | **Media export** — `verify export usb /mnt/usb` copies the database + evidence + a static HTML report to a USB stick. | Physical transfer. The air-gap courier pattern. |
| ★☆☆ | **QR code evidence** — encode small evidence items (checksums, short logs) as QR codes for camera-based transfer across air gaps. | Niche but real. Some envs have optical diodes. |
| ★☆☆ | **Incremental sync** — `verify sync --from /mnt/usb/incoming` merges changes from another Verify instance. CRDT-inspired. | Async collaboration across air-gapped machines. |

---

## Automation & Scripting

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Hook scripts** — `verify/hooks/pre-version`, `verify/hooks/post-test-run`. Shell scripts auto-executed on events. Receive context as env vars. | Extension without plugins. The Unix way. |
| ★★☆ | **`verify test run`** — executes a test definition's attached script, captures exit code + stdout/stderr as evidence, sets status automatically. | Full automation. `verify campaign run VERSION_ID` runs everything. |
| ★★☆ | **Watch mode** — `verify watch CAMPAIGN_ID` tails the database and prints test run status changes in real-time. | Like `tail -f` for your campaign. |
| ★☆☆ | **Scheduled campaigns** — `verify scheduler add "0 8 * * 1" "campaign run Quarterly"`. In-process cron. | Recurring validation without external cron. |
| ★☆☆ | **Plugin system** — Python entry points for custom evidence collectors, custom report renderers, custom import formats. `verify.plugins` namespace. | Extensibility without forking. |

---

## Architecture

| ★ | Idea | Why |
|----|------|-----|
| ★★★ | **Pagination on list queries** — `verify req list --limit 50 --offset 100`. All list endpoints. | 10,000 requirements will happen. |
| ★★☆ | **Session/transaction middleware** — a single `db_session` context injected via Click instead of per-command factories. One transaction per CLI invocation. | Right now each service call opens its own connection. Fine for SQLite, but wasteful. |
| ★★☆ | **Background task queue** — for long-running evidence collection or report generation. `verify task list`, `verify task status TASK_ID`. | Don't block the terminal for 30s evidence copies. |
| ★☆☆ | **Telemetry-free observability** — `--verbose` flag, structured logging to file, timing information per command. All local. | Debugging without phoning home. |
| ★☆☆ | **Configuration file** — `~/.config/verify/config.toml` for defaults: evidence dir, default domain, editor, template paths. | Reduces CLI flag repetition. |

---

## Would-not-do (yet)

Things that sound good but add complexity disproportionate to value in a single-user air-gapped tool:

- **Multi-user server** — turns a local tool into a distributed system. Use the read-only web dashboard instead.
- **Real-time collaboration** — CRDTs, WebSocket sync. Vast complexity. File-based sync covers 80%.
- **OAuth / SSO** — single-user tool. HTTP basic auth is plenty.
- **Microservices** — it's SQLite. Keep it monolithic.
- **GraphQL API** — REST-ish JSON over HTTP is simpler. Or just use the Python API.
- **Notification system** — email/Slack/webhook alerts require network. Hook scripts can call anything.
- **Cloud storage backends** — S3, GCS. Air-gapped means local filesystem.
- **Mobile app** — terminal UI covers phones via SSH clients.
