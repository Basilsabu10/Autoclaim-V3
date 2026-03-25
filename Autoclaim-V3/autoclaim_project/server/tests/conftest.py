"""
Pytest configuration and shared fixtures for AutoClaim-V3 tests.
Uses an in-memory SQLite database so tests never touch the real DB.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import get_db
from app.db import models
from app.core.security import get_password_hash

# --------------------------------------------------------------------------- #
#  In-memory SQLite engine                                                     #
# --------------------------------------------------------------------------- #

TEST_DB_URL = "sqlite:///./test_autoclaim.db"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once before any tests run."""
    models.Base.metadata.create_all(bind=engine)
    yield
    models.Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Yield a fresh database session; rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db):
    """TestClient with the real-DB session swapped for the test session."""
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
#  Reusable user factories                                                     #
# --------------------------------------------------------------------------- #

def _create_user(db, email, password, role="user", name="Test User",
                 policy_id=None, vehicle_number=None):
    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        role=role,
        name=name,
        policy_id=policy_id,
        vehicle_number=vehicle_number,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, email, password):
    resp = client.post("/login", data={"username": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


def _auth_headers(client, email, password):
    token = _login(client, email, password)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
#  Convenience fixtures                                                        #
# --------------------------------------------------------------------------- #

@pytest.fixture()
def regular_user(db):
    return _create_user(db, "user@test.com", "password123", role="user",
                        name="Regular User", policy_id="POL001",
                        vehicle_number="KL01AB1234")


@pytest.fixture()
def agent_user(db):
    return _create_user(db, "agent@test.com", "agentpass", role="agent",
                        name="Agent Smith")


@pytest.fixture()
def admin_user(db):
    return _create_user(db, "admin@test.com", "adminpass", role="admin",
                        name="Admin User")


@pytest.fixture()
def user_token(client, regular_user):
    return _auth_headers(client, "user@test.com", "password123")


@pytest.fixture()
def agent_token(client, agent_user):
    return _auth_headers(client, "agent@test.com", "agentpass")


@pytest.fixture()
def admin_token(client, admin_user):
    return _auth_headers(client, "admin@test.com", "adminpass")


# --------------------------------------------------------------------------- #
#  Policy fixtures                                                             #
# --------------------------------------------------------------------------- #

@pytest.fixture()
def policy_plan(db):
    """Create a sample policy plan for testing."""
    from datetime import datetime
    plan = models.PolicyPlan(
        name="Standard Coverage",
        description="Standard coverage plan",
        coverage_amount=500000,
        premium_monthly=1500,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@pytest.fixture()
def unlinked_policy(db, policy_plan):
    """Create a policy that is NOT yet linked to any registered user."""
    from datetime import datetime
    # Use user_id=0 as a placeholder (no real user)
    policy = models.Policy(
        user_id=0,
        plan_id=policy_plan.id,
        vehicle_make="Maruti",
        vehicle_model="Baleno",
        vehicle_year=2020,
        vehicle_registration="KL-07-XY-9999",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 1, 1),
        status="active",
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy
