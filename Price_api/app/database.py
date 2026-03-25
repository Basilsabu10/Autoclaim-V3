from sqlalchemy import create_engine, Column, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./parts_prices.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class PartPrice(Base):
    __tablename__ = "parts_prices"
    __table_args__ = (
        UniqueConstraint("make", "model", "part_key", name="uq_make_model_part"),
    )

    id                = Column(Integer, primary_key=True, index=True)
    make              = Column(String, nullable=False)
    model             = Column(String, nullable=False)
    part_key          = Column(String, nullable=False)
    repair_cost       = Column(Integer, nullable=True)
    replacement_cost  = Column(Integer, nullable=False)
    source            = Column(String, nullable=True)
    updated_at        = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
