import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app

PASSWORD = "correct horse battery staple"


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)

        def database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"ALLOW_BOOTSTRAP_REGISTRATION": "true"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def bootstrap(self, email="owner@example.com"):
        return self.client.post("/auth/bootstrap", json={"email": email, "password": PASSWORD})

    def login(self, email="owner@example.com", password=PASSWORD):
        return self.client.post("/auth/login", json={"email": email, "password": password})

    def test_bootstrap_disabled_by_default(self):
        with patch.dict(os.environ, {"ALLOW_BOOTSTRAP_REGISTRATION": "false"}):
            self.assertEqual(self.bootstrap().status_code, 404)

    def test_bootstrap_creates_manager_and_refuses_second_owner(self):
        response = self.bootstrap()
        self.assertEqual(response.status_code, 201)
        token = response.json()["access_token"]
        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.json()["email"], "owner@example.com")
        self.assertEqual(me.json()["role"], "manager")
        self.assertEqual(self.bootstrap("other@example.com").status_code, 409)

    def test_login_and_logout_revoke_session(self):
        self.bootstrap()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        self.assertEqual(self.client.get("/contacts", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/auth/logout", headers=headers).status_code, 204)
        self.assertEqual(self.client.get("/contacts", headers=headers).status_code, 401)

    def test_logout_all_revokes_every_session(self):
        self.bootstrap()
        first = self.login().json()["access_token"]
        second = self.login().json()["access_token"]
        self.assertEqual(
            self.client.post("/auth/logout-all", headers={"Authorization": f"Bearer {first}"}).status_code, 204
        )
        for token in (first, second):
            self.assertEqual(
                self.client.get("/contacts", headers={"Authorization": f"Bearer {token}"}).status_code, 401
            )

    def test_failed_logins_lock_account(self):
        self.bootstrap()
        for _ in range(5):
            self.assertEqual(self.login(password="wrong password").status_code, 401)
        self.assertEqual(self.login().status_code, 423)

    def test_manager_can_create_and_disable_sales_user(self):
        owner = self.bootstrap().json()["access_token"]
        headers = {"Authorization": f"Bearer {owner}"}
        response = self.client.post(
            "/auth/users", json={"email": "sales@example.com", "password": PASSWORD, "role": "sales"}, headers=headers
        )
        self.assertEqual(response.status_code, 201)
        user_id = response.json()["id"]
        sales_token = self.login("sales@example.com").json()["access_token"]
        self.assertEqual(
            self.client.get("/auth/users", headers={"Authorization": f"Bearer {sales_token}"}).status_code, 403
        )
        self.assertEqual(
            self.client.patch(f"/auth/users/{user_id}", json={"is_active": False}, headers=headers).status_code, 200
        )
        self.assertEqual(
            self.client.get("/contacts", headers={"Authorization": f"Bearer {sales_token}"}).status_code, 401
        )

    def test_invalid_input_and_protected_routes(self):
        self.assertEqual(self.client.get("/contacts").status_code, 401)
        self.assertEqual(self.client.get("/contacts", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        self.bootstrap()
        self.assertEqual(self.login(password="wrong password").status_code, 401)
        self.assertEqual(
            self.client.post("/auth/bootstrap", json={"email": "not-an-email", "password": PASSWORD}).status_code, 422
        )
        self.assertEqual(
            self.client.post("/auth/bootstrap", json={"email": "a@b.co", "password": "short"}).status_code, 422
        )

    def test_password_never_stored_in_plaintext(self):
        self.bootstrap()
        with Session(self.engine) as db:
            user = db.query(models.User).one()
            self.assertNotEqual(user.password_hash, PASSWORD)
            self.assertIn("$", user.password_hash)


if __name__ == "__main__":
    unittest.main()
