"""Tests for the requirement module."""

import pytest
from sqlalchemy import select

from verify.definitions.models import RequirementTestMapping, TestDefinition
from verify.requirements.models import Requirement
from verify.requirements.service import RequirementServiceImpl
from verify.shared.exceptions import NotFoundError, RequirementImportError


def test_import_from_csv(session_factory, db_session, tmp_path):
    csv_path = tmp_path / "reqs.csv"
    csv_path.write_text(
        "key,title,description,domain\n"
        "REQ-001,Login Page,Must authenticate users,security\n"
        "REQ-002,API Rate Limit,,api\n"
    )
    service = RequirementServiceImpl(session_factory)

    created = service.import_from_csv(str(csv_path))

    assert len(created) == 2
    assert created[0].key == "REQ-001"
    assert created[0].title == "Login Page"
    assert created[0].domain == "security"
    assert created[1].key == "REQ-002"
    assert created[1].description is None

    stored = list(db_session.execute(select(Requirement)).scalars())
    assert len(stored) == 2


def test_import_from_csv_skips_duplicates(session_factory, tmp_path):
    csv_path = tmp_path / "reqs.csv"
    csv_path.write_text("key,title,description,domain\nREQ-001,First,,general\n")
    service = RequirementServiceImpl(session_factory)

    first = service.import_from_csv(str(csv_path))
    assert len(first) == 1

    second = service.import_from_csv(str(csv_path))
    assert len(second) == 0


def test_import_from_csv_no_headers(session_factory, tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")
    service = RequirementServiceImpl(session_factory)

    with pytest.raises(RequirementImportError, match="No headers"):
        service.import_from_csv(str(csv_path))


def test_import_from_csv_missing_key(session_factory, tmp_path):
    csv_path = tmp_path / "reqs.csv"
    csv_path.write_text("key,title,description,domain\n,Has Title,,general\n")
    service = RequirementServiceImpl(session_factory)

    created = service.import_from_csv(str(csv_path))
    assert len(created) == 0


def test_list_all(session_factory, db_session):
    r1 = Requirement(key="REQ-A", title="Alpha", domain="security")
    r2 = Requirement(key="REQ-B", title="Beta", domain="api")
    r3 = Requirement(key="REQ-C", title="Gamma", domain="security")
    db_session.add_all([r1, r2, r3])
    db_session.commit()

    service = RequirementServiceImpl(session_factory)
    assert len(service.list_all()) == 3
    assert len(service.list_all(domain="security")) == 2
    assert len(service.list_all(domain="api")) == 1
    assert len(service.list_all(domain="nonexistent")) == 0


def test_get_by_key(session_factory, db_session):
    req = Requirement(key="REQ-X", title="Test")
    db_session.add(req)
    db_session.commit()

    service = RequirementServiceImpl(session_factory)
    found = service.get_by_key("REQ-X")
    assert found.title == "Test"

    with pytest.raises(NotFoundError):
        service.get_by_key("NONEXISTENT")


def test_get_by_id(session_factory, db_session):
    req = Requirement(key="REQ-Y", title="Test")
    db_session.add(req)
    db_session.commit()

    service = RequirementServiceImpl(session_factory)
    found = service.get_by_id(req.id)
    assert found.key == "REQ-Y"

    with pytest.raises(NotFoundError):
        service.get_by_id("nonexistent-id")


def test_create_version(session_factory, db_session):
    req = Requirement(key="REQ-Z", title="Original", domain="general", version=1)
    db_session.add(req)
    db_session.commit()

    service = RequirementServiceImpl(session_factory)
    new_req = service.create_version(
        "REQ-Z", {"title": "Updated Title", "status": "deprecated"}
    )

    assert new_req.key == "REQ-Z"
    assert new_req.title == "Updated Title"
    assert new_req.status == "deprecated"
    assert new_req.version == 2
    assert new_req.parent_id == req.id
    assert new_req.domain == "general"

    with pytest.raises(NotFoundError):
        service.create_version("NONEXISTENT", {})


def test_get_coverage(session_factory, db_session):
    req = Requirement(key="REQ-COV", title="Covered Req")
    td = TestDefinition(name="Test Alpha", description="Some test")
    db_session.add_all([req, td])
    db_session.commit()

    mapping = RequirementTestMapping(
        requirement_id=req.id,
        test_definition_id=td.id,
        coverage_claim="partial",
    )
    db_session.add(mapping)
    db_session.commit()

    service = RequirementServiceImpl(session_factory)
    cov = service.get_coverage(req.id)

    assert cov["requirement_key"] == "REQ-COV"
    assert cov["covered_by"] == 1
    assert cov["tests"][0]["test_name"] == "Test Alpha"
    assert cov["tests"][0]["coverage_claim"] == "partial"


def test_get_coverage_not_found(session_factory):
    service = RequirementServiceImpl(session_factory)
    with pytest.raises(NotFoundError):
        service.get_coverage("nonexistent-id")
