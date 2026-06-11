"""Verify CLI — entry point."""

from pathlib import Path

import click

from verify.cli.campaigns import campaign_group
from verify.cli.evidence_commands import evidence_group
from verify.cli.export import export_group
from verify.cli.help import help_group
from verify.cli.requirements import requirement_group
from verify.cli.tests import test_group
from verify.shared.database import get_session_factory, init_db


@click.group()
@click.option("--db-path", envvar="VERIFY_DB_PATH", help="SQLite database path")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx, db_path, quiet, verbose):
    """Verify — Validation campaign management platform."""
    if db_path:
        import os

        os.environ["VERIFY_DB_PATH"] = db_path
    ctx.meta["quiet"] = quiet
    ctx.meta["verbose"] = verbose
    init_db()
    ctx.meta["session_factory"] = get_session_factory()


main.add_command(requirement_group)
main.add_command(campaign_group)
main.add_command(evidence_group)
main.add_command(test_group)
main.add_command(help_group)
main.add_command(export_group)


@main.command("dashboard")
@click.pass_context
def dashboard(ctx):
    """Launch the terminal dashboard."""
    from verify.cli.tui import VerifyDashboard

    app = VerifyDashboard(ctx.meta["session_factory"])
    app.run()


@main.command("init", help="Initialize Verify data directory")
@click.option("--home", envvar="VERIFY_HOME", help="Verify data directory")
def init_cmd(home):
    """Create the Verify data directory and initialize the database."""
    from verify.shared.database import ensure_safe_directory, get_verify_home

    if home:
        import os

        os.environ["VERIFY_HOME"] = home
    home_dir = get_verify_home()
    ensure_safe_directory(home_dir)
    click.echo(f"Verify home: {home_dir}")
    init_db()
    click.echo("Database initialized.")


@main.command("example")
@click.argument("domain", type=click.Choice(["kubernetes", "webui", "api"]))
def example_cmd(domain):
    """Print a worked example for a domain."""
    examples_readme = Path(__file__).resolve().parent.parent.parent / "examples" / "README.md"
    if not examples_readme.exists():
        click.echo("Error: examples/README.md not found", err=True)
        raise SystemExit(1)

    raw = examples_readme.read_text()

    # Extract the section for the requested domain
    sections = _parse_examples_readme(raw)

    if domain not in sections:
        click.echo(f"Error: no example for domain '{domain}'", err=True)
        raise SystemExit(1)

    content = sections[domain]

    try:
        from rich.console import Console
        from rich.markdown import Markdown

        Console().print(Markdown(content))
    except ImportError:
        click.echo(content)


def _parse_examples_readme(raw: str) -> dict[str, str]:
    """Split examples/README.md into per-domain sections.

    Sections are keyed by domain name, identified by section headings.
    """
    sections: dict[str, str] = {}
    heading_map = {
        "## 1. kubernetes compliance": "kubernetes",
        "## 2. web ui testing": "webui",
        "## 3. api validation": "api",
    }

    parts = raw.split("\n---\n")
    for part in parts:
        stripped = part.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        for heading, key in heading_map.items():
            if heading in lower:
                sections[key] = stripped
                break

    return sections


@main.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def show_completion(shell):
    """Print shell completion script for the given shell."""
    if shell == "bash":
        click.echo('eval "$(_VERIFY_COMPLETE=bash_source verify)"')
    elif shell == "zsh":
        click.echo('eval "$(_VERIFY_COMPLETE=zsh_source verify)"')
    elif shell == "fish":
        click.echo('_VERIFY_COMPLETE=fish_source verify | source')
