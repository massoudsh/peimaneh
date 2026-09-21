import datetime
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app
from app.negotiation.state_machine import NegotiationStage


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)

        def database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = database
        self.client = TestClient(app)
        response = self.client.post("/contacts", json={"name": "Test buyer"})
        self.assertEqual(response.status_code, 200)
        self.contact = response.json()["id"]
        response = self.client.post("/threads", json={"contact_id": self.contact})
        self.assertEqual(response.status_code, 200)
        self.thread = response.json()["id"]
        self.path = f"/threads/{self.thread}"
        self.due = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def schedule(self, due=None):
        return self.client.put(self.path + "/follow-up", json={"due_at": (due or self.due).isoformat()})

    def test_schedule_reschedule_and_audit(self):
        self.assertEqual(self.schedule().status_code, 200)
        later = self.due + datetime.timedelta(days=1)
        response = self.schedule(later)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(datetime.datetime.fromisoformat(response.json()["next_follow_up_at"]), later)
        events = self.client.get(self.path + "/audit").json()
        self.assertEqual([event["action"] for event in events], ["follow_up_scheduled"] * 2)

    def test_schedule_requires_future_timezone_aware_date(self):
        for value in ["2020-01-01T12:00:00Z", "2099-01-01T12:00:00", "invalid", None]:
            with self.subTest(value=value):
                response = self.client.put(self.path + "/follow-up", json={"due_at": value})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(self.path + "/audit").json(), [])

    def test_timezone_normalization(self):
        due = self.due.astimezone(datetime.timezone(datetime.timedelta(hours=3, minutes=30)))
        response = self.schedule(due)
        value = datetime.datetime.fromisoformat(response.json()["next_follow_up_at"])
        self.assertEqual(value.utcoffset(), datetime.timedelta())
        self.assertEqual(value, due)

    def test_complete_clears_reminder_and_records_time(self):
        self.schedule()
        response = self.client.post(self.path + "/follow-up/complete")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["next_follow_up_at"])
        self.assertIsNotNone(response.json()["last_follow_up_at"])
        self.assertEqual(self.client.post(self.path + "/follow-up/complete").status_code, 409)
        self.assertEqual(self.client.get(self.path + "/audit").json()[-1]["action"], "follow_up_completed")

    def test_cancel_is_idempotent(self):
        self.schedule()
        for _ in range(2):
            response = self.client.delete(self.path + "/follow-up")
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["next_follow_up_at"])
        self.assertEqual(len(self.client.get(self.path + "/audit").json()), 2)

    def test_contact_reply_cancels_reminder(self):
        self.schedule()
        response = self.client.post(self.path + "/messages", json={"sender": "contact", "text": "Thank you"})
        self.assertEqual(response.json()["status"], "received")
        self.assertIsNone(self.client.get(self.path).json()["next_follow_up_at"])
        event = self.client.get(self.path + "/audit").json()[-1]
        self.assertEqual(event["detail"], {"reason": "contact_replied"})

    def test_draft_requires_approval_and_preserves_reminder(self):
        self.schedule()
        response = self.client.post(self.path + "/messages", json={"sender": "agent_draft", "text": "Draft"})
        self.assertEqual(response.json()["status"], "needs_approval")
        self.assertIsNotNone(self.client.get(self.path).json()["next_follow_up_at"])

    def test_human_message_status_and_blank_validation(self):
        response = self.client.post(self.path + "/messages", json={"sender": "human", "text": "Sent manually"})
        self.assertEqual(response.json()["status"], "sent")
        for text in ["", "   ", "x" * 50001]:
            self.assertEqual(self.client.post(self.path + "/messages", json={"sender": "human", "text": text}).status_code, 422)

    def test_due_list_and_open_filters(self):
        self.schedule()
        self.assertEqual(self.client.get("/threads?due_only=true").json(), [])
        with patch("app.models._now", return_value=self.due + datetime.timedelta(seconds=1)):
            response = self.client.get("/threads?due_only=true")
        self.assertEqual([item["id"] for item in response.json()], [self.thread])
        with Session(self.engine) as session:
            session.get(models.Thread, self.thread).stage = NegotiationStage.CONFIRMATION
            session.commit()
        with patch("app.models._now", return_value=self.due + datetime.timedelta(seconds=1)):
            self.assertEqual(self.client.get("/threads?due_only=true").json(), [])
        self.assertEqual(self.client.get("/threads?open_only=true").json(), [])
        self.assertEqual(len(self.client.get("/threads").json()), 1)
        self.assertEqual(self.schedule().status_code, 409)

    def test_filters_pagination_and_bounds(self):
        self.client.post("/threads", json={"contact_id": self.contact})
        first = self.client.get("/threads?limit=1").json()
        second = self.client.get("/threads?limit=1&offset=1").json()
        self.assertNotEqual(first[0]["id"], second[0]["id"])
        self.assertEqual(self.client.get("/threads?stage=quote").json(), [])
        self.assertEqual(self.client.get("/threads?contact_id=unknown").json(), [])
        for query in ["limit=0", "limit=201", "offset=-1", "stage=invalid"]:
            self.assertEqual(self.client.get("/threads?" + query).status_code, 422)

    def test_transition_audit_and_invalid_transition(self):
        self.assertEqual(self.client.post(self.path + "/transition?target_stage=confirmation").status_code, 400)
        self.assertEqual(self.client.get(self.path + "/audit").json(), [])
        self.assertEqual(self.client.post(self.path + "/transition?target_stage=quote").status_code, 200)
        event = self.client.get(self.path + "/audit").json()[0]
        self.assertEqual(event["detail"], {"from": "inquiry", "to": "quote"})

    def test_confirmation_clears_follow_up(self):
        self.schedule()
        with Session(self.engine) as session:
            session.get(models.Thread, self.thread).stage = NegotiationStage.PROFORMA
            session.commit()
        response = self.client.post(self.path + "/transition?target_stage=confirmation")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["next_follow_up_at"])

    def test_missing_threads(self):
        for method, path, data in [
            ("put", "/follow-up", {"due_at": self.due.isoformat()}),
            ("delete", "/follow-up", None),
            ("post", "/follow-up/complete", None),
            ("get", "/audit", None),
        ]:
            response = self.client.request(method, "/threads/missing" + path, json=data)
            self.assertEqual(response.status_code, 404)

    def test_audit_is_thread_scoped(self):
        self.schedule()
        other = self.client.post("/threads", json={"contact_id": self.contact}).json()["id"]
        self.assertEqual(self.client.get(f"/threads/{other}/audit").json(), [])
        with Session(self.engine) as session:
            self.assertEqual(len(session.scalars(select(models.AuditLog)).all()), 1)


if __name__ == "__main__":
    unittest.main()
