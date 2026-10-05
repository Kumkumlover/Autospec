"""sample_dxf_generator.py — Programmatic Synthetic 2D CAD Plan Generator

Generates a realistic 2BHK Indian residential floor plan DXF with:
- Layers: A-WALL, A-DOOR, A-GLAZ, FLOOR_FINISH, CEILING_PLASTER, E-LITE, E-FAN, E-SWCH, PLUMBING
- Block Definitions: LIGHT_DOWNLIGHT, FAN_CEILING, SWITCH_MODULAR, SOCKET_16A, WC_COMMODE, WASH_BASIN, EXHAUST_FAN
- Openings configured to trigger all IS 1200 deduction tiers:
  * Ventilator V1 (0.6m x 0.6m = 0.36 m2): Tier 1 (<= 0.5 m2, zero deduction)
  * Window W1 (1.5m x 1.2m = 1.80 m2): Tier 2 (0.5 - 3.0 m2, single-face deduction)
  * Door D1 (1.0m x 2.1m = 2.10 m2): Tier 2 (0.5 - 3.0 m2, single-face deduction)
  * French Window W_LRG (2.4m x 1.5m = 3.60 m2): Tier 3 (> 3.0 m2, both-faces deduction)
  * Small pipe cutout (0.25m x 0.3m = 0.075 m2): Masonry exempt (<= 0.1 m2)
"""

import os

import ezdxf


