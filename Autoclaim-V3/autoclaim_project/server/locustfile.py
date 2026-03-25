"""
Locust load test for AutoClaim-V3 API.

Simulates realistic user behaviour:
  - Login (on startup)
  - View claim list (high frequency)
  - View notifications (medium frequency)
  - Check wallet balance (low frequency)

Usage:
  pip install locust
  cd server
  locust -f locustfile.py --host http://localhost:8000

Then open http://localhost:8089 to configure users & spawn rate.

For headless CI runs:
  locust -f locustfile.py --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 60s --headless
"""

from locust import HttpUser, task, between
import random

# ── Seed accounts (create these before running the load test) ─────────────
LOAD_TEST_USERS = [
    {"email": f"loadtest{i}@autoclaim.com", "password": "loadtest123"}
    for i in range(1, 6)
]


class AutoClaimUser(HttpUser):
    """Simulates a logged-in AutoClaim user browsing their claims."""

    # Each simulated user waits 1–3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Login once at the beginning of each simulated user session."""
        creds = random.choice(LOAD_TEST_USERS)
        resp = self.client.post(
            "/login",
            data={"username": creds["email"], "password": creds["password"]},
            name="/login",
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            # If login fails (seed accounts not created), use empty headers
            self.headers = {}

    # ── Tasks ─────────────────────────────────────────────────────────────

    @task(5)
    def view_claims(self):
        """Most frequent: view own claim list."""
        self.client.get("/claims", headers=self.headers, name="/claims [list]")

    @task(3)
    def view_notifications(self):
        """Medium frequency: poll notifications."""
        self.client.get(
            "/notifications/my", headers=self.headers, name="/notifications/my"
        )

    @task(2)
    def view_wallet(self):
        """Lower frequency: check wallet balance."""
        self.client.get("/wallet/me", headers=self.headers, name="/wallet/me")

    @task(1)
    def view_profile(self):
        """Occasional: fetch profile."""
        self.client.get("/me", headers=self.headers, name="/me")


class AutoClaimAgentUser(HttpUser):
    """Simulates an insurance agent reviewing assigned claims."""

    wait_time = between(2, 5)

    def on_start(self):
        resp = self.client.post(
            "/login",
            data={"username": "agent1@autoclaim.com", "password": "agentpass123"},
            name="/login [agent]",
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    @task(4)
    def view_all_claims(self):
        """Agent views all claims (filtered to assigned)."""
        self.client.get("/claims", headers=self.headers, name="/claims [agent]")

    @task(1)
    def view_notifications(self):
        self.client.get(
            "/notifications/my", headers=self.headers, name="/notifications/my [agent]"
        )
