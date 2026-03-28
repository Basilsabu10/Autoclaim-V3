"""
Coverage & Depreciation Engine — AutoClaim v3.0
================================================
Computes the effective (depreciation-adjusted) coverage amount and drives
payout decisions from it.

Formula (from AutoClaim v3 Implementation Plan):
  base_coverage      = plan_coverage × 0.95
  depreciation_rate  = 5% year-1, +3% per additional year (capped at 80%)
  effective_coverage = base_coverage × (1 − depreciation_rate)

Payout tiers:
  repair < 75% of coverage      → pay full repair estimate
  75% ≤ repair < 100% coverage  → pay 70% of coverage
  repair ≥ coverage              → TOTALED → agent decision required (no auto-approve)

Auto-approval threshold:
  = 20% of effective_coverage   (replaces fixed SystemSetting lookup)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional


# ── Public helpers ────────────────────────────────────────────────────────────

def compute_effective_coverage(
    plan_coverage: int,
    start_date: datetime,
    accident_date: Optional[datetime] = None,
) -> float:
    """
    Return the depreciation-adjusted coverage amount in ₹.

    Parameters
    ----------
    plan_coverage : int
        Raw coverage amount stored in the PolicyPlan (e.g. ₹5,00,000).
    start_date : datetime
        Policy start date.
    accident_date : datetime, optional
        Date of the reported accident. Falls back to *today* if not provided.

    Returns
    -------
    float
        Effective coverage in ₹ (>= 0).
    """
    reference = accident_date or datetime.utcnow()

    # Clamp to zero to handle edge cases (policy issued today)
    age_days = max(0, (reference - start_date).days)
    age_years = age_days / 365.0

    # Depreciation: 5% in year 1, +3% for each additional year, capped at 80%
    if age_years <= 1:
        depreciation_rate = 0.05
    else:
        extra_years = age_years - 1
        depreciation_rate = 0.05 + (extra_years * 0.03)

    depreciation_rate = min(depreciation_rate, 0.80)  # 80% cap

    base_coverage = plan_coverage * 0.95
    effective = base_coverage * (1.0 - depreciation_rate)
    return max(0.0, effective)


def compute_payout(
    repair_estimate: float,
    effective_coverage: float,
) -> dict:
    """
    Determine payout amount and rule given the repair estimate.

    Returns
    -------
    dict with keys:
        payout_amount  : float — actual ₹ to pay
        payout_rule    : str   — "full" | "partial" | "totaled"
        is_totaled     : bool  — True blocks auto-approval
        reasoning      : str   — human-readable explanation
    """
    if effective_coverage <= 0:
        # Edge case: no computable coverage (very old policy)
        return {
            "payout_amount": 0,
            "payout_rule": "totaled",
            "is_totaled": True,
            "reasoning": "Effective coverage is zero (policy fully depreciated). Requires agent decision.",
        }

    ratio = repair_estimate / effective_coverage

    if ratio >= 1.0:
        # Repair cost equals or exceeds full coverage → TOTALED
        return {
            "payout_amount": 0,
            "payout_rule": "totaled",
            "is_totaled": True,
            "reasoning": (
                f"Repair estimate ₹{repair_estimate:,.0f} ≥ effective coverage "
                f"₹{effective_coverage:,.0f} ({ratio*100:.1f}%). Vehicle flagged as TOTALED."
            ),
        }
    elif ratio >= 0.75:
        # 75–99% of coverage → partial payout at 70% of coverage
        payout = effective_coverage * 0.70
        return {
            "payout_amount": round(payout),
            "payout_rule": "partial",
            "is_totaled": False,
            "reasoning": (
                f"Repair estimate ₹{repair_estimate:,.0f} is {ratio*100:.1f}% of effective "
                f"coverage ₹{effective_coverage:,.0f} (75–99% band). Payout = 70% of coverage "
                f"= ₹{payout:,.0f}."
            ),
        }
    else:
        # Below 75% → pay full repair estimate
        return {
            "payout_amount": round(repair_estimate),
            "payout_rule": "full",
            "is_totaled": False,
            "reasoning": (
                f"Repair estimate ₹{repair_estimate:,.0f} is {ratio*100:.1f}% of effective "
                f"coverage ₹{effective_coverage:,.0f} (<75% band). Full repair amount paid."
            ),
        }


def compute_auto_approval_threshold(effective_coverage: float) -> float:
    """
    Return the auto-approval threshold = 20% of effective coverage.

    This replaces the static SystemSetting lookup with a dynamic value
    tied to the actual policy coverage at claim time.
    """
    return effective_coverage * 0.20