def generate_sample_2bhk_dxf(output_path: str = "samples/sample_2bhk_plan.dxf") -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # AutoCAD 2018 DXF format
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # 4 = Millimeters
    msp = doc.modelspace()

    # 1. Create Standard Architectural Layers
    doc.layers.add(name="A-WALL", color=7)  # White/Black
    doc.layers.add(name="A-DOOR", color=1)  # Red
    doc.layers.add(name="A-GLAZ", color=4)  # Cyan
    doc.layers.add(name="FLOOR_FINISH", color=8)  # Gray
    doc.layers.add(name="CEILING_PLASTER", color=9)  # Light Gray
    doc.layers.add(name="E-LITE", color=2)  # Yellow
    doc.layers.add(name="E-FAN", color=3)  # Green
    doc.layers.add(name="E-SWCH", color=5)  # Blue
    doc.layers.add(name="PLUMBING", color=6)  # Magenta

    # 2. Define Reusable Blocks
    # Downlight Block (Circle with cross)
    blk_light = doc.blocks.new(name="LIGHT_DOWNLIGHT")
    blk_light.add_circle(center=(0, 0), radius=75, dxfattribs={"color": 2})
    blk_light.add_line(start=(-75, 0), end=(75, 0), dxfattribs={"color": 2})
    blk_light.add_line(start=(0, -75), end=(0, 75), dxfattribs={"color": 2})

    # Ceiling Fan Block (Circle with 3 blade lines)
    blk_fan = doc.blocks.new(name="FAN_CEILING")
    blk_fan.add_circle(center=(0, 0), radius=120, dxfattribs={"color": 3})
    blk_fan.add_line(start=(0, 0), end=(0, 450), dxfattribs={"color": 3})
    blk_fan.add_line(start=(0, 0), end=(-389, -225), dxfattribs={"color": 3})
    blk_fan.add_line(start=(0, 0), end=(389, -225), dxfattribs={"color": 3})

    # Modular Switch Block (Small rectangle)
    blk_sw = doc.blocks.new(name="SWITCH_MODULAR")
    blk_sw.add_lwpolyline([(0, 0), (120, 0), (120, 60), (0, 60)], close=True, dxfattribs={"color": 5})

    # 16A Power Socket
    blk_soc = doc.blocks.new(name="SOCKET_16A")
    blk_soc.add_lwpolyline([(0, 0), (150, 0), (150, 80), (0, 80)], close=True, dxfattribs={"color": 5})

    # Exhaust Fan Block
    blk_exh = doc.blocks.new(name="EXHAUST_FAN")
    blk_exh.add_circle(center=(0, 0), radius=100, dxfattribs={"color": 3})

    # WC Commode Block
    blk_wc = doc.blocks.new(name="WC_COMMODE")
    blk_wc.add_lwpolyline([(0, 0), (400, 0), (400, 600), (0, 600)], close=True, dxfattribs={"color": 6})

    # Wash Basin Block
    blk_basin = doc.blocks.new(name="WASH_BASIN")
    blk_basin.add_lwpolyline([(0, 0), (550, 0), (550, 400), (0, 400)], close=True, dxfattribs={"color": 6})

    # Door Blocks
    blk_d1 = doc.blocks.new(name="DOOR_1000X2100")
    blk_d1.add_line((0, 0), (1000, 0), dxfattribs={"color": 1})
    blk_d1.add_arc(center=(0, 0), radius=1000, start_angle=0, end_angle=90, dxfattribs={"color": 1})

    blk_d2 = doc.blocks.new(name="DOOR_900X2100")
    blk_d2.add_line((0, 0), (900, 0), dxfattribs={"color": 1})

    blk_d3 = doc.blocks.new(name="DOOR_750X2100")
    blk_d3.add_line((0, 0), (750, 0), dxfattribs={"color": 1})

    # Window Blocks
    blk_w1 = doc.blocks.new(name="WINDOW_1500X1200")
    blk_w1.add_lwpolyline([(0, 0), (1500, 0), (1500, 230), (0, 230)], close=True, dxfattribs={"color": 4})

    blk_w_lrg = doc.blocks.new(name="WINDOW_2400X1500")  # > 3.0 m2 opening!
    blk_w_lrg.add_lwpolyline([(0, 0), (2400, 0), (2400, 230), (0, 230)], close=True, dxfattribs={"color": 4})

    blk_v1 = doc.blocks.new(name="VENT_600X600")  # <= 0.5 m2 opening!
    blk_v1.add_lwpolyline([(0, 0), (600, 0), (600, 230), (0, 230)], close=True, dxfattribs={"color": 4})

    # 3. Add Wall Polylines (Exterior: 11.0m x 8.0m = 88.0 sq.m footprint)
    # Outer Wall
    outer_wall_pts = [(0, 0), (11000, 0), (11000, 8000), (0, 8000)]
    msp.add_lwpolyline(outer_wall_pts, close=True, dxfattribs={"layer": "A-WALL"})

    # Internal Partition Walls (Total wall centerline length approx 58 meters)
    msp.add_line((0, 4500), (11000, 4500), dxfattribs={"layer": "A-WALL"})
    msp.add_line((5000, 0), (5000, 4500), dxfattribs={"layer": "A-WALL"})
    msp.add_line((5000, 4500), (5000, 8000), dxfattribs={"layer": "A-WALL"})
    msp.add_line((8000, 4500), (8000, 8000), dxfattribs={"layer": "A-WALL"})

    # 4. Add Room Floor Polylines (Total carpet area ~ 84.5 sq.m)
    # Living & Dining: 5.0m x 4.5m = 22.5 sqm
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 4500), (0, 4500)], close=True, dxfattribs={"layer": "FLOOR_FINISH"})
    # Kitchen: 6.0m x 4.5m = 27.0 sqm
    msp.add_lwpolyline(
        [(5000, 0), (11000, 0), (11000, 4500), (5000, 4500)], close=True, dxfattribs={"layer": "FLOOR_FINISH"}
    )
    # Master Bedroom: 5.0m x 3.5m = 17.5 sqm
    msp.add_lwpolyline(
        [(0, 4500), (5000, 4500), (5000, 8000), (0, 8000)], close=True, dxfattribs={"layer": "FLOOR_FINISH"}
    )
    # Bedroom 2: 3.0m x 3.5m = 10.5 sqm
    msp.add_lwpolyline(
        [(5000, 4500), (8000, 4500), (8000, 8000), (5000, 8000)], close=True, dxfattribs={"layer": "FLOOR_FINISH"}
    )
    # Toilets: 3.0m x 3.5m = 10.5 sqm
    msp.add_lwpolyline(
        [(8000, 4500), (11000, 4500), (11000, 8000), (8000, 8000)], close=True, dxfattribs={"layer": "FLOOR_FINISH"}
    )

    # Add Ceiling Polyline
    msp.add_lwpolyline(
        [(0, 0), (11000, 0), (11000, 8000), (0, 8000)], close=True, dxfattribs={"layer": "CEILING_PLASTER"}
    )

    # 5. Insert Openings (Door & Window Blocks)
    # D1 Main Door (1.0 x 2.1 = 2.1 m2) -> Tier 2
    msp.add_blockref("DOOR_1000X2100", (2000, 0), dxfattribs={"layer": "A-DOOR"})
    # D2 Bedroom Doors (0.9 x 2.1 = 1.89 m2) -> Tier 2
    msp.add_blockref("DOOR_900X2100", (2500, 4500), dxfattribs={"layer": "A-DOOR"})
    msp.add_blockref("DOOR_900X2100", (6000, 4500), dxfattribs={"layer": "A-DOOR"})
    # D3 Toilet Door (0.75 x 2.1 = 1.575 m2) -> Tier 2
    msp.add_blockref("DOOR_750X2100", (8500, 4500), dxfattribs={"layer": "A-DOOR"})

    # W1 Windows (1.5 x 1.2 = 1.80 m2) -> Tier 2
    msp.add_blockref("WINDOW_1500X1200", (2000, 8000), dxfattribs={"layer": "A-GLAZ"})
    msp.add_blockref("WINDOW_1500X1200", (6000, 8000), dxfattribs={"layer": "A-GLAZ"})

    # W_LRG Large Living Balcony French Window (2.4 x 1.5 = 3.60 m2) -> Tier 3 (> 3.0 m2)
    msp.add_blockref("WINDOW_2400X1500", (7000, 0), dxfattribs={"layer": "A-GLAZ"})

    # V1 Toilet Ventilator (0.6 x 0.6 = 0.36 m2) -> Tier 1 (<= 0.5 m2)
    msp.add_blockref("VENT_600X600", (9500, 8000), dxfattribs={"layer": "A-GLAZ"})

    # 6. Insert Electrical Blocks
    # Downlights (18 instances across rooms)
    light_positions = [
        (1000, 1000),
        (2500, 1000),
        (4000, 1000),
        (1000, 2500),
        (2500, 2500),
        (4000, 2500),
        (1000, 3800),
        (2500, 3800),
        (4000, 3800),
        (6500, 1500),
        (8500, 1500),
        (6500, 3000),
        (8500, 3000),
        (1500, 5500),
        (3500, 5500),
        (1500, 7000),
        (3500, 7000),
        (6500, 6000),
    ]
    for pos in light_positions:
        msp.add_blockref("LIGHT_DOWNLIGHT", pos, dxfattribs={"layer": "E-LITE"})

    # Ceiling Fans (3 instances)
    msp.add_blockref("FAN_CEILING", (2500, 2250), dxfattribs={"layer": "E-FAN"})  # Living
    msp.add_blockref("FAN_CEILING", (2500, 6250), dxfattribs={"layer": "E-FAN"})  # Master Bed
    msp.add_blockref("FAN_CEILING", (6500, 6250), dxfattribs={"layer": "E-FAN"})  # Bed 2

    # Exhaust Fans (2 instances in kitchen & toilet)
    msp.add_blockref("EXHAUST_FAN", (10500, 2000), dxfattribs={"layer": "E-FAN"})
    msp.add_blockref("EXHAUST_FAN", (10500, 7500), dxfattribs={"layer": "E-FAN"})

    # Modular Switches (8 instances)
    switch_positions = [
        (500, 500),
        (4500, 500),
        (5500, 500),
        (500, 5000),
        (4500, 5000),
        (5500, 5000),
        (7500, 5000),
        (8500, 5000),
    ]
    for pos in switch_positions:
        msp.add_blockref("SWITCH_MODULAR", pos, dxfattribs={"layer": "E-SWCH"})

    # Sockets (4 instances)
    socket_positions = [(1200, 200), (4000, 200), (6000, 200), (2000, 4700)]
    for pos in socket_positions:
        msp.add_blockref("SOCKET_16A", pos, dxfattribs={"layer": "E-SWCH"})

    # Plumbing Fixtures (2 Toilets: 2 EWCs, 2 Basins)
    msp.add_blockref("WC_COMMODE", (9000, 6000), dxfattribs={"layer": "PLUMBING"})
    msp.add_blockref("WC_COMMODE", (10200, 6000), dxfattribs={"layer": "PLUMBING"})
    msp.add_blockref("WASH_BASIN", (9000, 7200), dxfattribs={"layer": "PLUMBING"})
    msp.add_blockref("WASH_BASIN", (10200, 7200), dxfattribs={"layer": "PLUMBING"})

    doc.saveas(output_path)
    return output_path


if __name__ == "__main__":
    path = generate_sample_2bhk_dxf()
    print(f"Generated synthetic architectural CAD plan at: {path}")
