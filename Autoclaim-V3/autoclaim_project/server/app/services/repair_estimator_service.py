

from typing import Dict, Any, List, Optional
import os

# USD to INR conversion rate (update periodically)
USD_TO_INR = 84.0

# Industry-standard repair cost ranges in USD (parts + labor)
# Source: RepairPal, CostHelper, AAA repair cost data
PART_PRICE_TABLE_USD: Dict[str, Dict[str, Any]] = {
    # ── BUMPERS ──────────────────────────────────────────────────────────────
    "front_bumper": {
        "name": "Front Bumper",
        "min": 300,
        "max": 900,
        "icon": "🚗"
    },
    "rear_bumper": {
        "name": "Rear Bumper",
        "min": 250,
        "max": 800,
        "icon": "🚗"
    },

    # ── HOOD / TRUNK ─────────────────────────────────────────────────────────
    "hood": {
        "name": "Hood",
        "min": 400,
        "max": 1200,
        "icon": "🔧"
    },
    "trunk": {
        "name": "Trunk Lid",
        "min": 300,
        "max": 900,
        "icon": "🔧"
    },
    "trunk_lid": {
        "name": "Trunk Lid",
        "min": 300,
        "max": 900,
        "icon": "🔧"
    },

    # ── FENDERS ──────────────────────────────────────────────────────────────
    "fender_fl": {
        "name": "Front Left Fender",
        "min": 200,
        "max": 600,
        "icon": "🔩"
    },
    "fender_fr": {
        "name": "Front Right Fender",
        "min": 200,
        "max": 600,
        "icon": "🔩"
    },
    "fender_rl": {
        "name": "Rear Left Fender",
        "min": 250,
        "max": 700,
        "icon": "🔩"
    },
    "fender_rr": {
        "name": "Rear Right Fender",
        "min": 250,
        "max": 700,
        "icon": "🔩"
    },

    # ── DOORS ────────────────────────────────────────────────────────────────
    "door_fl": {
        "name": "Front Left Door",
        "min": 300,
        "max": 900,
        "icon": "🚪"
    },
    "door_fr": {
        "name": "Front Right Door",
        "min": 300,
        "max": 900,
        "icon": "🚪"
    },
    "door_rl": {
        "name": "Rear Left Door",
        "min": 300,
        "max": 900,
        "icon": "🚪"
    },
    "door_rr": {
        "name": "Rear Right Door",
        "min": 300,
        "max": 900,
        "icon": "🚪"
    },

    # ── ROOF ─────────────────────────────────────────────────────────────────
    "roof": {
        "name": "Roof Panel",
        "min": 800,
        "max": 2500,
        "icon": "🏠"
    },

    # ── QUARTER PANELS ───────────────────────────────────────────────────────
    "quarter_panel_l": {
        "name": "Left Quarter Panel",
        "min": 400,
        "max": 1200,
        "icon": "🔩"
    },
    "quarter_panel_r": {
        "name": "Right Quarter Panel",
        "min": 400,
        "max": 1200,
        "icon": "🔩"
    },

    # ── GLASS ────────────────────────────────────────────────────────────────
    "windshield": {
        "name": "Windshield",
        "min": 200,
        "max": 600,
        "icon": "🪟"
    },
    "rear_windshield": {
        "name": "Rear Windshield",
        "min": 150,
        "max": 500,
        "icon": "🪟"
    },
    "window_fl": {
        "name": "Front Left Window",
        "min": 100,
        "max": 350,
        "icon": "🪟"
    },
    "window_fr": {
        "name": "Front Right Window",
        "min": 100,
        "max": 350,
        "icon": "🪟"
    },

    # ── LIGHTS ───────────────────────────────────────────────────────────────
    "headlight_l": {
        "name": "Left Headlight Assembly",
        "min": 150,
        "max": 500,
        "icon": "💡"
    },
    "headlight_r": {
        "name": "Right Headlight Assembly",
        "min": 150,
        "max": 500,
        "icon": "💡"
    },
    "taillight_l": {
        "name": "Left Taillight Assembly",
        "min": 100,
        "max": 400,
        "icon": "💡"
    },
    "taillight_r": {
        "name": "Right Taillight Assembly",
        "min": 100,
        "max": 400,
        "icon": "💡"
    },

    # ── GRILLE / MIRRORS ─────────────────────────────────────────────────────
    "grille": {
        "name": "Front Grille",
        "min": 100,
        "max": 400,
        "icon": "🔲"
    },
    "side_mirror_l": {
        "name": "Left Side Mirror",
        "min": 80,
        "max": 250,
        "icon": "🪞"
    },
    "side_mirror_r": {
        "name": "Right Side Mirror",
        "min": 80,
        "max": 250,
        "icon": "🪞"
    },

    # ── MECHANICAL ───────────────────────────────────────────────────────────
    "radiator": {
        "name": "Radiator",
        "min": 200,
        "max": 600,
        "icon": "⚙️"
    },
    "frame": {
        "name": "Frame / Chassis",
        "min": 1000,
        "max": 5000,
        "icon": "⚙️"
    },
    "engine": {
        "name": "Engine Components",
        "min": 1500,
        "max": 8000,
        "icon": "⚙️"
    },
    "suspension": {
        "name": "Suspension",
        "min": 300,
        "max": 1500,
        "icon": "⚙️"
    },
    "axle": {
        "name": "Axle",
        "min": 400,
        "max": 1200,
        "icon": "⚙️"
    },
}

