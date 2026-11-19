"""AgentFactory API access: base URL, registry publish/fetch, tokens.

Split out of cli.py (#190); `agent_gen.cli` is the entry point and re-exports these names."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

DEFAULT_API_URL = "https://api.agentfactory.dev"


def _resolve_api_url(env=os.environ) -> str:
    """One base URL for the whole API (auth, license, registry): AGENTFACTORY_API_URL.

    AGENTFACTORY_REGISTRY_URL is the pre-0.5 name; it still works for one release, with a warning.
    """
    url = env.get("AGENTFACTORY_API_URL", "").strip()
    if url:
        return url.rstrip("/")
    legacy = env.get("AGENTFACTORY_REGISTRY_URL", "").strip()
    if legacy:
        sys.stderr.write("[librarian] AGENTFACTORY_REGISTRY_URL is deprecated; use AGENTFACTORY_API_URL.\n")
        return legacy.rstrip("/")
    return DEFAULT_API_URL


REGISTRY_URL = _resolve_api_url()  # name kept for callers/tests; it is the API base URL


def _require_safe_url(url: str, what: str) -> str:
    """Allow https anywhere and http only for localhost; never file:, ftp: or others."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme == "https" or (parsed.scheme == "http" and local):
        return url
    raise click.ClickException(f"Refusing {what} '{url}': only https:// (or http://localhost) is allowed.")


def _registry_publish(manifest: dict, zip_path: Path) -> dict:
    """POST manifest JSON + ZIP to the registry. Returns the registry response."""
    import urllib.error
    import urllib.request

    boundary = "AgentFactoryBoundary"
    manifest_bytes = json.dumps(manifest).encode()
    zip_bytes = zip_path.read_bytes()

    parts = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="manifest"'
            f"\r\nContent-Type: application/json\r\n\r\n".encode()
            + manifest_bytes
            + b"\r\n"
        ),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"'
            f'; filename="{zip_path.name}"\r\nContent-Type: application/zip\r\n\r\n'.encode()
            + zip_bytes
            + b"\r\n"
        ),
    ]
    sig_path = zip_path.with_name(zip_path.name + ".sig")
    if sig_path.exists():  # publisher signature from `wrap --sign` / `sign` (#144)
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="signature"\r\n\r\n'.encode()
            + sig_path.read_bytes()
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    _require_safe_url(REGISTRY_URL, "registry URL")
    req = urllib.request.Request(f"{REGISTRY_URL}/registry/publish", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    _attach_auth_header(req)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail", exc.reason)
        except (OSError, ValueError, AttributeError):  # body unreadable, not JSON, or not an object
            detail = exc.reason
        raise click.ClickException(f"Registry error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise click.ClickException(f"Registry unreachable: {exc.reason}") from exc


def _registry_fetch(slug: str) -> tuple[dict, bytes]:
    """GET agent entry from registry and download its ZIP. Returns (entry_dict, zip_bytes)."""
    import urllib.error
    import urllib.request

    name, _, version = slug.partition("@")
    path = f"/registry/{name}/{version}" if version else f"/registry/{name}"

    _require_safe_url(REGISTRY_URL, "registry URL")
    req = urllib.request.Request(f"{REGISTRY_URL}{path}", method="GET")
    _attach_auth_header(req)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            entry = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise click.ClickException(f"Agent '{slug}' not found in registry.") from exc
        raise click.ClickException(f"Registry error {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise click.ClickException(f"Registry unreachable: {exc.reason}") from exc

    zip_url = entry.get("zip_url")
    if not zip_url:
        raise click.ClickException(f"Registry response missing 'zip_url' for '{slug}'.")
    _require_safe_url(zip_url, "download URL")

    try:
        with urllib.request.urlopen(zip_url, timeout=60) as resp:
            zip_bytes = resp.read()
    except urllib.error.URLError as exc:
        raise click.ClickException(f"Failed to download agent ZIP: {exc.reason}") from exc

    return entry, zip_bytes


def _token_path() -> Path:
    return Path.home() / ".agentfactory" / "token"


def _attach_auth_header(req) -> None:
    token_path = _token_path()
    if token_path.exists():
        req.add_header("Authorization", f"Bearer {token_path.read_text().strip()}")


def _api_json(method: str, path: str, payload: dict | None = None, auth: bool = False) -> dict:
    """Small JSON client for the AgentFactory API (same URL policy as the registry helpers)."""
    import urllib.error
    import urllib.request

    _require_safe_url(REGISTRY_URL, "API URL")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{REGISTRY_URL}{path}", data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if auth:
        _attach_auth_header(req)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode()).get("detail", exc.reason)
        except (OSError, ValueError, AttributeError):  # body unreadable, not JSON, or not an object
            detail = exc.reason
        raise click.ClickException(f"API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise click.ClickException(f"API unreachable ({REGISTRY_URL}): {exc.reason}") from exc


def _write_token(token: str) -> Path:
    path = _token_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(token.strip())
    os.replace(tmp, path)
    return path
