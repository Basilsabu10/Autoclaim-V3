# AutoClaim Price API — Service Layer
# Copied from Price_api/app/services/price_estimate_service.py
# Updated import to use the merged model path.

from sqlalchemy.orm import Session
from app.price_api.models import PartPrice

# Maps damage_type → recommended action
DAMAGE_ACTION = {
    "scratch":  "repair",
    "dent":     "repair",
    "crack":    "repair_or_replace",
    "crush":    "replace",
    "missing":  "replace",
    "broken":   "replace",
    "shatter":  "replace",
    "tear":     "repair_or_replace",
    "deform":   "replace",
}

# All canonical part keys — aligned with Autoclaim's YOLO model output
VALID_PART_KEYS = {
    # Bumpers
    "front_bumper", "rear_bumper",
    # Hood / Trunk
    "hood", "trunk",
    # Doors
    "door_fl", "door_fr", "door_rl", "door_rr",
    # Fenders
    "fender_fl", "fender_fr", "fender_rl", "fender_rr",
    # Glass
    "windshield", "rear_windshield", "window_fl", "window_fr",
    # Lights
    "headlight_l", "headlight_r", "taillight_l", "taillight_r",
    # Grille / Mirrors
    "grille", "side_mirror_l", "side_mirror_r",
    # Roof / Quarter panels
    "roof", "quarter_panel_l", "quarter_panel_r",
    # Misc
    "license_plate",
}


def get_part_price(db: Session, make: str, model: str, part_key: str):
    """Exact match first, then fallback to same make (any model average)."""
    row = db.query(PartPrice).filter(
        PartPrice.make.ilike(make),
        PartPrice.model.ilike(model),
        PartPrice.part_key == part_key
    ).first()

    if row:
        return row, "exact"

    # Fallback — same make, same part, average across models
    rows = db.query(PartPrice).filter(
        PartPrice.make.ilike(make),
        PartPrice.part_key == part_key
    ).all()

    if rows:
        avg_repair      = int(sum(r.repair_cost or 0 for r in rows) / len(rows))
        avg_replacement = int(sum(r.replacement_cost for r in rows) / len(rows))
        return {
            "repair_cost":      avg_repair,
            "replacement_cost": avg_replacement,
        }, "fallback"

    return None, "not_found"


def build_estimate(db: Session, make: str, model: str, parts: list):
    results      = []
    unrecognized = []

    for item in parts:
        part_key    = item["part_key"]
        damage_type = item.get("damage_type", "scratch").lower().strip()

        if part_key not in VALID_PART_KEYS:
            unrecognized.append(part_key)
            continue

        action    = DAMAGE_ACTION.get(damage_type, "replace")
        price_row, match_type = get_part_price(db, make, model, part_key)

        if price_row is None:
            unrecognized.append(part_key)
            continue

        # Handle both ORM object and dict fallback
        repair_cost      = price_row.repair_cost      if hasattr(price_row, "repair_cost")      else price_row["repair_cost"]
        replacement_cost = price_row.replacement_cost if hasattr(price_row, "replacement_cost") else price_row["replacement_cost"]

        if action == "repair":
            cost = repair_cost or 0
        elif action == "replace":
            cost = replacement_cost
        else:  # repair_or_replace — worst case
            cost = replacement_cost

        results.append({
            "part_key":         part_key,
            "damage_type":      damage_type,
            "action":           action,
            "repair_cost":      repair_cost or 0,
            "replacement_cost": replacement_cost,
            "recommended_cost": cost,
            "price_source":     match_type,
        })

    total = sum(r["recommended_cost"] or 0 for r in results)

    return {
        "vehicle": f"{make} {model}",
        "parts":   results,
        "summary": {
            "total_parts":       len(results),
            "recommended_total": total,
            "repair_count":      sum(1 for r in results if r["action"] == "repair"),
            "replace_count":     sum(1 for r in results if r["action"] in ("replace", "repair_or_replace")),
        },
        "unrecognized_parts": unrecognized,
    }
