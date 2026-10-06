"""test_use_cases.py — End-to-End Realistic Architectural Use Cases

Tests the 4 realistic Indian architectural scenarios:
1. Use Case 1: Mid-Market 2BHK/3BHK Residential Apartment (110 sqm) with Reflected Ceiling Plan (RCP)
2. Use Case 2: High-End Custom Villa with Sunken Slabs & Large French Glazing (> 3.0 sqm Tier 3)
3. Use Case 3: Commercial Office Fit-Out with Non-Standard Layers & 2x2 Grid Panels
4. Use Case 4: PreDCR Municipal Sanction Drawing Package
"""

import os
import pytest

from cad_parser import CadParser
from spec_parser import parse_client_brief
from boq_engine import BoqEngine


@pytest.fixture
def parser():
    return CadParser()


@pytest.fixture
def engine():
    return BoqEngine()


def test_use_case_1_midmarket_2bhk_rcp(parser, engine, tmp_path):
    """Use Case 1: Standard 2BHK/3BHK Residential Apartment (Mid-Market)."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "use_case_1_2bhk_rcp.dxf")
    assert os.path.exists(dxf_path), f"CAD file not found: {dxf_path}"

    # 1. Vector CAD Extraction
    takeoff = parser.parse_dxf_file(dxf_path)
    assert takeoff.units == "mm"
    assert takeoff.total_floor_area_sqm >= 100.0  # 110 sqm floor plan
    assert len(takeoff.openings) >= 5  # Doors, Windows, Ventilators

    # Verify block counts from Reflected Ceiling Plan (RCP)
    counts = takeoff.block_counts
    assert counts.get("RECESSED_DOWNLIGHT_12W", 0) == 18
    assert counts.get("BLDC_CEILING_FAN_1200MM", 0) == 3
    assert counts.get("MODULAR_SWITCH_6A", 0) == 8
    assert counts.get("POWER_SOCKET_16A", 0) == 4
    assert counts.get("EWC_WALL_HUNG", 0) == 2
    assert counts.get("WASH_BASIN_COUNTER", 0) == 2

    # 2. Client Brief Interpretation
    brief_text = (
        "Client wants 12W 3000K warm white recessed LED downlights in living and bedrooms, "
        "1200mm BLDC energy-efficient ceiling fans (Havells/Atomberg), modular switches from Schneider, "
        "and 600x600mm vitrified tiles."
    )
    spec = parse_client_brief(brief_text)
    assert spec.preferred_lighting_brand in ("Havells", "Philips", "Any")
    assert spec.lighting_wattage == 12
    assert spec.lighting_color_temp == "3000K"
    assert spec.preferred_fan_brand in ("Atomberg", "Havells")
    assert spec.fan_type == "BLDC"
    assert spec.preferred_switch_brand == "Schneider"
    assert spec.flooring_preference == "Vitrified Tile"

    # 3. BOQ Compilation & IS 1200 Deductions
    boq = engine.generate_boq(takeoff, spec)
    assert boq["grand_total_inr"] > 0
    items = boq["items"]

    # Verify trade categorization
    trades = {it["trade"] for it in items}
    assert "Civil" in trades
    assert "Electrical" in trades
    assert "Finishes" in trades
    assert "Plumbing" in trades

    # Verify line items have valid quantities and active buy-links
    for it in items:
        assert it["quantity"] > 0
        assert it["unit_rate_inr"] > 0
        assert it["total_cost_inr"] > 0
        assert it["buy_url"].startswith("http")

    # Verify IS 1200 plaster deduction was performed for standard openings
    plaster_audit = boq["is1200_plaster_audit"]
    assert plaster_audit["gross_plaster_area_both_faces_sqm"] > 0
    assert plaster_audit["total_opening_deduction_sqm"] > 0

    # 4. Verify Excel Export
    excel_path = os.path.join(str(tmp_path), "use_case_1_boq.xlsx")
    saved_path = engine.export_to_excel(boq, excel_path)
    assert os.path.exists(saved_path)
    assert os.path.getsize(saved_path) > 5000


def test_use_case_2_villa_large_glazing_tier3(parser, engine, tmp_path):
    """Use Case 2: High-End Custom Villa with Tier 3 Large Openings (> 3.0 sq.m)."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "use_case_2_villa_glazing.dxf")
    assert os.path.exists(dxf_path), f"CAD file not found: {dxf_path}"

    takeoff = parser.parse_dxf_file(dxf_path)
    assert takeoff.total_floor_area_sqm >= 300.0  # 330 sqm villa footprint
    assert any("SUNKEN" in lyr.upper() for lyr in takeoff.detected_layers)

    # Verify Tier 3 openings (> 3.0 sq.m)
    tier3_openings = [op for op in takeoff.openings if op.area_sqm > 3.0]
    assert len(tier3_openings) >= 2, "Must detect large French sliding doors or panoramic windows > 3.0 sqm"

    # Verify IS 1200 Part 12 Tier 3 Plaster Deductions
    plaster_audit = engine.calculate_is1200_plaster(
        takeoff.total_wall_area_sqm,
        takeoff.openings,
        wall_thickness_m=0.23,
    )

    # In Tier 3, reveals/jambs MUST be added back to the net plaster area
    assert plaster_audit["total_reveal_addition_sqm"] > 0, "IS 1200 Tier 3 requires reveal addition for openings > 3.0 sqm"
    tier3_audits = [a for a in plaster_audit["openings_audit"] if "Tier 3" in a["statutory_tier"]]
    assert len(tier3_audits) >= 2
    for audit in tier3_audits:
        # Both faces deducted: 2.0 * area
        expected_ded = audit["area_sqm"] * 2.0
        assert abs(audit["face_deduction_sqm"] - expected_ded) < 0.05
        assert audit["reveal_addition_sqm"] > 0

    # Client Brief & BOQ
    brief_text = (
        "Use premium 15W dimmable warm downlights, magnetic track lights in living room, "
        "premium Jaquar sanitaryware, and Asian Paints Royale acrylic emulsion on all internal plaster."
    )
    spec = parse_client_brief(brief_text)
    boq = engine.generate_boq(takeoff, spec)

    # Verify premium catalog SKUs
    skus = [it["sku_id"] for it in boq["items"]]
    assert "LGT-MAG-TRK-20W" in skus, "Magnetic track light should be matched"
    assert "PLB-SNK-SUN-100" in skus, "Sunken slab drainage trap should be included"

    excel_path = os.path.join(str(tmp_path), "use_case_2_boq.xlsx")
    saved_path = engine.export_to_excel(boq, excel_path)
    assert os.path.exists(saved_path)


