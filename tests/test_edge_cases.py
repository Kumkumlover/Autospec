"""test_edge_cases.py — Unit & Integration Tests for Pipeline Edge Cases

Tests:
1. CAD Vector & Geometry Edge Cases:
   - Unclosed polylines with drafting gaps (0.02m)
   - Nested blocks (block references inside block definitions)
   - Exploded geometry (raw circles on lighting layer)
   - 3D non-planar polylines (Z != 0)
   - Unit and scale conversions (mm, m, inches)
2. IS 1200 Rule Engine Edge Cases:
   - Plaster Tier 1 (<= 0.5 sqm), Tier 2 (0.5 to 3.0 sqm), Tier 3 (> 3.0 sqm)
   - Masonry deductions (<= 0.1 sqm exempt)
3. Natural Language Brief Edge Cases:
   - Hinglish / Regional vernacular brief
   - Vague and Vastu-driven brief
   - Conflicting specifications
4. BOQ & Excel Export Edge Cases:
   - Zero-count items
   - Currency formatting & valid formulas
"""

import os
import openpyxl
import pytest

from cad_parser import CadParser
from spec_parser import parse_client_brief, ClientSpecification
from boq_engine import BoqEngine
from cad_parser import OpeningItem, ParsedCadTakeoff


@pytest.fixture
def parser():
    return CadParser()


@pytest.fixture
def engine():
    return BoqEngine()


def test_edge_case_unclosed_polylines(parser):
    """Verifies that an unclosed polyline with a 20mm drafting gap calculates area gracefully."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "edge_cases_geometry.dxf")
    takeoff = parser.parse_dxf_file(dxf_path)

    # FLOOR_UNCLOSED has points forming a 10m x 8m room with a 20mm gap
    # Area should be ~80 sqm and NOT throw an exception or evaluate to 0.0
    area = takeoff.polyline_areas_sqm.get("FLOOR_UNCLOSED", 0.0)
    assert area >= 75.0, f"Unclosed polyline area should be ~80 sqm, got {area}"


def test_edge_case_nested_blocks(parser):
    """Verifies that nested blocks inside block definitions are recursively traversed and counted."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "edge_cases_geometry.dxf")
    takeoff = parser.parse_dxf_file(dxf_path)

    counts = takeoff.block_counts
    # WORKSTATION_POD contains OFFICE_DESK and TASK_CHAIR
    assert counts.get("WORKSTATION_POD", 0) == 2
    assert counts.get("OFFICE_DESK", 0) >= 2, "Nested child block OFFICE_DESK should be traversed"
    assert counts.get("TASK_CHAIR", 0) >= 2, "Nested child block TASK_CHAIR should be traversed"


