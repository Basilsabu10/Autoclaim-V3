"""
API tests for the Notifications endpoints.

TC-36: Notifications appear in user's list
TC-37: Mark notification as read
TC-38: Fetch only unread notifications via unread_count
TC-    : Another user cannot mark someone else's notification
"""

import pytest
from app.db import models


def _seed_notification(db, user, message="Test notification", is_read=False, claim_id=None):
    notif = models.Notification(
        user_id=user.id,
        message=message,
        claim_id=claim_id,
        is_read=is_read,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


class TestGetNotifications:

    def test_empty_notifications_returns_empty_list(self, client, regular_user, user_token):
        """New user has no notifications."""
        resp = client.get("/notifications/my", headers=user_token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["notifications"] == []
        assert data["unread_count"] == 0

    def test_notifications_returned_for_user(self, client, regular_user, user_token, db):
        """TC-36: Notification appears in list after being created."""
        _seed_notification(db, regular_user, "Claim submitted successfully")
        resp = client.get("/notifications/my", headers=user_token)
        assert resp.status_code == 200
        notifications = resp.json()["notifications"]
        assert len(notifications) == 1
        assert "submitted" in notifications[0]["message"].lower()

    def test_unread_count_is_accurate(self, client, regular_user, user_token, db):
        """TC-38: unread_count matches actual unread notifications."""
        _seed_notification(db, regular_user, "Unread 1", is_read=False)
        _seed_notification(db, regular_user, "Unread 2", is_read=False)
        _seed_notification(db, regular_user, "Already read", is_read=True)
        resp = client.get("/notifications/my", headers=user_token)
        assert resp.json()["unread_count"] == 2

    def test_notifications_without_auth_returns_401(self, client):
        resp = client.get("/notifications/my")
        assert resp.status_code == 401

    def test_notifications_are_user_specific(
        self, client, regular_user, agent_user, user_token, agent_token, db
    ):
        """A user can only see their own notifications."""
        _seed_notification(db, agent_user, "Agent notification")
        resp = client.get("/notifications/my", headers=user_token)
        for n in resp.json()["notifications"]:
            assert n["message"] != "Agent notification"


class TestMarkNotificationRead:

    def test_mark_single_notification_as_read(self, client, regular_user, user_token, db):
        """TC-37: PATCH /notifications/{id}/read sets is_read=True."""
        notif = _seed_notification(db, regular_user, "Unread notification")
        resp = client.patch(f"/notifications/{notif.id}/read", headers=user_token)
        assert resp.status_code == 200

        # Verify in list
        list_resp = client.get("/notifications/my", headers=user_token)
        notifications = list_resp.json()["notifications"]
        updated = next(n for n in notifications if n["id"] == notif.id)
        assert updated["is_read"] is True

    def test_mark_read_nonexistent_notification_returns_404(self, client, regular_user, user_token):
        resp = client.patch("/notifications/99999/read", headers=user_token)
        assert resp.status_code == 404

    def test_cannot_mark_other_users_notification(
        self, client, regular_user, agent_user, user_token, db
    ):
        """Security: cannot mark another user's notification as read."""
        notif = _seed_notification(db, agent_user, "Agent notif")
        resp = client.patch(f"/notifications/{notif.id}/read", headers=user_token)
        assert resp.status_code == 404  # Not found (scoped to user)


class TestMarkAllRead:

    def test_mark_all_as_read(self, client, regular_user, user_token, db):
        """POST /notifications/read-all marks all as read."""
        _seed_notification(db, regular_user, "A", is_read=False)
        _seed_notification(db, regular_user, "B", is_read=False)
        resp = client.post("/notifications/read-all", headers=user_token)
        assert resp.status_code == 200

        list_resp = client.get("/notifications/my", headers=user_token)
        assert list_resp.json()["unread_count"] == 0
