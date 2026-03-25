from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import io

from app.database import get_db, PartPrice
from app.services.price_estimate_service import build_estimate, VALID_PART_KEYS

router = APIRouter(prefix="/api/price-estimate", tags=["Price Estimate"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class PartInput(BaseModel):
    part_key:    str
    damage_type: str

class EstimateRequest(BaseModel):
    car_make:  str
    car_model: str
    parts:     List[PartInput]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("")
def get_estimate(req: EstimateRequest, db: Session = Depends(get_db)):
    """
    Main estimate endpoint — called by Autoclaim.
    Returns per-part repair/replacement cost with action (repair | replace | repair_or_replace).
    """
    return build_estimate(
        db,
        make=req.car_make,
        model=req.car_model,
        parts=[p.dict() for p in req.parts]
    )


@router.get("/parts")
def get_parts():
    """Returns all valid part keys — for frontend dropdowns."""
    return {"parts": sorted(VALID_PART_KEYS)}


@router.post("/import")
async def import_prices(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload the filled Excel/CSV to seed the database.
    Accepts parts_prices_template.xlsx.
    Expected columns: make, model, part_key, repair_cost, replacement_cost, source (optional)
    """
    content = await file.read()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")

    required_cols = {"make", "model", "part_key", "repair_cost", "replacement_cost"}
    missing = required_cols - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    # Drop rows with no replacement cost
    df = df.dropna(subset=["replacement_cost"])
    df["repair_cost"]      = df["repair_cost"].fillna(0).astype(int)
    df["replacement_cost"] = df["replacement_cost"].astype(int)
    df["source"]           = df.get("source", "").fillna("")

    inserted = 0
    updated  = 0

    for _, row in df.iterrows():
        existing = db.query(PartPrice).filter(
            PartPrice.make      == row["make"],
            PartPrice.model     == row["model"],
            PartPrice.part_key  == row["part_key"]
        ).first()

        if existing:
            existing.repair_cost      = row["repair_cost"]
            existing.replacement_cost = row["replacement_cost"]
            existing.source           = str(row["source"])
            updated += 1
        else:
            db.add(PartPrice(
                make             = row["make"],
                model            = row["model"],
                part_key         = row["part_key"],
                repair_cost      = row["repair_cost"],
                replacement_cost = row["replacement_cost"],
                source           = str(row["source"]),
            ))
            inserted += 1

    db.commit()

    return {
        "status":   "success",
        "inserted": inserted,
        "updated":  updated,
        "total":    inserted + updated,
    }