# Fuzzy aliases – maps common Groq output variations to canonical keys
PANEL_ALIASES: Dict[str, str] = {
    # bumpers
    "bumper_front": "front_bumper",
    "bumper_rear": "rear_bumper",
    "front bumper": "front_bumper",
    "rear bumper": "rear_bumper",
    # hood
    "bonnet": "hood",
    # doors
    "front_left_door": "door_fl",
    "front_right_door": "door_fr",
    "rear_left_door": "door_rl",
    "rear_right_door": "door_rr",
    # fenders
    "front_left_fender": "fender_fl",
    "front_right_fender": "fender_fr",
    "left_fender": "fender_fl",
    "right_fender": "fender_fr",
    # quarter panels
    "left_quarter_panel": "quarter_panel_l",
    "right_quarter_panel": "quarter_panel_r",
    # lights
    "left_headlight": "headlight_l",
    "right_headlight": "headlight_r",
    "left_taillight": "taillight_l",
    "right_taillight": "taillight_r",
    # mirrors
    "left_mirror": "side_mirror_l",
    "right_mirror": "side_mirror_r",
    # glass
    "front_windshield": "windshield",
    "back_windshield": "rear_windshield",
}


def _resolve_panel_key(panel: str) -> Optional[str]:
    """Resolve a panel name to a canonical key in PART_PRICE_TABLE_USD."""
    if not panel:
        return None
    key = panel.strip().lower().replace(" ", "_")
    # Direct match
    if key in PART_PRICE_TABLE_USD:
        return key
    # Alias match
    if key in PANEL_ALIASES:
        return PANEL_ALIASES[key]
    # Partial match (e.g. "door" matches "door_fl")
    for table_key in PART_PRICE_TABLE_USD:
        if key in table_key or table_key in key:
            return table_key
    return None


