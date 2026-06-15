"""TestDefinition domain model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verify.shared.models import Base, UUIDMixin

if TYPE_CHECKING:
    from verify.requirements.models import Requirement


class TestDefinition(Base, UUIDMixin):
    """A reusable test specification that validates one or more requirements."""

    __tablename__ = "test_definitions"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[str] | dict[str, Any] | None] = mapped_column(JSON)
    exec_command: Mapped[str | None] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    requirement_mappings: Mapped[list["RequirementTestMapping"]] = relationship(
        "RequirementTestMapping", back_populates="test_definition", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TestDefinition {self.name}>"


class RequirementTestMapping(Base, UUIDMixin):
    """Many-to-many link table between Requirement and TestDefinition.

    A dedicated model (rather than a simple association table) so we can
    carry metadata like coverage claims or mapping rationale.
    """

    __tablename__ = "requirement_test_mappings"

    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id"), nullable=False
    )
    test_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("test_definitions.id"), nullable=False
    )
    coverage_claim: Mapped[str | None] = mapped_column(
        String(64), default="full"
    )

    requirement: Mapped["Requirement"] = relationship(back_populates="test_mappings")
    test_definition: Mapped["TestDefinition"] = relationship(
        back_populates="requirement_mappings"
    )

    def __repr__(self) -> str:
        return (
            f"<ReqTestMapping req={self.requirement_id} "
            f"test={self.test_definition_id}>"
        )
