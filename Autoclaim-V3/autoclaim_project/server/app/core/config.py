"""
Configuration settings for the AutoClaim server.
Loads environment variables and provides centralized settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application settings loaded from environment variables."""
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "basil")  # Change in production!
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/autoclaim.db")
    
    # AI Services
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # Groq model (LLaMA 4 Scout Vision)
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"

    # AI Mode: "hybrid" (YOLO damage/parts + Groq identity/forensics/scene)
    #          "yolo_only" (no external API — YOLO + sensible defaults)
    AI_MODE: str = os.getenv("AI_MODE", "yolo_only")

    # Custom YOLO11m-seg model for damage + parts segmentation
    YOLO_SEG_MODEL_PATH: str = os.getenv(
        "YOLO_SEG_MODEL_PATH",
        str(BASE_DIR / "models" / "best.pt")
    )

    # Legacy YOLO model path (kept for backward compatibility)
    YOLO_MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "yolov8n.pt"))

    # Upload directory — use HuggingFace persistent storage (/data) if available
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "/data/uploads" if os.path.isdir("/data") else str(BASE_DIR / "uploads")
    )
    
    # CORS — always allow localhost for dev; add production frontend URL when set
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "https://autoclaim-v3.vercel.app",
        *([os.getenv("FRONTEND_URL")] if os.getenv("FRONTEND_URL") else []),
    ]


# Singleton settings instance
settings = Settings()
