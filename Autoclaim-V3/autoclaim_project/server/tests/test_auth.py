"""
Unit + Integration tests for Authentication API endpoints.

Covers:
  TC-01  Register with valid details
  TC-02  Duplicate email registration
  TC-03  Short password validation
  TC-04  Login with valid credentials
  TC-05  Login with invalid password
  TC-06  /me returns correct profile
  TC-07  Protected endpoint without token → 401
  TC-08  Update profile (name, vehicle_number)
  TC-09  Admin registers an agent
  TC-10  Non-admin cannot register an agent
"""

import pytest


# =========================================================================== #
# Registration                                                                 #
# =========================================================================== #

class TestRegistration:

    def test_register_valid_user(self, client, unlinked_policy):
        """TC-01: Register with a valid policy returns 200 and links vehicle details."""
        resp = client.post("/register", json={
            "email": "newuser@example.com",
            "password": "secure123",
            "username": "New User",
            "policy_number": str(unlinked_policy.id),
        })
        assert resp.status_code == 200
        assert resp.json()["message"] == "User created successfully"

    def test_register_invalid_policy_number(self, client):
        """TC-11: Register with a non-existent policy number returns 400."""
        resp = client.post("/register", json={
            "email": "badpolicy@example.com",
            "password": "secure123",
            "username": "Bad Policy User",
            "policy_number": "999999",
        })
        assert resp.status_code == 400
        assert "no such policy" in resp.json()["detail"].lower()

    def test_register_links_vehicle_from_policy(self, client, db, unlinked_policy):
        """TC-12: After registration, user's vehicle_number matches policy's vehicle_registration."""
        from app.db import models

        client.post("/register", json={
            "email": "vcheck@example.com",
            "password": "secure123",
            "username": "Vehicle Check",
            "policy_number": str(unlinked_policy.id),
        })
        user = db.query(models.User).filter(
            models.User.email == "vcheck@example.com"
        ).first()
        assert user is not None
        assert user.vehicle_number == unlinked_policy.vehicle_registration
        assert user.policy_id == str(unlinked_policy.id)

    def test_register_duplicate_policy_rejected(self, client, db, unlinked_policy):
        """TC-13: Registering with an already-claimed policy returns 400."""
        # First registration claims the policy
        client.post("/register", json={
            "email": "first@example.com",
            "password": "secure123",
            "username": "First User",
            "policy_number": str(unlinked_policy.id),
        })
        # Second registration with same policy should fail
        resp = client.post("/register", json={
            "email": "second@example.com",
            "password": "secure123",
            "username": "Second User",
            "policy_number": str(unlinked_policy.id),
        })
        assert resp.status_code == 400
        assert "already linked" in resp.json()["detail"].lower()

    def test_register_missing_policy_number(self, client):
        """Register without a policy number returns 400."""
        resp = client.post("/register", json={
            "email": "nopolicy@example.com",
            "password": "secure123",
            "username": "No Policy",
        })
        assert resp.status_code == 400
        assert "required" in resp.json()["detail"].lower()

    def test_register_duplicate_email(self, client, regular_user):
        """TC-02: Registering with an already-used email returns 400."""
        resp = client.post("/register", json={
            "email": "user@test.com",  # same as regular_user fixture
            "password": "anotherpass",
            "username": "Clone",
        })
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_register_short_password(self, client):
        """TC-03: Password < 6 chars returns 422 validation error."""
        resp = client.post("/register", json={
            "email": "short@example.com",
            "password": "abc",
            "username": "Short Pass",
        })
        assert resp.status_code == 422

    def test_register_invalid_email_format(self, client):
        """Email format validation returns 422."""
        resp = client.post("/register", json={
            "email": "not-an-email",
            "password": "valid123",
            "username": "Bad Email",
        })
        assert resp.status_code == 422

    def test_register_creates_user_role(self, client, db, unlinked_policy):
        """Public registration always creates role='user' (never admin/agent)."""
        from app.db import models

        client.post("/register", json={
            "email": "rolecheck@example.com",
            "password": "rolepass1",
            "username": "Role Check",
            "policy_number": str(unlinked_policy.id),
        })
        user = db.query(models.User).filter(
            models.User.email == "rolecheck@example.com"
        ).first()
        assert user is not None
        assert user.role == "user"

    def test_register_password_is_hashed(self, client, db, unlinked_policy):
        """Password must not be stored in plain text."""
        from app.db import models

        client.post("/register", json={
            "email": "hashtest@example.com",
            "password": "plaintextpass",
            "username": "Hash Test",
            "policy_number": str(unlinked_policy.id),
        })
        user = db.query(models.User).filter(
            models.User.email == "hashtest@example.com"
        ).first()
        assert user is not None
        assert user.hashed_password != "plaintextpass"
        assert len(user.hashed_password) > 20  # bcrypt hashes are long


