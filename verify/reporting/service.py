"""Reporting service — generate summaries and export reports."""


import json
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from verify.campaigns.models import CampaignVersion, TestRun
from verify.evidence.models import Evidence
from verify.shared.database import make_service_session
from verify.shared.exceptions import NotFoundError


class ReportingService(Protocol):
    """Interface for generating validation reports."""

    def build_summary(self, campaign_version_id: str) -> dict:
        """Build a summary dictionary for a campaign version.

        Returns:
            dict with keys:
                - campaign_name
                - version_number
                - total_tests
                - passed / failed / error / skipped / pending counts
                - coverage_percent
                - evidence_count
                - test_results: list of per-test details
        """
        ...

    def export_json(self, campaign_version_id: str, output_path: str) -> None:
        """Write a JSON report to the given path."""
        ...

    def export_text(self, campaign_version_id: str) -> str:
        """Return a human-readable text table."""
        ...

    def export_html(self, campaign_version_id: str, output_path: str) -> None:
        """Write a self-contained HTML report to the given path."""
        ...


class ReportingServiceImpl:
    """Concrete implementation using database queries."""

    def __init__(self, session_factory) -> None:
        self._session_factory = lambda: make_service_session(session_factory)

    def build_summary(self, campaign_version_id: str) -> dict:
        with self._session_factory() as session:
            version = session.execute(
                select(CampaignVersion)
                .where(CampaignVersion.id == campaign_version_id)
                .options(selectinload(CampaignVersion.campaign))
            ).scalar_one_or_none()
            if version is None:
                raise NotFoundError(
                    f"CampaignVersion with id '{campaign_version_id}' not found"
                )

            runs = list(
                session.execute(
                    select(TestRun)
                    .where(TestRun.campaign_version_id == campaign_version_id)
                    .options(selectinload(TestRun.test_definition))
                ).scalars()
            )

            evidence_count = session.execute(
                select(Evidence).join(TestRun).where(
                    TestRun.campaign_version_id == campaign_version_id
                )
            ).scalars()
            evidence_count = len(list(evidence_count)) if evidence_count else 0

            counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "pending": 0}
            test_details = []
            for tr in runs:
                status = tr.status or "pending"
                if status in counts:
                    counts[status] += 1
                else:
                    counts["pending"] += 1

                test_details.append({
                    "test_run_id": tr.id,
                    "test_name": tr.test_definition.name if tr.test_definition else "N/A",
                    "test_definition_id": tr.test_definition_id,
                    "status": tr.status,
                    "started_at": tr.started_at.isoformat() if tr.started_at else None,
                    "completed_at": tr.completed_at.isoformat() if tr.completed_at else None,
                    "notes": tr.notes,
                    "executor": tr.executor,
                })

            total = len(runs)
            completed = total - counts["pending"]
            coverage_percent = round(
                (counts["passed"] / completed * 100) if completed > 0 else 0.0, 1
            )

            return {
                "campaign_name": version.campaign.name,
                "campaign_id": version.campaign_id,
                "version_number": version.version_number,
                "version_id": version.id,
                "version_notes": version.notes,
                "version_created_at": (
                    version.created_at.isoformat() if version.created_at else None
                ),
                "total_tests": total,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "error": counts["error"],
                "skipped": counts["skipped"],
                "pending": counts["pending"],
                "coverage_percent": coverage_percent,
                "evidence_count": evidence_count,
                "test_results": test_details,
            }

    def export_json(self, campaign_version_id: str, output_path: str) -> None:
        summary = self.build_summary(campaign_version_id)
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

    def export_text(self, campaign_version_id: str) -> str:
        from tabulate import tabulate

        summary = self.build_summary(campaign_version_id)

        lines = [
            f"Report: {summary['campaign_name']}",
            f"Version: v{summary['version_number']}",
            f"Created: {summary['version_created_at']}",
            "",
            f"Total tests:    {summary['total_tests']}",
            f"  Passed:       {summary['passed']}",
            f"  Failed:       {summary['failed']}",
            f"  Error:        {summary['error']}",
            f"  Skipped:      {summary['skipped']}",
            f"  Pending:      {summary['pending']}",
            f"Pass rate:      {summary['coverage_percent']}%",
            f"Evidence items: {summary['evidence_count']}",
        ]

        if summary["test_results"]:
            rows = []
            for tr in summary["test_results"]:
                rows.append([
                    tr["test_name"],
                    tr["status"] or "",
                    tr["notes"] or "",
                ])
            lines.append("")
            lines.append(tabulate(rows, headers=["Test", "Status", "Notes"], tablefmt="simple"))

        return "\n".join(lines)

    def export_html(self, campaign_version_id: str, output_path: str) -> None:
        summary = self.build_summary(campaign_version_id)
        html = _build_html_report(summary)
        with open(output_path, "w") as f:
            f.write(html)


