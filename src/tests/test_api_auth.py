"""Tests for the AgentFactory API — auth endpoints and license validation."""
import os
import tempfile
import unittest
import importlib
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Set required env vars before importing the app
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
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
        os.environ["JWT_SECRET"] = "test-jwt-secret-32chars-long-ok"

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
    def _get_client(self):
        from fastapi.testclient import TestClient
        from agent_gen.api.main import app
        return TestClient(app, raise_server_exceptions=True)

    def test_valid_pro_key_for_pro_tier(self):
        client = self._get_client()
        resp = client.post("/v1/validate", json={"key": "pro_abc123", "tier": "pro"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["valid"])
        self.assertEqual(resp.json()["tier"], "pro")

    def test_pro_key_valid_for_free_tier(self):
        client = self._get_client()
        resp = client.post("/v1/validate", json={"key": "pro_abc123", "tier": "free"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["valid"])

    def test_free_key_invalid_for_pro_tier(self):
        client = self._get_client()
        resp = client.post("/v1/validate", json={"key": "free_abc123", "tier": "pro"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["valid"])

    def test_invalid_key_format(self):
        client = self._get_client()
        resp = client.post("/v1/validate", json={"key": "notavalidkey", "tier": "pro"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["valid"])

    def test_enterprise_key_for_team_tier(self):
        client = self._get_client()
        resp = client.post("/v1/validate", json={"key": "enterprise_xyz", "tier": "team"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["valid"])


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
        auth_module._pending_states[state] = True
        with patch("agent_gen.api.routers.auth.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(json=lambda: {})
            resp = client.get(f"/auth/github/callback?code=testcode&state={state}")
            self.assertEqual(resp.status_code, 502)

    def test_github_callback_user_fetch_failure_returns_502(self):
        client, auth_module, state = self._get_client_and_state()
        auth_module._pending_states[state] = True
        with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
             patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
            mock_post.return_value = MagicMock(json=lambda: {"access_token": "tok"})
            mock_get.return_value = MagicMock(status_code=500)
            resp = client.get(f"/auth/github/callback?code=testcode&state={state}")
            self.assertEqual(resp.status_code, 502)

    def test_github_callback_creates_new_user_and_sets_cookie(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup_db(tmp)
            client, auth_module, state = self._get_client_and_state()
            auth_module._pending_states[state] = True
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(json=lambda: {"access_token": "tok"})
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
            auth_module._pending_states[state] = True
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(json=lambda: {"access_token": "tok"})
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
            auth_module._pending_states[state] = True
            with patch("agent_gen.api.routers.auth.httpx.post") as mock_post, \
                 patch("agent_gen.api.routers.auth.httpx.get") as mock_get:
                mock_post.return_value = MagicMock(json=lambda: {"access_token": "tok"})
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


if __name__ == "__main__":
    unittest.main()