# =========================================================================== #
# Login                                                                        #
# =========================================================================== #

class TestLogin:

    def test_login_valid_credentials(self, client, regular_user):
        """TC-04: Login returns access_token and role."""
        resp = client.post("/login", data={
            "username": "user@test.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "user"

    def test_login_wrong_password(self, client, regular_user):
        """TC-05: Wrong password returns 401."""
        resp = client.post("/login", data={
            "username": "user@test.com",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Login with an email that was never registered returns 401."""
        resp = client.post("/login", data={
            "username": "ghost@example.com",
            "password": "doesnotmatter",
        })
        assert resp.status_code == 401

    def test_login_returns_correct_role_for_agent(self, client, agent_user):
        """Login as agent returns role='agent'."""
        resp = client.post("/login", data={
            "username": "agent@test.com",
            "password": "agentpass",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "agent"

    def test_login_returns_correct_role_for_admin(self, client, admin_user):
        """Login as admin returns role='admin'."""
        resp = client.post("/login", data={
            "username": "admin@test.com",
            "password": "adminpass",
        })
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"


# =========================================================================== #
# Profile (/me)                                                                #
# =========================================================================== #

class TestProfile:

    def test_get_me_with_valid_token(self, client, regular_user, user_token):
        """TC-06: /me returns correct user profile."""
        resp = client.get("/me", headers=user_token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@test.com"
        assert data["role"] == "user"
        assert data["name"] == "Regular User"
        assert data["vehicle_number"] == "KL01AB1234"

    def test_get_me_without_token(self, client):
        """TC-07: Accessing /me without a token returns 401."""
        resp = client.get("/me")
        assert resp.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        """TC-07: Tampered/invalid JWT returns 401."""
        resp = client.get("/me", headers={"Authorization": "Bearer invalidtoken.abc.def"})
        assert resp.status_code == 401

    def test_update_profile_name(self, client, regular_user, user_token):
        """TC-08: Update name succeeds and is reflected in /me."""
        resp = client.put("/me", json={"name": "Updated Name"}, headers=user_token)
        assert resp.status_code == 200
        me = client.get("/me", headers=user_token).json()
        assert me["name"] == "Updated Name"

    def test_update_profile_vehicle_number(self, client, regular_user, user_token):
        """TC-08: Update vehicle_number succeeds."""
        resp = client.put("/me", json={"vehicle_number": "KL99ZZ9999"}, headers=user_token)
        assert resp.status_code == 200
        me = client.get("/me", headers=user_token).json()
        assert me["vehicle_number"] == "KL99ZZ9999"

    def test_update_profile_blank_name_rejected(self, client, regular_user, user_token):
        """Blank name update must be rejected (validator)."""
        resp = client.put("/me", json={"name": "   "}, headers=user_token)
        assert resp.status_code == 422


# =========================================================================== #
# Admin — Agent Management                                                     #
# =========================================================================== #

class TestAdminAgentManagement:

    def test_admin_registers_agent(self, client, admin_user, admin_token):
        """TC-09: Admin can create an agent account."""
        resp = client.post(
            "/admin/register-agent",
            params={
                "email": "newagent@autoclaim.com",
                "password": "agentsecret",
                "name": "New Agent",
            },
            headers=admin_token,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"]["role"] == "agent"
        assert data["agent"]["email"] == "newagent@autoclaim.com"

    def test_non_admin_cannot_register_agent(self, client, regular_user, user_token):
        """TC-10: Regular user attempt returns 403."""
        resp = client.post(
            "/admin/register-agent",
            params={
                "email": "hacker@autoclaim.com",
                "password": "hack123",
                "name": "Hacker",
            },
            headers=user_token,
        )
        assert resp.status_code == 403

    def test_agent_cannot_register_agent(self, client, agent_user, agent_token):
        """TC-10: Agent role also returns 403."""
        resp = client.post(
            "/admin/register-agent",
            params={
                "email": "another@autoclaim.com",
                "password": "pass123",
                "name": "Another",
            },
            headers=agent_token,
        )
        assert resp.status_code == 403

    def test_admin_list_agents(self, client, admin_user, agent_user, admin_token):
        """TC-34: Admin can list all agents."""
        resp = client.get("/admin/agents", headers=admin_token)
        assert resp.status_code == 200
        emails = [a["email"] for a in resp.json()["agents"]]
        assert "agent@test.com" in emails

    def test_non_admin_cannot_list_agents(self, client, regular_user, user_token):
        """TC-35: Non-admin cannot list agents."""
        resp = client.get("/admin/agents", headers=user_token)
        assert resp.status_code == 403
