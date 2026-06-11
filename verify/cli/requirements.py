"""CLI commands for requirement management."""

import json

import click

from verify.requirements.service import RequirementServiceImpl
from verify.shared.exceptions import NotFoundError, RequirementImportError


def _get_service(ctx: click.Context) -> RequirementServiceImpl:
    return RequirementServiceImpl(ctx.meta["session_factory"])


@click.group("req")
def requirement_group() -> None:
    """Manage requirements."""


@requirement_group.command("import")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["csv", "excel"]), default="csv")
@click.option("--sheet", default=None, help="Sheet name for Excel imports")
@click.option("--update", is_flag=True, help="Update existing requirements (upsert)")
@click.pass_context
def import_reqs(
    ctx: click.Context, file_path: str, fmt: str, sheet: str | None, update: bool
) -> None:
    """Import requirements from a CSV or Excel file."""
    service = _get_service(ctx)
    try:
        if fmt == "csv":
            created = service.import_from_csv(file_path, update=update)
        else:
            created = service.import_from_excel(file_path, sheet, update=update)
        click.echo(f"Imported {len(created)} requirement(s)")
        for req in created:
            click.echo(f"  {req.key} — {req.title}")
    except RequirementImportError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)


@requirement_group.command("list")
@click.option("--domain", default=None, help="Filter by domain")
@click.pass_context
def list_reqs(ctx: click.Context, domain: str | None) -> None:
    """List all requirements."""
    service = _get_service(ctx)
    reqs = service.list_all(domain)
    if not reqs:
        click.echo("No requirements found.")
        return
    for req in reqs:
        click.echo(f"{req.key:20s}  v{req.version:<3d}  {req.domain:15s}  {req.title}")


@requirement_group.command("show")
@click.argument("key")
@click.pass_context
def show_req(ctx: click.Context, key: str) -> None:
    """Show a requirement by its key."""
    service = _get_service(ctx)
    try:
        req = service.get_by_key(key)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Key:         {req.key}")
    click.echo(f"ID:          {req.id}")
    click.echo(f"Title:       {req.title}")
    click.echo(f"Domain:      {req.domain}")
    click.echo(f"Version:     {req.version}")
    click.echo(f"Status:      {req.status}")
    if req.description:
        click.echo(f"Description: {req.description}")
    if req.attributes:
        click.echo(f"Attributes:  {json.dumps(req.attributes, indent=2)}")


@requirement_group.command("coverage")
@click.argument("key")
@click.pass_context
def coverage(ctx: click.Context, key: str) -> None:
    """Show test coverage for a requirement."""
    service = _get_service(ctx)
    try:
        req = service.get_by_key(key)
        cov = service.get_coverage(req.id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Coverage for {cov['requirement_key']}: {cov['requirement_title']}")
    click.echo(f"  Covered by {cov['covered_by']} test(s)")
    for t in cov["tests"]:
        click.echo(f"  - {t['test_name']}  [{t['coverage_claim']}]")


@requirement_group.command("search")
@click.argument("query")
@click.pass_context
def search_reqs(ctx, query):
    """Full-text search requirements."""
    service = _get_service(ctx)
    results = service.search(query)
    if not results:
        click.echo("No matching requirements.")
        return
    for req in results:
        click.echo(f"{req.key:20s}  v{req.version:<3d}  {req.domain:15s}  {req.title}")


@requirement_group.command("diff")
@click.argument("key")
@click.argument("v1", type=int)
@click.argument("v2", type=int)
@click.pass_context
def diff_versions(ctx, key, v1, v2):
    """Show differences between two versions of a requirement."""
    service = _get_service(ctx)
    try:
        diff = service.diff_versions(key, v1, v2)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    if not diff:
        click.echo("No differences.")
        return
    for field, (old, new) in diff.items():
        click.echo(f"  {field}:")
        click.echo(f"    - {old}")
        click.echo(f"    + {new}")


@requirement_group.command("archive")
@click.argument("key")
@click.pass_context
def archive_req(ctx, key):
    """Archive (soft-delete) a requirement."""
    service = _get_service(ctx)
    try:
        req = service.archive(key)
        click.echo(f"Archived: {req.key}")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)


@requirement_group.command("set-parent")
@click.argument("child_key")
@click.argument("parent_key")
@click.pass_context
def set_parent(ctx, child_key, parent_key):
    """Set the decomposition parent of a requirement."""
    service = _get_service(ctx)
    try:
        _req = service.set_parent(child_key, parent_key)
        click.echo(f"Set parent of {child_key} to {parent_key}")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)


@requirement_group.command("export")
@click.option("--format", "fmt", type=click.Choice(["markdown"]), default="markdown")
@click.option("--output", "-o", required=True, help="Output file path")
@click.pass_context
def export_reqs(ctx, fmt, output):
    """Export requirements to a file."""
    service = _get_service(ctx)
    if fmt == "markdown":
        service.export_markdown(output)
        click.echo(f"Exported to {output}")


@requirement_group.command("rebuild-fts")
@click.pass_context
def rebuild_fts_cmd(ctx):
    """Rebuild the full-text search index."""
    service = _get_service(ctx)
    service.rebuild_fts()
    click.echo("FTS index rebuilt.")
