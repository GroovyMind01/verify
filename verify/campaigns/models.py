"""Campaign domain model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verify.shared.models import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from verify.definitions.models import TestDefinition
    from verify.evidence.models import Evidence


class Campaign(Base, UUIDMixin, TimestampMixin):
    """A validation campaign — a container for versioned test execution plans."""

    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    versions: Mapped[list["CampaignVersion"]] = relationship(
        "CampaignVersion", back_populates="campaign", cascade="all, delete-orphan",
        order_by="CampaignVersion.version_number"
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.name}>"


class CampaignVersion(Base, UUIDMixin):
    """An immutable snapshot of a campaign at a point in time.

    Each version captures which tests were selected, the state of the
    requirement set, and the test runs executed against it.
    """

    __tablename__ = "campaign_versions"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    milestone: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="versions")
    test_runs: Mapped[list["TestRun"]] = relationship(
        "TestRun", back_populates="campaign_version", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CampaignVersion {self.campaign_id} v{self.version_number}>"


class TestRun(Base, UUIDMixin):
    """A single execution of a TestDefinition within a specific CampaignVersion."""

    __tablename__ = "test_runs"

    campaign_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaign_versions.id"), nullable=False
    )
    test_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_definitions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    executor: Mapped[str | None] = mapped_column(String(256))
    output: Mapped[str | None] = mapped_column(Text)

    campaign_version: Mapped["CampaignVersion"] = relationship(back_populates="test_runs")
    test_definition: Mapped["TestDefinition"] = relationship()
    evidence_items: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="test_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestRun {self.id[:8]} status={self.status}>"
