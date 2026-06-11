"""TUI dashboard for Verify."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    TabbedContent,
    TabPane,
)

from verify.campaigns.service import CampaignServiceImpl
from verify.requirements.service import RequirementServiceImpl


class VerifyDashboard(App):
    """Terminal dashboard for Verify validation campaigns."""

    CSS = """
    #campaigns-table {
        height: 2fr;
        min-height: 3;
    }

    #versions-table {
        height: 1fr;
        min-height: 3;
        margin-top: 1;
    }

    #versions-label {
        height: 1;
        margin-top: 1;
        color: $text-disabled;
    }

    #requirements-table {
        height: 1fr;
        min-height: 3;
    }

    #search-input {
        margin-bottom: 1;
    }

    #test-runs-table {
        height: 1fr;
        min-height: 3;
    }

    #selected-version-label {
        height: auto;
        color: $text-disabled;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("1", "focus_tab('campaigns')", "Campaigns", show=True),
        Binding("2", "focus_tab('requirements')", "Requirements", show=True),
        Binding("3", "focus_tab('test-runs')", "Test Runs", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("slash", "search_requirements", "Search", show=False, key_display="/"),
    ]

    def __init__(self, session_factory):
        super().__init__()
        self.campaign_svc = CampaignServiceImpl(session_factory)
        self.req_svc = RequirementServiceImpl(session_factory)
        self._selected_version_id: str | None = None
        self._campaign_id_for_versions: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Campaigns", id="campaigns"):
                with VerticalScroll():
                    yield DataTable(id="campaigns-table", cursor_type="row")
                    yield Label("", id="versions-label")
                    yield DataTable(id="versions-table", cursor_type="row")
            with TabPane("Requirements", id="requirements"):
                with VerticalScroll():
                    yield Input(
                        placeholder="Type to filter by key or title...",
                        id="search-input",
                    )
                    yield DataTable(id="requirements-table", cursor_type="row")
            with TabPane("Test Runs", id="test-runs"):
                with VerticalScroll():
                    yield Label(
                        "Select a version: press Enter on a version row in the Campaigns tab",
                        id="selected-version-label",
                    )
                    yield DataTable(id="test-runs-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self._init_tables()
        self._populate_campaigns()
        self._populate_requirements()
        self._populate_test_runs()

    def _init_tables(self) -> None:
        campaigns = self.query_one("#campaigns-table", DataTable)
        campaigns.add_column("Name")
        campaigns.add_column("Status")
        campaigns.add_column("Due Date")
        campaigns.add_column("Pass Rate")

        versions = self.query_one("#versions-table", DataTable)
        versions.add_column("Version")
        versions.add_column("Status")
        versions.add_column("Milestone")
        versions.add_column("Tests P/F/E/S")
        versions.add_column("Created")

        reqs = self.query_one("#requirements-table", DataTable)
        reqs.add_column("Key")
        reqs.add_column("Title")
        reqs.add_column("Domain")
        reqs.add_column("Archived")

        runs = self.query_one("#test-runs-table", DataTable)
        runs.add_column("Test Name")
        runs.add_column("Status")
        runs.add_column("Executor")
        runs.add_column("Notes")

    # ── populate helpers ──────────────────────────────────────────────

    def _populate_campaigns(self) -> None:
        table = self.query_one("#campaigns-table", DataTable)
        table.clear()
        try:
            campaigns = self.campaign_svc.list_all()
        except Exception:
            return

        for campaign in campaigns:
            versions = self.campaign_svc.list_versions(campaign.id)
            pass_rate_str = "-"
            if versions:
                try:
                    summary = self.campaign_svc.get_summary(versions[0].id)
                    total = summary["total_tests"]
                    if total > 0:
                        pass_rate_str = (
                            f"{summary['pass_rate']}% ({summary['passed']}/{total})"
                        )
                except Exception:
                    pass

            due_date = (
                campaign.due_date.strftime("%Y-%m-%d")
                if campaign.due_date
                else "-"
            )

            table.add_row(
                campaign.name,
                campaign.status,
                due_date,
                pass_rate_str,
                key=campaign.id,
            )

        self._sync_campaign_versions()

    def _sync_campaign_versions(self) -> None:
        """Re-populate versions if the current campaign is still selected."""
        if self._campaign_id_for_versions:
            self._populate_versions(self._campaign_id_for_versions)

    def _populate_versions(self, campaign_id: str) -> None:
        self._campaign_id_for_versions = campaign_id
        label = self.query_one("#versions-label", Label)
        table = self.query_one("#versions-table", DataTable)
        table.clear()

        try:
            campaign = self.campaign_svc.get_by_id(campaign_id)
            versions = self.campaign_svc.list_versions(campaign_id)
        except Exception:
            label.update("")
            return

        label.update(f"Versions for {campaign.name}:")

        for v in versions:
            try:
                summary = self.campaign_svc.get_summary(v.id)
                stats = (
                    f"{summary['passed']}/{summary['failed']}/"
                    f"{summary['error']}/{summary['skipped']}"
                )
            except Exception:
                stats = "-/-/-/-"

            created = (
                v.created_at.strftime("%Y-%m-%d %H:%M")
                if v.created_at
                else "-"
            )

            table.add_row(
                f"v{v.version_number}",
                v.status,
                v.milestone or "-",
                stats,
                created,
                key=v.id,
            )

    def _populate_requirements(self, query: str = "") -> None:
        table = self.query_one("#requirements-table", DataTable)
        table.clear()
        try:
            requirements = self.req_svc.list_all()
        except Exception:
            return

        q = query.strip().lower()
        for req in requirements:
            if q and q not in req.key.lower() and q not in req.title.lower():
                continue
            table.add_row(
                req.key,
                req.title,
                req.domain,
                "Yes" if req.archived else "No",
                key=req.id,
            )

    def _populate_test_runs(self) -> None:
        table = self.query_one("#test-runs-table", DataTable)
        label = self.query_one("#selected-version-label", Label)
        table.clear()

        if not self._selected_version_id:
            label.update(
                "Select a version: press Enter on a version row in the Campaigns tab"
            )
            return

        try:
            test_runs = self.campaign_svc.get_test_runs(self._selected_version_id)
            summary = self.campaign_svc.get_summary(self._selected_version_id)
        except Exception:
            label.update("Error loading test runs.")
            return

        label.update(
            f"{summary['campaign_name']}  v{summary['version_number']}  "
            f"P:{summary['passed']} F:{summary['failed']} "
            f"E:{summary['error']} S:{summary['skipped']} Pend:{summary['pending']}  "
            f"({summary['pass_rate']}% pass rate)"
        )

        color_map = {
            "passed": "green",
            "failed": "red",
            "error": "yellow",
            "skipped": "yellow",
            "running": "blue",
        }

        for tr in test_runs:
            status = tr.status or "pending"
            color = color_map.get(status, "dim")
            test_name = (
                tr.test_definition.name
                if tr.test_definition
                else "N/A"
            )

            table.add_row(
                test_name,
                f"[{color}]{status}[/{color}]",
                tr.executor or "-",
                tr.notes or "-",
                key=tr.id,
            )

    # ── event handlers ────────────────────────────────────────────────

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        row_key = event.row_key
        if row_key is None:
            return

        table = event.control
        if table.id == "campaigns-table":
            self._selected_version_id = None
            self._populate_versions(row_key.value)
            self._populate_test_runs()
        elif table.id == "versions-table":
            self._selected_version_id = row_key.value
            self._populate_test_runs()
            self.query_one(TabbedContent).active = "test-runs"

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._populate_requirements(event.value)

    # ── actions ──────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._populate_campaigns()
        self._populate_requirements(
            self.query_one("#search-input", Input).value
        )
        if self._selected_version_id:
            self._populate_test_runs()

    def action_focus_tab(self, tab_id: str) -> None:
        tab_content = self.query_one(TabbedContent)
        tab_content.active = tab_id
        if tab_id == "campaigns":
            self.query_one("#campaigns-table", DataTable).focus()
        elif tab_id == "requirements":
            self.query_one("#search-input", Input).focus()
        elif tab_id == "test-runs":
            self.query_one("#test-runs-table", DataTable).focus()

    def action_search_requirements(self) -> None:
        self.query_one(TabbedContent).active = "requirements"
        self.query_one("#search-input", Input).focus()
