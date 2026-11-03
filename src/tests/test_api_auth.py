"""Tests for the AgentFactory API — auth endpoints and license validation."""
import os
import tempfile
import unittest
import importlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="API tests need the [api] extra")
pytest.importorskip("jose", reason="API tests need the [api] extra")

# Set required env vars before importing the app
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only-0123456789abcdef")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_agentfactory.db")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")


class TestDatabaseInit(unittest.TestCase):
    def test_init_db_creates_users_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
            # Re-import db with new env
            import importlib
            import agent_gen.api.db as db_module
            importlib.reload(db_module)
            db_module.init_db()
            with db_module.get_conn() as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                ).fetchall()
                self.assertEqual(len(rows), 1)


class TestJwtUtils(unittest.TestCase):
    def setUp(self):
        os.environ["JWT_SECRET"] = "test-jwt-secret-at-least-32-characters-long"

    def test_create_and_decode_token(self):
        from agent_gen.api.jwt_utils import create_token, decode_token
        token = create_token("user-123")
        self.assertIsInstance(token, str)
        user_id = decode_token(token)
        self.assertEqual(user_id, "user-123")

    def test_decode_invalid_token_returns_none(self):
        from agent_gen.api.jwt_utils import decode_token
        self.assertIsNone(decode_token("not.a.valid.token"))

    def test_decode_tampered_token_returns_none(self):
        from agent_gen.api.jwt_utils import create_token, decode_token
        token = create_token("user-456")
        tampered = token[:-5] + "XXXXX"
        self.assertIsNone(decode_token(tampered))