def test_use_case_3_commercial_office_fitout(parser, engine, tmp_path):
    """Use Case 3: Commercial Office / Retail Interior Fit-Out with non-standard layers."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "use_case_3_commercial_office.dxf")
    assert os.path.exists(dxf_path), f"CAD file not found: {dxf_path}"

    takeoff = parser.parse_dxf_file(dxf_path)
    # Check non-standard layers were properly recognized
    assert any("PARTITION" in lyr for lyr in takeoff.detected_layers)
    assert any("CARPET" in lyr for lyr in takeoff.detected_layers)
    assert any("GRID_LIGHT" in lyr for lyr in takeoff.detected_layers)

    # Block counts
    counts = takeoff.block_counts
    assert counts.get("GRID_LIGHT_600X600_36W", 0) >= 24
    assert counts.get("TRACK_LIGHT_20W", 0) == 8
    assert counts.get("HVAC_DIFFUSER_4WAY", 0) == 6

    # Brief
    brief_text = (
        "Provide 36W 600x600 LED ceiling grid panels, 2x2 acoustic ceiling tiles, "
        "2-inch aluminium partition framing, and commercial carpet tiles."
    )
    spec = parse_client_brief(brief_text)
    boq = engine.generate_boq(takeoff, spec)

    # Check commercial fit-out line items
    descriptions = [it["description"].lower() for it in boq["items"]]
    skus = [it["sku_id"] for it in boq["items"]]

    assert "LGT-WIP-36W-2X2" in skus, "36W 2x2 Grid LED Panel SKU should be in BOQ"
    assert "FIN-CLG-ACO-2X2" in skus, "Armstrong Acoustic Ceiling Tile SKU should be in BOQ"
    assert "CIV-ALU-GLS-50MM" in skus, "Aluminium Glass Partition SKU should be in BOQ"
    assert "FIN-CRPT-MOD-500" in skus, "Commercial Carpet Tile SKU should be in BOQ"

    excel_path = os.path.join(str(tmp_path), "use_case_3_boq.xlsx")
    saved_path = engine.export_to_excel(boq, excel_path)
    assert os.path.exists(saved_path)


def test_use_case_4_predcr_municipal_sanction(parser, engine, tmp_path):
    """Use Case 4: PreDCR Municipal Sanction Drawing Package."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "use_case_4_predcr_sanction.dxf")
    assert os.path.exists(dxf_path), f"CAD file not found: {dxf_path}"

    takeoff = parser.parse_dxf_file(dxf_path)
    layers = takeoff.detected_layers

    # Verify municipal PreDCR layers were parsed
    assert "_RESIMAIN" in layers
    assert "_CARPET AREA" in layers
    assert "_MARGINLINE" in layers

    # Floor area should be extracted from _RESIMAIN or _CARPET AREA
    assert takeoff.total_floor_area_sqm >= 60.0

    # Municipal openings detected
    assert len(takeoff.openings) >= 2

    # BOQ successfully compiles without layer error
    spec = parse_client_brief("Standard residential municipal building approval")
    boq = engine.generate_boq(takeoff, spec)
    assert boq["grand_total_inr"] > 0
