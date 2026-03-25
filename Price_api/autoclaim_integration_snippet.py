# ── Add this to repair_estimator_service.py in Autoclaim ──────────────────
# Install httpx if not already: pip install httpx

import httpx
import os

PRICE_API_URL = os.getenv("PRICE_API_URL", "http://localhost:8001/api/price-estimate")


async def get_price_estimate(car_make: str, car_model: str, damage_part_mapping: list) -> dict:
    """
    Calls the Price API to get real INR costs for detected damaged parts.

    damage_part_mapping comes directly from YOLO output, e.g.:
    [
        {"part_key": "hood",         "damage_type": "dent"},
        {"part_key": "front_bumper", "damage_type": "crush"},
    ]
    """
    payload = {
        "car_make":  car_make,
        "car_model": car_model,
        "parts":     damage_part_mapping,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(PRICE_API_URL, json=payload)
            response.raise_for_status()
            return response.json()

    except httpx.ConnectError:
        # Price API is down — fall back to empty result
        return {"error": "Price API unavailable", "parts": [], "summary": {"recommended_total": 0}}

    except httpx.HTTPStatusError as e:
        return {"error": f"Price API error: {e.response.status_code}", "parts": []}


# ── Example usage inside your existing claim flow ─────────────────────────
#
# result = await get_price_estimate(
#     car_make  = claim.car_make,
#     car_model = claim.car_model,
#     damage_part_mapping = yolo_output.damage_part_mapping
# )
#
# total_cost = result["summary"]["recommended_total"]
# breakdown  = result["parts"]
