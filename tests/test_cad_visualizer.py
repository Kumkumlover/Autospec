"""Unit tests for Interactive CAD Visualizer (cad_visualizer.py)."""

import os

import plotly.graph_objects as go
import pytest

from cad_parser import parse_cad_file
from cad_visualizer import CadVisualizer
from sample_dxf_generator import generate_sample_2bhk_dxf


@pytest.fixture(scope="session")
def sample_dxf(tmp_path_factory):
    p = tmp_path_factory.mktemp("cad_viz") / "test_viz_2bhk.dxf"
    generate_sample_2bhk_dxf(str(p))
    return str(p)


def test_visualizer_generates_plotly_figure(sample_dxf):
    takeoff = parse_cad_file(sample_dxf)
    viz = CadVisualizer(takeoff)
    fig = viz.build_interactive_figure()

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0

    trace_names = [t.name for t in fig.data]
    assert any("Walls" in n for n in trace_names)
    assert any("Openings" in n for n in trace_names)
    assert any("Lighting" in n for n in trace_names)
    assert any("Fans" in n for n in trace_names)

    # 1:1 isometric architectural aspect ratio check
    assert fig.layout.xaxis.scaleratio == 1
    assert fig.layout.xaxis.scaleanchor == "y"


def test_visualizer_dwg_two_story_house():
    dwg_file = "samples/two_story_house.dwg"
    assert os.path.exists(dwg_file)

    takeoff = parse_cad_file(dwg_file)
    assert len(takeoff.block_instances) > 0
    assert len(takeoff.wall_segments) > 0

    viz = CadVisualizer(takeoff)
    fig = viz.build_interactive_figure()

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    trace_names = [t.name for t in fig.data]
    assert any("Walls" in n for n in trace_names)
    assert any("Openings" in n for n in trace_names)


def test_visualizer_trade_filtering(sample_dxf):
    takeoff = parse_cad_file(sample_dxf)
    viz = CadVisualizer(takeoff)

    # Filter to only Lighting
    fig_filtered = viz.build_interactive_figure(visible_trades=["Electrical - Lighting"])
    names = [t.name for t in fig_filtered.data]

    assert any("Lighting" in n for n in names)
    assert not any("Fans" in n for n in names)
    assert not any("Walls" in n for n in names)


def test_visualizer_blueprint_raster_image(sample_dxf):
    takeoff = parse_cad_file(sample_dxf)
    viz = CadVisualizer(takeoff)
    png_bytes = viz.generate_blueprint_image(sample_dxf, dpi=72)

    assert png_bytes is not None
    assert len(png_bytes) > 1000
    # Valid PNG header magic bytes
    assert png_bytes.startswith(b"\x89PNG")


def test_visualizer_dwg_apartment_1():
    dwg_file = "samples/Apartment-1.dwg"
    if not os.path.exists(dwg_file):
        pytest.skip("Apartment-1.dwg not present in samples/")

    takeoff = parse_cad_file(dwg_file)
    assert takeoff.units == "m"
    assert len(takeoff.block_instances) > 0
    assert len(takeoff.wall_segments) > 0
    assert takeoff.total_wall_area_sqm > 100.0

    viz = CadVisualizer(takeoff)
    fig = viz.build_interactive_figure()

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    trace_names = [t.name for t in fig.data]
    assert any("Walls" in n for n in trace_names)
    assert any("Openings" in n for n in trace_names)


def test_visualizer_two_tier_linework():
    dwg_file = "samples/Apartment-1.dwg"
    if not os.path.exists(dwg_file):
        pytest.skip("Apartment-1.dwg not present in samples/")

    takeoff = parse_cad_file(dwg_file)
    linework = getattr(takeoff, "architectural_linework", {})
    assert "walls" in linework and len(linework["walls"]) > 100
    assert "doors" in linework and len(linework["doors"]) > 100
    assert "windows" in linework and len(linework["windows"]) > 10
    assert "furniture" in linework and len(linework["furniture"]) > 1000

    viz = CadVisualizer(takeoff)
    fig_focus = viz.build_interactive_figure(focus_mode="takeoff_focus", label_mode="openings")
    assert isinstance(fig_focus, go.Figure)

    names = [t.name for t in fig_focus.data]
    assert any("Walls" in n for n in names)
    assert any("Doors" in n for n in names)
    assert any("Furniture" in n for n in names)
    assert any("Windows" in n for n in names)


def test_visualizer_themes_and_opening_coordinates(sample_dxf):
    takeoff = parse_cad_file(sample_dxf)
    viz = CadVisualizer(takeoff)

    # 1. Dark theme (AutoCAD Model Space)
    fig_dark = viz.build_interactive_figure(theme="dark", dark_mode=True)
    assert fig_dark.layout.plot_bgcolor == "#0D1117"
    assert fig_dark.layout.paper_bgcolor == "#0D1117"

    # 2. Light theme (Drafting Paper - high contrast)
    fig_light = viz.build_interactive_figure(theme="light", dark_mode=False)
    assert fig_light.layout.plot_bgcolor == "#FFFFFF"
    assert fig_light.layout.paper_bgcolor == "#FFFFFF"

    # 3. Blueprint Navy theme
    fig_blue = viz.build_interactive_figure(theme="blueprint")
    assert fig_blue.layout.plot_bgcolor == "#0B1D3A"

    # 4. Opening coordinates verification
    assert len(takeoff.openings) > 0
    # At least some openings should have valid x, y coordinates
    coords = [(op.x, op.y) for op in takeoff.openings if op.x is not None and op.y is not None]
    assert len(coords) > 0

