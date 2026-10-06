"""Unit tests for CAD Vector Parser (cad_parser.py)."""

import os

import pytest

from cad_parser import CadParser, parse_dxf_file
from sample_dxf_generator import generate_sample_2bhk_dxf


@pytest.fixture(scope="session")
def sample_dxf_path(tmp_path_factory):
    dxf_file = tmp_path_factory.mktemp("cad") / "test_sample_2bhk.dxf"
    generate_sample_2bhk_dxf(str(dxf_file))
    return str(dxf_file)


def test_cad_parser_loads_dxf(sample_dxf_path):
    parser = CadParser(default_units="mm")
    takeoff = parser.parse_dxf_file(sample_dxf_path)

    assert takeoff is not None
    assert takeoff.units == "mm"
    assert takeoff.scale_factor_to_meters == 0.001


def test_cad_parser_block_counts(sample_dxf_path):
    takeoff = parse_dxf_file(sample_dxf_path)

    # Lighting
    assert takeoff.block_counts.get("LIGHT_DOWNLIGHT") == 18
    # Fans
    assert takeoff.block_counts.get("FAN_CEILING") == 3
    assert takeoff.block_counts.get("EXHAUST_FAN") == 2
    # Switches & Sockets
    assert takeoff.block_counts.get("SWITCH_MODULAR") == 8
    assert takeoff.block_counts.get("SOCKET_16A") == 4
    # Plumbing
    assert takeoff.block_counts.get("WC_COMMODE") == 2
    assert takeoff.block_counts.get("WASH_BASIN") == 2


def test_cad_parser_openings_detection(sample_dxf_path):
    takeoff = parse_dxf_file(sample_dxf_path)

    assert len(takeoff.openings) >= 6

    # Verify presence of different opening types
    types = [op.type for op in takeoff.openings]
    assert "Door" in types
    assert "Window" in types
    assert "Ventilator" in types

    # Check that D1 Main Door (1.0m x 2.1m = 2.1 m2) is present
    d1_ops = [op for op in takeoff.openings if abs(op.area_sqm - 2.1) < 0.05]
    assert len(d1_ops) >= 1
    assert d1_ops[0].width_m == 1.0
    assert d1_ops[0].height_m == 2.1


def test_cad_parser_surface_areas(sample_dxf_path):
    takeoff = parse_dxf_file(sample_dxf_path)

    # Footprint of 11.0m x 8.0m = 88.0 sqm
    assert abs(takeoff.total_floor_area_sqm - 88.0) < 5.0
    assert takeoff.total_wall_area_sqm > 50.0
    assert takeoff.total_ceiling_area_sqm > 50.0


def test_cad_parser_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_dxf_file("non_existent_file.dxf")


def test_cad_parser_dwg_support():
    """Verify DWG-to-DXF converter and takeoff parsing on two_story_house.dwg."""
    from cad_parser import is_dwg_converter_available, parse_cad_file

    assert is_dwg_converter_available() is True

    dwg_file = "samples/two_story_house.dwg"
    assert os.path.exists(dwg_file)

    takeoff = parse_cad_file(dwg_file)
    assert takeoff is not None
    assert takeoff.units == "m"
    assert takeoff.total_floor_area_sqm > 100.0
    assert takeoff.total_wall_area_sqm > 100.0
    assert len(takeoff.openings) >= 5
    assert any(op.type == "Door" for op in takeoff.openings)


def test_cad_parser_dwg_bytes_upload():
    """Verify parsing in-memory DWG bytes."""
    from cad_parser import parse_cad_file

    dwg_file = "samples/two_story_house.dwg"
    with open(dwg_file, "rb") as f:
        dwg_bytes = f.read()

    takeoff = parse_cad_file(dwg_bytes, filename="uploaded_user_house.dwg")
    assert takeoff is not None
    assert takeoff.file_name == "uploaded_user_house.dwg"
    assert takeoff.total_floor_area_sqm > 100.0


def test_cad_parser_image_file_conversion():
    """Verify raster floor plan image (.PNG/.JPG) ingestion and vector conversion."""
    from cad_parser import parse_cad_file

    img_file = "samples/test_render_sample.png"
    assert os.path.exists(img_file)

    takeoff = parse_cad_file(img_file)
    assert takeoff is not None
    assert takeoff.units == "m"
    assert takeoff.total_floor_area_sqm > 30.0
    assert takeoff.wall_length_m > 30.0
    assert len(takeoff.openings) >= 1


def test_cad_parser_image_bytes_upload():
    """Verify in-memory image bytes ingestion."""
    from cad_parser import parse_cad_file

    img_file = "samples/test_render_sample.png"
    with open(img_file, "rb") as f:
        img_bytes = f.read()

    takeoff = parse_cad_file(img_bytes, filename="my_scanned_plan.png")
    assert takeoff is not None
    assert takeoff.file_name == "my_scanned_plan.png"
    assert takeoff.total_floor_area_sqm > 30.0


def test_cad_parser_pdf_conversion(tmp_path):
    """Verify architectural PDF ingestion and vector conversion."""
    import pymupdf
    from cad_parser import parse_cad_file

    pdf_path = str(tmp_path / "architectural_sheet.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    # Draw floor plan rects
    shape = page.new_shape()
    shape.draw_rect(pymupdf.Rect(50, 50, 550, 750))
    shape.draw_line(pymupdf.Point(50, 400), pymupdf.Point(550, 400))
    shape.finish(width=2, color=(0, 0, 0))
    shape.commit()
    doc.save(pdf_path)
    doc.close()

    takeoff = parse_cad_file(pdf_path)
    assert takeoff is not None
    assert takeoff.total_floor_area_sqm > 10.0
