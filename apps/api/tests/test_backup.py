from pathlib import Path

import pytest

from record.backup import BackupIntegrityError, create_backup, restore_backup, verify_backup


def test_backup_manifest_verifies_and_restores(tmp_path: Path):
    source = tmp_path / "records"
    (source / "P001").mkdir(parents=True)
    (source / "P001" / "profile.json").write_text('{"patient_id":"P001"}', encoding="utf-8")
    archive = tmp_path / "records.zip"
    create_backup(source, archive)
    manifest = verify_backup(archive)
    assert manifest["files"][0]["path"] == "P001/profile.json"
    restored = tmp_path / "restored"
    restore_backup(archive, restored)
    assert (restored / "P001" / "profile.json").read_text(encoding="utf-8") == (
        '{"patient_id":"P001"}'
    )


def test_backup_rejects_tampered_archive(tmp_path: Path):
    source = tmp_path / "records"
    source.mkdir()
    (source / "a.txt").write_text("a", encoding="utf-8")
    archive = tmp_path / "records.zip"
    create_backup(source, archive)
    import zipfile

    with zipfile.ZipFile(archive, "a") as modified:
        modified.writestr("a.txt", "tampered")
    with pytest.raises(BackupIntegrityError):
        verify_backup(archive)
