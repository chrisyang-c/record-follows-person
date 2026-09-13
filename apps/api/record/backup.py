"""Portable, manifest-verified backup for the filesystem record projection."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4


class BackupIntegrityError(ValueError):
    """Raised when a backup is incomplete, altered, or attempts path traversal."""


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*") if path.is_file() and not path.name.endswith(".tmp")
    )


def create_backup(root: Path, destination: Path) -> Path:
    root, destination = Path(root), Path(destination)
    if not root.exists():
        raise FileNotFoundError(root)
    files = _files(root)
    manifest = {
        "format": 1,
        "root_name": root.name,
        "files": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _digest(path),
                "size": path.stat().st_size,
            }
            for path in files
        ],
    }
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for path in files:
                archive.write(path, path.relative_to(root).as_posix())
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _manifest(archive: zipfile.ZipFile) -> dict:
    try:
        data = json.loads(archive.read("MANIFEST.json"))
    except (KeyError, json.JSONDecodeError) as exc:
        raise BackupIntegrityError("backup has no valid MANIFEST.json") from exc
    if data.get("format") != 1 or not isinstance(data.get("files"), list):
        raise BackupIntegrityError("unsupported backup manifest")
    return data


def verify_backup(archive_path: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        manifest = _manifest(archive)
        names = set(archive.namelist())
        for item in manifest["files"]:
            relative = Path(item["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.as_posix() not in names:
                raise BackupIntegrityError(f"unsafe or missing backup path: {relative}")
            info = archive.getinfo(relative.as_posix())
            if info.file_size != item["size"]:
                raise BackupIntegrityError(f"size mismatch: {relative}")
            digest = hashlib.sha256(archive.read(relative.as_posix())).hexdigest()
            if digest != item["sha256"]:
                raise BackupIntegrityError(f"checksum mismatch: {relative}")
    return manifest


def restore_backup(archive_path: Path, target: Path, *, overwrite: bool = False) -> Path:
    target = Path(target)
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise FileExistsError(f"restore target is not empty: {target}")
    verify_backup(archive_path)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            if name == "MANIFEST.json":
                continue
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise BackupIntegrityError(f"unsafe restore path: {relative}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    return target
