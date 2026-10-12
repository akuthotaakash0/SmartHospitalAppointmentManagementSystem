import os
import tempfile
import unittest
import pandas as pd
import app as app_module


class RegistrationRouteTest(unittest.TestCase):
    def test_register_works_when_cwd_changes(self):
        original_cwd = os.getcwd()
        temp_dir = tempfile.mkdtemp(prefix="hospital-test-", dir=os.getcwd())

        try:
            # Ensure test user is not present before running
            if os.path.exists(app_module.USERS_FILE):
                users = pd.read_csv(app_module.USERS_FILE)
                if not users.empty and "test@example.com" in users["email"].values:
                    users = users[users["email"] != "test@example.com"]
                    users.to_csv(app_module.USERS_FILE, index=False)

            os.chdir(temp_dir)
            client = app_module.app.test_client()

            response = client.post(
                "/register",
                data={"name": "Test User", "email": "test@example.com", "password": "secret123"},
                follow_redirects=True,
            )

            self.assertEqual(response.status_code, 200)
            self.assertIn("User Login", response.get_data(as_text=True))

            users = pd.read_csv(app_module.USERS_FILE)
            self.assertIn("test@example.com", users["email"].tolist())
        finally:
            os.chdir(original_cwd)
            # Clean up test user
            if os.path.exists(app_module.USERS_FILE):
                users = pd.read_csv(app_module.USERS_FILE)
                if not users.empty and "test@example.com" in users["email"].values:
                    users = users[users["email"] != "test@example.com"]
                    users.to_csv(app_module.USERS_FILE, index=False)
            try:
                os.rmdir(temp_dir)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
