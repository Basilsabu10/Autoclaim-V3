"""
AutoClaim Server - Main FastAPI Application.
Insurance claim processing with AI-powered damage analysis.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.db.database import engine
from app.db import models
from app.api import auth, claims
from app.api import notifications
from app.api import wallet
from app.api import clearance
from app.services import ai_orchestrator
from app.price_api.router import router as price_router

# Create FastAPI app
app = FastAPI(
    title="AutoClaim API",
    description="Insurance claim processing with AI-powered damage analysis",
    version="3.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables (idempotent — only adds missing tables)
models.Base.metadata.create_all(bind=engine)

# ── Safe column migration (idempotent — runs every startup) ─────────────────
try:
    from sqlalchemy import text, inspect as sa_inspect
    with engine.connect() as conn:
        inspector = sa_inspect(engine)
        claims_cols = [c["name"] for c in inspector.get_columns("claims")]
        forensic_cols = [c["name"] for c in inspector.get_columns("forensic_analyses")]

        # Legacy column (pre-v3)
        if "gd_entry_path" not in claims_cols:
            conn.execute(text("ALTER TABLE claims ADD COLUMN gd_entry_path VARCHAR"))
            conn.commit()
            print("✅ Migration: added gd_entry_path")

        # v3 Phase 1 — Agent clearance + video session columns
        clearance_columns = [
            ("clearance_conducted_at",    "TIMESTAMP"),
            ("clearance_agent_id",        "INTEGER"),
            ("agent_document_type",        "VARCHAR"),
            ("agent_document_number",      "VARCHAR"),
            ("clearance_notes",            "TEXT"),
            ("video_session_started_at",   "TIMESTAMP"),  # v3.1 Jitsi session tracking
        ]
        for col, coltype in clearance_columns:
            if col not in claims_cols:
                conn.execute(text(f"ALTER TABLE claims ADD COLUMN {col} {coltype}"))
                conn.commit()
                print(f"✅ Migration: added claims.{col}")

        # v3 Phase 3 — Coverage & payout columns
        payout_columns = [
            ("effective_coverage_amount", "INTEGER"),
            ("payout_rule",              "VARCHAR"),
            ("payout_amount",            "INTEGER"),
            ("is_totaled",               "BOOLEAN DEFAULT FALSE"),
        ]
        for col, coltype in payout_columns:
            if col not in claims_cols:
                conn.execute(text(f"ALTER TABLE claims ADD COLUMN {col} {coltype}"))
                conn.commit()
                print(f"✅ Migration: added claims.{col}")

        # v3 Phase 4 — AI generation detection columns (forensic_analyses)
        ai_gen_columns = [
            ("ai_generated_detected",    "BOOLEAN DEFAULT FALSE"),
            ("ai_generation_confidence", "FLOAT"),
            ("ai_generation_indicators", "JSON"),
        ]
        for col, coltype in ai_gen_columns:
            if col not in forensic_cols:
                conn.execute(text(f"ALTER TABLE forensic_analyses ADD COLUMN {col} {coltype}"))
                conn.commit()
                print(f"✅ Migration: added forensic_analyses.{col}")

        print("✅ All v3 migrations complete")
except Exception as e:
    print(f"⚠️  Column migration check: {e}")

# Include routers
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(clearance.router)
app.include_router(notifications.router)
app.include_router(wallet.router)
app.include_router(price_router)

# Serve uploaded files (images, documents) — uses persistent storage on HuggingFace
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.on_event("startup")
async def startup_event():
    """Initialize AI services on startup."""
    print("🚀 Starting AutoClaim server...")
    
    # Initialize AI services (lazy — models load on first request, not at startup)
    try:
        ai_status = ai_orchestrator.initialize_services()
        print(f"✅ AI Services registered: {ai_status}")
    except Exception as e:
        print(f"⚠️  AI init deferred (will load on first request): {e}")
    
    # Create default admin user if it doesn't exist
    try:
        from app.db.database import SessionLocal
        from app.core.security import get_password_hash
        
        db = SessionLocal()
        try:
            # Hardcoded admin credentials
            ADMIN_EMAIL = "admin@autoclaim.com"
            ADMIN_PASSWORD = "admin123"
            
            admin = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
            if not admin:
                admin = models.User(
                    email=ADMIN_EMAIL,
                    hashed_password=get_password_hash(ADMIN_PASSWORD),
                    role="admin",
                    name="System Administrator"
                )
                db.add(admin)
                db.commit()
                print(f"✅ Admin user created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
            else:
                print(f"✅ Admin user exists: {ADMIN_EMAIL}")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Admin user creation failed: {e}")
    
    # ── Auto-seed policy plans & policies ────────────────────────────────
    # Ensures policies are always available for registration, even after
    # Neon free-tier data eviction. Safe to run every startup (idempotent).
    try:
        from app.db.database import SessionLocal
        db = SessionLocal()
        try:
            from scripts.seed_policies import create_policy_plans, create_policies, get_or_create_unassigned_user
            print("🌱 Seeding policy data...")
            plan_map = create_policy_plans(db)
            unassigned_id = get_or_create_unassigned_user(db)
            create_policies(db, plan_map, unassigned_id)
            db.commit()
            print("✅ Policy data seeded successfully")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  Policy seeding skipped: {e}")
    
    print(f"✅ Server ready!")


@app.get("/")
def root():
    """API root endpoint."""
    return {
        "name": "AutoClaim API",
        "version": "2.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint with AI service status."""
    from app.services.yolo11_seg_service import get_model_info
    
    model_info = get_model_info()
    
    return {
        "status": "healthy",
        "ai_services": {
            "yolov8": model_info.get("model_initialized", False),
            "yolov8_gpu": model_info.get("gpu_info", {}).get("available", False),
            "groq": True  # Assume available if GROQ_API_KEY is set
        }
    }
