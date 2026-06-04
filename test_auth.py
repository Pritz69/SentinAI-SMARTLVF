import unittest
import os
import sqlite3
from fastapi.testclient import TestClient

# Mock environment keys before importing app
os.environ["GROQ_API_KEY"] = "mock_groq_key"
os.environ["GOOGLE_API_KEY"] = "mock_google_key"

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

if __name__ == "__main__":
    unittest.main()
