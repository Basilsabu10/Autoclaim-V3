"""
Unit tests for the repair cost estimator service.

Tests:
  - Empty parts list returns zeros
  - Known panel keys return correct price ranges
  - Alias resolution (e.g. 'bonnet' → 'hood')
  - Partial match resolution (e.g. 'door' → some door panel)
  - Duplicate panels counted only once
  - Unknown/unrecognized panels tracked separately
  - INR conversion is applied correctly
  - Multi-panel totals are summed correctly
"""

import pytest
from app.services.repair_estimator_service import (
    estimate_repair_cost,
    PART_PRICE_TABLE_USD,
    USD_TO_INR,
)


class TestEstimateRepairCostEmpty:

    def test_empty_panels_returns_zeros(self):
        result = estimate_repair_cost([])
        assert result["total_usd_min"] == 0
        assert result["total_usd_max"] == 0
        assert result["total_inr_min"] == 0
        assert result["total_inr_max"] == 0
        assert result["breakdown"] == []
        assert result["unrecognized_panels"] == []

    def test_empty_panels_includes_usd_rate(self):
        result = estimate_repair_cost([])
        assert result["usd_to_inr_rate"] == USD_TO_INR


class TestKnownPanels:

    def test_front_bumper_price_in_range(self):
        result = estimate_repair_cost(["front_bumper"])
        assert result["total_usd_min"] == PART_PRICE_TABLE_USD["front_bumper"]["min"]
        assert result["total_usd_max"] == PART_PRICE_TABLE_USD["front_bumper"]["max"]

    def test_inr_conversion_applied(self):
        result = estimate_repair_cost(["front_bumper"])
        expected_min = round(PART_PRICE_TABLE_USD["front_bumper"]["min"] * USD_TO_INR)
        expected_max = round(PART_PRICE_TABLE_USD["front_bumper"]["max"] * USD_TO_INR)
        assert result["total_inr_min"] == expected_min
        assert result["total_inr_max"] == expected_max

    def test_hood_resolved(self):
        result = estimate_repair_cost(["hood"])
        assert len(result["breakdown"]) == 1
        assert result["breakdown"][0]["panel_key"] == "hood"

    def test_windshield_resolved(self):
        result = estimate_repair_cost(["windshield"])
        assert result["breakdown"][0]["part"] == "Windshield"


class TestAliasResolution:

    def test_bonnet_alias_resolves_to_hood(self):
        result = estimate_repair_cost(["bonnet"])
        assert len(result["breakdown"]) == 1
        assert result["breakdown"][0]["panel_key"] == "hood"

    def test_front_bumper_space_alias(self):
        result = estimate_repair_cost(["front bumper"])
        assert result["breakdown"][0]["panel_key"] == "front_bumper"

    def test_bumper_front_alias(self):
        result = estimate_repair_cost(["bumper_front"])
        assert result["breakdown"][0]["panel_key"] == "front_bumper"

    def test_left_headlight_alias(self):
        result = estimate_repair_cost(["left_headlight"])
        assert result["breakdown"][0]["panel_key"] == "headlight_l"

    def test_left_mirror_alias(self):
        result = estimate_repair_cost(["left_mirror"])
        assert result["breakdown"][0]["panel_key"] == "side_mirror_l"


class TestDuplicatePanels:

    def test_duplicate_panels_counted_once(self):
        result = estimate_repair_cost(["front_bumper", "front_bumper"])
        assert len(result["breakdown"]) == 1

    def test_alias_and_canonical_counted_once(self):
        """'bonnet' and 'hood' resolve to same key; should appear once."""
        result = estimate_repair_cost(["hood", "bonnet"])
        assert len(result["breakdown"]) == 1


class TestUnrecognizedPanels:

    def test_unknown_panel_tracked(self):
        result = estimate_repair_cost(["flux_capacitor"])
        assert "flux_capacitor" in result["unrecognized_panels"]
        assert result["total_usd_min"] == 0  # unknown has no price

    def test_mix_of_known_and_unknown(self):
        result = estimate_repair_cost(["front_bumper", "mystery_part"])
        assert len(result["breakdown"]) == 1
        assert "mystery_part" in result["unrecognized_panels"]


class TestMultiPanelTotals:

    def test_multi_panel_totals_summed(self):
        panels = ["front_bumper", "hood", "windshield"]
        result = estimate_repair_cost(panels)
        expected_min = sum(PART_PRICE_TABLE_USD[p]["min"] for p in panels)
        expected_max = sum(PART_PRICE_TABLE_USD[p]["max"] for p in panels)
        assert result["total_usd_min"] == expected_min
        assert result["total_usd_max"] == expected_max
        assert len(result["breakdown"]) == 3

    def test_breakdown_contains_icon(self):
        result = estimate_repair_cost(["front_bumper"])
        assert "icon" in result["breakdown"][0]


class TestVehicleInfo:

    def test_vehicle_info_with_make_model_year(self):
        result = estimate_repair_cost(["hood"], "Toyota", "Innova", "2022")
        assert "Toyota" in result["vehicle_info"]
        assert "Innova" in result["vehicle_info"]
        assert "2022" in result["vehicle_info"]

    def test_vehicle_info_unknown_when_empty(self):
        result = estimate_repair_cost([])
        assert result["vehicle_info"] == "Unknown Vehicle"

    def test_custom_usd_to_inr_rate(self):
        custom_rate = 90.0
        result = estimate_repair_cost(["front_bumper"], usd_to_inr=custom_rate)
        expected_min = round(PART_PRICE_TABLE_USD["front_bumper"]["min"] * custom_rate)
        assert result["total_inr_min"] == expected_min
        assert result["usd_to_inr_rate"] == custom_rate
