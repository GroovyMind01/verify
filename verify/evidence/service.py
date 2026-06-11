"""Evidence service — collect, store, retrieve artifacts."""

import json
import mimetypes
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Protocol

from sqlalchemy import select

from verify.campaigns.models import CampaignVersion, TestRun
from verify.evidence.models import Evidence
from verify.shared.database import get_evidence_dir, make_service_session
from verify.shared.exceptions import NotFoundError, ValidationError
from verify.shared.security import (
    compute_sha256,
    ensure_safe_directory,
    is_symlink,
    resolve_safe_path,
    sanitize_filename,
    secure_copy,
)


class EvidenceStore(Protocol):
    """Interface for evidence persistence and retrieval."""

    def collect(
        self,
        test_run_id: str,
        source_path: str,
        evidence_type: str,
        metadata: dict | None = None,
    ) -> Evidence:
        """Copy the artifact from source_path into the evidence store
        and create a database record."""
        ...

    def list_for_test_run(self, test_run_id: str) -> list[Evidence]:
        """List all evidence items for a test run."""
        ...

    def list_for_campaign_version(self, campaign_version_id: str) -> list[Evidence]:
        """List all evidence items across all test runs in a campaign version."""
        ...

    def get_evidence_path(self, evidence_id: str) -> Path:
        """Return the absolute filesystem path to an evidence artifact."""
        ...


