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

@app.on_event("startup")
async def startup_event():
    """Initialize AI services on startup."""
    print("🚀 Starting AutoClaim server...")

    # Initialize AI services
    ai_status = ai_orchestrator.initialize_services()
    print(f"✅ AI Services: {ai_status}")

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
