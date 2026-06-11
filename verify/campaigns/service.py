"""Campaign service — create, version, execute, report."""

from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from verify.campaigns.models import Campaign, CampaignVersion, TestRun
from verify.definitions.models import TestDefinition
from verify.shared.database import make_service_session
from verify.shared.exceptions import NotFoundError, ValidationError


class CampaignService(Protocol):
    """Interface for campaign lifecycle operations."""

    def create(self, name: str, description: str | None = None) -> Campaign:
        """Create a new campaign in draft status."""
        ...

    def list_all(self) -> list[Campaign]:
        """List all campaigns."""
        ...

    def get_by_id(self, campaign_id: str) -> Campaign:
        """Retrieve a campaign by its UUID."""
        ...

    def create_version(
        self,
        campaign_id: str,
        test_definition_ids: list[str],
        notes: str | None = None,
    ) -> CampaignVersion:
        """Create a new version of a campaign with a selected set of tests."""
        ...

    def list_versions(self, campaign_id: str) -> list[CampaignVersion]:
        """List all versions of a campaign."""
        ...

    def get_test_runs(self, campaign_version_id: str) -> list[TestRun]:
        """List all test runs for a given campaign version."""
        ...

    def update_test_run_status(
        self, test_run_id: str, status: str, notes: str | None = None
    ) -> TestRun:
        """Update the status of a test run."""
        ...

    def get_summary(self, campaign_version_id: str) -> dict:
        """Return a summary of a campaign version: pass/fail/coverage stats."""
        ...

    def create_version_from_failed(
        self, campaign_id: str, previous_version_id: str, notes: str | None = None
    ) -> CampaignVersion:
        """Create a new version containing only the failed/error tests from a previous version."""
        ...

    def compare_versions(self, version_id_a: str, version_id_b: str) -> dict:
        """Compare two campaign versions: test status changes, tests added/removed."""
        ...

    def set_milestone(self, version_id: str, milestone: str) -> CampaignVersion:
        """Set the milestone label on a campaign version."""
        ...

    def set_due_date(self, campaign_id: str, due_date: str) -> Campaign:
        """Set the due date on a campaign (accepts ISO format string)."""
        ...

    def list_templates(self) -> list[Campaign]:
        """List campaigns marked as templates."""
        ...


