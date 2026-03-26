"""
Authentication API routes.
Handles user registration, login, and current user info.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from app.db.database import get_db
from app.db import models
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.dependencies import get_current_user

router = APIRouter(tags=["Authentication"])


class RegisterRequest(BaseModel):
    """Registration request body schema."""
    email: EmailStr          # validates email format automatically
    password: str
    username: Optional[str] = None  # Frontend uses 'username' for name
    name: Optional[str] = None
    policy_number: Optional[str] = None
    vehicle_number: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("username", "name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v


@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account (public registration).
    
    This endpoint only allows registration of regular 'user' accounts.
<<<<<<< HEAD
    If a policy_number is provided, it is validated against the policies table,
    ownership is transferred to the new user, and the vehicle registration
    is copied to the user profile.
=======
    Agents must be registered by admins via the admin dashboard.
    The policy_number must correspond to a valid Policy.id in the database.
    
    Args:
        request: Registration data (email, password, name, policy_number)
>>>>>>> b394b5b5980b3d970fd5d97e3aff16de5451db8e
    """
    # Check if user already exists
    existing = db.query(models.User).filter(models.User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # ── Validate policy number ───────────────────────────────────────────
    if not request.policy_number:
        raise HTTPException(status_code=400, detail="Policy number is required")
    try:
        policy_id_int = int(request.policy_number)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid policy number format")
    
<<<<<<< HEAD
    # ── Validate & look up the policy (if provided) ─────────────────────
    policy = None
    vehicle_reg = request.vehicle_number  # fallback to manually entered value
    
    if request.policy_number:
        try:
            pid = int(request.policy_number)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Policy ID must be a number")
        
        policy = db.query(models.Policy).filter(models.Policy.id == pid).first()
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy ID {pid} not found")
        
        # Check the policy isn't already claimed by another regular user
        if policy.user_id:
            owner = db.query(models.User).filter(models.User.id == policy.user_id).first()
            if owner and owner.role == "user":
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy {pid} is already linked to another user"
                )
        
        # Use the vehicle registration from the policy record
        vehicle_reg = policy.vehicle_registration
    
    # ── Create the user ─────────────────────────────────────────────────
=======
    policy = db.query(models.Policy).filter(models.Policy.id == policy_id_int).first()
    if not policy:
        raise HTTPException(
            status_code=400,
            detail="Invalid policy number — no such policy exists"
        )
    
    # Ensure the policy isn't already claimed by another registered user
    existing_owner = db.query(models.User).filter(
        models.User.policy_id == str(policy_id_int)
    ).first()
    if existing_owner:
        raise HTTPException(
            status_code=400,
            detail="This policy is already linked to another user"
        )
    
    # ── Create user ──────────────────────────────────────────────────────
    user_name = request.name or request.username  # frontend compatibility
>>>>>>> b394b5b5980b3d970fd5d97e3aff16de5451db8e
    hashed_pw = get_password_hash(request.password)
    
    new_user = models.User(
        email=request.email, 
        hashed_password=hashed_pw, 
        role="user",
        name=user_name,
<<<<<<< HEAD
        policy_id=str(policy.id) if policy else request.policy_number,
        vehicle_number=vehicle_reg,
=======
        policy_id=str(policy.id),
        vehicle_number=policy.vehicle_registration  # auto-populate from policy
>>>>>>> b394b5b5980b3d970fd5d97e3aff16de5451db8e
    )
    db.add(new_user)
    db.flush()  # get new_user.id before commit
    
    # Link the policy record to this new user
    policy.user_id = new_user.id
    db.commit()
    db.refresh(new_user)
    
    # ── Link policy to the new user ─────────────────────────────────────
    if policy:
        policy.user_id = new_user.id
        db.commit()
        logger.info("Policy %s linked to user %s (%s)", policy.id, new_user.id, new_user.email)
    
    return {"message": "User created successfully"}


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Login and get access token.
    
    Uses OAuth2 password flow - username field contains email.
    """
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={
        "sub": user.email, 
        "role": user.role, 
        "user_id": user.id
    })
    
    return {
        "access_token": token, 
        "token_type": "bearer", 
        "role": user.role
    }


@router.get("/me")
def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current logged-in user info including profile fields."""
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "vehicle_number": user.vehicle_number,
        "policy_id": user.policy_id,
        "created_at": user.created_at.isoformat(),
    }


class UpdateProfileRequest(BaseModel):
    """Profile update request body."""
    name: Optional[str] = None
    vehicle_number: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                raise ValueError("Name cannot be blank")
        return v

    @field_validator("vehicle_number", mode="before")
    @classmethod
    def strip_vehicle(cls, v):
        return v.strip() if isinstance(v, str) else v


@router.put("/me")
def update_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's name and vehicle number."""
    user = db.query(models.User).filter(models.User.email == current_user["email"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if request.name is not None:
        user.name = request.name
    if request.vehicle_number is not None:
        user.vehicle_number = request.vehicle_number
    db.commit()
    return {"message": "Profile updated successfully"}


@router.post("/admin/register-agent")
def register_agent(
    email: str = Query(..., description="Agent email address"),
    password: str = Query(..., description="Agent password"),
    name: str = Query(..., description="Agent full name"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new agent account (admin only).
    
    Only administrators can create agent accounts.
    Agents have elevated permissions compared to regular users.
    
    Args:
        email: Agent email address
        password: Plain text password (will be hashed)
        name: Agent's full name
        current_user: Current authenticated user (must be admin)
        db: Database session
    """
    # Verify admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can register agents"
        )
    
    # Check if email already exists
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create agent account
    hashed_pw = get_password_hash(password)
    new_agent = models.User(
        email=email,
        hashed_password=hashed_pw,
        role="agent",
        name=name
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    # Log that the new agent has joined the auto-assignment rotation
    agent_count = db.query(models.User).filter(
        models.User.role == "agent", models.User.is_active == True
    ).count()
    logger.info(
        "[AutoAssign] Agent '%s' joined rotation pool (pool size: %s)",
        new_agent.name or new_agent.email, agent_count
    )
    print(f"[AutoAssign] Agent '{new_agent.name or new_agent.email}' joined rotation (pool size: {agent_count})")

    return {
        "message": "Agent created successfully",
        "agent": {
            "id": new_agent.id,
            "email": new_agent.email,
            "name": new_agent.name,
            "role": new_agent.role,
            "created_at": new_agent.created_at.isoformat()
        }
    }


@router.get("/admin/agents")
def get_all_agents(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all agent accounts (admin only).
    
    Returns a list of all users with the 'agent' role.
    
    Args:
        current_user: Current authenticated user (must be admin)
        db: Database session
    """
    # Verify admin role
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view agents"
        )
    
    # Get all agents
    agents = db.query(models.User).filter(models.User.role == "agent").all()
    
    return {
        "agents": [
            {
                "id": agent.id,
                "email": agent.email,
                "name": agent.name,
                "role": agent.role,
                "created_at": agent.created_at.isoformat()
            }
            for agent in agents
        ]
    }
