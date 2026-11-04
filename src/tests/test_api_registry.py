"""Registry API (#193): publish / list / fetch / download, ownership, immutability, and the CLI round trip."""
import hashlib
import importlib
import io
import json
import os
import socket
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="API tests need the [api] extra")
pytest.importorskip("multipart", reason="registry upload needs python-multipart ([api] extra)")

from click.testing import CliRunner  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "registry-tests-secret-0123456789abcdef")
    monkeypatch.delenv("AGENTFACTORY_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/reg.db")
    monkeypatch.setenv("REGISTRY_STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("API_PUBLIC_URL", "https://api.example.test")
    import agent_gen.api.db as db
    importlib.reload(db)
    db.init_db()
    import agent_gen.api.deps as deps
    importlib.reload(deps)
    import agent_gen.api.routers.registry as registry
    importlib.reload(registry)
    import agent_gen.api.main as main
    importlib.reload(main)

    def user(handle: str) -> str:
        uid = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO users (id, github_id, github_handle, email, avatar_url, plan, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, '', 'free', ?, ?)",
                (uid, abs(hash(handle)) % 10**9, handle, f"{handle}@example.test", now, now))
        return db.issue_api_token(uid, "tests")

    return TestClient(main.app), db, user, tmp_path


def bundle(name: str, version: str = "1.0.0", extra: dict | None = None, manifest_name: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("agent-manifest.json", json.dumps({"name": manifest_name or name, "version": version}))
        for k, v in (extra or {}).items():
            zf.writestr(k, v)
    return buf.getvalue()


def publish(client, token, name="demo", version="1.0.0", data=None, **meta):
    m = {"name": name, "version": version, "description": "Demo agent", "tags": ["demo"], **meta}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/registry/publish", headers=headers,
                       data={"manifest": json.dumps(m)},
                       files={"file": ("demo.zip", data if data is not None else bundle(name, version), "application/zip")})


def test_publish_requires_auth(api):
    client, *_ = api
    assert publish(client, None).status_code == 401
    assert publish(client, "aft_not-a-real-token").status_code == 401


def test_publish_fetch_download_round_trip(api):
    client, db, user, tmp = api
    token = user("alice")
    data = bundle("demo")
    r = publish(client, token, data=data)
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["sha256"] == hashlib.sha256(data).hexdigest()
    assert entry["zip_url"] == "https://api.example.test/registry/demo/1.0.0/download"
    assert entry["owner"] == "alice" and entry["versions"] == ["1.0.0"]

    assert client.get("/registry/demo").json()["version"] == "1.0.0"
    assert client.get("/registry/demo/1.0.0").json()["sha256"] == entry["sha256"]
    dl = client.get("/registry/demo/1.0.0/download")
    assert dl.status_code == 200 and dl.content == data
    assert dl.headers["content-type"] == "application/zip"


def test_versions_are_immutable_and_latest_moves(api):
    client, _, user, _ = api
    token = user("alice")
    assert publish(client, token).status_code == 201
    assert publish(client, token).status_code == 409
    assert publish(client, token, version="1.1.0").status_code == 201
    latest = client.get("/registry/demo").json()
    assert latest["version"] == "1.1.0" and latest["versions"] == ["1.0.0", "1.1.0"]


def test_only_owner_can_publish_new_versions(api):
    client, _, user, _ = api
    alice, bob = user("alice"), user("bob")
    assert publish(client, alice).status_code == 201
    assert publish(client, bob, version="2.0.0").status_code == 403


@pytest.mark.parametrize("meta,status", [
    ({"name": "../evil"}, 422),
    ({"name": "/abs"}, 422),
    ({"version": "latest"}, 422),
    ({"description": ""}, 422),
    ({"tags": ["Not Valid"]}, 422),
])
def test_publish_validates_metadata(api, meta, status):
    client, _, user, _ = api
    name = meta.get("name", "demo")
    r = publish(client, user("alice"), data=bundle("demo"), **{**meta, "name": name})
    assert r.status_code == status, r.text


@pytest.mark.parametrize("data,detail", [
    (b"not a zip", "not a ZIP"),
    (bundle("demo", manifest_name="other"), "names 'other'"),
    (bundle("demo", extra={"../escape.txt": "x"}), "unsafe path"),
])
def test_publish_validates_archive(api, data, detail):
    client, _, user, _ = api
    r = publish(client, user("alice"), data=data)
    assert r.status_code == 422 and detail in r.json()["detail"]


