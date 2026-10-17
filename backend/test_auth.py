import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)

        def database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def test_first_registration_is_manager_and_duplicate_is_rejected(self):
        payload = {"email": "OWNER@EXAMPLE.COM", "password": "correct horse battery staple"}
        response = self.client.post("/auth/register", json={**payload, "role": "manager"})
        self.assertEqual(response.status_code, 201)
        token = response.json()["access_token"]
        me = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.json()["email"], "owner@example.com")
        self.assertEqual(me.json()["role"], "manager")
        self.assertEqual(self.client.post("/auth/register", json={**payload, "role": "manager"}).status_code, 409)

    def test_later_registration_cannot_escalate_to_manager(self):
        self.client.post("/auth/register", json={"email": "owner@example.com", "password": "correct horse battery staple", "role": "manager"})
        self.assertEqual(self.client.post("/auth/register", json={"email": "sales@example.com", "password": "correct horse battery staple", "role": "manager"}).status_code, 403)
        response = self.client.post("/auth/register", json={"email": "sales@example.com", "password": "correct horse battery staple", "role": "sales"})
        self.assertEqual(response.status_code, 201)

    def test_invalid_login_and_protected_routes(self):
        self.assertEqual(self.client.get("/contacts").status_code, 401)
        self.client.post("/auth/register", json={"email": "owner@example.com", "password": "correct horse battery staple", "role": "manager"})
        self.assertEqual(self.client.post("/auth/login", json={"email": "owner@example.com", "password": "wrong password"}).status_code, 401)
        response = self.client.post("/auth/login", json={"email": "owner@example.com", "password": "correct horse battery staple"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/contacts", headers={"Authorization": "Bearer invalid"}).status_code, 401)

    def test_sales_cannot_manage_policy(self):
        self.client.post("/auth/register", json={"email": "owner@example.com", "password": "correct horse battery staple", "role": "manager"})
        response = self.client.post("/auth/register", json={"email": "sales@example.com", "password": "correct horse battery staple", "role": "sales"})
        token = response.json()["access_token"]
        policy = {"product_category": "saffron", "price_floor": 100, "allowed_payment_terms": ["TT"]}
        self.assertEqual(self.client.post("/policy", json=policy, headers={"Authorization": f"Bearer {token}"}).status_code, 403)

    def test_password_never_stored_in_plaintext(self):
        self.client.post("/auth/register", json={"email": "owner@example.com", "password": "correct horse battery staple", "role": "manager"})
        with Session(self.engine) as db:
            user = db.query(models.User).one()
            self.assertNotEqual(user.password_hash, "correct horse battery staple")
            self.assertIn("$", user.password_hash)


if __name__ == "__main__":
    unittest.main()
