"""CLI commands for test definition management."""

import click

from verify.definitions.service import DefinitionServiceImpl
from verify.requirements.service import RequirementServiceImpl
from verify.shared.exceptions import NotFoundError


def _get_def_service(ctx):
    return DefinitionServiceImpl(ctx.meta["session_factory"])


def _get_req_service(ctx):
    return RequirementServiceImpl(ctx.meta["session_factory"])


@click.group("test")
def test_group():
    """Manage test definitions."""


@test_group.command("create")
@click.option("--name", required=True, help="Test name")
@click.option("--description", help="Test description")
@click.option("--domain", default="general", help="Domain")
@click.option("--tags", help="Comma-separated tags")
@click.pass_context
def create_test(ctx, name, description, domain, tags):
    """Create a test definition."""
    service = _get_def_service(ctx)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    td = service.create(name=name, description=description, domain=domain, tags=tag_list)
    click.echo(f"Created test: {td.name} ({td.id})")


@test_group.command("list")
@click.option("--domain", help="Filter by domain")
@click.pass_context
def list_tests(ctx, domain):
    """List test definitions."""
    service = _get_def_service(ctx)
    tests = service.list_all(domain)
    if not tests:
        click.echo("No test definitions found.")
        return
    for td in tests:
        tags = ",".join(td.tags) if td.tags else ""
        click.echo(f"{td.id:38s}  {td.domain:15s}  {td.name:30s}  [{tags}]")


@test_group.command("show")
@click.argument("test_id")
@click.pass_context
def show_test(ctx, test_id):
    """Show test definition details."""
    service = _get_def_service(ctx)
    try:
        td = service.get_by_id(test_id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Name:     {td.name}")
    click.echo(f"ID:       {td.id}")
    click.echo(f"Domain:   {td.domain}")
    click.echo(f"Status:   {td.status}")
    click.echo(f"Tags:     {', '.join(td.tags) if td.tags else 'none'}")
    if td.description:
        click.echo(f"Desc:     {td.description}")
    if td.expected_result:
        click.echo(f"Expected: {td.expected_result}")


@test_group.command("map")
@click.argument("test_id")
@click.argument("requirement_key")
@click.option("--claim", default="full", help="Coverage claim (full, partial, indirect)")
@click.pass_context
def map_test(ctx, test_id, requirement_key, claim):
    """Map a test definition to a requirement."""
    def_svc = _get_def_service(ctx)
    req_svc = _get_req_service(ctx)
    try:
        req = req_svc.get_by_key(requirement_key)
        _mapping = def_svc.map_to_requirement(test_id, req.id, claim)
        click.echo(f"Mapped test to {requirement_key} [{claim}]")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)


@test_group.command("import")
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def import_tests(ctx, file_path):
    """Import test definitions from CSV."""
    service = _get_def_service(ctx)
    created = service.import_from_csv(file_path)
    click.echo(f"Imported {len(created)} test definition(s)")
    for td in created:
        click.echo(f"  {td.name}")
