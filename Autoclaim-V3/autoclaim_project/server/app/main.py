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
from app.services import ai_orchestrator
from app.price_api.router import router as price_router

# Create FastAPI app
app = FastAPI(
    title="AutoClaim API",
    description="Insurance claim processing with AI-powered damage analysis",
    version="2.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(notifications.router)
app.include_router(wallet.router)
app.include_router(price_router)

# Serve uploaded files (images, documents)
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.on_event("startup")
async def startup_event():
    """Initialize AI services and create admin user on server startup."""
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
            from scripts.seed_policies import create_policy_plans, create_policies
            print("🌱 Seeding policy data...")
            plan_map = create_policy_plans(db)
            create_policies(db, plan_map)
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