def estimate_repair_cost(
    damaged_panels: List[str],
    vehicle_make: Optional[str] = None,
    vehicle_model: Optional[str] = None,
    vehicle_year: Optional[str] = None,
    usd_to_inr: float = USD_TO_INR
) -> Dict[str, Any]:
    """
    Estimate repair cost from a list of damaged panels.

    Args:
        damaged_panels: List of panel keys from Groq AI (e.g. ["front_bumper", "hood"])
        vehicle_make: Vehicle make (for display only)
        vehicle_model: Vehicle model (for display only)
        vehicle_year: Vehicle year (for display only)
        usd_to_inr: USD to INR conversion rate

    Returns:
        dict with:
          - breakdown: list of {part, usd_min, usd_max, inr_min, inr_max, icon}
          - total_usd_min, total_usd_max
          - total_inr_min, total_inr_max
          - usd_to_inr_rate
          - unrecognized_panels: panels that couldn't be priced
          - vehicle_info: make/model/year string
    """
    if not damaged_panels:
        return {
            "breakdown": [],
            "total_usd_min": 0,
            "total_usd_max": 0,
            "total_inr_min": 0,
            "total_inr_max": 0,
            "usd_to_inr_rate": usd_to_inr,
            "unrecognized_panels": [],
            "vehicle_info": _build_vehicle_info(vehicle_make, vehicle_model, vehicle_year)
        }

    breakdown = []
    unrecognized = []
    seen_keys = set()  # Avoid duplicate parts

    for panel in damaged_panels:
        key = _resolve_panel_key(panel)
        if key and key not in seen_keys:
            seen_keys.add(key)
            info = PART_PRICE_TABLE_USD[key]
            inr_min = round(info["min"] * usd_to_inr)
            inr_max = round(info["max"] * usd_to_inr)
            breakdown.append({
                "panel_key": key,
                "part": info["name"],
                "icon": info.get("icon", "🔧"),
                "usd_min": info["min"],
                "usd_max": info["max"],
                "inr_min": inr_min,
                "inr_max": inr_max,
            })
        elif not key:
            unrecognized.append(panel)

    total_usd_min = sum(p["usd_min"] for p in breakdown)
    total_usd_max = sum(p["usd_max"] for p in breakdown)
    total_inr_min = round(total_usd_min * usd_to_inr)
    total_inr_max = round(total_usd_max * usd_to_inr)

    print(f"[RepairEstimator] {len(breakdown)} parts priced: "
          f"${total_usd_min}–${total_usd_max} USD → "
          f"₹{total_inr_min:,}–₹{total_inr_max:,} INR")

    return {
        "breakdown": breakdown,
        "total_usd_min": total_usd_min,
        "total_usd_max": total_usd_max,
        "total_inr_min": total_inr_min,
        "total_inr_max": total_inr_max,
        "usd_to_inr_rate": usd_to_inr,
        "unrecognized_panels": unrecognized,
        "vehicle_info": _build_vehicle_info(vehicle_make, vehicle_model, vehicle_year)
    }


def _build_vehicle_info(make: Optional[str], model: Optional[str], year=None) -> str:
    """Build a human-readable vehicle info string."""
    parts = [str(p) for p in [year, make, model] if p]
    return " ".join(parts) if parts else "Unknown Vehicle"


def get_price_estimate_from_api(
    car_make: str,
    car_model: str,
    price_api_parts: list,
) -> Optional[Dict[str, Any]]:
    """
    Get per-part INR cost estimates via the merged Price API service (direct call, no HTTP).

    Args:
        car_make:        Vehicle make, e.g. "Toyota"
        car_model:       Vehicle model, e.g. "Innova"
        price_api_parts: List of {part_key, damage_type} dicts from YOLO output.

    Returns:
        Price estimate dict on success, None on failure (caller falls back to static table).
    """
    if not price_api_parts:
        return None

    db_res = None
    try:
        from app.price_api.service import build_estimate
        from app.db.database import SessionLocal

        db = SessionLocal()
        try:
            db_res = build_estimate(
                db,
                make=car_make or "Unknown",
                model=car_model or "Unknown",
                parts=price_api_parts,
            )
        finally:
            db.close()

    except Exception as e:
        print(f"[PriceAPI] Direct call failed ({type(e).__name__}: {e})")
        
    if db_res and db_res.get("summary", {}).get("recommended_total", 0) > 0:
        return db_res

    print(f"[PriceAPI] Missing DB prices or call failed — falling back to static table")
    part_keys = [p.get("part_key") for p in price_api_parts if p.get("part_key")]
    static_est = estimate_repair_cost(part_keys, car_make, car_model)
    
    parts_list = []
    for item in static_est.get("breakdown", []):
        parts_list.append({
            "part_key": item["panel_key"],
            "damage_type": "unknown",
            "action": "repair_or_replace",
            "repair_cost": item["inr_min"],
            "replacement_cost": item["inr_max"],
            "recommended_cost": item["inr_max"],
            "price_source": "static_fallback",
        })
        
    total = sum(r["recommended_cost"] for r in parts_list)
    return {
        "vehicle": static_est.get("vehicle_info"),
        "parts": parts_list,
        "summary": {
            "total_parts": len(parts_list),
            "recommended_total": total,
            "repair_count": 0,
            "replace_count": len(parts_list),
        },
        "unrecognized_parts": static_est.get("unrecognized_panels", [])
    }
