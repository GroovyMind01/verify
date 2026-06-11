"""Evidence domain model."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verify.shared.models import Base, UUIDMixin

if TYPE_CHECKING:
    from verify.campaigns.models import TestRun


class Evidence(Base, UUIDMixin):
    """An artifact collected during a TestRun.

    The type field is free-form (e.g. "screenshot", "log", "command_output",
    "manifest", "api_response"). No fixed enum — different domains produce
    different evidence types.
    """

    __tablename__ = "evidence"

    test_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_runs.id"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    test_run: Mapped["TestRun"] = relationship(back_populates="evidence_items")

    def __repr__(self) -> str:
        return f"<Evidence type={self.evidence_type} run={self.test_run_id[:8]}>"