def test_archive_without_manifest_rejected(api):
    client, _, user, _ = api
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.md", "hi")
    assert publish(client, user("alice"), data=buf.getvalue()).status_code == 422


def test_size_limit(api, monkeypatch):
    client, _, user, _ = api
    monkeypatch.setenv("REGISTRY_MAX_ZIP_BYTES", "100")
    r = publish(client, user("alice"), data=bundle("demo", extra={"big.txt": "x" * 5000}))
    assert r.status_code == 413


def test_list_and_search(api):
    client, _, user, _ = api
    token = user("alice")
    publish(client, token, name="demo", data=bundle("demo"))
    publish(client, token, name="docs-system", data=bundle("docs-system"), description="Documentation agent",
            tags=["docs"])
    names = [u["name"] for u in client.get("/registry").json()]
    assert set(names) == {"demo", "docs-system"}
    found = client.get("/registry", params={"q": "documentation"}).json()
    assert [u["name"] for u in found] == ["docs-system"] and found[0]["latest_version"] == "1.0.0"


def test_unknown_unit_and_version_404(api):
    client, _, user, _ = api
    assert client.get("/registry/nope").status_code == 404
    publish(client, user("alice"))
    assert client.get("/registry/demo/9.9.9").status_code == 404


def test_revoked_and_expired_tokens(api):
    client, db, user, _ = api
    token = user("alice")
    assert db.revoke_api_token(token)
    assert publish(client, token).status_code == 401
    with db.get_conn() as conn:
        uid = conn.execute("SELECT id FROM users WHERE github_handle='alice'").fetchone()["id"]
        expired = db.issue_api_token(uid, "old", ttl_days=1)
        conn.execute("UPDATE api_tokens SET expires_at = '2000-01-01T00:00:00+00:00' WHERE label = 'old'")
    assert publish(client, expired).status_code == 401


def test_tokens_cli(api):
    _, db, user, _ = api
    user("carol")
    from agent_gen.api.main import _build_cli
    runner = CliRunner()
    out = runner.invoke(_build_cli(), ["tokens", "add", "--github-handle", "carol", "--label", "laptop"])
    assert out.exit_code == 0, out.output
    token = out.output.strip()
    assert token.startswith("aft_") and db.api_token_user(token)
    assert runner.invoke(_build_cli(), ["tokens", "revoke", token]).exit_code == 0
    assert db.api_token_user(token) is None
    assert runner.invoke(_build_cli(), ["tokens", "add", "--github-handle", "nobody"]).exit_code != 0


# ---------------------------------------------------------------- CLI round trip against a live server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.integration
def test_cli_publish_then_import_from_registry(api, tmp_path, monkeypatch):
    """The MVP loop on one machine: wrap → publish (CLI, Bearer token) → import --from-registry in another project."""
    uvicorn = pytest.importorskip("uvicorn")
    _, db, user, _ = api
    token = user("alice")
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("API_PUBLIC_URL", base)

    import agent_gen.api.main as main
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    home = tmp_path / "home"
    (home / ".agentfactory").mkdir(parents=True)
    (home / ".agentfactory" / "token").write_text(token)
    monkeypatch.setenv("HOME", str(home))
    import agent_gen.cli as cli_module
    monkeypatch.setattr(cli_module, "REGISTRY_URL", base)
    runner = CliRunner()
    try:
        src = tmp_path / "publisher"
        src.mkdir()
        os.chdir(src)
        assert runner.invoke(cli_module.cli, ["init"]).exit_code == 0
        assert runner.invoke(cli_module.cli, ["deploy", "demo"]).exit_code == 0
        assert runner.invoke(cli_module.cli, ["describe", "demo", "--desc", "Demo agent"]).exit_code == 0
        r = runner.invoke(cli_module.cli, ["wrap", "demo"])
        assert r.exit_code == 0, r.output
        r = runner.invoke(cli_module.cli, ["publish", "demo"])
        assert r.exit_code == 0, r.output

        dst = tmp_path / "consumer"
        dst.mkdir()
        os.chdir(dst)
        assert runner.invoke(cli_module.cli, ["init"]).exit_code == 0
        r = runner.invoke(cli_module.cli, ["import", "--from-registry", "demo"])
        assert r.exit_code == 0, r.output
        assert "checksum auto-verified" in r.output
        assert (dst / ".ai" / "agents" / "demo" / "agent-manifest.json").exists()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        os.chdir(Path(__file__).parent)
