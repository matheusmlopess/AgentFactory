"""Device login (#201): API flow, single-use tokens, Bearer /auth/me, and `agentfactory-gen login|whoami|logout`."""
import importlib
import os
import socket
import stat
import threading
import time
import uuid
from datetime import datetime, timezone

import pytest

pytest.importorskip("fastapi", reason="API tests need the [api] extra")

from click.testing import CliRunner  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "device-tests-secret-0123456789abcdef")
    monkeypatch.delenv("AGENTFACTORY_ENV", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/dev.db")
    monkeypatch.setenv("WEBAPP_URL", "https://app.example.test")
    monkeypatch.setenv("DEVICE_POLL_INTERVAL", "0.1")
    import agent_gen.api.db as db
    importlib.reload(db)
    db.init_db()
    import agent_gen.api.deps as deps
    importlib.reload(deps)
    import agent_gen.api.routers.auth as auth
    importlib.reload(auth)
    import agent_gen.api.routers.registry as registry
    importlib.reload(registry)
    import agent_gen.api.main as main
    importlib.reload(main)
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, github_id, github_handle, email, avatar_url, plan, created_at, updated_at) "
            "VALUES (?, 4242, 'alice', 'alice@example.test', '', 'pro', ?, ?)", (uid, now, now))
    from agent_gen.api.jwt_utils import create_token
    return TestClient(main.app), db, uid, create_token(uid), main


def test_device_flow_issues_token_once(api):
    client, db, uid, session, _ = api
    start = client.post("/auth/cli/device", json={}).json()
    assert start["verification_uri"] == "https://app.example.test/device"
    assert start["user_code"] in start["verification_uri_complete"]
    assert len(start["user_code"]) == 9 and start["user_code"][4] == "-"

    assert client.get("/auth/cli/poll", params={"device_code": start["device_code"]}).json()["status"] == "pending"

    client.cookies.set("session", session)
    assert client.post("/auth/cli/approve", json={"user_code": start["user_code"].lower().replace("-", "")}).json() == {"approved": True}
    client.cookies.clear()

    done = client.post("/auth/cli/poll", json={"device_code": start["device_code"]}).json()
    assert done["status"] == "authorized" and done["token"].startswith("aft_")
    assert done["user"]["github_handle"] == "alice"
    again = client.post("/auth/cli/poll", json={"device_code": start["device_code"]}).json()
    assert again == {"status": "expired", "token": None, "user": None}

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {done['token']}"})
    assert me.status_code == 200 and me.json()["plan"] == "pro"


def test_approve_requires_session_and_valid_code(api):
    client, _, _, session, _ = api
    start = client.post("/auth/cli/device", json={}).json()
    assert client.post("/auth/cli/approve", json={"user_code": start["user_code"]}).status_code == 401
    client.cookies.set("session", session)
    assert client.post("/auth/cli/approve", json={"user_code": "ZZZZ-ZZZZ"}).status_code == 400
    assert client.post("/auth/cli/approve", json={"user_code": start["user_code"]}).status_code == 200
    assert client.post("/auth/cli/approve", json={"user_code": start["user_code"]}).status_code == 400


def test_expired_code(api):
    client, db, _, session, _ = api
    start = client.post("/auth/cli/device", json={}).json()
    with db.get_conn() as conn:
        conn.execute("UPDATE device_codes SET expires_at = '2000-01-01T00:00:00+00:00'")
    client.cookies.set("session", session)
    assert client.post("/auth/cli/approve", json={"user_code": start["user_code"]}).status_code == 400
    assert client.post("/auth/cli/poll", json={"device_code": start["device_code"]}).json()["status"] == "expired"


def test_pending_codes_are_capped(api, monkeypatch):
    client, db, *_ = api
    monkeypatch.setattr(db, "MAX_PENDING_DEVICE_CODES", 3)
    for _ in range(3):
        assert client.post("/auth/cli/device", json={}).status_code == 200
    assert client.post("/auth/cli/device", json={}).status_code == 429


def test_logout_revokes_bearer_token(api):
    client, db, uid, *_ = api
    token = db.issue_api_token(uid, "t")
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.post("/auth/cli/logout", headers=h).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.integration
def test_cli_login_whoami_logout(api, tmp_path, monkeypatch):
    uvicorn = pytest.importorskip("uvicorn")
    _, db, uid, _, main = api
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    import agent_gen.cli as cli_module
    monkeypatch.setattr(cli_module, "REGISTRY_URL", f"http://127.0.0.1:{port}")

    def approve_when_started():
        for _ in range(100):
            with db.get_conn() as conn:
                row = conn.execute("SELECT user_code FROM device_codes WHERE approved_by IS NULL").fetchone()
            if row:
                db.approve_device_code(row["user_code"], uid)
                return
            time.sleep(0.05)

    approver = threading.Thread(target=approve_when_started, daemon=True)
    approver.start()
    runner = CliRunner()
    try:
        r = runner.invoke(cli_module.cli, ["login", "--no-browser"])
        assert r.exit_code == 0, r.output
        assert "Signed in as alice" in r.output
        token_file = home / ".agentfactory" / "token"
        assert stat.S_IMODE(os.stat(token_file).st_mode) == 0o600
        token = token_file.read_text()
        assert db.api_token_user(token) == uid

        r = runner.invoke(cli_module.cli, ["whoami"])
        assert r.exit_code == 0 and r.output.startswith("alice (pro)")

        r = runner.invoke(cli_module.cli, ["logout"])
        assert r.exit_code == 0 and not token_file.exists()
        assert db.api_token_user(token) is None
        assert runner.invoke(cli_module.cli, ["whoami"]).exit_code != 0
    finally:
        server.should_exit = True
        thread.join(timeout=5)
