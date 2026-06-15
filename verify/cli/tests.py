"""CLI commands for test definition management."""

import click

from verify.campaigns.service import CampaignServiceImpl
from verify.definitions.service import DefinitionServiceImpl
from verify.requirements.service import RequirementServiceImpl
from verify.shared.exceptions import NotFoundError, ValidationError


def _get_def_service(ctx):
    return DefinitionServiceImpl(ctx.meta["session_factory"])


def _get_req_service(ctx):
    return RequirementServiceImpl(ctx.meta["session_factory"])


def _get_campaign_service(ctx):
    return CampaignServiceImpl(ctx.meta["session_factory"])


@click.group("test")
def test_group():
    """Manage test definitions."""


@test_group.command("create")
@click.option("--name", required=True, help="Test name")
@click.option("--description", help="Test description")
@click.option("--domain", default="general", help="Domain")
@click.option("--tags", help="Comma-separated tags")
@click.option("--exec", "exec_cmd", help="Shell command to run when this test executes")
@click.pass_context
def create_test(ctx, name, description, domain, tags, exec_cmd):
    """Create a test definition."""
    service = _get_def_service(ctx)
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    td = service.create(
        name=name,
        description=description,
        domain=domain,
        tags=tag_list,
        exec_command=exec_cmd,
    )
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
        cmd = f"  [{td.exec_command[:40]}...]" if td.exec_command else ""
        click.echo(f"{td.id:38s}  {td.domain:15s}  {td.name:30s}  [{tags}]{cmd}")


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
    if td.exec_command:
        click.echo(f"Command:  {td.exec_command}")
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
        def_svc.map_to_requirement(test_id, req.id, claim)
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


@test_group.command("run")
@click.argument("test_run_id")
@click.option("--exec", "exec_cmd", help="Override the command to execute")
@click.option("--no-output", is_flag=True, help="Suppress command output")
@click.pass_context
def run_test(ctx, test_run_id, exec_cmd, no_output):
    """Execute the command attached to a test run and record the result."""
    service = _get_campaign_service(ctx)
    try:
        tr = service.run_test(test_run_id, command_override=exec_cmd)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2 if isinstance(e, NotFoundError) else 1)

    _print_test_result(tr, no_output)


@test_group.command("exec")
@click.argument("test_id")
@click.option(
    "--exec", "exec_cmd",
    help="Command to execute (overrides test definition's exec_command)",
)
@click.option("--campaign", default=None, help="Campaign name to group under (default: Ad-hoc)")
@click.option("--no-output", is_flag=True, help="Suppress command output")
@click.pass_context
def exec_test(ctx, test_id, exec_cmd, campaign, no_output):
    """Execute a test definition ad-hoc — no campaign setup needed.

    Creates a minimal campaign + test run on the fly, executes the
    command, and displays the full output.

    Examples:

        verify test exec <test-id>
        verify test exec <test-id> --exec 'curl -sf https://api.example.com/health'
        verify test exec <test-id> --campaign "Quick Checks"
    """
    service = _get_campaign_service(ctx)
    try:
        tr = service.exec_test(test_id, command=exec_cmd, campaign_name=campaign)
    except (NotFoundError, ValidationError) as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2 if isinstance(e, NotFoundError) else 1)

    _print_test_result(tr, no_output)


def _print_test_result(tr, no_output=False):
    status_icon = {"passed": "\u2705", "failed": "\u274c", "error": "\u26a0\ufe0f"}
    icon = status_icon.get(tr.status, "?")
    td_name = tr.test_definition.name if tr.test_definition else "?"
    click.echo(f"\n{icon}  [{tr.status.upper()}]  {td_name}")

    if tr.notes:
        click.echo(f"    {tr.notes}")

    if tr.output and not no_output:
        click.echo("    ── output ──")
        lines = tr.output.split("\n")
        if len(lines) > 80:
            shown = lines[-80:]
            hint = (
                f"    (showing last 80 of {len(lines)} lines"
                " — use 'verify evidence preview' for full)"
            )
            click.echo(hint)
            for line in shown:
                click.echo(f"    {line}")
        else:
            for line in lines:
                click.echo(f"    {line}")

        click.echo(
            "    (full output saved as evidence"
            f" — 'verify evidence list --test-run {tr.id}')"
        )


@test_group.command("set-exec")
@click.argument("test_id")
@click.argument("command")
@click.pass_context
def set_exec(ctx, test_id, command):
    """Attach a shell command to an existing test definition."""
    service = _get_def_service(ctx)
    try:
        service.set_exec_command(test_id, command)
        click.echo(f"Exec command set for {test_id}")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)
