"""
Agent registry: publish, list, fetch and download Portable Units.

Contract: CRAFT `contracts/registry-api.md` (ADR 0002). Consumers: `agentfactory-gen publish`,
`agentfactory-gen import --from-registry`, the webapp registry pages and the harness client.

- Units are owned by their first publisher; only the owner can publish new versions.
- Versions are immutable: re-publishing an existing version is a 409.
- The server stores the ZIP's sha256 and returns it with every entry, so `import --from-registry`
  verifies downloads against the registry, not against the file itself.
- ZIPs live under REGISTRY_STORAGE_DIR (default ./data/registry/<name>/<version>.zip).
"""
import hashlib
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from ...librarian import MANIFEST_FILE, validate_name
from ..db import get_conn
from ..deps import get_publisher
from ..models import RegistryEntry, RegistrySummary, User

router = APIRouter(prefix="/registry", tags=["registry"])

_VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?")
_TAG_RE = re.compile(r"[a-z0-9][a-z0-9\-]{0,31}")
_MAX_TAGS = 10
_MAX_DESCRIPTION = 500


def _storage_dir() -> Path:
    return Path(os.environ.get("REGISTRY_STORAGE_DIR", "./data/registry"))


def _max_zip_bytes() -> int:
    return int(os.environ.get("REGISTRY_MAX_ZIP_BYTES", str(20 * 1024 * 1024)))


