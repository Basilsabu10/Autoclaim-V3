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

# Create database tables (idempotent — only adds missing tables)
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

# ── One-time reset flag key ──────────────────────────────────────────────
# Change this value to trigger a fresh wipe on the next deploy.
DB_RESET_FLAG = "db_reset_v1"


@app.on_event("startup")
async def startup_event():
    """Initialize AI services; one-time DB wipe + reseed; ensure admin exists."""
    print("🚀 Starting AutoClaim server...")

    # Initialize AI services
    ai_status = ai_orchestrator.initialize_services()
    print(f"✅ AI Services: {ai_status}")

    # ── DATABASE: ONE-TIME RESET ──────────────────────────────────────────────
    # On the FIRST boot after deploy the flag doesn't exist ➜ wipe all data.
    # On every subsequent restart the flag is found ➜ skip the wipe.
    # To force a new wipe, change DB_RESET_FLAG above (e.g. "db_reset_v2").
    # Compatible with both SQLite and PostgreSQL.
    # ─────────────────────────────────────────────────────────────────────────
    try:
        from app.db.database import SessionLocal
        from app.core.security import get_password_hash

        db = SessionLocal()
        try:
            # Check if we've already done this reset
            flag = db.query(models.SystemSetting).filter(
                models.SystemSetting.key == DB_RESET_FLAG
            ).first()

            if flag:
                print(f"✅ Database already reset ({DB_RESET_FLAG}), skipping wipe")
            else:
                # ── FIRST BOOT: wipe everything ─────────────────────────────
                print("🗑️  First boot — wiping all data …")

                # Delete in FK-safe order
                db.query(models.WalletTransaction).delete()
                db.query(models.Wallet).delete()
                db.query(models.ClaimDocument).delete()
                db.query(models.ClaimNote).delete()
                db.query(models.Notification).delete()
                db.query(models.ForensicAnalysis).delete()
                db.query(models.Claim).delete()
                db.query(models.Policy).delete()
                db.query(models.PolicyPlan).delete()
                from app.price_api.models import PartPrice
                db.query(PartPrice).delete()
                db.query(models.SystemSetting).delete()
                db.query(models.User).delete()
                db.commit()
                print("✅ All data deleted")

                # Write the flag so we never wipe again
                db.add(models.SystemSetting(key=DB_RESET_FLAG, value="done"))
                db.commit()
                print(f"✅ Reset flag '{DB_RESET_FLAG}' saved")

            # ── ENSURE ADMIN USER (every restart) ───────────────────────────
            admin = db.query(models.User).filter(
                models.User.email == "admin@autoclaim.com"
            ).first()
            if not admin:
                admin = models.User(
                    email="admin@autoclaim.com",
                    hashed_password=get_password_hash("admin123"),
                    role="admin",
                    name="System Administrator",
                )
                db.add(admin)
                db.commit()
                print("✅ Admin user created: admin@autoclaim.com / admin123")
            else:
                print(f"✅ Admin user exists: {admin.email}")

            # ── SEED POLICY PLANS (every restart, skip if exists) ───────────
            plans_data = [
                {
                    "name": "Basic Coverage",
                    "description": "Essential coverage for everyday drivers. Covers basic collision and liability.",
                    "coverage_amount": 50000,
                    "premium_monthly": 120,
                },
                {
                    "name": "Standard Coverage",
                    "description": "Comprehensive protection with enhanced benefits. Includes collision, comprehensive, and roadside assistance.",
                    "coverage_amount": 100000,
                    "premium_monthly": 200,
                },
                {
                    "name": "Premium Coverage",
                    "description": "Maximum protection for high-value vehicles. Full coverage with zero deductible option.",
                    "coverage_amount": 250000,
                    "premium_monthly": 350,
                },
                {
                    "name": "Platinum Elite",
                    "description": "Ultimate insurance package with concierge service. Luxury vehicle specialist coverage.",
                    "coverage_amount": 500000,
                    "premium_monthly": 600,
                },
            ]
            seeded = 0
            for plan_data in plans_data:
                existing = db.query(models.PolicyPlan).filter(
                    models.PolicyPlan.name == plan_data["name"]
                ).first()
                if not existing:
                    db.add(models.PolicyPlan(**plan_data))
                    seeded += 1
            if seeded:
                db.commit()
                print(f"✅ Seeded {seeded} new policy plan(s)")
            else:
                print("✅ All policy plans already exist, skipping seed")

            # ── SEED POLICIES (every restart, skip if registration exists) ──
            from datetime import datetime, timedelta

            # Fetch plan IDs by name
            plan_map = {}
            for p in db.query(models.PolicyPlan).all():
                plan_map[p.name] = p.id

            policies_data = [
                # Policy 1
                {"vehicle_year": 2022, "vehicle_make": "Honda",       "vehicle_model": "City",    "vehicle_registration": "KL-01-AB-1234", "plan": "Basic Coverage"},
                # Policy 2
                {"vehicle_year": 2023, "vehicle_make": "Toyota",      "vehicle_model": "Fortuner","vehicle_registration": "KL-02-CD-5678", "plan": "Standard Coverage"},
                # Policy 3
                {"vehicle_year": 2020, "vehicle_make": "Kia",         "vehicle_model": "Seltos",  "vehicle_registration": "KL-07-CU-7475", "plan": "Premium Coverage"},
                # Policy 4
                {"vehicle_year": 2020, "vehicle_make": "Kia",         "vehicle_model": "Seltos",  "vehicle_registration": "KL-07-CU-7476", "plan": "Premium Coverage"},
                # Policy 5
                {"vehicle_year": 2020, "vehicle_make": "Volkswagen",  "vehicle_model": "Vento",   "vehicle_registration": "KL-64-C-599",   "plan": "Standard Coverage"},
                # Policy 6
                {"vehicle_year": 2014, "vehicle_make": "Volkswagen",  "vehicle_model": "Vento",   "vehicle_registration": "KL-63-C-599",   "plan": "Basic Coverage"},
                # Policy 7
                {"vehicle_year": 2020, "vehicle_make": "Suzuki",      "vehicle_model": "Baleno",  "vehicle_registration": "KL 63 F 3227",  "plan": "Standard Coverage"},
                # Policy 8
                {"vehicle_year": 2021, "vehicle_make": "Maruti",      "vehicle_model": "Swift",   "vehicle_registration": "KL-10-AA-1111", "plan": "Basic Coverage"},
                # Policy 9
                {"vehicle_year": 2019, "vehicle_make": "Hyundai",     "vehicle_model": "i20",     "vehicle_registration": "KL-05-BB-2222", "plan": "Platinum Elite"},
                # Policy 10
                {"vehicle_year": 2023, "vehicle_make": "Tata",        "vehicle_model": "Nexon",   "vehicle_registration": "KL-14-CC-3333", "plan": "Premium Coverage"},
            ]

            policy_seeded = 0
            for pd in policies_data:
                existing = db.query(models.Policy).filter(
                    models.Policy.vehicle_registration == pd["vehicle_registration"]
                ).first()
                if not existing:
                    policy = models.Policy(
                        user_id=admin.id,
                        plan_id=plan_map[pd["plan"]],
                        vehicle_make=pd["vehicle_make"],
                        vehicle_model=pd["vehicle_model"],
                        vehicle_year=pd["vehicle_year"],
                        vehicle_registration=pd["vehicle_registration"],
                        start_date=datetime.utcnow() - timedelta(days=90),
                        end_date=datetime.utcnow() + timedelta(days=275),
                        status="active",
                    )
                    db.add(policy)
                    policy_seeded += 1
            if policy_seeded:
                db.commit()
                print(f"✅ Seeded {policy_seeded} new policy/policies")
            else:
                print("✅ All 10 policies already exist, skipping seed")

        finally:
            db.close()

    except Exception as e:
        print(f"⚠️  Database reset/seed failed: {e}")
        import traceback
        traceback.print_exc()

    print("✅ Server ready!")


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
