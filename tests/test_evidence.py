"""Tests for the evidence module."""

import pytest
from sqlalchemy import select

from verify.campaigns.models import Campaign, CampaignVersion, TestRun
from verify.definitions.models import TestDefinition
from verify.evidence.models import Evidence
from verify.evidence.service import FileEvidenceStore
from verify.shared.exceptions import NotFoundError, ValidationError


def _setup_test_run(db_session, campaign_name="C", test_name="T"):
    campaign = Campaign(name=campaign_name)
    td = TestDefinition(name=test_name)
    db_session.add_all([campaign, td])
    db_session.commit()

    version = CampaignVersion(campaign_id=campaign.id, version_number=1)
    db_session.add(version)
    db_session.commit()

    tr = TestRun(campaign_version_id=version.id, test_definition_id=td.id)
    db_session.add(tr)
    db_session.commit()
    return tr


def test_collect_evidence(session_factory, db_session, temp_evidence_dir, tmp_path):
    tr = _setup_test_run(db_session)

    source = tmp_path / "log.txt"
    source.write_text("test output")

    store = FileEvidenceStore(session_factory, evidence_dir=temp_evidence_dir)
    ev = store.collect(str(tr.id), str(source), "log", {"key": "value"})

    assert ev.evidence_type == "log"
    assert ev.test_run_id == tr.id
    assert ev.metadata_["key"] == "value"
    assert "sha256" in ev.metadata_

    stored = db_session.execute(
        select(Evidence).where(Evidence.id == ev.id)
    ).scalar_one()
    assert stored.evidence_type == "log"

    dest_path = store.get_evidence_path(ev.id)
    assert dest_path.exists()
    assert dest_path.read_text() == "test output"


def test_collect_missing_test_run(session_factory, temp_evidence_dir, tmp_path):
    source = tmp_path / "file.txt"
    source.write_text("content")

    store = FileEvidenceStore(session_factory, evidence_dir=temp_evidence_dir)
    with pytest.raises(NotFoundError):
        store.collect("nonexistent", str(source), "log")


def test_collect_source_not_a_file(session_factory, temp_evidence_dir, tmp_path):
    store = FileEvidenceStore(session_factory, evidence_dir=temp_evidence_dir)
    with pytest.raises(ValidationError):
        store.collect("some-id", str(tmp_path), "log")


def test_list_for_test_run(session_factory, db_session, temp_evidence_dir, tmp_path):
    tr = _setup_test_run(db_session)

    s1 = tmp_path / "a.txt"
    s2 = tmp_path / "b.txt"
    s1.write_text("a")
    s2.write_text("b")

    store = FileEvidenceStore(session_factory, evidence_dir=temp_evidence_dir)
    store.collect(str(tr.id), str(s1), "output")
    store.collect(str(tr.id), str(s2), "screenshot")

    items = store.list_for_test_run(tr.id)
    assert len(items) == 2


def test_list_for_campaign_version(session_factory, db_session, temp_evidence_dir, tmp_path):
    tr = _setup_test_run(db_session)

    source = tmp_path / "ev.txt"
    source.write_text("evidence data")

    store = FileEvidenceStore(session_factory, evidence_dir=temp_evidence_dir)
    store.collect(str(tr.id), str(source), "log")

    items = store.list_for_campaign_version(tr.campaign_version_id)
    assert len(items) == 1


def test_get_evidence_path_not_found(session_factory):
    store = FileEvidenceStore(session_factory)
    with pytest.raises(NotFoundError):
        store.get_evidence_path("nonexistent")


def test_default_evidence_dir():
    store = FileEvidenceStore(lambda: None)
    path = store._evidence_dir
    assert path.name == "evidence"
    assert "verify" in str(path)
