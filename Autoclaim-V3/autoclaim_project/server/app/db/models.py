"""
Database models for the AutoClaim system.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    """User accounts for the insurance system."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user")  # user, admin, agent
    is_active = Column(Boolean, default=True)  # False = deactivated; skipped by auto-assign
    created_at = Column(DateTime, default=datetime.utcnow)

    # User profile fields
    name = Column(String, nullable=True)
    policy_id = Column(String, nullable=True)
    vehicle_number = Column(String, nullable=True)

    # Relationships
    claims = relationship("Claim", back_populates="user", foreign_keys="Claim.user_id")
    policies = relationship("Policy", back_populates="user")
    wallet = relationship("Wallet", back_populates="user", uselist=False)


class PolicyPlan(Base):
    """Insurance policy plans/templates."""
    __tablename__ = "policy_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    coverage_amount = Column(Integer, nullable=False)
    premium_monthly = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    policies = relationship("Policy", back_populates="plan")


class Policy(Base):
    """Active insurance policies for users."""
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    plan_id = Column(Integer, ForeignKey("policy_plans.id"), index=True, nullable=False)

    # Vehicle details
    vehicle_make = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_year = Column(Integer, nullable=True)
    vehicle_registration = Column(String, index=True, nullable=True)  # License plate
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    status = Column(String, default="active")  # active, expired, cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="policies")
    plan = relationship("PolicyPlan", back_populates="policies")
    claims = relationship("Claim", back_populates="policy")


class ForensicAnalysis(Base):
    """
    Forensic analysis data for insurance claims.
    Stores results from EXIF extraction, OCR, YOLO11m-seg and Groq AI.
    """
    __tablename__ = "forensic_analyses"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, unique=True)

    # ── EXIF METADATA ────────────────────────────────────────────────────────
    exif_timestamp = Column(DateTime, nullable=True)
    exif_gps_lat = Column(Float, nullable=True)
    exif_gps_lon = Column(Float, nullable=True)
    exif_location_name = Column(String, nullable=True)
    exif_camera_make = Column(String, nullable=True)
    exif_camera_model = Column(String, nullable=True)

    # ── OCR RESULTS ──────────────────────────────────────────────────────────
    ocr_plate_text = Column(String, nullable=True)
    ocr_plate_confidence = Column(Float, nullable=True)

    # Duplicate / re-submission detection
    image_hashes = Column(JSON, nullable=True)  # List of pHash strings

    # ── YOLO DAMAGE DETECTION ────────────────────────────────────────────────
    yolo_damage_detected = Column(Boolean, default=False)
    yolo_detections = Column(JSON, default=list)   # Raw detection objects
    yolo_severity = Column(String, nullable=True)  # minor | moderate | severe
    yolo_summary = Column(Text, nullable=True)

    # ── IMAGE INTEGRITY (Groq forensics) ─────────────────────────────────────
    is_screen_recapture = Column(Boolean, default=False)
    has_ui_elements = Column(Boolean, default=False)
    has_watermarks = Column(Boolean, default=False)
    image_quality = Column(String, nullable=True)      # high | medium | low
    is_blurry = Column(Boolean, default=False)
    multiple_light_sources = Column(Boolean, default=False)
    shadows_inconsistent = Column(Boolean, default=False)
    ela_score = Column(Float, nullable=True)           # ELA Error Level Analysis Manipulation Score (0-1)
    authenticity_score = Column(Float, nullable=True)  # 0–100 (computed)
    forgery_detected = Column(Boolean, default=False)  # computed

    # ── VEHICLE IDENTIFICATION ────────────────────────────────────────────────
    vehicle_make = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_year = Column(String, nullable=True)
    vehicle_color = Column(String, nullable=True)

    # License plate cross-validation
    license_plate_text = Column(String, nullable=True)
    license_plate_match_status = Column(String, nullable=True)  # MATCH | MISMATCH | UNKNOWN

    # ── DAMAGE ASSESSMENT ────────────────────────────────────────────────────
    ai_damage_detected = Column(Boolean, default=False)
    ai_damaged_panels = Column(JSON, default=list)   # Panel names from YOLO/Groq
    ai_damage_type = Column(String, nullable=True)   # dent|scratch|crack|crush|missing
    ai_severity = Column(String, nullable=True)      # none|minor|moderate|severe|totaled
    ai_structural_damage = Column(Boolean, default=False)  # True if severe/totaled

    # Physical damage markers (Groq vision)
    airbags_deployed = Column(Boolean, default=False)
    fluid_leaks_visible = Column(Boolean, default=False)
    parts_missing = Column(Boolean, default=False)

    # Cost estimation
    ai_cost_min = Column(Integer, nullable=True)
    ai_cost_max = Column(Integer, nullable=True)
    repair_cost_breakdown = Column(JSON, nullable=True)  # Per-part breakdown from Price API

    # ── PRE-EXISTING DAMAGE ──────────────────────────────────────────────────
    pre_existing_damage_detected = Column(Boolean, default=False)
    pre_existing_indicators = Column(JSON, default=list)
    pre_existing_description = Column(Text, nullable=True)
    pre_existing_confidence = Column(Float, nullable=True)

    # ── RISK & FINAL ASSESSMENT (rule-based computed) ─────────────────────────
    ai_risk_flags = Column(JSON, default=list)         # e.g. ["PLATE_MISMATCH", "HIGH_COST"]
    fraud_probability = Column(String, nullable=True)  # VERY_LOW | LOW | MEDIUM | HIGH
    fraud_score = Column(Float, nullable=True)         # 0.0–1.0
    overall_confidence_score = Column(Float, nullable=True)  # 0–100
    ai_recommendation = Column(String, nullable=True)  # APPROVED | FLAGGED | REJECTED
    ai_reasoning = Column(Text, nullable=True)
    human_review_priority = Column(String, nullable=True)  # LOW | MEDIUM | HIGH | CRITICAL

    # ── METADATA ─────────────────────────────────────────────────────────────
    analyzed_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    claim = relationship("Claim", back_populates="forensic_analysis")