class CampaignServiceImpl:
    """Concrete implementation of CampaignService."""

    def __init__(self, session_factory) -> None:
        self._session_factory = lambda: make_service_session(session_factory)

    def create(self, name: str, description: str | None = None) -> Campaign:
        with self._session_factory() as session:
            campaign = Campaign(name=name, description=description)
            session.add(campaign)
            session.commit()
            session.expunge(campaign)
            return campaign

    def list_all(self) -> list[Campaign]:
        with self._session_factory() as session:
            stmt = select(Campaign).order_by(Campaign.name)
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results

    def get_by_id(self, campaign_id: str) -> Campaign:
        with self._session_factory() as session:
            stmt = select(Campaign).where(Campaign.id == campaign_id)
            campaign = session.execute(stmt).scalar_one_or_none()
            if campaign is None:
                raise NotFoundError(f"Campaign with id '{campaign_id}' not found")
            session.expunge(campaign)
            return campaign

    def create_version(
        self,
        campaign_id: str,
        test_definition_ids: list[str],
        notes: str | None = None,
    ) -> CampaignVersion:
        with self._session_factory() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()
            if campaign is None:
                raise NotFoundError(f"Campaign with id '{campaign_id}' not found")

            for td_id in test_definition_ids:
                td = session.execute(
                    select(TestDefinition).where(TestDefinition.id == td_id)
                ).scalar_one_or_none()
                if td is None:
                    raise NotFoundError(f"TestDefinition with id '{td_id}' not found")

            max_vn = session.execute(
                select(func.max(CampaignVersion.version_number)).where(
                    CampaignVersion.campaign_id == campaign_id
                )
            ).scalar()
            next_version = (max_vn or 0) + 1

            version = CampaignVersion(
                campaign_id=campaign_id,
                version_number=next_version,
                notes=notes,
            )
            session.add(version)
            session.flush()

            for td_id in test_definition_ids:
                tr = TestRun(
                    campaign_version_id=version.id,
                    test_definition_id=td_id,
                )
                session.add(tr)

            session.commit()
            session.expunge(version)
            return version

    def list_versions(self, campaign_id: str) -> list[CampaignVersion]:
        with self._session_factory() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()
            if campaign is None:
                raise NotFoundError(f"Campaign with id '{campaign_id}' not found")

            stmt = (
                select(CampaignVersion)
                .where(CampaignVersion.campaign_id == campaign_id)
                .order_by(CampaignVersion.version_number.desc())
            )
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results

    def get_test_runs(self, campaign_version_id: str) -> list[TestRun]:
        with self._session_factory() as session:
            version = session.execute(
                select(CampaignVersion).where(CampaignVersion.id == campaign_version_id)
            ).scalar_one_or_none()
            if version is None:
                raise NotFoundError(
                    f"CampaignVersion with id '{campaign_version_id}' not found"
                )

            stmt = (
                select(TestRun)
                .where(TestRun.campaign_version_id == campaign_version_id)
                .options(selectinload(TestRun.test_definition))
            )
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
                if r.test_definition is not None:
                    session.expunge(r.test_definition)
            return results

    def update_test_run_status(
        self, test_run_id: str, status: str, notes: str | None = None
    ) -> TestRun:
        from datetime import datetime, timezone

        with self._session_factory() as session:
            tr = session.execute(
                select(TestRun).where(TestRun.id == test_run_id)
            ).scalar_one_or_none()
            if tr is None:
                raise NotFoundError(f"TestRun with id '{test_run_id}' not found")

            tr.status = status
            if notes is not None:
                tr.notes = notes

            now = datetime.now(timezone.utc)
            if status == "running" and tr.started_at is None:
                tr.started_at = now
            elif status in ("passed", "failed", "error", "skipped"):
                if tr.started_at is None:
                    tr.started_at = now
                tr.completed_at = now

            session.commit()
            session.expunge(tr)
            return tr

    def get_summary(self, campaign_version_id: str) -> dict:
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

            counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "pending": 0}
            details = []
            for tr in runs:
                status = tr.status or "pending"
                if status in counts:
                    counts[status] += 1
                else:
                    counts["pending"] += 1

                details.append({
                    "test_run_id": tr.id,
                    "test_name": tr.test_definition.name if tr.test_definition else "N/A",
                    "status": tr.status,
                    "notes": tr.notes,
                })

            total = len(runs)
            completed = total - counts["pending"]
            passed = counts["passed"]
            pass_rate = (passed / completed * 100) if completed > 0 else 0.0

            return {
                "campaign_name": version.campaign.name,
                "version_number": version.version_number,
                "total_tests": total,
                "passed": counts["passed"],
                "failed": counts["failed"],
                "error": counts["error"],
                "skipped": counts["skipped"],
                "pending": counts["pending"],
                "pass_rate": round(pass_rate, 1),
                "test_results": details,
            }

    def create_version_from_failed(
        self,
        campaign_id: str,
        previous_version_id: str,
        notes: str | None = None,
    ) -> CampaignVersion:
        with self._session_factory() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()
            if campaign is None:
                raise NotFoundError(f"Campaign with id '{campaign_id}' not found")

            prev_version = session.execute(
                select(CampaignVersion).where(CampaignVersion.id == previous_version_id)
            ).scalar_one_or_none()
            if prev_version is None:
                raise NotFoundError(
                    f"CampaignVersion with id '{previous_version_id}' not found"
                )

            failed_runs = list(
                session.execute(
                    select(TestRun).where(
                        TestRun.campaign_version_id == previous_version_id,
                        TestRun.status.in_(["failed", "error"]),
                    )
                ).scalars()
            )

            if not failed_runs:
                raise ValidationError(
                    "No failed or error tests found in the previous version"
                )

            max_vn = session.execute(
                select(func.max(CampaignVersion.version_number)).where(
                    CampaignVersion.campaign_id == campaign_id
                )
            ).scalar()
            next_version = (max_vn or 0) + 1

            version = CampaignVersion(
                campaign_id=campaign_id,
                version_number=next_version,
                notes=notes,
            )
            session.add(version)
            session.flush()

            seen: set[str] = set()
            for tr in failed_runs:
                if tr.test_definition_id not in seen:
                    seen.add(tr.test_definition_id)
                    new_tr = TestRun(
                        campaign_version_id=version.id,
                        test_definition_id=tr.test_definition_id,
                    )
                    session.add(new_tr)

            session.commit()
            session.expunge(version)
            return version

    def compare_versions(self, version_id_a: str, version_id_b: str) -> dict:
        with self._session_factory() as session:
            runs_a = list(
                session.execute(
                    select(TestRun).where(
                        TestRun.campaign_version_id == version_id_a
                    )
                ).scalars()
            )
            runs_b = list(
                session.execute(
                    select(TestRun).where(
                        TestRun.campaign_version_id == version_id_b
                    )
                ).scalars()
            )

            map_a = {tr.test_definition_id: tr for tr in runs_a}
            map_b = {tr.test_definition_id: tr for tr in runs_b}

            ids_a = set(map_a.keys())
            ids_b = set(map_b.keys())

            added = list(ids_b - ids_a)
            removed = list(ids_a - ids_b)
            common = ids_a & ids_b

            changed = []
            for td_id in common:
                a = map_a[td_id]
                b = map_b[td_id]
                if a.status != b.status:
                    changed.append({
                        "test_definition_id": td_id,
                        "status_a": a.status,
                        "status_b": b.status,
                    })

            return {
                "version_id_a": version_id_a,
                "version_id_b": version_id_b,
                "added_test_definition_ids": added,
                "removed_test_definition_ids": removed,
                "changed": changed,
            }

    def set_milestone(self, version_id: str, milestone: str) -> CampaignVersion:
        with self._session_factory() as session:
            version = session.execute(
                select(CampaignVersion).where(CampaignVersion.id == version_id)
            ).scalar_one_or_none()
            if version is None:
                raise NotFoundError(
                    f"CampaignVersion with id '{version_id}' not found"
                )
            version.milestone = milestone
            session.commit()
            session.expunge(version)
            return version

    def set_due_date(self, campaign_id: str, due_date: str) -> Campaign:
        with self._session_factory() as session:
            campaign = session.execute(
                select(Campaign).where(Campaign.id == campaign_id)
            ).scalar_one_or_none()
            if campaign is None:
                raise NotFoundError(f"Campaign with id '{campaign_id}' not found")
            campaign.due_date = datetime.fromisoformat(due_date)
            session.commit()
            session.expunge(campaign)
            return campaign

    def list_templates(self) -> list[Campaign]:
        with self._session_factory() as session:
            stmt = select(Campaign).where(Campaign.is_template.is_(True))
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results
