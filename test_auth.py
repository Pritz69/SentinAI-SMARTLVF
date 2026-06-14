import unittest
import os
import sqlite3
from fastapi.testclient import TestClient

import sys
from unittest.mock import MagicMock

# Mock out heavy imports to run tests instantly
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.metrics.pairwise"] = MagicMock()

# Mock environment keys before importing app
os.environ["GROQ_API_KEY"] = "mock_groq_key"
os.environ["GOOGLE_API_KEY"] = "mock_google_key"
os.environ["SQLITE_DB_PATH"] = "test_state.db"

from unittest.mock import patch

class MockChromaVectorRepository:
    def __init__(self, *args, **kwargs):
        pass
    async def initialize(self):
        pass
    async def add_exploit_vector(self, *args, **kwargs):
        pass
    async def query_similar_exploits(self, *args, **kwargs):
        return []

# Setup class patcher for ChromaDB
patcher_chroma = patch("database.chroma_repo.ChromaVectorRepository", MockChromaVectorRepository)
patcher_chroma.start()

from main import app
from database.sqlite_user_repo import user_repo

class TestSentinAIAuth(unittest.TestCase):
    def setUp(self):
        # We will use a clean test DB or clear test records to prevent conflicts
        self.client = TestClient(app)
        
        # Clear database users to make tests isolated, except for seeds
        conn = sqlite3.connect(user_repo.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username NOT IN ('admin', 'user')")
        conn.commit()
        conn.close()

    def test_preseeded_credentials(self):
        """Verify default admin and user credentials work."""
        # 1. Admin login
        resp = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["role"], "admin")
        self.assertEqual(data["username"], "admin")
        self.assertIn("access_token", data)

        # 2. User login
        resp = self.client.post("/api/v1/auth/login", json={"username": "user", "password": "user123"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["role"], "user")
        self.assertEqual(data["username"], "user")
        self.assertIn("access_token", data)

    def test_registration_flow(self):
        """Test registering a new user, checking duplicate validation, and logging in."""
        # 1. Register a new analyst (role will default to 'user')
        reg_payload = {
            "username": "analyst99",
            "password": "securepassword"
        }
        resp = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["username"], "analyst99")
        self.assertEqual(data["role"], "user")
        self.assertIn("id", data)

        # 2. Try registering same username (should fail)
        resp2 = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("Username already taken", resp2.json()["detail"])

        # 3. Log in with the newly registered user
        login_resp = self.client.post("/api/v1/auth/login", json={"username": "analyst99", "password": "securepassword"})
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.json()
        token = login_data["access_token"]
        self.assertEqual(login_data["role"], "user")

        # 4. Check profile endpoint
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data["username"], "analyst99")
        self.assertEqual(me_data["role"], "user")

    def test_failed_login(self):
        """Verify login fails with incorrect password or non-existent username."""
        # Incorrect password
        resp = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Incorrect username or password", resp.json()["detail"])

        # Non-existent user
        resp2 = self.client.post("/api/v1/auth/login", json={"username": "nobody", "password": "somepassword"})
        self.assertEqual(resp2.status_code, 401)

    def test_endpoint_authorization_rules(self):
        """
        Verify security policy access boundaries:
        - Anonymous users get 401 on targets endpoint.
        - User mode accounts can GET list targets and POST register new targets.
        - User mode accounts get 403 Forbidden on DELETE target.
        - Admin mode accounts can do all.
        """
        # 1. No credentials (anonymous)
        resp_anon = self.client.get("/api/v1/targets")
        self.assertEqual(resp_anon.status_code, 401)

        # 2. Authenticate as User role
        user_login = self.client.post("/api/v1/auth/login", json={"username": "user", "password": "user123"})
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # User should be able to list targets
        resp_list = self.client.get("/api/v1/targets", headers=user_headers)
        self.assertEqual(resp_list.status_code, 200)

        # User SHOULD be able to create a target successfully
        new_target = {
            "name": "User customer registered target",
            "description": "User mode writes this",
            "target_type": "mock",
            "system_prompt": "some prompt",
            "secret_token": "token",
            "headers": "{}",
            "use_llm": False
        }
        resp_post_user = self.client.post("/api/v1/targets", json=new_target, headers=user_headers)
        self.assertEqual(resp_post_user.status_code, 200)
        target_id = resp_post_user.json()["id"]

        # User should NOT be able to delete the target (403 Forbidden)
        resp_del_user = self.client.delete(f"/api/v1/targets/{target_id}", headers=user_headers)
        self.assertEqual(resp_del_user.status_code, 403)
        self.assertIn("Special administration privileges required", resp_del_user.json()["detail"])

        # 3. Authenticate as Admin role
        admin_login = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Admin SHOULD be able to delete the target successfully
        resp_del_admin = self.client.delete(f"/api/v1/targets/{target_id}", headers=admin_headers)
        self.assertEqual(resp_del_admin.status_code, 200)

    def test_user_deletion_and_listing(self):
        """Test listing users and deleting users with role policies."""
        # 1. Login as admin
        admin_login = self.client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Login as user
        user_login = self.client.post("/api/v1/auth/login", json={"username": "user", "password": "user123"})
        user_token = user_login.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 3. List users as Admin (should succeed)
        list_resp = self.client.get("/api/v1/auth/users", headers=admin_headers)
        self.assertEqual(list_resp.status_code, 200)
        users = list_resp.json()
        self.assertTrue(any(u["username"] == "admin" for u in users))
        self.assertTrue(any(u["username"] == "user" for u in users))

        # 4. List users as User (should get 403 Forbidden)
        list_resp_user = self.client.get("/api/v1/auth/users", headers=user_headers)
        self.assertEqual(list_resp_user.status_code, 403)

        # 5. Create a new user for deletion test
        reg_payload = {"username": "deleteme", "password": "password123"}
        reg_resp = self.client.post("/api/v1/auth/register", json=reg_payload)
        self.assertEqual(reg_resp.status_code, 201)

        # 6. Try to delete 'deleteme' user as 'user' (should get 403 Forbidden)
        del_resp_unauth = self.client.delete("/api/v1/auth/users/deleteme", headers=user_headers)
        self.assertEqual(del_resp_unauth.status_code, 403)

        # 7. Try to delete 'admin' user as admin (should get 400 Bad Request)
        del_resp_admin = self.client.delete("/api/v1/auth/users/admin", headers=admin_headers)
        self.assertEqual(del_resp_admin.status_code, 400)

        # 8. Delete 'deleteme' user as admin (should succeed)
        del_resp_success = self.client.delete("/api/v1/auth/users/deleteme", headers=admin_headers)
        self.assertEqual(del_resp_success.status_code, 200)

        # 9. Try to delete self-deletion for a normal user
        self_payload = {"username": "selfdelete", "password": "password123"}
        self.client.post("/api/v1/auth/register", json=self_payload)
        sd_login = self.client.post("/api/v1/auth/login", json={"username": "selfdelete", "password": "password123"})
        sd_token = sd_login.json()["access_token"]
        sd_headers = {"Authorization": f"Bearer {sd_token}"}
        del_self = self.client.delete("/api/v1/auth/users/selfdelete", headers=sd_headers)
        self.assertEqual(del_self.status_code, 200)

if __name__ == "__main__":
    unittest.main()