class Claim(Base):
    """Insurance claim submitted by a user."""
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), index=True, nullable=True)
    assigned_agent_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    description = Column(Text, nullable=True)
    image_paths = Column(JSON, default=list)  # Damage images
    status = Column(String, index=True, default="pending")  # pending | processing | approved | rejected | failed
    assignment_method = Column(String, nullable=True)  # NULL | "auto" | "manual"
    created_at = Column(DateTime, default=datetime.utcnow)
    accident_date = Column(DateTime, nullable=True)
    decision_date = Column(DateTime, nullable=True)

    # Upload paths
    front_image_path = Column(String, nullable=True)
    estimate_bill_path = Column(String, nullable=True)
    gd_entry_path = Column(String, nullable=True)

    # Quick-access fields (denormalized for performance)
    vehicle_number_plate = Column(String, nullable=True)
    ai_recommendation = Column(String, nullable=True)
    estimated_cost_min = Column(Integer, nullable=True)
    estimated_cost_max = Column(Integer, nullable=True)

    # Relationships
    user = relationship("User", back_populates="claims", foreign_keys=[user_id])
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
    policy = relationship("Policy", back_populates="claims")
    forensic_analysis = relationship("ForensicAnalysis", back_populates="claim", uselist=False)
    notes = relationship("ClaimNote", back_populates="claim", order_by="ClaimNote.created_at")
    supplementary_docs = relationship("ClaimDocument", back_populates="claim")


class Notification(Base):
    """In-app notifications for users."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    claim_id = Column(Integer, ForeignKey("claims.id"), index=True, nullable=True)
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    claim = relationship("Claim")


class ClaimNote(Base):
    """Internal agent/admin notes on a claim."""
    __tablename__ = "claim_notes"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="notes")
    author = relationship("User")


class ClaimDocument(Base):
    """Supplementary documents uploaded after initial claim submission."""
    __tablename__ = "claim_documents"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String, nullable=False)
    label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="supplementary_docs")
    uploader = relationship("User")


class SystemSetting(Base):
    """
    Lightweight key/value store for system-level counters and flags.
    Used by auto-assignment to persist the round-robin counter across restarts.
    """
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value = Column(String(255), nullable=False)


class Wallet(Base):
    """Demo wallet for each user. Receives credits when claims are approved."""
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, unique=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet", order_by="WalletTransaction.created_at.desc()")


class WalletTransaction(Base):
    """Ledger of wallet credits/debits for a user."""
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), index=True, nullable=False)
    claim_id = Column(Integer, ForeignKey("claims.id"), index=True, nullable=True)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, default="credit")  # credit | debit
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    wallet = relationship("Wallet", back_populates="transactions")
    claim = relationship("Claim")


# Register Price API model with this Base so it's created on startup
from app.price_api.models import PartPrice  # noqa: F401, E402
