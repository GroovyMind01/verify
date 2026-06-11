"""Embedded help system for air-gapped environments."""

import click


@click.group("help", hidden=True)
def help_group():
    """Show help topics (offline documentation)."""


@help_group.command("concepts")
def help_concepts():
    """Core concepts: requirements, tests, campaigns, evidence."""
    click.echo("""
Verify — Core Concepts
======================

Requirements
    A requirement is a verifiable functional or non-functional criterion that a
    system must satisfy. Each requirement has a unique user-defined key (e.g.
    K8S-001), a title, a domain, an optional description, and a JSON attributes
    blob for domain-specific extensions (severity, owner, sprint, etc.).

    Requirements support versioning through a self-referencing parent chain —
    when a requirement changes, you create a new version that links back to its
    predecessor. This preserves audit history without losing traceability.

    Requirements can also form a decomposition hierarchy via set-parent, where
    a high-level requirement is broken down into sub-requirements.

Test Definitions
    A test definition describes *how* to verify something — it includes a name,
    description, step-by-step instructions, expected result, domain, and tags.
    Test definitions are reusable templates that can be mapped to multiple
    requirements.

    The RequirementTestMapping table links tests to requirements with an
    optional coverage_claim field (full, partial, or none), creating a
    traceability matrix.

Campaigns
    A campaign is a scheduled validation activity. It has a name, status, and
    an immutable snapshot called a CampaignVersion. When you create a version,
    you lock in a specific set of test definitions. The system generates a
    TestRun record for each test definition in the snapshot.

    TestRun statuses are free-form strings: pending, running, passed, failed,
    error, skipped. You update these as you execute tests.

Evidence
    Evidence is any artifact that proves a test was executed: log files,
    screenshots, command output, JSON reports, etc. Evidence is stored in the
    file system (under the Verify data directory) and tracked in the database.
    Each evidence item has a type (free-form string), MIME type, and a SHA-256
    checksum for integrity verification.

    Evidence can be collected manually, or auto-captured from command output.
""")


@help_group.command("workflow")
def help_workflow():
    """Typical validation workflow."""
    click.echo("""
Typical Validation Workflow
============================

The end-to-end validation lifecycle follows six stages:

1. Import Requirements
   Import your requirements from CSV or Excel files:
       verify req import requirements.csv
       verify req import requirements.xlsx --format excel --sheet "Sheet1"

   Each row becomes a Requirement record with a key, title, domain, and
   description. Use --update to upsert existing records.

2. Define Tests
   Create test definitions through the Python API (CLI support coming):
       from verify.definitions.service import DefinitionServiceImpl
       def_svc.create(name="...", description="...", steps=[...])

   Tests describe the verification procedure — what to do, what to check,
   and what result to expect.

3. Map Coverage
   Link each test definition to the requirements it verifies:
       def_svc.map_to_requirement(test_id, requirement_id, coverage_claim="full")

   Use coverage_claim to indicate whether a test fully or partially covers
   a requirement. Check coverage at any time:
       verify req coverage K8S-001

4. Create Campaign
   Create a campaign to group related validation work:
       verify campaign create "Q3 Release Validation"
       verify campaign version <campaign-id> -t <test-id-1> -t <test-id-2>

   The campaign version snapshots the test list; TestRun records are created
   automatically with status "pending".

5. Execute Tests & Collect Evidence
   Update test run statuses as you execute:
       verify campaign status <version-id>

   Collect evidence artifacts for each test run:
       verify evidence collect <test-run-id> ./results/output.json --type junit
       verify evidence run <test-run-id> --type scan_output -- kyverno apply policies/

   Verify evidence integrity at any time:
       verify evidence verify <evidence-id>

6. Report
   Generate reports in text, JSON, or HTML format:
       verify campaign report <version-id>
       verify campaign report <version-id> --format json -o report.json
       verify campaign report <version-id> --format html

   Use rerun to create a new version with only previously failed tests:
       verify campaign rerun <campaign-id> <previous-version-id>
""")


@help_group.command("csv-format")
def help_csv_format():
    """CSV import format reference."""
    click.echo("""
CSV Import Format Reference
===========================

Verify imports requirements from CSV files. The expected format is:

Columns (header row required)
-----------------------------
    key          — Unique requirement identifier (max 64 chars)
                   Example: K8S-001, UI-005, API-003
    title        — Short human-readable title
                   Example: "Pod must run as non-root"
    domain       — Domain label for grouping
                   Recommended values: kubernetes, webui, api, security, general
    description  — Detailed description (optional, may contain commas if quoted)
    parent       — Parent key for decomposition hierarchy (optional)
                   The referenced key must already exist in the database.

Example CSV file
----------------
key,title,domain,description,parent
K8S-001,"Pod must run as non-root","kubernetes","All containers must set runAsNonRoot=true",
K8S-002,"No privileged containers","kubernetes","Containers must not request privileged mode",
K8S-003,"Resource limits required","kubernetes","Every container must define CPU and memory limits",
K8S-003a,"CPU limits","kubernetes","Containers must declare CPU limits",K8S-003
K8S-003b,"Memory limits","kubernetes","Containers must declare memory limits",K8S-003

Notes
-----
- The CSV parser handles quoted fields (RFC 4180 compliant).
- Fields containing commas must be double-quoted.
- Newlines within quoted fields are supported.
- The key column values are case-sensitive.
- Use --update to upsert: existing keys are updated, new keys are inserted.
- Parent references are resolved during import; if the parent key doesn't
  exist, the import will fail for that row.

Excel format
------------
For .xlsx imports, use --format excel and optionally --sheet to select a
specific worksheet. The same column layout applies.
""")


@help_group.command("storage")
def help_storage():
    """Where Verify stores data."""
    click.echo("""
Verify Storage Layout
=====================

Verify is designed for air-gapped, single-user environments. All data is
stored on the local filesystem with no network dependencies.

Database
--------
    SQLite database file. Resolved in this order:
    1. VERIFY_DB_PATH environment variable
    2. $VERIFY_HOME/verify.db
    3. $XDG_DATA_HOME/verify/verify.db
    4. ~/.local/share/verify/verify.db

    The database uses WAL journal mode for concurrent reads. Foreign keys
    are enforced. Table schema is created automatically on first use (no
    migration tool needed).

    You can use a custom database path for isolated workflows:
        verify --db-path /tmp/my-project.db req list

Data Directory
--------------
    VERIFY_HOME or $XDG_DATA_HOME/verify or ~/.local/share/verify

    Contains the following subdirectories (auto-created as needed):

    evidence/         — Collected evidence files, organized by test run ID.
                        Each file is stored with its SHA-256 checksum for
                        integrity verification.

    exports/          — Generated reports and exported data. Report files
                        are written here by default.

    backups/          — Database backups. Use for manual snapshots before
                        major operations.

    templates/        — Custom report templates.

Security
--------
    All directories are created with owner-only permissions (0o700).
    All files are created with owner-only permissions (0o600).
    Symlinks are never followed when copying evidence files, preventing
    information disclosure.
    JSON parsing limits protect against DoS attacks (1 MB max, depth 20).

Bundling for Transfer
---------------------
    Bundle evidence for a campaign version into a portable archive:
        verify evidence bundle <version-id> -o evidence.tar.gz

    Export the database, reports, and evidence to a portable directory:
        verify export usb /mnt/usb --include-evidence
""")
