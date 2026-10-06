"""test_cases_generator.py — Synthetic CAD Generator for Real-World Scenarios and Edge Cases

Generates 5 dedicated benchmark .DXF drawings in samples/:
1. use_case_1_2bhk_rcp.dxf — Mid-Market 2BHK Residential Apartment (110 sqm) with Reflected Ceiling Plan (RCP)
2. use_case_2_villa_glazing.dxf — High-End Custom Villa (330 sqm) with Tier 3 Large Openings (>3.0 sqm) & Sunken Slabs
3. use_case_3_commercial_office.dxf — Commercial Office Fit-Out (186 sqm / 2,000 sqft) with non-standard layers
4. use_case_4_predcr_sanction.dxf — Municipal Single-Window Sanction Package with strict PreDCR layers
5. edge_cases_geometry.dxf — Critical Edge Cases (unclosed polylines, nested blocks, exploded circles, 3D vertices)
"""

from __future__ import annotations

import os
import ezdxf


def generate_use_case_1_2bhk_rcp(output_path: str = "samples/use_case_1_2bhk_rcp.dxf") -> str:
    """Use Case 1: Standard 2BHK/3BHK Residential Apartment (Mid-Market) with Reflected Ceiling Plan (RCP)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Layers
    doc.layers.add(name="A-WALL", color=7)
    doc.layers.add(name="A-DOOR", color=1)
    doc.layers.add(name="A-GLAZ", color=4)
    doc.layers.add(name="A-FLOR-TILE", color=8)
    doc.layers.add(name="RCP-LIGHT", color=2)
    doc.layers.add(name="RCP-FAN", color=3)
    doc.layers.add(name="E-SWITCH-SOCKET", color=5)
    doc.layers.add(name="A-PLUMB-CORE", color=6)

    # Reusable Blocks
    # 12W Downlight
    b_light = doc.blocks.new(name="RECESSED_DOWNLIGHT_12W")
    b_light.add_circle(center=(0, 0), radius=75, dxfattribs={"color": 2})
    b_light.add_line(start=(-75, 0), end=(75, 0), dxfattribs={"color": 2})
    b_light.add_line(start=(0, -75), end=(0, 75), dxfattribs={"color": 2})

    # BLDC Ceiling Fan
    b_fan = doc.blocks.new(name="BLDC_CEILING_FAN_1200MM")
    b_fan.add_circle(center=(0, 0), radius=150, dxfattribs={"color": 3})
    b_fan.add_line(start=(0, 0), end=(0, 600), dxfattribs={"color": 3})
    b_fan.add_line(start=(0, 0), end=(-520, -300), dxfattribs={"color": 3})
    b_fan.add_line(start=(0, 0), end=(520, -300), dxfattribs={"color": 3})

    # Modular Switch 6A
    b_sw = doc.blocks.new(name="MODULAR_SWITCH_6A")
    b_sw.add_lwpolyline([(0, 0), (120, 0), (120, 60), (0, 60)], close=True, dxfattribs={"color": 5})

    # Power Socket 16A
    b_soc = doc.blocks.new(name="POWER_SOCKET_16A")
    b_soc.add_lwpolyline([(0, 0), (150, 0), (150, 80), (0, 80)], close=True, dxfattribs={"color": 5})

    # Sanitaryware: EWC and Basin
    b_ewc = doc.blocks.new(name="EWC_WALL_HUNG")
    b_ewc.add_lwpolyline([(0, 0), (380, 0), (380, 560), (0, 560)], close=True, dxfattribs={"color": 6})
    b_bsn = doc.blocks.new(name="WASH_BASIN_COUNTER")
    b_bsn.add_lwpolyline([(0, 0), (550, 0), (550, 400), (0, 400)], close=True, dxfattribs={"color": 6})

    # Doors & Windows
    b_d1 = doc.blocks.new(name="DOOR_MAIN_1000X2100")
    b_d1.add_line((0, 0), (1000, 0), dxfattribs={"color": 1})
    b_d2 = doc.blocks.new(name="DOOR_BED_900X2100")
    b_d2.add_line((0, 0), (900, 0), dxfattribs={"color": 1})
    b_d3 = doc.blocks.new(name="DOOR_TOILET_750X2100")
    b_d3.add_line((0, 0), (750, 0), dxfattribs={"color": 1})

    b_w1 = doc.blocks.new(name="WINDOW_BED_1500X1200")
    b_w1.add_lwpolyline([(0, 0), (1500, 0), (1500, 230), (0, 230)], close=True, dxfattribs={"color": 4})
    b_v1 = doc.blocks.new(name="VENT_TOILET_600X600")
    b_v1.add_lwpolyline([(0, 0), (600, 0), (600, 230), (0, 230)], close=True, dxfattribs={"color": 4})

    # Floor Polylines & Walls (11.0m x 10.0m = 110.0 sq.m)
    msp.add_lwpolyline([(0, 0), (11000, 0), (11000, 10000), (0, 10000)], close=True, dxfattribs={"layer": "A-WALL"})
    msp.add_lwpolyline([(0, 0), (11000, 0), (11000, 10000), (0, 10000)], close=True, dxfattribs={"layer": "A-FLOR-TILE"})

    # Internal Wall Partitions
    msp.add_line((0, 5000), (11000, 5000), dxfattribs={"layer": "A-WALL"})
    msp.add_line((5500, 0), (5500, 5000), dxfattribs={"layer": "A-WALL"})
    msp.add_line((7500, 5000), (7500, 10000), dxfattribs={"layer": "A-WALL"})

    # Insert 18x 12W Downlights in Living & Bedrooms
    downlight_coords = [
        # Living/Dining (6 lights)
        (1500, 7500), (3500, 7500), (5500, 7500),
        (1500, 9000), (3500, 9000), (5500, 9000),
        # Master Bedroom (6 lights)
        (8500, 6500), (10000, 6500),
        (8500, 8000), (10000, 8000),
        (8500, 9200), (10000, 9200),
        # Bedroom 2 (6 lights)
        (1500, 1500), (3500, 1500),
        (1500, 3000), (3500, 3000),
        (1500, 4200), (3500, 4200),
    ]
    for pt in downlight_coords:
        msp.add_blockref("RECESSED_DOWNLIGHT_12W", pt, dxfattribs={"layer": "RCP-LIGHT"})

    # Insert 3x BLDC Ceiling Fans
    msp.add_blockref("BLDC_CEILING_FAN_1200MM", (3500, 8250), dxfattribs={"layer": "RCP-FAN"})  # Living
    msp.add_blockref("BLDC_CEILING_FAN_1200MM", (9250, 7500), dxfattribs={"layer": "RCP-FAN"})  # Master Bed
    msp.add_blockref("BLDC_CEILING_FAN_1200MM", (2500, 2500), dxfattribs={"layer": "RCP-FAN"})  # Bed 2

    # Insert 8x Modular Switches & 4x 16A Sockets
    switch_coords = [
        (200, 5200), (200, 7000), (5700, 5200), (7700, 5200),
        (7700, 9800), (200, 4800), (200, 200), (5300, 200)
    ]
    for pt in switch_coords:
        msp.add_blockref("MODULAR_SWITCH_6A", pt, dxfattribs={"layer": "E-SWITCH-SOCKET"})

    socket_coords = [(1000, 5200), (9500, 5200), (1000, 200), (8000, 200)]
    for pt in socket_coords:
        msp.add_blockref("POWER_SOCKET_16A", pt, dxfattribs={"layer": "E-SWITCH-SOCKET"})

    # Sanitaryware: 2x EWC and 2x Basins
    msp.add_blockref("EWC_WALL_HUNG", (6000, 1000), dxfattribs={"layer": "A-PLUMB-CORE"})
    msp.add_blockref("EWC_WALL_HUNG", (9000, 1000), dxfattribs={"layer": "A-PLUMB-CORE"})
    msp.add_blockref("WASH_BASIN_COUNTER", (6000, 2000), dxfattribs={"layer": "A-PLUMB-CORE"})
    msp.add_blockref("WASH_BASIN_COUNTER", (9000, 2000), dxfattribs={"layer": "A-PLUMB-CORE"})

    # Insert Openings: Doors, Windows, Ventilators
    msp.add_blockref("DOOR_MAIN_1000X2100", (0, 6000), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_BED_900X2100", (7500, 5500), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_BED_900X2100", (5000, 4000), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_TOILET_750X2100", (5500, 3000), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("WINDOW_BED_1500X1200", (3000, 0), dxfattribs={"layer": "A-GLAZ"})
    msp.add_blockref("WINDOW_BED_1500X1200", (9000, 10000), dxfattribs={"layer": "A-GLAZ"})
    msp.add_blockref("VENT_TOILET_600X600", (7000, 0), dxfattribs={"layer": "A-GLAZ"})

    doc.saveas(output_path)
    return output_path


def generate_use_case_2_villa_glazing(output_path: str = "samples/use_case_2_villa_glazing.dxf") -> str:
    """Use Case 2: High-End Custom Villa with Sunken Slabs & Large French Glazing (> 3.0 sq.m Tier 3)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Layers
    doc.layers.add(name="A-WALL", color=7)
    doc.layers.add(name="A-DOOR", color=1)
    doc.layers.add(name="A-GLAZ", color=4)
    doc.layers.add(name="FLOOR_MARBLE", color=8)
    doc.layers.add(name="SUNKEN_SLAB", color=6)
    doc.layers.add(name="FALSE_CEIL_COVE", color=9)
    doc.layers.add(name="E-LITE-PREMIUM", color=2)
    doc.layers.add(name="PLUMB_JAQUAR", color=6)

    # Reusable Blocks
    # French Door 3.0m x 2.4m = 7.2 sqm (> 3.0 sqm -> Tier 3 Plaster Deduction)
    b_french = doc.blocks.new(name="FRENCH_SLIDING_3000X2400")
    b_french.add_lwpolyline([(0, 0), (3000, 0), (3000, 230), (0, 230)], close=True, dxfattribs={"color": 1})

    # Large Panoramic Window 2.5m x 1.5m = 3.75 sqm (> 3.0 sqm -> Tier 3 Plaster Deduction)
    b_pano = doc.blocks.new(name="PANORAMIC_WINDOW_2500X1500")
    b_pano.add_lwpolyline([(0, 0), (2500, 0), (2500, 230), (0, 230)], close=True, dxfattribs={"color": 4})

    # 15W Dimmable Downlight & Magnetic Track Light
    b_dim = doc.blocks.new(name="DOWNLIGHT_15W_DIMMABLE")
    b_dim.add_circle(center=(0, 0), radius=90, dxfattribs={"color": 2})

    b_trk = doc.blocks.new(name="MAGNETIC_TRACK_LIGHT_20W")
    b_trk.add_lwpolyline([(0, 0), (1000, 0), (1000, 50), (0, 50)], close=True, dxfattribs={"color": 2})

    # Jaquar Premium Sanitaryware
    b_jwc = doc.blocks.new(name="JAQUAR_PREMIUM_WC")
    b_jwc.add_lwpolyline([(0, 0), (400, 0), (400, 650), (0, 650)], close=True, dxfattribs={"color": 6})
    b_jbsn = doc.blocks.new(name="JAQUAR_ARTIZE_BASIN")
    b_jbsn.add_lwpolyline([(0, 0), (600, 0), (600, 450), (0, 450)], close=True, dxfattribs={"color": 6})

    # Sunken Slab Drainage Trap
    b_trap = doc.blocks.new(name="SUNKEN_SLAB_FLOOR_TRAP_100MM")
    b_trap.add_circle(center=(0, 0), radius=100, dxfattribs={"color": 6})

    # Multi-story Villa Footprint (22.0m x 15.0m = 330.0 sq.m)
    msp.add_lwpolyline([(0, 0), (22000, 0), (22000, 15000), (0, 15000)], close=True, dxfattribs={"layer": "A-WALL"})
    msp.add_lwpolyline([(0, 0), (22000, 0), (22000, 15000), (0, 15000)], close=True, dxfattribs={"layer": "FLOOR_MARBLE"})
    msp.add_lwpolyline([(500, 500), (21500, 500), (21500, 14500), (500, 14500)], close=True, dxfattribs={"layer": "FALSE_CEIL_COVE"})

    # Internal partitions (120m wall length)
    msp.add_line((0, 7500), (22000, 7500), dxfattribs={"layer": "A-WALL"})
    msp.add_line((11000, 0), (11000, 15000), dxfattribs={"layer": "A-WALL"})
    msp.add_line((16500, 0), (16500, 7500), dxfattribs={"layer": "A-WALL"})

    # Sunken Slabs for Toilets & Plumbing (2x 15 sqm sunken areas)
    msp.add_lwpolyline([(16500, 0), (22000, 0), (22000, 3000), (16500, 3000)], close=True, dxfattribs={"layer": "SUNKEN_SLAB"})
    msp.add_lwpolyline([(16500, 4000), (22000, 4000), (22000, 7000), (16500, 7000)], close=True, dxfattribs={"layer": "SUNKEN_SLAB"})

    # Insert 2x Large French Doors (3.0m x 2.4m = 7.2 sqm each) -> Total 14.4 sqm Tier 3 Plaster!
    msp.add_blockref("FRENCH_SLIDING_3000X2400", (2000, 0), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("FRENCH_SLIDING_3000X2400", (6000, 0), dxfattribs={"layer": "A-DOOR"})

    # Insert 2x Panoramic Windows (2.5m x 1.5m = 3.75 sqm each) -> Tier 3 Plaster!
    msp.add_blockref("PANORAMIC_WINDOW_2500X1500", (12000, 15000), dxfattribs={"layer": "A-GLAZ"})
    msp.add_blockref("PANORAMIC_WINDOW_2500X1500", (17000, 15000), dxfattribs={"layer": "A-GLAZ"})

    # 15W Dimmable Downlights & Magnetic Track
    for x in range(2000, 10000, 2000):
        for y in range(2000, 7000, 2000):
            msp.add_blockref("DOWNLIGHT_15W_DIMMABLE", (x, y), dxfattribs={"layer": "E-LITE-PREMIUM"})
    msp.add_blockref("MAGNETIC_TRACK_LIGHT_20W", (4000, 4000), dxfattribs={"layer": "E-LITE-PREMIUM"})
    msp.add_blockref("MAGNETIC_TRACK_LIGHT_20W", (4000, 5500), dxfattribs={"layer": "E-LITE-PREMIUM"})

    # Sanitaryware & Sunken Floor Traps
    msp.add_blockref("JAQUAR_PREMIUM_WC", (18000, 1000), dxfattribs={"layer": "PLUMB_JAQUAR"})
    msp.add_blockref("JAQUAR_ARTIZE_BASIN", (20000, 1000), dxfattribs={"layer": "PLUMB_JAQUAR"})
    msp.add_blockref("SUNKEN_SLAB_FLOOR_TRAP_100MM", (19000, 1500), dxfattribs={"layer": "SUNKEN_SLAB"})
    msp.add_blockref("SUNKEN_SLAB_FLOOR_TRAP_100MM", (19000, 5500), dxfattribs={"layer": "SUNKEN_SLAB"})

    doc.saveas(output_path)
    return output_path


def generate_use_case_3_commercial_office(output_path: str = "samples/use_case_3_commercial_office.dxf") -> str:
    """Use Case 3: Commercial Office Fit-Out (186 sqm / 2,000 sqft) with non-standard layers."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Non-standard Commercial Layer Names
    doc.layers.add(name="ELEC_NEW", color=5)
    doc.layers.add(name="PARTITION_GLASS", color=7)
    doc.layers.add(name="GRID_LIGHT", color=2)
    doc.layers.add(name="CARPET_FLOOR", color=8)
    doc.layers.add(name="ACOUSTIC_CEIL", color=9)
    doc.layers.add(name="HVAC_DIFFUSER", color=4)

    # Reusable Commercial Blocks
    # 600x600 2x2 LED Grid Panel (36W)
    b_grid = doc.blocks.new(name="GRID_LIGHT_600X600_36W")
    b_grid.add_lwpolyline([(0, 0), (600, 0), (600, 600), (0, 600)], close=True, dxfattribs={"color": 2})

    # Track Light
    b_trk = doc.blocks.new(name="TRACK_LIGHT_20W")
    b_trk.add_lwpolyline([(0, 0), (1200, 0), (1200, 60), (0, 60)], close=True, dxfattribs={"color": 2})

    # AC 4-Way Diffuser
    b_ac = doc.blocks.new(name="HVAC_DIFFUSER_4WAY")
    b_ac.add_lwpolyline([(0, 0), (600, 0), (600, 600), (0, 600)], close=True, dxfattribs={"color": 4})
    b_ac.add_line((0, 0), (600, 600), dxfattribs={"color": 4})
    b_ac.add_line((600, 0), (0, 600), dxfattribs={"color": 4})

    # Open-plan office envelope (18.6m x 10.0m = 186.0 sq.m / 2,002 sq.ft)
    msp.add_lwpolyline([(0, 0), (18600, 0), (18600, 10000), (0, 10000)], close=True, dxfattribs={"layer": "CARPET_FLOOR"})
    msp.add_lwpolyline([(0, 0), (18600, 0), (18600, 10000), (0, 10000)], close=True, dxfattribs={"layer": "ACOUSTIC_CEIL"})

    # 50mm Aluminium Glass Partitions (Conference Room & Cabin, 28 meters total)
    msp.add_lwpolyline([(0, 6000), (6000, 6000), (6000, 10000)], close=False, dxfattribs={"layer": "PARTITION_GLASS"})
    msp.add_lwpolyline([(6000, 6000), (12000, 6000), (12000, 10000)], close=False, dxfattribs={"layer": "PARTITION_GLASS"})

    # Insert 24x 600x600 2x2 LED Grid Panels across the acoustic ceiling grid
    for x in range(1500, 18000, 2400):
        for y in range(1500, 9000, 2000):
            msp.add_blockref("GRID_LIGHT_600X600_36W", (x, y), dxfattribs={"layer": "GRID_LIGHT"})

    # Insert 8x Track Lights in Corridor & Display
    for x in range(2000, 18000, 2000):
        msp.add_blockref("TRACK_LIGHT_20W", (x, 500), dxfattribs={"layer": "GRID_LIGHT"})

    # Insert 6x HVAC 4-Way Diffusers
    diffuser_coords = [(3000, 3000), (8000, 3000), (14000, 3000), (3000, 8000), (8000, 8000), (14000, 8000)]
    for pt in diffuser_coords:
        msp.add_blockref("HVAC_DIFFUSER_4WAY", pt, dxfattribs={"layer": "HVAC_DIFFUSER"})

    # Modular floor power boxes on ELEC_NEW
    for x in range(2000, 18000, 3000):
        msp.add_line((x, 2000), (x, 4000), dxfattribs={"layer": "ELEC_NEW"})

    doc.saveas(output_path)
    return output_path


def generate_use_case_4_predcr_sanction(output_path: str = "samples/use_case_4_predcr_sanction.dxf") -> str:
    """Use Case 4: PreDCR Municipal Sanction Drawing Package with strict AutoDCR layers."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Strict PreDCR Layer Conventions (Pune/Mumbai/Delhi municipal sanction format)
    doc.layers.add(name="_PLOT", color=1)
    doc.layers.add(name="_MARGINLINE", color=2)
    doc.layers.add(name="_BUILDING", color=3)
    doc.layers.add(name="_PROPOSED WORK", color=7)
    doc.layers.add(name="_RESIMAIN", color=4)
    doc.layers.add(name="_CARPET AREA", color=8)
    doc.layers.add(name="_DOOR", color=1)
    doc.layers.add(name="_WINDOW", color=5)

    # Plot Boundary (15m x 20m = 300 sqm)
    msp.add_lwpolyline([(0, 0), (15000, 0), (15000, 20000), (0, 20000)], close=True, dxfattribs={"layer": "_PLOT"})

    # Margin Line (Setbacks: 3m front, 2m sides, 2m rear)
    msp.add_lwpolyline([(2000, 3000), (13000, 3000), (13000, 18000), (2000, 18000)], close=True, dxfattribs={"layer": "_MARGINLINE"})

    # Proposed Building Envelope (11m x 15m = 165 sqm)
    msp.add_lwpolyline([(2000, 3000), (13000, 3000), (13000, 18000), (2000, 18000)], close=True, dxfattribs={"layer": "_PROPOSED WORK"})

    # Main Residential Flat 1 (_RESIMAIN: 70 sqm)
    msp.add_lwpolyline([(2000, 3000), (9000, 3000), (9000, 13000), (2000, 13000)], close=True, dxfattribs={"layer": "_RESIMAIN"})

    # Municipal Carpet Area Polylines (_CARPET AREA: 65 sqm net)
    msp.add_lwpolyline([(2230, 3230), (8770, 3230), (8770, 12770), (2230, 12770)], close=True, dxfattribs={"layer": "_CARPET AREA"})

    # Doors and Windows on municipal layers
    doc.blocks.new(name="PREDCR_D1").add_line((0, 0), (1000, 0), dxfattribs={"color": 1})
    doc.blocks.new(name="PREDCR_W1").add_line((0, 0), (1500, 0), dxfattribs={"color": 5})

    msp.add_blockref("PREDCR_D1", (2000, 5000), dxfattribs={"layer": "_DOOR"})
    msp.add_blockref("PREDCR_D1", (5000, 3000), dxfattribs={"layer": "_DOOR"})
    msp.add_blockref("PREDCR_W1", (2000, 9000), dxfattribs={"layer": "_WINDOW"})
    msp.add_blockref("PREDCR_W1", (8000, 13000), dxfattribs={"layer": "_WINDOW"})

    doc.saveas(output_path)
    return output_path


def generate_edge_cases_geometry(output_path: str = "samples/edge_cases_geometry.dxf") -> str:
    """Critical Edge Cases: Unclosed polylines (0.02m gap), nested blocks, exploded circles, 3D vertices."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Layers
    doc.layers.add(name="FLOOR_UNCLOSED", color=8)
    doc.layers.add(name="LIGHTS_EXPLODED", color=2)
    doc.layers.add(name="WALLS_3D", color=7)
    doc.layers.add(name="FURN_NESTED", color=3)

    # 1. Unclosed Polyline with 0.02m (20mm) drafting gap
    # Start: (0, 0), End: (0, 20) -> Gap is 20mm (0.02m)
    unclosed_pts = [(0, 0), (10000, 0), (10000, 8000), (0, 8000), (0, 20)]
    msp.add_lwpolyline(unclosed_pts, close=False, dxfattribs={"layer": "FLOOR_UNCLOSED"})

    # 2. Nested Blocks: A compound WORKSTATION_POD block containing child blocks
    b_desk = doc.blocks.new(name="OFFICE_DESK")
    b_desk.add_lwpolyline([(0, 0), (1200, 0), (1200, 600), (0, 600)], close=True, dxfattribs={"color": 3})

    b_chair = doc.blocks.new(name="TASK_CHAIR")
    b_chair.add_circle(center=(600, -300), radius=250, dxfattribs={"color": 3})

    b_pod = doc.blocks.new(name="WORKSTATION_POD")
    b_pod.add_blockref("OFFICE_DESK", (0, 0))
    b_pod.add_blockref("TASK_CHAIR", (0, 0))

    # Insert 4x Workstation Pods
    msp.add_blockref("WORKSTATION_POD", (2000, 2000), dxfattribs={"layer": "FURN_NESTED"})
    msp.add_blockref("WORKSTATION_POD", (5000, 2000), dxfattribs={"layer": "FURN_NESTED"})

    # 3. Exploded Geometry: Downlights drawn as raw CIRCLEs on LIGHTS_EXPLODED layer (no block reference)
    for x in range(2000, 8000, 1500):
        msp.add_circle(center=(x, 5000), radius=100, dxfattribs={"layer": "LIGHTS_EXPLODED"})

    # 4. 3D Non-Planar Polyline (Z = 3500 mm)
    p3d = msp.add_polyline3d(
        [(1000, 1000, 3500), (5000, 1000, 3500), (5000, 4000, 3500), (1000, 4000, 3500)],
        close=True,
        dxfattribs={"layer": "WALLS_3D"}
    )

    doc.saveas(output_path)
    return output_path


def generate_all_test_drawings() -> dict[str, str]:
    """Generates all 5 benchmark CAD test drawings."""
    return {
        "use_case_1": generate_use_case_1_2bhk_rcp(),
        "use_case_2": generate_use_case_2_villa_glazing(),
        "use_case_3": generate_use_case_3_commercial_office(),
        "use_case_4": generate_use_case_4_predcr_sanction(),
        "edge_cases": generate_edge_cases_geometry(),
    }


if __name__ == "__main__":
    results = generate_all_test_drawings()
    print("Successfully generated all benchmark DXF test drawings:")
    for k, v in results.items():
        print(f" - {k}: {v}")