def _build_html_report(summary: dict) -> str:
    passed = summary["passed"]
    failed = summary["failed"]
    error = summary["error"]
    skipped = summary["skipped"]
    pending = summary["pending"]
    total = summary["total_tests"]
    pass_rate = summary["coverage_percent"]
    name = _esc(summary["campaign_name"])
    vnum = summary["version_number"]
    vnotes = _esc(summary["version_notes"]) if summary.get("version_notes") else ""
    created = summary["version_created_at"] or "N/A"
    evidence = summary["evidence_count"]

    rows = ""
    for tr in summary["test_results"]:
        status = tr["status"] or "pending"
        status_class = {
            "passed": "status-passed",
            "failed": "status-failed",
            "error": "status-error",
            "skipped": "status-skipped",
            "pending": "status-pending",
        }.get(status, "status-pending")
        rows += (
            "<tr>"
            f"<td>{_esc(tr['test_name'])}</td>"
            f"<td class=\"{status_class}\">{_esc(status)}</td>"
            f"<td>{_esc(tr['notes'] or '')}</td>"
            "</tr>\n"
        )

    def _tag(tag: str, count: int, extra_class: str = "") -> str:
        cls = f" {extra_class}" if extra_class else ""
        return (
            f'<div class="stat-card{cls}">'
            f'<div class="label">{tag}</div>'
            f'<div class="value">{count}</div>'
            "</div>"
        )

    stats_html = "\n    ".join([
        _tag("Total", total),
        _tag("Passed", passed, "stat-passed"),
        _tag("Failed", failed, "stat-failed"),
        _tag("Errors", error, "stat-error"),
        _tag("Skipped", skipped, "stat-skipped"),
        _tag("Pending", pending, "stat-pending"),
    ])

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        f"<title>Validation Report &mdash; {name} v{vnum}</title>\n"
        "<style>\n"
        "*, *::before, *::after {\n"
        "  box-sizing: border-box; margin: 0; padding: 0;\n"
        "}\n"
        "body {\n"
        "  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,\n"
        "    sans-serif;\n"
        "  line-height: 1.6; color: #1a1a2e;\n"
        "  background: #f8f9fa; padding: 2rem;\n"
        "}\n"
        ".report {\n"
        "  max-width: 960px; margin: 0 auto; background: #fff;\n"
        "  border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);\n"
        "  padding: 2rem;\n"
        "}\n"
        "h1 { font-size: 1.5rem; color: #16213e; margin-bottom: .25rem; }\n"
        "h2 {\n"
        "  font-size: 1.1rem; color: #0f3460;\n"
        "  margin: 1.5rem 0 .75rem;\n"
        "  border-bottom: 2px solid #e94560; padding-bottom: .25rem;\n"
        "}\n"
        ".subtitle { color: #6c757d; font-size: .9rem; margin-bottom: 1.5rem; }\n"
        ".stats {\n"
        "  display: grid;\n"
        "  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));\n"
        "  gap: .75rem; margin-bottom: 1.5rem;\n"
        "}\n"
        ".stat-card {\n"
        "  background: #f0f2f5; border-radius: 6px;\n"
        "  padding: 1rem; text-align: center;\n"
        "}\n"
        ".stat-card .label {\n"
        "  font-size: .8rem; color: #6c757d;\n"
        "  text-transform: uppercase; letter-spacing: .5px;\n"
        "}\n"
        ".stat-card .value { font-size: 1.5rem; font-weight: 700; }\n"
        ".stat-passed .value { color: #198754; }\n"
        ".stat-failed .value { color: #dc3545; }\n"
        ".stat-error .value { color: #fd7e14; }\n"
        ".stat-skipped .value { color: #6c757d; }\n"
        ".stat-pending .value { color: #0d6efd; }\n"
        "table { width: 100%; border-collapse: collapse; font-size: .9rem; }\n"
        "th {\n"
        "  text-align: left; padding: .6rem .75rem;\n"
        "  background: #e9ecef; font-weight: 600;\n"
        "  border-bottom: 2px solid #dee2e6;\n"
        "}\n"
        "td { padding: .5rem .75rem; border-bottom: 1px solid #e9ecef; }\n"
        "tr:hover { background: #f8f9fa; }\n"
        ".status-passed { color: #198754; font-weight: 600; }\n"
        ".status-failed { color: #dc3545; font-weight: 600; }\n"
        ".status-error { color: #fd7e14; font-weight: 600; }\n"
        ".status-skipped { color: #6c757d; }\n"
        ".status-pending { color: #0d6efd; }\n"
        "@media print {\n"
        "  body { background: #fff; padding: 0; }\n"
        "  .report { box-shadow: none; border-radius: 0; max-width: 100%; }\n"
        "  tr:hover { background: transparent; }\n"
        "}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<div class=\"report\">\n"
        "<h1>Validation Report</h1>\n"
        "<div class=\"subtitle\">\n"
        f"  {name} &mdash; Version {vnum}"
        + (f" &mdash; {vnotes}" if vnotes else "")
        + f"<br>\n"
        f"  Created: {created}\n"
        "</div>\n"
        "\n"
        "<h2>Summary</h2>\n"
        "<div class=\"stats\">\n"
        f"    {stats_html}\n"
        "</div>\n"
        f"<p><strong>Pass rate:</strong> {pass_rate}%</p>\n"
        f"<p><strong>Evidence items:</strong> {evidence}</p>\n"
        "\n"
        "<h2>Test Results</h2>\n"
        "<table>\n"
        "<thead><tr><th>Test</th><th>Status</th><th>Notes</th></tr></thead>\n"
        "<tbody>\n"
        f"{rows}"
        "</tbody>\n"
        "</table>\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