class TestLicenseValidation(unittest.TestCase):
    """Keys are random and looked up by hash; the key text no longer encodes a plan."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = f"sqlite:///{self._tmp.name}/test.db"
        import agent_gen.api.db as db_module
        importlib.reload(db_module)
        db_module.init_db()
        self.db = db_module
        from fastapi.testclient import TestClient
        import agent_gen.api.main as main_module
        self.client = TestClient(main_module.app, raise_server_exceptions=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _validate(self, key: str, tier: str) -> dict:
        resp = self.client.post("/v1/validate", json={"key": key, "tier": tier})
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_issued_pro_key_valid_for_pro_and_free(self):
        key = self.db.issue_license_key("pro")
        self.assertEqual(self._validate(key, "pro"), {"valid": True, "tier": "pro"})
        self.assertTrue(self._validate(key, "free")["valid"])

    def test_pro_key_invalid_for_team_tier(self):
        key = self.db.issue_license_key("pro")
        self.assertFalse(self._validate(key, "team")["valid"])

    def test_forged_prefix_keys_are_rejected(self):
        for forged in ("pro_abc123", "enterprise_xyz", "enterprise_" + "x" * 40):
            self.assertFalse(self._validate(forged, "free")["valid"], forged)

    def test_revoked_key_is_rejected(self):
        key = self.db.issue_license_key("team")
        self.assertTrue(self.db.revoke_license_key(key))
        self.assertFalse(self._validate(key, "free")["valid"])

    def test_unknown_tier_is_rejected(self):
        key = self.db.issue_license_key("enterprise")
        self.assertFalse(self._validate(key, "platinum")["valid"])

    def test_only_hash_is_stored(self):
        key = self.db.issue_license_key("pro")
        with self.db.get_conn() as conn:
            rows = [tuple(r) for r in conn.execute("SELECT * FROM license_keys").fetchall()]
        self.assertTrue(rows)
        self.assertFalse(any(key in str(col) for row in rows for col in row))


class TestAuthMe(unittest.TestCase):
    def _get_client(self):
        from fastapi.testclient import TestClient
        from agent_gen.api.main import app
        return TestClient(app, raise_server_exceptions=True)

    def test_me_without_cookie_returns_401(self):
        client = self._get_client()
        resp = client.get("/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_me_with_invalid_cookie_returns_401(self):
        client = self._get_client()
        client.cookies.set("session", "invalid.jwt.token")
        resp = client.get("/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_me_with_valid_session_returns_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
            import agent_gen.api.db as db_module
            importlib.reload(db_module)
            db_module.init_db()

            # Insert a test user
            import uuid
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            user_id = str(uuid.uuid4())
            with db_module.get_conn() as conn:
                conn.execute(
                    "INSERT INTO users (id, github_id, github_handle, email, avatar_url, plan, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, 99999, "testuser", "test@example.com", "", "free", now, now),
                )

            from agent_gen.api.jwt_utils import create_token
            token = create_token(user_id)

            import agent_gen.api.deps as deps_module
            importlib.reload(deps_module)

            from fastapi.testclient import TestClient
            import agent_gen.api.main as main_module
            importlib.reload(main_module)
            client = TestClient(main_module.app, raise_server_exceptions=True)
            client.cookies.set("session", token)
            resp = client.get("/auth/me")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["github_handle"], "testuser")
            self.assertEqual(data["plan"], "free")


class TestAuthLogout(unittest.TestCase):
    def test_logout_clears_cookie(self):
        from fastapi.testclient import TestClient
        from agent_gen.api.main import app
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post("/auth/logout")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from agent_gen.api.main import app
        client = TestClient(app)
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


class TestGithubLoginUnconfigured(unittest.TestCase):
    def test_github_login_without_client_id_returns_503(self):
        saved = os.environ.pop("GITHUB_CLIENT_ID", None)
        try:
            import importlib
            import agent_gen.api.routers.auth as auth_module
            importlib.reload(auth_module)
            import agent_gen.api.main as main_module
            importlib.reload(main_module)
            from fastapi.testclient import TestClient
            client = TestClient(main_module.app, raise_server_exceptions=False)
            resp = client.get("/auth/github", follow_redirects=False)
            self.assertEqual(resp.status_code, 503)
        finally:
            if saved:
                os.environ["GITHUB_CLIENT_ID"] = saved


class TestGithubOAuthCallback(unittest.TestCase):
    """Tests for /auth/github (login redirect) and /auth/github/callback."""

    def _setup_db(self, tmp: str):
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
        import agent_gen.api.db as db_module
        importlib.reload(db_module)
        db_module.init_db()
        import agent_gen.api.deps as deps_module
        importlib.reload(deps_module)
        return db_module

    def _get_client_and_state(self, auth_env: dict | None = None):
        """Return (TestClient, auth_module, state_token) with a real pending state."""
        if auth_env:
            for k, v in auth_env.items():
                os.environ[k] = v
        os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
        import agent_gen.api.routers.auth as auth_module
        importlib.reload(auth_module)
        import agent_gen.api.main as main_module
        importlib.reload(main_module)
        from fastapi.testclient import TestClient
        client = TestClient(main_module.app, raise_server_exceptions=True)
        # Trigger /auth/github to plant a real state token
        redir = client.get("/auth/github", follow_redirects=False)
        location = redir.headers.get("location", "")
        state = ""
        for part in location.split("&"):
            if part.startswith("state=") or "?state=" in part:
                state = part.split("state=", 1)[-1]
        return client, auth_module, state

    def test_github_login_redirects_to_github_oauth(self):
        client, _, _ = self._get_client_and_state()
        redir = client.get("/auth/github", follow_redirects=False)
        self.assertIn(redir.status_code, [302, 307])
        self.assertIn("github.com/login/oauth/authorize", redir.headers["location"])
        self.assertIn("test-client-id", redir.headers["location"])

    def test_github_callback_invalid_state_returns_400(self):
        client, _, _ = self._get_client_and_state()
        resp = client.get("/auth/github/callback?code=abc&state=completely-invalid-state")
        self.assertEqual(resp.status_code, 400)

    def test_github_callback_no_access_token_returns_502(self):
        client, auth_module, state = self._get_client_and_state()
        auth_module._remember_state(state)
        with patch("agent_gen.api.routers.auth.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
            resp = client.get(f"/auth/github/callback?code=testcode&state={state}")
            self.assertEqual(resp.status_code, 502)

    def test_github_callback_user_fetch_failure_returns_502(self):
        client, auth_module, state = self._get_client_and_state()
        auth_module._remember_state(state)
        with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
             patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
            mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "tok"})
            mock_get.return_value = MagicMock(status_code=500)
            resp = client.get(f"/auth/github/callback?code=testcode&state={state}")
            self.assertEqual(resp.status_code, 502)

    def test_github_callback_creates_new_user_and_sets_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup_db(tmp)
            client, auth_module, state = self._get_client_and_state()
            auth_module._remember_state(state)
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "tok"})
                user_data = {
                    "id": 11111, "login": "newuser",
                    "email": "new@example.com", "avatar_url": "",
                }
                mock_get.return_value = MagicMock(
                    status_code=200, json=lambda: user_data
                )
                resp = client.get(
                    f"/auth/github/callback?code=testcode&state={state}",
                    follow_redirects=False,
                )
            self.assertIn(resp.status_code, [302, 307])
            self.assertIn("session", resp.cookies)
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT github_handle, plan FROM users WHERE github_id = ?", (11111,)
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["github_handle"], "newuser")
            self.assertEqual(row["plan"], "free")

    def test_github_callback_updates_existing_user_preserves_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup_db(tmp)
            now = datetime.now(timezone.utc).isoformat()
            existing_id = str(uuid.uuid4())
            with db.get_conn() as conn:
                conn.execute(
                    "INSERT INTO users (id, github_id, github_handle, email, avatar_url, plan, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (existing_id, 22222, "oldhandle", "old@x.com", "", "pro", now, now),
                )
            client, auth_module, state = self._get_client_and_state()
            auth_module._remember_state(state)
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "tok"})
                updated = {"id": 22222, "login": "newhandle", "email": "new@x.com", "avatar_url": ""}
                mock_get.return_value = MagicMock(status_code=200, json=lambda: updated)
                client.get(
                    f"/auth/github/callback?code=testcode&state={state}",
                    follow_redirects=False,
                )
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT id, github_handle, plan FROM users WHERE github_id = ?", (22222,)
                ).fetchone()
            self.assertEqual(row["id"], existing_id)
            self.assertEqual(row["github_handle"], "newhandle")
            self.assertEqual(row["plan"], "pro")  # plan not overwritten on update

    def test_github_callback_email_fallback_from_emails_endpoint(self):
        """When user has no public email, callback fetches from /user/emails."""
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup_db(tmp)
            client, auth_module, state = self._get_client_and_state()
            auth_module._remember_state(state)
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(status_code=200, json=lambda: {"access_token": "tok"})
                # First call: user has no email
                user_no_email = {"id": 33333, "login": "noemailer", "email": None, "avatar_url": ""}
                # Second call: /user/emails returns primary
                emails_data = [{"email": "private@x.com", "primary": True, "verified": True}]
                mock_get.side_effect = [
                    MagicMock(status_code=200, json=lambda: user_no_email),
                    MagicMock(status_code=200, json=lambda: emails_data),
                ]
                client.get(
                    f"/auth/github/callback?code=testcode&state={state}",
                    follow_redirects=False,
                )
            with db.get_conn() as conn:
                row = conn.execute(
                    "SELECT email FROM users WHERE github_id = ?", (33333,)
                ).fetchone()
            self.assertEqual(row["email"], "private@x.com")


class TestJwtSecretPolicy(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("JWT_SECRET", "AGENTFACTORY_ENV")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_missing_secret_refuses_outside_dev(self):
        from agent_gen.api.jwt_utils import InsecureConfigError, check_config
        os.environ.pop("JWT_SECRET", None)
        os.environ.pop("AGENTFACTORY_ENV", None)
        with self.assertRaises(InsecureConfigError):
            check_config()

    def test_placeholder_and_short_secrets_refused(self):
        from agent_gen.api.jwt_utils import InsecureConfigError, check_config
        os.environ.pop("AGENTFACTORY_ENV", None)
        for bad in ("change_me_generate_a_real_secret", "dev-secret-change-in-production", "short"):
            os.environ["JWT_SECRET"] = bad
            with self.assertRaises(InsecureConfigError, msg=bad):
                check_config()

    def test_dev_env_allows_default_secret(self):
        from agent_gen.api.jwt_utils import check_config, create_token, decode_token
        os.environ.pop("JWT_SECRET", None)
        os.environ["AGENTFACTORY_ENV"] = "dev"
        check_config()
        self.assertEqual(decode_token(create_token("u1")), "u1")

    def test_app_startup_fails_without_secret(self):
        from fastapi.testclient import TestClient
        from agent_gen.api.jwt_utils import InsecureConfigError
        import agent_gen.api.main as main_module
        os.environ.pop("JWT_SECRET", None)
        os.environ.pop("AGENTFACTORY_ENV", None)
        with self.assertRaises(InsecureConfigError):
            with TestClient(main_module.app):
                pass

    def test_secret_is_read_at_call_time(self):
        from agent_gen.api.jwt_utils import create_token, decode_token
        os.environ.pop("AGENTFACTORY_ENV", None)
        os.environ["JWT_SECRET"] = "a" * 40
        token = create_token("u2")
        os.environ["JWT_SECRET"] = "b" * 40
        self.assertIsNone(decode_token(token))


class TestOAuthStateStore(unittest.TestCase):
    def setUp(self):
        import agent_gen.api.routers.auth as auth_module
        self.auth = auth_module
        self.auth._pending_states.clear()

    def test_state_is_single_use(self):
        self.auth._remember_state("s1")
        self.assertTrue(self.auth._consume_state("s1"))
        self.assertFalse(self.auth._consume_state("s1"))

    def test_expired_state_rejected(self):
        self.auth._remember_state("s2")
        with patch("agent_gen.api.routers.auth.time.time", return_value=10**12):
            self.assertFalse(self.auth._consume_state("s2"))

    def test_store_is_capped(self):
        with patch.object(self.auth, "_MAX_PENDING_STATES", 5):
            for i in range(20):
                self.auth._remember_state(f"s{i}")
            self.assertEqual(len(self.auth._pending_states), 5)
            self.assertIn("s19", self.auth._pending_states)

    def test_login_redirect_is_url_encoded(self):
        from fastapi.testclient import TestClient
        import agent_gen.api.main as main_module
        os.environ["GITHUB_REDIRECT_URI"] = "http://localhost:8000/auth/github/callback?x=1&y=2"
        try:
            importlib.reload(self.auth)
            importlib.reload(main_module)
            client = TestClient(main_module.app)
            location = client.get("/auth/github", follow_redirects=False).headers["location"]
        finally:
            os.environ.pop("GITHUB_REDIRECT_URI", None)
            importlib.reload(self.auth)
            importlib.reload(main_module)
        self.assertIn(
            "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fgithub%2Fcallback%3Fx%3D1%26y%3D2",
            location,
        )

    def test_token_exchange_http_error_returns_502(self):
        from fastapi.testclient import TestClient
        import agent_gen.api.main as main_module
        importlib.reload(self.auth)
        importlib.reload(main_module)
        client = TestClient(main_module.app, raise_server_exceptions=True)
        self.auth._remember_state("s3")
        with patch("agent_gen.api.routers.auth.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500, json=lambda: {"access_token": "tok"})
            resp = client.get("/auth/github/callback?code=c&state=s3")
        self.assertEqual(resp.status_code, 502)


class TestKeysCli(unittest.TestCase):
    def test_add_and_revoke(self):
        from click.testing import CliRunner
        import agent_gen.api.db as db_module
        from agent_gen.api.main import _build_cli
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/k.db"
            importlib.reload(db_module)
            cli = _build_cli()
            runner = CliRunner()
            out = runner.invoke(cli, ["keys", "add", "--plan", "team"])
            self.assertEqual(out.exit_code, 0, out.output)
            key = out.output.strip()
            self.assertTrue(key.startswith("afk_"))
            self.assertEqual(db_module.license_plan(key), "team")
            self.assertEqual(runner.invoke(cli, ["keys", "revoke", key]).exit_code, 0)
            self.assertIsNone(db_module.license_plan(key))
            self.assertNotEqual(runner.invoke(cli, ["keys", "revoke", key]).exit_code, 0)


if __name__ == "__main__":
    unittest.main()
