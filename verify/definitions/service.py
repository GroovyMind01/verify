"""Test definition service — CRUD for test definitions and requirement mappings."""

import csv
from typing import Protocol

from sqlalchemy import select

from verify.definitions.models import RequirementTestMapping, TestDefinition
from verify.shared.database import make_service_session
from verify.shared.exceptions import NotFoundError, ValidationError


class DefinitionService(Protocol):
    """Interface for test definition operations."""

    def create(
        self,
        name: str,
        description: str | None = None,
        steps: list | dict | None = None,
        expected_result: str | None = None,
        domain: str = "general",
        tags: list[str] | None = None,
        exec_command: str | None = None,
    ) -> TestDefinition:
        ...

    def set_exec_command(self, test_id: str, command: str) -> TestDefinition:
        """Attach a shell command to an existing test definition."""
        ...

    def list_all(self, domain: str | None = None) -> list[TestDefinition]:
        ...

    def get_by_id(self, test_id: str) -> TestDefinition:
        ...

    def map_to_requirement(
        self,
        test_definition_id: str,
        requirement_id: str,
        coverage_claim: str = "full",
    ) -> RequirementTestMapping:
        ...

    def import_from_csv(self, file_path: str) -> list[TestDefinition]:
        """Import test definitions from a CSV file."""
        ...

    def get_mappings_for_requirement(self, requirement_id: str) -> list[RequirementTestMapping]:
        """Get all test mappings for a requirement."""
        ...


class DefinitionServiceImpl:
    def __init__(self, session_factory) -> None:
        self._session_factory = lambda: make_service_session(session_factory)

    def create(
        self,
        name: str,
        description: str | None = None,
        steps: list | dict | None = None,
        expected_result: str | None = None,
        domain: str = "general",
        tags: list[str] | None = None,
        exec_command: str | None = None,
    ) -> TestDefinition:
        with self._session_factory() as session:
            td = TestDefinition(
                name=name,
                description=description,
                steps=steps,
                expected_result=expected_result,
                domain=domain,
                tags=tags,
                exec_command=exec_command,
            )
            session.add(td)
            session.commit()
            session.expunge(td)
            return td

    def list_all(self, domain: str | None = None) -> list[TestDefinition]:
        with self._session_factory() as session:
            stmt = select(TestDefinition)
            if domain:
                stmt = stmt.where(TestDefinition.domain == domain)
            results = list(session.execute(stmt.order_by(TestDefinition.name)).scalars())
            for r in results:
                session.expunge(r)
            return results

    def get_by_id(self, test_id: str) -> TestDefinition:
        with self._session_factory() as session:
            stmt = select(TestDefinition).where(TestDefinition.id == test_id)
            result = session.execute(stmt).scalar_one_or_none()
            if result is None:
                raise NotFoundError(f"TestDefinition with id '{test_id}' not found")
            session.expunge(result)
            return result

    def map_to_requirement(
        self,
        test_definition_id: str,
        requirement_id: str,
        coverage_claim: str = "full",
    ) -> RequirementTestMapping:
        with self._session_factory() as session:
            mapping = RequirementTestMapping(
                test_definition_id=test_definition_id,
                requirement_id=requirement_id,
                coverage_claim=coverage_claim,
            )
            session.add(mapping)
            session.commit()
            session.expunge(mapping)
            return mapping

    def import_from_csv(self, file_path: str) -> list[TestDefinition]:
        with self._session_factory() as session, open(file_path, newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValidationError(f"No headers found in {file_path}")

            created = []
            for row in reader:
                name = (row.get("name") or "").strip()
                if not name:
                    continue

                tags_str = (row.get("tags") or "").strip()
                tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None

                td = TestDefinition(
                    name=name,
                    description=(row.get("description") or "").strip() or None,
                    steps=(row.get("steps") or "").strip() or None,
                    expected_result=(row.get("expected_result") or "").strip() or None,
                    domain=(row.get("domain") or "general").strip() or "general",
                    tags=tags,
                )
                session.add(td)
                created.append(td)

            session.commit()
            for td in created:
                session.expunge(td)
            return created

    def get_mappings_for_requirement(
        self, requirement_id: str
    ) -> list[RequirementTestMapping]:
        with self._session_factory() as session:
            stmt = select(RequirementTestMapping).where(
                RequirementTestMapping.requirement_id == requirement_id
            )
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results

    def set_exec_command(self, test_id: str, command: str) -> TestDefinition:
        with self._session_factory() as session:
            td = session.execute(
                select(TestDefinition).where(TestDefinition.id == test_id)
            ).scalar_one_or_none()
            if td is None:
                raise NotFoundError(f"TestDefinition with id '{test_id}' not found")
            td.exec_command = command
            session.commit()
            session.expunge(td)
            return td