class FileEvidenceStore:
    """Stores evidence as plain files in a configurable directory.

    Files are copied (not moved) to avoid modifying the source.
    Symlinks are rejected — only regular files are accepted.
    Directory layout:

        <evidence_dir>/
          <test_run_id>/
            <evidence_id>_<sanitized_filename>
    """

    def __init__(self, session_factory, evidence_dir: Path | None = None) -> None:
        self._session_factory = lambda: make_service_session(session_factory)
        self._evidence_dir = evidence_dir or get_evidence_dir()
        ensure_safe_directory(self._evidence_dir)

    def collect(
        self,
        test_run_id: str,
        source_path: str,
        evidence_type: str,
        metadata: dict | None = None,
    ) -> Evidence:
        source = Path(source_path).resolve()

        if is_symlink(source):
            raise ValidationError(f"Refusing to collect symlink: {source_path}")

        if not source.is_file():
            raise ValidationError(f"Source path is not a file: {source_path}")

        with self._session_factory() as session:
            tr = session.execute(
                select(TestRun).where(TestRun.id == test_run_id)
            ).scalar_one_or_none()
            if tr is None:
                raise NotFoundError(f"TestRun with id '{test_run_id}' not found")

            safe_name = sanitize_filename(source.name)
            evidence = Evidence(
                test_run_id=test_run_id,
                evidence_type=evidence_type,
                mime_type=mimetypes.guess_type(source.name)[0],
                file_path="",
                metadata_=metadata,
            )
            session.add(evidence)
            session.flush()

            dest_dir = resolve_safe_path(self._evidence_dir, test_run_id)
            ensure_safe_directory(dest_dir)
            dest_name = f"{evidence.id}_{safe_name}"
            dest_path = dest_dir / dest_name

            secure_copy(source, dest_path)
            checksum = compute_sha256(dest_path)

            evidence.file_path = str(dest_path)
            evidence.metadata_ = (evidence.metadata_ or {}) | {"sha256": checksum}
            session.commit()
            session.expunge(evidence)
            return evidence

    def list_for_test_run(self, test_run_id: str) -> list[Evidence]:
        with self._session_factory() as session:
            stmt = (
                select(Evidence)
                .where(Evidence.test_run_id == test_run_id)
                .order_by(Evidence.collected_at.desc())
            )
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results

    def list_for_campaign_version(self, campaign_version_id: str) -> list[Evidence]:
        with self._session_factory() as session:
            stmt = (
                select(Evidence)
                .join(TestRun)
                .where(TestRun.campaign_version_id == campaign_version_id)
                .order_by(Evidence.collected_at.desc())
            )
            results = list(session.execute(stmt).scalars())
            for r in results:
                session.expunge(r)
            return results

    def get_evidence_path(self, evidence_id: str) -> Path:
        with self._session_factory() as session:
            ev = session.execute(
                select(Evidence).where(Evidence.id == evidence_id)
            ).scalar_one_or_none()
            if ev is None:
                raise NotFoundError(f"Evidence with id '{evidence_id}' not found")
            path = Path(ev.file_path)
            return path

    def verify_integrity(self, evidence_id: str) -> dict:
        with self._session_factory() as session:
            ev = session.execute(
                select(Evidence).where(Evidence.id == evidence_id)
            ).scalar_one_or_none()
            if ev is None:
                raise NotFoundError(f"Evidence with id '{evidence_id}' not found")

            file_path = Path(ev.file_path)
            if not file_path.exists():
                raise ValidationError(f"Evidence file not found on disk: {file_path}")

            expected = ev.checksum or (ev.metadata_ or {}).get("sha256", "")
            actual = compute_sha256(file_path)
            valid = bool(expected) and actual == expected

            return {"valid": valid, "expected": expected, "actual": actual}

    def sign_evidence(self, evidence_id: str, key_id: str | None = None) -> Evidence:
        with self._session_factory() as session:
            ev = session.execute(
                select(Evidence).where(Evidence.id == evidence_id)
            ).scalar_one_or_none()
            if ev is None:
                raise NotFoundError(f"Evidence with id '{evidence_id}' not found")

            file_path = Path(ev.file_path)
            sig_path = Path(str(file_path) + ".asc")

            cmd = ["gpg", "--detach-sign", "--armor"]
            if key_id:
                cmd.extend(["--local-user", key_id])
            cmd.append(str(file_path))

            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise ValidationError(
                    "GPG signing failed. Ensure GPG is installed and a key is available. "
                    "Run 'gpg --gen-key' to create a signing key."
                )

            ev.metadata_ = (ev.metadata_ or {}) | {"gpg_signature": str(sig_path)}
            session.commit()
            session.expunge(ev)
            return ev

    def preview(self, evidence_id: str) -> str:
        with self._session_factory() as session:
            ev = session.execute(
                select(Evidence).where(Evidence.id == evidence_id)
            ).scalar_one_or_none()
            if ev is None:
                raise NotFoundError(f"Evidence with id '{evidence_id}' not found")

            mime = ev.mime_type or ""
            text_mime_prefixes = ("text/", "application/json", "application/xml")
            if not any(mime.startswith(prefix) for prefix in text_mime_prefixes):
                return "(binary file — no preview)"

            try:
                with open(ev.file_path, encoding="utf-8", errors="replace") as f:
                    content = f.read(4096)
                return content if content else "(empty file)"
            except OSError:
                return "(unable to read file)"

    def auto_capture(
        self, test_run_id: str, command: list[str], evidence_type: str = "command_output"
    ) -> Evidence:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=300
            )
        except subprocess.TimeoutExpired:
            raise ValidationError("Command timed out after 300 seconds")
        except FileNotFoundError:
            raise ValidationError(f"Command not found: {command[0]}")

        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr

        with self._session_factory() as session:
            tr = session.execute(
                select(TestRun).where(TestRun.id == test_run_id)
            ).scalar_one_or_none()
            if tr is None:
                raise NotFoundError(f"TestRun with id '{test_run_id}' not found")

            evidence = Evidence(
                test_run_id=test_run_id,
                evidence_type=evidence_type,
                mime_type="text/plain",
                file_path="",
            )
            session.add(evidence)
            session.flush()

            dest_dir = resolve_safe_path(self._evidence_dir, test_run_id)
            ensure_safe_directory(dest_dir)
            dest_name = f"{evidence.id}_capture.txt"
            dest_path = dest_dir / dest_name

            with open(dest_path, "w") as f:
                f.write(output)

            checksum = compute_sha256(dest_path)
            evidence.file_path = str(dest_path)
            evidence.checksum = checksum
            evidence.metadata_ = {
                "sha256": checksum,
                "command": command,
                "return_code": result.returncode,
            }

            if result.returncode == 0:
                tr.status = "passed"
            else:
                tr.status = "failed"

            session.commit()
            session.expunge(evidence)
            return evidence

    def bundle(self, campaign_version_id: str, output_path: str) -> Path:
        with self._session_factory() as session:
            version = session.execute(
                select(CampaignVersion).where(CampaignVersion.id == campaign_version_id)
            ).scalar_one_or_none()
            if version is None:
                raise NotFoundError(
                    f"CampaignVersion with id '{campaign_version_id}' not found"
                )

            evidence_items = list(
                session.execute(
                    select(Evidence)
                    .join(TestRun)
                    .where(TestRun.campaign_version_id == campaign_version_id)
                ).scalars()
            )

            if not evidence_items:
                raise ValidationError("No evidence found for this campaign version")

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)

                meta: dict = {
                    "campaign_version_id": campaign_version_id,
                    "evidence_count": len(evidence_items),
                    "items": [],
                }

                for ev in evidence_items:
                    src = Path(ev.file_path)
                    if src.exists():
                        dest = tmp / src.name
                        shutil.copy2(src, dest)
                        meta["items"].append({
                            "id": ev.id,
                            "type": ev.evidence_type,
                            "file": src.name,
                            "checksum": ev.checksum,
                        })

                meta_path = tmp / "metadata.json"
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2, default=str)

                with tarfile.open(output, "w:gz") as tar:
                    tar.add(tmp, arcname="evidence_bundle")

            return output.resolve()
