"""CLI commands for campaign management."""

import json

import click

from verify.campaigns.service import CampaignServiceImpl
from verify.reporting.service import ReportingServiceImpl
from verify.shared.exceptions import NotFoundError


def _get_campaign_service(ctx: click.Context) -> CampaignServiceImpl:
    return CampaignServiceImpl(ctx.meta["session_factory"])


def _get_reporting_service(ctx: click.Context) -> ReportingServiceImpl:
    return ReportingServiceImpl(ctx.meta["session_factory"])


@click.group("campaign")
def campaign_group() -> None:
    """Manage validation campaigns."""


@campaign_group.command("create")
@click.argument("name")
@click.option("--description", default=None, help="Campaign description")
@click.pass_context
def create(ctx: click.Context, name: str, description: str | None) -> None:
    """Create a new campaign."""
    service = _get_campaign_service(ctx)
    campaign = service.create(name, description)
    click.echo(f"Created campaign: {campaign.name}")
    click.echo(f"  ID: {campaign.id}")


@campaign_group.command("list")
@click.pass_context
def list_campaigns(ctx: click.Context) -> None:
    """List all campaigns."""
    service = _get_campaign_service(ctx)
    campaigns = service.list_all()
    if not campaigns:
        click.echo("No campaigns found.")
        return
    for c in campaigns:
        click.echo(f"{c.id:38s}  {c.status:10s}  {c.name}")


@campaign_group.command("show")
@click.argument("campaign_id")
@click.pass_context
def show(ctx: click.Context, campaign_id: str) -> None:
    """Show campaign details."""
    service = _get_campaign_service(ctx)
    try:
        campaign = service.get_by_id(campaign_id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Name:        {campaign.name}")
    click.echo(f"ID:          {campaign.id}")
    click.echo(f"Status:      {campaign.status}")
    click.echo(f"Created:     {campaign.created_at}")
    if campaign.description:
        click.echo(f"Description: {campaign.description}")

    versions = service.list_versions(campaign_id)
    click.echo(f"\nVersions ({len(versions)}):")
    for v in versions:
        click.echo(f"  v{v.version_number}  {v.id}  [{v.status}]  {v.notes or ''}")


@campaign_group.command("version")
@click.argument("campaign_id")
@click.option("--tests", "-t", multiple=True, help="Test definition IDs to include")
@click.option("--notes", default=None, help="Version notes")
@click.pass_context
def create_version(
    ctx: click.Context, campaign_id: str, tests: tuple[str, ...], notes: str | None
) -> None:
    """Create a new version of a campaign."""
    service = _get_campaign_service(ctx)
    try:
        version = service.create_version(campaign_id, list(tests), notes)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Created version v{version.version_number}")
    click.echo(f"  ID: {version.id}")
    click.echo(f"  Tests included: {len(tests)}")


@campaign_group.command("status")
@click.argument("campaign_version_id")
@click.pass_context
def status(ctx: click.Context, campaign_version_id: str) -> None:
    """Show campaign version status and test run summary."""
    service = _get_campaign_service(ctx)
    try:
        summary = service.get_summary(campaign_version_id)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Campaign: {summary['campaign_name']}  v{summary['version_number']}")
    click.echo(f"Tests:    {summary['total_tests']} total")
    click.echo(f"  Passed:  {summary['passed']}")
    click.echo(f"  Failed:  {summary['failed']}")
    click.echo(f"  Error:   {summary['error']}")
    click.echo(f"  Skipped: {summary['skipped']}")
    click.echo(f"  Pending: {summary['pending']}")
    click.echo(f"Pass rate: {summary['pass_rate']}%")

    if summary["test_results"]:
        click.echo()
        for tr in summary["test_results"]:
            icons = {
                "passed": "[PASS]",
                "failed": "[FAIL]",
                "error": "[ERR ]",
                "skipped": "[SKIP]",
                "pending": "[PEND]",
            }
            status_icon = icons.get(tr["status"], "[???]")
            click.echo(f"  {status_icon}  {tr['test_name']}")


@campaign_group.command("report")
@click.argument("campaign_version_id")
@click.option("--format", "fmt", type=click.Choice(["text", "json", "html"]), default="text")
@click.option("--output", "-o", default=None, help="Write report to file")
@click.pass_context
def report(
    ctx: click.Context, campaign_version_id: str, fmt: str, output: str | None
) -> None:
    """Generate a report for a campaign version."""
    reporting = _get_reporting_service(ctx)
    try:
        if fmt == "json":
            if output:
                reporting.export_json(campaign_version_id, output)
                click.echo(f"Report written to {output}")
            else:
                click.echo(
                    json.dumps(
                        reporting.build_summary(campaign_version_id), indent=2, default=str
                    )
                )
        elif fmt == "html":
            if output:
                reporting.export_html(campaign_version_id, output)
                click.echo(f"Report written to {output}")
            else:
                from verify.shared.database import get_exports_dir

                dest = str(get_exports_dir() / f"report_{campaign_version_id}.html")
                reporting.export_html(campaign_version_id, dest)
                click.echo(f"Report written to {dest}")
        else:
            text = reporting.export_text(campaign_version_id)
            if output:
                with open(output, "w") as f:
                    f.write(text)
                click.echo(f"Report written to {output}")
            else:
                click.echo(text)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)


@campaign_group.command("rerun")
@click.argument("campaign_id")
@click.argument("previous_version_id")
@click.option("--notes", help="Version notes")
@click.pass_context
def rerun_failed(ctx, campaign_id, previous_version_id, notes):
    """Create a new version with only the failed tests from a previous version."""
    service = _get_campaign_service(ctx)
    try:
        version = service.create_version_from_failed(campaign_id, previous_version_id, notes)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)
    click.echo(f"Created re-run version v{version.version_number} ({version.id})")


@campaign_group.command("compare")
@click.argument("version_a")
@click.argument("version_b")
@click.pass_context
def compare_versions(ctx, version_a, version_b):
    """Compare two campaign versions."""
    service = _get_campaign_service(ctx)
    try:
        diff = service.compare_versions(version_a, version_b)
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)

    click.echo(f"Tests changed status: {len(diff.get('changed', []))}")
    for c in diff.get("changed", []):
        click.echo(f"  {c['test_name']}: {c['status_a']} → {c['status_b']}")
    click.echo(f"Tests only in A: {len(diff.get('only_in_a', []))}")
    click.echo(f"Tests only in B: {len(diff.get('only_in_b', []))}")


@campaign_group.command("set-due-date")
@click.argument("campaign_id")
@click.argument("date")
@click.pass_context
def set_due_date(ctx, campaign_id, date):
    """Set the due date for a campaign."""
    service = _get_campaign_service(ctx)
    try:
        campaign = service.set_due_date(campaign_id, date)
        click.echo(f"Due date set to {campaign.due_date}")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)


@campaign_group.command("set-milestone")
@click.argument("version_id")
@click.argument("milestone")
@click.pass_context
def set_milestone(ctx, version_id, milestone):
    """Set the milestone label on a campaign version."""
    service = _get_campaign_service(ctx)
    try:
        version = service.set_milestone(version_id, milestone)
        click.echo(f"Milestone set: {version.milestone}")
    except NotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(2)
