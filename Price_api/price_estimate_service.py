from sqlalchemy.orm import Session
from app.database import PartPrice

# Maps damage_type → recommended action
DAMAGE_ACTION = {
    "scratch":  "repair",
    "dent":     "repair",
    "crack":    "repair_or_replace",
    "crush":    "replace",
    "missing":  "replace",
}

VALID_PART_KEYS = {
    "trunk", "door_fl", "grille", "windshield", "door_rl",
    "headlight_l", "hood", "fender_fl", "taillight_l",
    "license_plate", "front_bumper", "rear_bumper", "side_mirror_l"
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
        # Return a fake row-like dict
        return {
            "repair_cost":      avg_repair,
            "replacement_cost": avg_replacement,
        }, "fallback"

    return None, "not_found"


def build_estimate(db: Session, make: str, model: str, parts: list):
    results = []
    unrecognized = []

    for item in parts:
        part_key    = item["part_key"]
        damage_type = item["damage_type"]

        if part_key not in VALID_PART_KEYS:
            unrecognized.append(part_key)
            continue

        action = DAMAGE_ACTION.get(damage_type, "replace")
        price_row, match_type = get_part_price(db, make, model, part_key)

        if price_row is None:
            unrecognized.append(part_key)
            continue

        # Handle both ORM object and dict fallback
        repair_cost      = price_row.repair_cost      if hasattr(price_row, "repair_cost")      else price_row["repair_cost"]
        replacement_cost = price_row.replacement_cost if hasattr(price_row, "replacement_cost") else price_row["replacement_cost"]

        # Pick cost based on action
        if action == "repair":
            cost = repair_cost
        elif action == "replace":
            cost = replacement_cost
        else:  # repair_or_replace — return both
            cost = replacement_cost  # worst case for summary

        results.append({
            "part_key":         part_key,
            "damage_type":      damage_type,
            "action":           action,
            "repair_cost":      repair_cost,
            "replacement_cost": replacement_cost,
            "recommended_cost": cost,
            "price_source":     match_type,
        })

    total = sum(r["recommended_cost"] or 0 for r in results)

    return {
        "vehicle":          f"{make} {model}",
        "parts":            results,
        "summary": {
            "total_parts":        len(results),
            "recommended_total":  total,
        },
        "unrecognized_parts": unrecognized,
    }
