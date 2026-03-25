# AutoClaim Price API — Models
# PartPrice SQLAlchemy model, registered with main app's Base so it's
# created automatically alongside all other AutoClaim tables on startup.

from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from datetime import datetime

from app.db.models import Base


class PartPrice(Base):
    __tablename__ = "parts_prices"
    __table_args__ = (
        UniqueConstraint("make", "model", "part_key", name="uq_make_model_part"),
    )

    id               = Column(Integer, primary_key=True, index=True)
    make             = Column(String, nullable=False)
    model            = Column(String, nullable=False)
    part_key         = Column(String, nullable=False)
    repair_cost      = Column(Integer, nullable=True)
    replacement_cost = Column(Integer, nullable=False)
    source           = Column(String, nullable=True)
    updated_at       = Column(DateTime, default=datetime.utcnow)
