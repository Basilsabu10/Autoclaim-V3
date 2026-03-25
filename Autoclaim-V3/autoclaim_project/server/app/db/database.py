"""
Database configuration and session management.
Provides SQLAlchemy engine, session factory, and dependency.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Create SQLAlchemy engine
# pool_pre_ping: test connections before use, auto-reconnect stale ones
# pool_recycle: refresh connections every 5 min to avoid SSL timeouts
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
    pool_recycle=300,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Database session dependency.
    
    Yields a database session and ensures it's closed after use.
    Use with FastAPI's Depends():
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
