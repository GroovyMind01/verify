"""CLI commands for evidence management."""

import click

from verify.evidence.service import FileEvidenceStore
from verify.shared.exceptions import NotFoundError, ValidationError
from verify.shared.security import safe_json_parse


def _get_store(ctx: click.Context) -> FileEvidenceStore:
    return FileEvidenceStore(ctx.meta["session_factory"])


@click.group("evidence")
def evidence_group() -> None:
    """Manage evidence and artifacts."""


@evidence_group.command("collect")
@click.argument("test_run_id")
@click.argument("source_path", type=click.Path(exists=True))
@click.option("--type", "evidence_type", required=True, help="Evidence type label")
@click.option("--meta", default=None, help="JSON metadata string")
@click.pass_context
def collect(
    ctx: click.Context, test_run_id: str, source_path: str, evidence_type: str, meta: str | None
) -> None:
    """Collect an evidence artifact for a test run."""
    store = _get_store(ctx)
    metadata = None
    if meta:
        metadata = safe_json_parse(meta)

    try:
        ev = store.collect(test_run_id, source_path, evidence_type, metadata)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Collected evidence: {ev.id}")
    click.echo(f"  Type: {ev.evidence_type}")
    click.echo(f"  MIME: {ev.mime_type}")
    click.echo(f"  Path: {ev.file_path}")


@evidence_group.command("list")
@click.option("--test-run", default=None, help="Filter by test run ID")
@click.option("--campaign-version", default=None, help="Filter by campaign version ID")
@click.pass_context
def list_evidence(
    ctx: click.Context, test_run: str | None, campaign_version: str | None
) -> None:
    """List evidence items."""
    store = _get_store(ctx)

    if test_run:
        items = store.list_for_test_run(test_run)
    elif campaign_version:
        items = store.list_for_campaign_version(campaign_version)
    else:
        click.echo("Error: specify --test-run or --campaign-version", err=True)
        raise SystemExit(1)

    if not items:
        click.echo("No evidence found.")
        return

    for ev in items:
        click.echo(f"{ev.id:38s}  {ev.evidence_type:16s}  {ev.file_path}")


@evidence_group.command("verify")
@click.argument("evidence_id")
@click.pass_context
def verify_evidence(ctx, evidence_id):
    """Verify the integrity of an evidence file."""
    store = _get_store(ctx)
    try:
        result = store.verify_integrity(evidence_id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    if result["valid"]:
        click.echo(f"Checksum OK: {result['expected'][:12]}...")
    else:
        click.echo("CHECKSUM MISMATCH!", err=True)
        click.echo(f"  Expected: {result['expected'][:12]}...")
        click.echo(f"  Actual:   {result['actual'][:12]}...")
        raise SystemExit(1)


@evidence_group.command("sign")
@click.argument("evidence_id")
@click.option("--key", help="GPG key ID")
@click.pass_context
def sign_evidence_cmd(ctx, evidence_id, key):
    """GPG-sign an evidence file."""
    store = _get_store(ctx)
    try:
        ev = store.sign_evidence(evidence_id, key)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Signed: {ev.id}")


@evidence_group.command("preview")
@click.argument("evidence_id")
@click.pass_context
def preview_evidence(ctx, evidence_id):
    """Preview evidence file content."""
    store = _get_store(ctx)
    try:
        content = store.preview(evidence_id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)
    click.echo(content)


@evidence_group.command("run")
@click.argument("test_run_id")
@click.argument("command", nargs=-1)
@click.option("--type", "evidence_type", default="command_output", help="Evidence type label")
@click.pass_context
def auto_capture(ctx, test_run_id, command, evidence_type):
    """Run a command and capture its output as evidence."""
    store = _get_store(ctx)
    try:
        ev = store.auto_capture(test_run_id, list(command), evidence_type)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Captured: {ev.id} (type={ev.evidence_type})")


@evidence_group.command("bundle")
@click.argument("campaign_version_id")
@click.option("--output", "-o", required=True, help="Output archive path (.tar.gz)")
@click.pass_context
def bundle_evidence(ctx, campaign_version_id, output):
    """Bundle all evidence for a campaign version into a .tar.gz archive."""
    store = _get_store(ctx)
    try:
        path = store.bundle(campaign_version_id, output)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Bundle created: {path}")
