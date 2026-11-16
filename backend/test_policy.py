import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.auth import current_user
from app.database import Base, get_db
from app.main import app
from app.policy.engine import OfferInput, evaluate_offer


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)

        def database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[current_user] = lambda: models.User(
            id="m", email="manager@example.com", role=models.UserRole.MANAGER
        )
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def policy(self, **overrides):
        payload = {
            "product_category": "saffron",
            "price_floor": 100.0,
            "max_discount_pct": 5.0,
            "allowed_payment_terms": ["LC", "TT 50%"],
            "sensitive_countries": ["Iran"],
            "sensitive_customers": ["Risky Buyer"],
        }
        payload.update(overrides)
        return self.client.post("/policy", json=payload)

    def test_versioning_and_audit(self):
        first = self.policy()
        second = self.policy(price_floor=120.0)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(second.json()["version"], 2)
        self.assertEqual(self.client.get("/policy/active").json()["price_floor"], 120.0)
        with Session(self.engine) as db:
            versions = db.scalars(select(models.PolicyConfig).order_by(models.PolicyConfig.version)).all()
            self.assertEqual([(item.version, item.is_active) for item in versions], [(1, False), (2, True)])
            audit = db.scalars(select(models.AuditLog)).all()
            self.assertEqual(len(audit), 2)
            self.assertEqual(audit[-1].actor, "manager@example.com")
            self.assertIsNone(audit[-1].thread_id)

    def test_no_active_policy_returns_404(self):
        self.assertEqual(self.client.get("/policy/active").status_code, 404)
        self.assertEqual(
            self.client.post("/policy/evaluate-offer", json={"price": 10, "payment_term": "LC"}).status_code, 404
        )

    def test_evaluation_flags_every_violation(self):
        self.policy()
        response = self.client.post("/policy/evaluate-offer", json={
            "price": 50, "payment_term": "cash", "discount_pct": 9,
            "country": "iran", "customer_name": "risky buyer",
        })
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "needs_human_approval")
        self.assertEqual(len(body["reasons"]), 5)

    def test_evaluation_is_ready_inside_policy(self):
        self.policy()
        response = self.client.post("/policy/evaluate-offer", json={
            "price": 100, "payment_term": "lc", "discount_pct": 5, "country": "UAE",
        })
        self.assertEqual(response.json(), {"status": "ready_to_send", "reasons": []})

    def test_sensitive_contact_forces_approval(self):
        self.policy()
        contact = self.client.post("/contacts", json={"name": "Safe Buyer", "is_sensitive": True}).json()
        response = self.client.post(
            "/policy/evaluate-offer",
            json={"price": 200, "payment_term": "LC", "contact_id": contact["id"]},
        )
        self.assertEqual(response.json()["status"], "needs_human_approval")
        self.assertIn("contact is marked sensitive", response.json()["reasons"])

    def test_input_validation(self):
        self.policy()
        for payload in [
            {"price": 0, "payment_term": "LC"},
            {"price": -1, "payment_term": "LC"},
            {"price": 10, "payment_term": "LC", "discount_pct": 101},
            {"price": 10, "payment_term": ""},
        ]:
            self.assertEqual(self.client.post("/policy/evaluate-offer", json=payload).status_code, 422)
        for payload in [
            {"product_category": "x", "price_floor": 0},
            {"product_category": "", "price_floor": 1},
            {"product_category": "x", "price_floor": 1, "max_discount_pct": 101},
        ]:
            self.assertEqual(self.client.post("/policy", json=payload).status_code, 422)

    def test_engine_missing_payment_terms_fails_closed(self):
        policy = models.PolicyConfig(
            product_category="x", price_floor=10, max_discount_pct=0,
            allowed_payment_terms=None, sensitive_countries=[], sensitive_customers=[],
        )
        decision = evaluate_offer(policy, OfferInput(price=10, payment_term="LC"))
        self.assertEqual(decision.status.value, "needs_human_approval")


if __name__ == "__main__":
    unittest.main()