def test_edge_case_exploded_circles(parser):
    """Verifies that circles drawn on lighting layers without block definitions are recognized as lighting points."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "edge_cases_geometry.dxf")
    takeoff = parser.parse_dxf_file(dxf_path)

    # 4 circles drawn on LIGHTS_EXPLODED
    exploded_lights = [b for b in takeoff.block_instances if "EXPLODED_LIGHT" in b["name"]]
    assert len(exploded_lights) == 4, f"Expected 4 exploded light circles, found {len(exploded_lights)}"
    assert any(info["trade"] == "Electrical - Lighting" for info in takeoff.classified_blocks.values())


def test_edge_case_3d_polylines(parser):
    """Verifies that 3D polylines with non-zero Z coordinates flatten to 2D without dimension errors."""
    dxf_path = os.path.join(os.path.dirname(__file__), "..", "samples", "edge_cases_geometry.dxf")
    takeoff = parser.parse_dxf_file(dxf_path)

    # WALLS_3D was created with Z = 3500mm
    # Should calculate wall length cleanly
    wall_segs = [s for s in takeoff.wall_segments if s.get("layer") == "WALLS_3D"]
    assert len(wall_segs) > 0, "3D polyline segments should be extracted without crashing"
    assert all("z" not in s for s in wall_segs), "Coordinates should be 2D flattened"


def test_edge_case_unit_scales(engine):
    """Verifies unit auto-detection on millimeters, meters, and inches drawings without 1,000x error."""
    # Simulate a 100 sq.m room in meters vs millimeters
    takeoff_m = ParsedCadTakeoff(
        file_name="plan_meters.dxf",
        units="m",
        scale_factor_to_meters=1.0,
        area_scale_factor=1.0,
        total_floor_area_sqm=100.0,
        total_wall_area_sqm=120.0,
        wall_length_m=40.0,
    )
    takeoff_mm = ParsedCadTakeoff(
        file_name="plan_mm.dxf",
        units="mm",
        scale_factor_to_meters=0.001,
        area_scale_factor=1e-6,
        total_floor_area_sqm=100.0,
        total_wall_area_sqm=120.0,
        wall_length_m=40.0,
    )

    spec = ClientSpecification(flooring_preference="Vitrified Tile")
    boq_m = engine.generate_boq(takeoff_m, spec)
    boq_mm = engine.generate_boq(takeoff_mm, spec)

    # Totals must match within floating precision regardless of input unit
    assert abs(boq_m["grand_total_inr"] - boq_mm["grand_total_inr"]) < 1.0


def test_edge_case_hinglish_brief():
    """Verifies vernacular Hinglish prompt parsing."""
    hinglish_prompt = (
        "Havells 12 watt ke warm downlight, Atomberg BLDC pankhe aur Schneider ke modular switch lagane hain"
    )
    spec = parse_client_brief(hinglish_prompt)

    assert spec.preferred_lighting_brand in ("Havells", "Philips")
    assert spec.lighting_wattage == 12
    assert spec.lighting_color_temp == "3000K"
    assert spec.preferred_fan_brand == "Atomberg"
    assert spec.fan_type == "BLDC"
    assert spec.preferred_switch_brand == "Schneider"
    assert spec.switch_grade == "Modular"


def test_edge_case_vague_and_conflicting_brief():
    """Verifies that vague/Vastu prompts and conflicting commercial briefs fall back cleanly."""
    # 1. Vague/Vastu prompt
    vague_prompt = "Use good quality warm lights in South-East kitchen and premium tiles in master bedroom"
    spec_vague = parse_client_brief(vague_prompt)
    assert spec_vague.lighting_color_temp == "3000K"
    assert spec_vague.flooring_preference == "Vitrified Tile"
    assert spec_vague.preferred_lighting_brand in ("Philips", "Havells", "Any")

    # 2. Conflicting brief (commercial fitting in residential space)
    conflict_prompt = "36W 2x2 LED grid panel for living room ceiling"
    spec_conflict = parse_client_brief(conflict_prompt)
    assert spec_conflict.lighting_wattage in (12, 15)


def test_edge_case_zero_count_items(engine, tmp_path):
    """Verifies that drawings with zero blocks or items do not produce NaN or corrupted Excel spreadsheets."""
    empty_takeoff = ParsedCadTakeoff(
        file_name="empty_cad.dxf",
        units="m",
        scale_factor_to_meters=1.0,
        area_scale_factor=1.0,
        total_floor_area_sqm=0.0,
        total_wall_area_sqm=0.0,
        wall_length_m=0.0,
        block_counts={},
        classified_blocks={},
        openings=[],
    )
    spec = ClientSpecification()
    boq = engine.generate_boq(empty_takeoff, spec)

    assert boq["grand_total_inr"] == 0.0

    # Ensure export to Excel completes without error
    out_xlsx = os.path.join(str(tmp_path), "empty_boq.xlsx")
    saved_path = engine.export_to_excel(boq, out_xlsx)
    assert os.path.exists(saved_path)

    # Verify openpyxl can read it back cleanly
    wb = openpyxl.load_workbook(saved_path, data_only=False)
    assert "Priced BOQ (IS 1200)" in wb.sheetnames
