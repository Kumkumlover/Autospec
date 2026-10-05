"""Unit tests for Statutory IS 1200 Rules Engine (boq_engine.py)."""

import pytest

from boq_engine import BoqEngine
from cad_parser import OpeningItem


@pytest.fixture
def engine():
    return BoqEngine()


# =============================================================================
# IS 1200 PART 4: MASONRY DEDUCTION TESTS
# =============================================================================


def test_is1200_masonry_small_opening_exempt(engine):
    """Openings <= 0.1 sq.m must have ZERO deduction."""
    wall_length = 10.0
    wall_height = 3.0
    wall_thickness = 0.23

    # Small opening: 0.2m x 0.4m = 0.08 sqm (<= 0.10 sqm)
    openings = [OpeningItem(id="OP-01", type="Pipe", width_m=0.2, height_m=0.4, area_sqm=0.08)]
    res = engine.calculate_is1200_masonry(wall_length, wall_height, wall_thickness, openings)

    assert res["total_deducted_area_sqm"] == 0.0
    assert res["total_deducted_volume_cum"] == 0.0
    assert res["net_masonry_volume_cum"] == round(wall_length * wall_height * wall_thickness, 2)


def test_is1200_masonry_boundary_case(engine):
    """Exactly 0.10 sq.m is exempt; 0.11 sq.m is deducted."""
    wall_thickness = 0.23
    openings = [
        OpeningItem(id="OP-EXACT", type="Vent", width_m=0.2, height_m=0.5, area_sqm=0.10),
        OpeningItem(id="OP-ABOVE", type="Vent", width_m=0.22, height_m=0.5, area_sqm=0.11),
    ]
    res = engine.calculate_is1200_masonry(10.0, 3.0, wall_thickness, openings)

    # Only OP-ABOVE (0.11) is deducted
    assert res["total_deducted_area_sqm"] == 0.11
    assert abs(res["total_deducted_volume_cum"] - (0.11 * wall_thickness)) < 0.01


def test_is1200_masonry_standard_door(engine):
    """Door 1.0m x 2.1m = 2.1 m2 (> 0.1 m2) must be fully deducted."""
    wall_thickness = 0.23
    openings = [OpeningItem(id="D1", type="Door", width_m=1.0, height_m=2.1, area_sqm=2.1)]
    res = engine.calculate_is1200_masonry(10.0, 3.0, wall_thickness, openings)

    assert res["total_deducted_area_sqm"] == 2.1
    expected_vol = round((30.0 - 2.1) * wall_thickness, 2)
    assert res["net_masonry_volume_cum"] == expected_vol


# =============================================================================
# IS 1200 PART 12: PLASTERING DEDUCTION TESTS
# =============================================================================


def test_is1200_plaster_tier1_exempt(engine):
    """Openings <= 0.5 sq.m: Zero deduction, no reveals added."""
    gross_wall_area = 50.0  # one face (both faces = 100.0)
    openings = [OpeningItem(id="V1", type="Ventilator", width_m=0.6, height_m=0.6, area_sqm=0.36)]

    res = engine.calculate_is1200_plaster(gross_wall_area, openings)

    assert res["total_opening_deduction_sqm"] == 0.0
    assert res["total_reveal_addition_sqm"] == 0.0
    assert res["net_plaster_area_sqm"] == 100.0


def test_is1200_plaster_tier2_single_face(engine):
    """Openings 0.5 < A <= 3.0 sq.m: Deduct single face (1.0 * A), no reveals added."""
    gross_wall_area = 50.0  # both faces = 100.0
    # Standard Door 1.0m x 2.1m = 2.10 sqm
    openings = [OpeningItem(id="D1", type="Door", width_m=1.0, height_m=2.1, area_sqm=2.1)]

    res = engine.calculate_is1200_plaster(gross_wall_area, openings)

    # 100.0 - 2.1 = 97.90 sqm
    assert res["total_opening_deduction_sqm"] == 2.1
    assert res["total_reveal_addition_sqm"] == 0.0
    assert res["net_plaster_area_sqm"] == 97.90


def test_is1200_plaster_tier3_both_faces_with_reveals(engine):
    """Openings > 3.0 sq.m: Deduct both faces (2.0 * A) and add reveals."""
    gross_wall_area = 50.0  # both faces = 100.0
    wall_thickness = 0.23
    # Large opening: 2.0m x 2.0m = 4.0 sqm (> 3.0 sqm)
    # Perimeter = 2 * (2 + 2) = 8.0 m
    # Reveal area = 8.0 * 0.23 = 1.84 sqm
    openings = [OpeningItem(id="W_LRG", type="Window", width_m=2.0, height_m=2.0, area_sqm=4.0)]

    res = engine.calculate_is1200_plaster(gross_wall_area, openings, wall_thickness_m=wall_thickness)

    assert res["total_opening_deduction_sqm"] == 8.0  # 2 * 4.0
    assert abs(res["total_reveal_addition_sqm"] - 1.84) < 0.01
    # Net = 100.0 - 8.0 + 1.84 = 93.84
    assert abs(res["net_plaster_area_sqm"] - 93.84) < 0.05
