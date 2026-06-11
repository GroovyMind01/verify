"""Tests for the campaign module."""

import pytest
from sqlalchemy import select

from verify.campaigns.models import Campaign, TestRun
from verify.campaigns.service import CampaignServiceImpl
from verify.definitions.models import TestDefinition
from verify.shared.exceptions import NotFoundError


def test_create_campaign(session_factory):
    service = CampaignServiceImpl(session_factory)
    campaign = service.create("Integration Tests", "Run all integration tests")

    assert campaign.name == "Integration Tests"
    assert campaign.description == "Run all integration tests"
    assert campaign.status == "draft"

    with session_factory() as s:
        stored = s.execute(
            select(Campaign).where(Campaign.id == campaign.id)
        ).scalar_one()
        assert stored.name == "Integration Tests"


def test_list_all_campaigns(session_factory, db_session):
    c1 = Campaign(name="Campaign A")
    c2 = Campaign(name="Campaign B")
    db_session.add_all([c1, c2])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    campaigns = service.list_all()
    assert len(campaigns) == 2


def test_get_by_id(session_factory, db_session):
    c = Campaign(name="Target")
    db_session.add(c)
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    found = service.get_by_id(c.id)
    assert found.name == "Target"

    with pytest.raises(NotFoundError):
        service.get_by_id("nonexistent")


def test_create_version(session_factory, db_session):
    c = Campaign(name="My Campaign")
    td1 = TestDefinition(name="Test 1")
    td2 = TestDefinition(name="Test 2")
    db_session.add_all([c, td1, td2])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    version = service.create_version(c.id, [td1.id, td2.id], notes="Initial snapshot")

    assert version.version_number == 1
    assert version.notes == "Initial snapshot"
    assert version.campaign_id == c.id

    runs = list(db_session.execute(
        select(TestRun).where(TestRun.campaign_version_id == version.id)
    ).scalars())
    assert len(runs) == 2
    assert {r.test_definition_id for r in runs} == {td1.id, td2.id}
    assert all(r.status == "pending" for r in runs)


def test_create_version_increments_number(session_factory, db_session):
    c = Campaign(name="Multi Version")
    td1 = TestDefinition(name="T1")
    db_session.add_all([c, td1])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    v1 = service.create_version(c.id, [td1.id])
    v2 = service.create_version(c.id, [td1.id])

    assert v1.version_number == 1
    assert v2.version_number == 2


def test_create_version_missing_campaign(session_factory):
    service = CampaignServiceImpl(session_factory)
    with pytest.raises(NotFoundError):
        service.create_version("nonexistent", [])


def test_create_version_missing_test(session_factory, db_session):
    c = Campaign(name="C")
    db_session.add(c)
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    with pytest.raises(NotFoundError):
        service.create_version(c.id, ["nonexistent-test"])


def test_list_versions(session_factory, db_session):
    c = Campaign(name="Versioned")
    td = TestDefinition(name="T")
    db_session.add_all([c, td])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    service.create_version(c.id, [td.id])
    service.create_version(c.id, [td.id])

    versions = service.list_versions(c.id)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[1].version_number == 1

    with pytest.raises(NotFoundError):
        service.list_versions("nonexistent")


def test_get_test_runs(session_factory, db_session):
    c = Campaign(name="C")
    td = TestDefinition(name="T")
    db_session.add_all([c, td])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    version = service.create_version(c.id, [td.id])

    runs = service.get_test_runs(version.id)
    assert len(runs) == 1
    assert runs[0].test_definition.name == "T"

    with pytest.raises(NotFoundError):
        service.get_test_runs("nonexistent")


def test_update_test_run_status(session_factory, db_session):
    c = Campaign(name="C")
    td = TestDefinition(name="T")
    db_session.add_all([c, td])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    version = service.create_version(c.id, [td.id])
    runs = service.get_test_runs(version.id)
    tr = runs[0]

    updated = service.update_test_run_status(tr.id, "running")
    assert updated.status == "running"
    assert updated.started_at is not None

    updated = service.update_test_run_status(tr.id, "passed", notes="All good")
    assert updated.status == "passed"
    assert updated.notes == "All good"
    assert updated.completed_at is not None

    with pytest.raises(NotFoundError):
        service.update_test_run_status("nonexistent", "passed")


def test_get_summary(session_factory, db_session):
    c = Campaign(name="Summary Test")
    td1 = TestDefinition(name="T1")
    td2 = TestDefinition(name="T2")
    td3 = TestDefinition(name="T3")
    db_session.add_all([c, td1, td2, td3])
    db_session.commit()

    service = CampaignServiceImpl(session_factory)
    version = service.create_version(c.id, [td1.id, td2.id, td3.id])
    runs = service.get_test_runs(version.id)

    service.update_test_run_status(runs[0].id, "passed")
    service.update_test_run_status(runs[1].id, "failed")

    summary = service.get_summary(version.id)

    assert summary["campaign_name"] == "Summary Test"
    assert summary["version_number"] == 1
    assert summary["total_tests"] == 3
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["pending"] == 1
    assert summary["pass_rate"] == 50.0

    with pytest.raises(NotFoundError):
        service.get_summary("nonexistent")
