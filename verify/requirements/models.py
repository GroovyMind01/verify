"""Requirement domain model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import DDL, JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verify.shared.models import Base, UUIDMixin

if TYPE_CHECKING:
    from verify.definitions.models import RequirementTestMapping


class Requirement(Base, UUIDMixin):
    """A verifiable requirement, typically imported from a specification source."""

    __tablename__ = "requirements"

    key: Mapped[str] = mapped_column(String(128), unique=False, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(
        String(64), nullable=False, default="general"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    source_file: Mapped[str | None] = mapped_column(String(1024))
    source_line: Mapped[int | None] = mapped_column(Integer)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("requirements.id"), nullable=True
    )

    decomposition_parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("requirements.id"), nullable=True
    )
    requirement_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="spec"
    )
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    children: Mapped[list["Requirement"]] = relationship(
        "Requirement", back_populates="parent", remote_side="Requirement.id",
        foreign_keys=lambda: [Requirement.parent_id],
    )
    parent: Mapped["Requirement | None"] = relationship(
        "Requirement", back_populates="children", remote_side=parent_id, uselist=False,
        foreign_keys=lambda: [Requirement.parent_id],
    )

    decomposition_children: Mapped[list["Requirement"]] = relationship(
        "Requirement", back_populates="decomposition_parent", remote_side="Requirement.id",
        foreign_keys=lambda: [Requirement.decomposition_parent_id],
    )
    decomposition_parent: Mapped["Requirement | None"] = relationship(
        "Requirement", back_populates="decomposition_children",
        remote_side=decomposition_parent_id, uselist=False,
        foreign_keys=lambda: [Requirement.decomposition_parent_id],
    )

    test_mappings: Mapped[list["RequirementTestMapping"]] = relationship(
        "RequirementTestMapping", back_populates="requirement", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Requirement {self.key} v{self.version}>"


# FTS5 virtual table — registered to be created alongside the requirements table
# when Base.metadata.create_all() runs on SQLite.

_fts_ddl = DDL(
    "CREATE VIRTUAL TABLE IF NOT EXISTS requirements_fts USING fts5("
    "    requirement_id, key, title, description,"
    "    tokenize='porter unicode61'"
    ")"
)

sa_event.listen(
    Requirement.__table__,
    "after_create",
    _fts_ddl.execute_if(dialect="sqlite"),
)
