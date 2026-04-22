"""Tests for the AgentFactory API — auth endpoints and license validation."""
import os
import tempfile
import unittest
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
        import tempfile, importlib
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


if __name__ == "__main__":
    unittest.main()
