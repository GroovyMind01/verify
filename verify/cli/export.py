"""Export data for physical transfer (USB, etc.)."""

import json
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import click

from verify.shared.database import get_db_path, get_evidence_dir
from verify.shared.security import ensure_safe_directory


@click.group("export")
def export_group():
    """Export data for transfer to another system."""


@export_group.command("usb")
@click.argument("target_dir", type=click.Path())
@click.option("--include-evidence", is_flag=True, help="Include evidence files")
@click.pass_context
def export_usb(ctx, target_dir, include_evidence):
    """Export database + reports + optional evidence to a directory (e.g. USB mount)."""
    target = Path(target_dir)
    if not target.exists():
        click.echo(f"Error: {target} does not exist", err=True)
        raise SystemExit(1)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    export_dir = target / f"verify-export-{stamp}"
    export_dir.mkdir(parents=True, exist_ok=True)
    ensure_safe_directory(export_dir)

    # Copy database
    db_path = get_db_path()
    if db_path.exists():
        shutil.copy2(db_path, export_dir / "verify.db")
        click.echo("Copied: verify.db")
    else:
        click.echo(f"Warning: database not found at {db_path}", err=True)

    # Copy evidence
    if include_evidence:
        evidence_dir = get_evidence_dir()
        if evidence_dir.exists():
            shutil.copytree(
                evidence_dir, export_dir / "evidence", symlinks=False, dirs_exist_ok=True
            )
            click.echo("Copied: evidence/")
        else:
            click.echo("Warning: evidence directory not found", err=True)

    # Create metadata
    metadata = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tool": "verify",
        "includes_evidence": include_evidence,
    }
    with open(export_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    click.echo(f"Export complete: {export_dir}")


@export_group.command("tar")
@click.argument("output", type=click.Path())
@click.option("--include-evidence", is_flag=True, help="Include evidence files")
@click.pass_context
def export_tar(ctx, output, include_evidence):
    """Export database + reports + optional evidence to a tar.gz archive."""
    output_path = Path(output).resolve()
    if output_path.suffix not in (".tar", ".gz", ".tgz"):
        output_path = output_path.with_suffix(".tar.gz")

    db_path = get_db_path()

    with tarfile.open(output_path, "w:gz") as tar:
        # Add database
        if db_path.exists():
            tar.add(db_path, arcname="verify.db")
            click.echo("Added: verify.db")
        else:
            click.echo(f"Warning: database not found at {db_path}", err=True)

        # Add evidence
        if include_evidence:
            evidence_dir = get_evidence_dir()
            if evidence_dir.exists():
                tar.add(evidence_dir, arcname="evidence")
                click.echo("Added: evidence/")
            else:
                click.echo("Warning: evidence directory not found", err=True)

    click.echo(f"Export complete: {output_path}")