def _public_url() -> str:
    """Base URL clients use to download ZIPs (must be https in production; see the CLI's URL policy)."""
    return os.environ.get("API_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def _zip_path(name: str, version: str) -> Path:
    return _storage_dir() / name / f"{version}.zip"


def _validate_bundle(data: bytes, name: str) -> None:
    """The upload must be a ZIP with agent-manifest.json at its root naming the same unit."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _bad("file is not a ZIP archive") from None
    with zf:
        for member in zf.namelist():
            p = PurePosixPath(member)
            if p.is_absolute() or ".." in p.parts or "\\" in member:
                raise _bad(f"unsafe path in archive: {member!r}")
        if MANIFEST_FILE not in zf.namelist():
            raise _bad(f"archive has no {MANIFEST_FILE} at its root (build it with `agentfactory-gen wrap`)")
        try:
            inner = json.loads(zf.read(MANIFEST_FILE))
        except (ValueError, UnicodeDecodeError):
            raise _bad(f"{MANIFEST_FILE} in the archive is not valid JSON") from None
    if inner.get("name") != name:
        raise _bad(f"archive manifest names {inner.get('name')!r}, publish request names {name!r}")


def _entry(name: str, version: str | None) -> RegistryEntry:
    with get_conn() as conn:
        unit = conn.execute(
            "SELECT u.name, u.description, u.tags, u.updated_at, o.github_handle AS owner "
            "FROM registry_units u JOIN users o ON o.id = u.owner_id WHERE u.name = ?",
            (name,),
        ).fetchone()
        if unit is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"agent '{name}' not found")
        versions = [r["version"] for r in conn.execute(
            "SELECT version FROM registry_versions WHERE name = ? ORDER BY published_at", (name,))]
        chosen = version or (versions[-1] if versions else None)
        row = conn.execute(
            "SELECT version, sha256, size_bytes, published_at FROM registry_versions WHERE name = ? AND version = ?",
            (name, chosen),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"version '{version}' of '{name}' not found")
    return RegistryEntry(
        name=unit["name"], description=unit["description"], tags=json.loads(unit["tags"]),
        owner=unit["owner"], version=row["version"], versions=versions, sha256=row["sha256"],
        size_bytes=row["size_bytes"], published_at=row["published_at"],
        zip_url=f"{_public_url()}/registry/{name}/{row['version']}/download",
    )


@router.get("", response_model=list[RegistrySummary])
def list_units(q: str = Query(default="", max_length=64), limit: int = Query(default=50, ge=1, le=100)):
    """Browse or search published units (name, description or tag contains *q*)."""
    like = f"%{q.lower()}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT u.name, u.description, u.tags, u.updated_at, "
            "(SELECT version FROM registry_versions v WHERE v.name = u.name ORDER BY published_at DESC LIMIT 1) "
            "AS latest FROM registry_units u "
            "WHERE lower(u.name) LIKE ? OR lower(u.description) LIKE ? OR lower(u.tags) LIKE ? "
            "ORDER BY u.updated_at DESC LIMIT ?",
            (like, like, like, limit),
        ).fetchall()
    return [RegistrySummary(name=r["name"], description=r["description"], tags=json.loads(r["tags"]),
                            latest_version=r["latest"], updated_at=r["updated_at"]) for r in rows]


@router.post("/publish", response_model=RegistryEntry, status_code=status.HTTP_201_CREATED)
async def publish(
    manifest: str = Form(..., description='JSON: {"name", "version", "description", "tags"}'),
    file: UploadFile = File(..., description="ZIP built by `agentfactory-gen wrap`"),
    user: User = Depends(get_publisher),
) -> RegistryEntry:
    try:
        meta = json.loads(manifest)
    except ValueError:
        raise _bad("manifest must be JSON") from None
    if not isinstance(meta, dict):
        raise _bad("manifest must be a JSON object")
    try:
        name = validate_name(meta.get("name"), "agent")
    except ValueError as exc:
        raise _bad(str(exc)) from None
    version = meta.get("version")
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise _bad(f"version {version!r} must look like 1.2.3 (optionally -pre or +build)")
    description = str(meta.get("description") or "").strip()
    if not description or len(description) > _MAX_DESCRIPTION:
        raise _bad(f"description is required and at most {_MAX_DESCRIPTION} characters")
    tags = meta.get("tags") or []
    if not isinstance(tags, list) or len(tags) > _MAX_TAGS or not all(
            isinstance(t, str) and _TAG_RE.fullmatch(t) for t in tags):
        raise _bad(f"tags: up to {_MAX_TAGS} lowercase words (a-z, 0-9, '-')")

    limit = _max_zip_bytes()
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"archive is larger than {limit} bytes")
    _validate_bundle(data, name)
    digest = hashlib.sha256(data).hexdigest()
    now = _now()

    with get_conn() as conn:
        unit = conn.execute("SELECT owner_id FROM registry_units WHERE name = ?", (name,)).fetchone()
        if unit is not None and unit["owner_id"] != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"'{name}' belongs to another publisher")
        if conn.execute("SELECT 1 FROM registry_versions WHERE name = ? AND version = ?",
                        (name, version)).fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail=f"{name}@{version} already exists; versions are immutable, bump the version")
        if unit is None:
            conn.execute(
                "INSERT INTO registry_units (name, owner_id, description, tags, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)", (name, user.id, description, json.dumps(tags), now, now))
        else:
            conn.execute("UPDATE registry_units SET description = ?, tags = ?, updated_at = ? WHERE name = ?",
                         (description, json.dumps(tags), now, name))
        conn.execute(
            "INSERT INTO registry_versions (name, version, sha256, size_bytes, published_by, published_at) "
            "VALUES (?, ?, ?, ?, ?, ?)", (name, version, digest, len(data), user.id, now))
        # Write the file inside the transaction: if this fails, the rows roll back with it.
        path = _zip_path(name, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".zip.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return _entry(name, version)


@router.get("/{name}", response_model=RegistryEntry)
def get_latest(name: str) -> RegistryEntry:
    """Metadata of the newest version, including `zip_url` and `sha256`."""
    return _entry(name, None)


@router.get("/{name}/{version}", response_model=RegistryEntry)
def get_version(name: str, version: str) -> RegistryEntry:
    """Metadata of one version, including `zip_url` and `sha256`."""
    return _entry(name, version)


@router.get("/{name}/{version}/download", response_class=FileResponse)
def download(name: str, version: str) -> FileResponse:
    """The stored ZIP. Clients verify it against the entry's `sha256`."""
    entry = _entry(name, version)
    path = _zip_path(entry.name, entry.version)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="archive missing from storage")
    return FileResponse(path, media_type="application/zip", filename=f"{entry.name}-v{entry.version}.zip")
