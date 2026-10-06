"""cad_parser.py — Local 2D CAD Vector Ingestion & Takeoff Engine

Zero-Cloud / Air-Gap Guarantee:
All CAD geometry parsing executes 100% in-memory via ezdxf. No drawing files
or coordinate data are transmitted externally.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

import ezdxf
from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace


@dataclass
class OpeningItem:
    """Represents a door, window, or ventilator opening for IS 1200 deductions."""

    id: str
    type: str  # "Door", "Window", "Ventilator"
    width_m: float
    height_m: float
    area_sqm: float
    layer: str = "A-DOOR"
    cad_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "width_m": round(self.width_m, 3),
            "height_m": round(self.height_m, 3),
            "area_sqm": round(self.area_sqm, 3),
            "layer": self.layer,
            "cad_ref": self.cad_ref,
        }


@dataclass
class ParsedCadTakeoff:
    """Structured container holding all quantities extracted from the CAD drawing."""

    file_name: str
    units: str
    scale_factor_to_meters: float
    area_scale_factor: float
    block_counts: dict[str, int] = field(default_factory=dict)
    classified_blocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    hatch_areas_sqm: dict[str, float] = field(default_factory=dict)
    polyline_areas_sqm: dict[str, float] = field(default_factory=dict)
    openings: list[OpeningItem] = field(default_factory=list)
    total_floor_area_sqm: float = 0.0
    total_wall_area_sqm: float = 0.0
    total_ceiling_area_sqm: float = 0.0
    wall_length_m: float = 0.0
    detected_layers: list[str] = field(default_factory=list)
    raw_summary: dict[str, Any] = field(default_factory=dict)
    block_instances: list[dict[str, Any]] = field(default_factory=list)
    wall_segments: list[dict[str, Any]] = field(default_factory=list)
    room_polygons: list[dict[str, Any]] = field(default_factory=list)
    bounding_box: dict[str, float] = field(default_factory=dict)
    architectural_linework: dict[str, list[list[tuple[float, float]]]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "units": self.units,
            "total_floor_area_sqm": round(self.total_floor_area_sqm, 2),
            "total_wall_area_sqm": round(self.total_wall_area_sqm, 2),
            "total_ceiling_area_sqm": round(self.total_ceiling_area_sqm, 2),
            "wall_length_m": round(self.wall_length_m, 2),
            "block_counts": self.block_counts,
            "classified_blocks": self.classified_blocks,
            "hatch_areas_sqm": {k: round(v, 2) for k, v in self.hatch_areas_sqm.items()},
            "polyline_areas_sqm": {k: round(v, 2) for k, v in self.polyline_areas_sqm.items()},
            "openings": [op.to_dict() for op in self.openings],
            "detected_layers": self.detected_layers,
            "raw_summary": self.raw_summary,
            "total_block_instances": len(self.block_instances),
            "total_wall_segments": len(self.wall_segments),
            "total_room_polygons": len(self.room_polygons),
            "architectural_linework_summary": {k: len(v) for k, v in self.architectural_linework.items()},
        }

    def __getattr__(self, name: str) -> Any:
        defaults = {
            "block_instances": [],
            "wall_segments": [],
            "room_polygons": [],
            "bounding_box": {},
            "architectural_linework": {},
            "openings": [],
            "detected_layers": [],
            "raw_summary": {},
            "hatch_areas_sqm": {},
            "polyline_areas_sqm": {},
            "block_counts": {},
            "classified_blocks": {},
            "wall_length_m": 0.0,
            "total_wall_area_sqm": 0.0,
            "total_floor_area_sqm": 0.0,
            "total_ceiling_area_sqm": 0.0,
            "scale_factor_to_meters": 1.0,
            "area_scale_factor": 1.0,
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


def find_dwg2dxf_executable() -> str | None:
    """Finds path to dwg2dxf executable if present locally or in system PATH."""
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "libredwg", "dwg2dxf.exe")
    if os.path.exists(local_path):
        return local_path
    return shutil.which("dwg2dxf")


def is_dwg_converter_available() -> bool:
    """Checks whether DWG-to-DXF conversion is supported in current environment."""
    if find_dwg2dxf_executable() is not None:
        return True
    try:
        import ezdxf.addons.odafc as odafc

        return odafc.is_installed()
    except Exception:
        return False


def convert_dwg_to_dxf(dwg_input: str | bytes, output_dxf_path: str | None = None) -> str:
    """Converts a binary AutoCAD .DWG file into an open ASCII .DXF file.

    Zero-Cloud Air-Gap Guarantee:
    Uses bundled local LibreDWG dwg2dxf (100% offline & air-gapped) or local ODA File Converter.
    Returns the path to the converted .dxf file.
    """
    temp_dwg = None
    if isinstance(dwg_input, bytes):
        fd, temp_dwg = tempfile.mkstemp(suffix=".dwg")
        with os.fdopen(fd, "wb") as f:
            f.write(dwg_input)
        input_path = temp_dwg
    else:
        if not os.path.exists(dwg_input):
            raise FileNotFoundError(f"CAD DWG file not found: {dwg_input}")
        input_path = dwg_input

    if output_dxf_path is None:
        output_dxf_path = os.path.splitext(input_path)[0] + ".dxf"
        if output_dxf_path == input_path:
            output_dxf_path = input_path + "_converted.dxf"

    # 1. Try LibreDWG dwg2dxf standalone binary
    dwg2dxf_exe = find_dwg2dxf_executable()
    if dwg2dxf_exe:
        cmd = [dwg2dxf_exe, "-o", output_dxf_path, input_path]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=False)
            if os.path.exists(output_dxf_path) and os.path.getsize(output_dxf_path) > 0:
                if temp_dwg and os.path.exists(temp_dwg):
                    try:
                        os.remove(temp_dwg)
                    except Exception:
                        pass
                return output_dxf_path
        except Exception:
            pass

    # 2. Try ezdxf ODA File Converter addon if available
    try:
        import ezdxf.addons.odafc as odafc

        if odafc.is_installed():
            doc = odafc.readfile(input_path)
            doc.saveas(output_dxf_path)
            if temp_dwg and os.path.exists(temp_dwg):
                try:
                    os.remove(temp_dwg)
                except Exception:
                    pass
            return output_dxf_path
    except Exception:
        pass

    if temp_dwg and os.path.exists(temp_dwg):
        try:
            os.remove(temp_dwg)
        except Exception:
            pass

    raise RuntimeError(
        "DWG conversion failed: No local DWG converter available. "
        "Please provide an open .DXF file directly (in AutoCAD: File > Save As > DXF or type DXFOUT), "
        "or ensure LibreDWG dwg2dxf is installed."
    )


class CadParser:
    """Parses 2D DXF and DWG CAD drawings to extract geometric takeoffs, block counts, and opening deductions."""

    # Standard trade classification keywords for block symbols (supports Indian and International conventions)
    BLOCK_CLASSIFICATION = {
        "Electrical - Lighting": [
            r"LIGHT",
            r"DOWNLIGHT",
            r"RECESSED",
            r"COVE",
            r"STRIP",
            r"PANEL_LIGHT",
            r"GRID_LIGHT",
            r"2X2",
            r"TRACK_LIGHT",
            r"TRACK",
            r"LED_PANEL",
            r"SPOT",
            r"LGT",
            r"CEILING_LIGHT",
            r"WALL_LIGHT",
            r"TUBE",
            r"LAMP",
            r"LUZ",
            r"FOCO",
            r"ILUM",
        ],
        "Electrical - Fans": [r"FAN", r"CEILING_FAN", r"CFAN", r"EXHAUST", r"VENT_FAN", r"BLDC", r"VENTILADOR"],
        "Electrical - Switches & Sockets": [
            r"SWITCH",
            r"SW_",
            r"SOCKET",
            r"MODULAR",
            r"PLUG",
            r"DB_",
            r"DISTRIBUTION",
            r"POWER_POINT",
            r"16A",
            r"6A",
            r"INTERRUPTOR",
            r"ENCHUFE",
        ],
        "Plumbing - Sanitaryware": [
            r"WC",
            r"COMMODE",
            r"EWC",
            r"BASIN",
            r"WASH_BASIN",
            r"SINK",
            r"SHOWER",
            r"TAP",
            r"FAUCET",
            r"URINAL",
            r"TRAP",
            r"FLOOR_TRAP",
            r"SUNKEN",
            r"LAVA",
            r"FREG",
            r"INODORO",
            r"BANO",
            r"DUCHA",
        ],
        "HVAC - Mechanical": [
            r"DIFFUSER",
            r"AC_",
            r"FCU",
            r"GRILL",
            r"HVAC",
            r"CASSETTE",
            r"RETURN_AIR",
        ],
        "Partitions & Architectural": [
            r"PARTITION",
            r"GLASS_WALL",
            r"ALU_PARTITION",
        ],
        "Openings - Doors & Windows": [
            r"DOOR",
            r"^D\d",
            r"WINDOW",
            r"^W\d",
            r"VENTILATOR",
            r"^V\d",
            r"GLAZING",
            r"PUERTA",
            r"PUERT",
            r"VENTANA",
            r"VENTAN",
            r"SLIDING",
            r"FRENCH",
        ],
        "Furniture & Equipment": [
            r"BED",
            r"CAMA",
            r"MUEBLE",
            r"MESA",
            r"SOFA",
            r"SILLA",
            r"CLOSET",
            r"COCINA",
            r"ESTUFA",
            r"NEV",
            r"DESK",
            r"CHAIR",
            r"WORKSTATION",
        ],
    }

    # Standard layer names in Indian and International AutoCAD drawings
    LAYER_CLASSIFICATION = {
        "Flooring": [
            r"FLOOR",
            r"A-FLOR",
            r"TILE",
            r"TILES",
            r"MARBLE",
            r"GRANITE",
            r"FINISH",
            r"GULV",
            r"PAVIMENTO",
            r"SUELO",
            r"_CARPET AREA",
            r"_CARPET",
            r"_FLOOR",
            r"_BUILTUP",
            r"_PROPOSED WORK",
            r"_RESIMAIN",
            r"_COMMERCIAL",
            r"CARPET_FLOOR",
            r"CARPET",
            r"OFFICE_FLOOR",
        ],
        "Ceiling": [
            r"CEIL",
            r"A-CLNG",
            r"FALSE_CEIL",
            r"GYPSUM",
            r"POP",
            r"TECHO",
            r"PLAFON",
            r"GRID_LIGHT",
            r"GRID_CEILING",
            r"ACOUSTIC_CEIL",
            r"ACOUSTIC",
            r"A-CLNG-GRID",
        ],
        "Walls": [
            r"WALL",
            r"A-WALL",
            r"CIVIL_WALL",
            r"BRICK",
            r"MASONRY",
            r"PARTITION",
            r"MURO",
            r"PARED",
            r"_WALL",
            r"_MARGINLINE",
            r"_COMWALL",
            r"PARTITION_GLASS",
            r"ALU_PARTITION",
            r"GLASS_PARTITION",
            r"ELEC_NEW",
        ],
        "Openings": [
            r"DOOR",
            r"A-DOOR",
            r"WINDOW",
            r"A-GLAZ",
            r"OPENING",
            r"VENT",
            r"PUERT",
            r"VENTAN",
            r"_DOOR",
            r"_WINDOW",
            r"_VENT",
            r"_OPENING",
            r"FRENCH_DOOR",
            r"SLIDING_DOOR",
        ],
    }

    def __init__(
        self,
        default_units: str = "auto",
        wall_height_m: float = 3.0,
        wall_thickness_m: float = 0.23,
    ) -> None:
        self.default_units = default_units.lower()
        self.wall_height_m = wall_height_m
        self.wall_thickness_m = wall_thickness_m

    def _resolve_drawing_units(self, doc: Drawing, msp: Modelspace) -> tuple[str, float, float]:
        """Resolves whether drawing is in mm, m, or inches based on bounding box and header."""
        # 1. Explicit user override
        if self.default_units in ("m", "meter", "meters"):
            return "m", 1.0, 1.0
        elif self.default_units in ("mm", "millimeter", "millimeters"):
            return "mm", 0.001, 1e-6
        elif self.default_units in ("inch", "inches", "in"):
            return "inches", 0.0254, 0.00064516
        elif self.default_units in ("ft", "feet"):
            return "feet", 0.3048, 0.092903

        # 2. Inspect LINE & LWPOLYLINE geometric bounding extents
        xs, ys = [], []
        line_lengths = []
        for e in msp.query("LINE LWPOLYLINE"):
            if e.dxftype() == "LINE":
                xs.extend([e.dxf.start.x, e.dxf.end.x])
                ys.extend([e.dxf.start.y, e.dxf.end.y])
                line_lengths.append(math.hypot(e.dxf.end.x - e.dxf.start.x, e.dxf.end.y - e.dxf.start.y))
            elif e.dxftype() == "LWPOLYLINE":
                pts = e.get_points(format="xy")
                if pts:
                    xs.extend([p[0] for p in pts[:4]])
                    ys.extend([p[1] for p in pts[:4]])

        max_span = 0.0
        if xs and ys:
            span_x = max(xs) - min(xs)
            span_y = max(ys) - min(ys)
            max_span = max(span_x, span_y)

        sorted_lens = sorted(line_lengths) if line_lengths else []
        p90_len = sorted_lens[int(len(sorted_lens) * 0.9)] if sorted_lens else 0.0
        avg_len = (sum(line_lengths) / len(line_lengths)) if line_lengths else 0.0

        try:
            insunits = doc.header.get("$INSUNITS", 0)
        except Exception:
            insunits = 0

        # Physical sanity check:
        # In a drawing drawn in millimeters, architectural segments (walls, doors, room edges)
        # measure 200mm to 10,000mm (average > 100, 90th percentile > 100).
        # In a drawing drawn in meters, segments measure 0.2m to 10.0m (average < 15, 90th percentile < 25).
        # Many CAD files and converters (like LibreDWG) set $INSUNITS=4 or $INSUNITS=1 by template default,
        # even when geometries were drafted in meters. Entity geometry takes physical precedence.
        if p90_len > 100.0 or avg_len > 100.0:
            unit_str = "mm"
            linear_scale = 0.001
        elif 0.05 <= p90_len <= 30.0 and avg_len <= 15.0:
            unit_str = "m"
            linear_scale = 1.0
        elif insunits == 4:
            unit_str = "mm"
            linear_scale = 0.001
        elif insunits == 6:
            unit_str = "m"
            linear_scale = 1.0
        elif insunits == 1 and max_span <= 500.0:
            unit_str = "inches"
            linear_scale = 0.0254
        elif max_span > 200.0:
            unit_str = "mm"
            linear_scale = 0.001
        else:
            unit_str = "m"
            linear_scale = 1.0

        area_scale = linear_scale * linear_scale
        return unit_str, linear_scale, area_scale

    def _classify_block_name(self, block_name: str) -> str:
        """Assigns an architectural trade to a CAD block name."""
        upper_name = block_name.upper()
        for trade, patterns in self.BLOCK_CLASSIFICATION.items():
            for pat in patterns:
                if re.search(pat, upper_name):
                    return trade
        return "Other Architectural Fittings"

    def _matches_layer_category(self, layer_name: str, category: str) -> bool:
        """Checks if a layer name belongs to a given category."""
        upper_layer = layer_name.upper()
        patterns = self.LAYER_CLASSIFICATION.get(category, [])
        return any(re.search(pat, upper_layer) for pat in patterns)

    def _categorize_layer_for_linework(self, layer_name: str) -> str:
        """Categorizes an AutoCAD layer into base architectural linework groups."""
        u = layer_name.upper()
        if re.search(r"WALL|MURO|PARED|BRICK|COL|PILAR|STRUCTURE|_MARGINLINE|_WALL|PARTITION", u):
            return "walls"
        elif re.search(r"DOOR|PUERT|ENTRY|_DOOR", u):
            return "doors"
        elif re.search(r"WINDOW|VENTAN|GLAZ|^W$|_WINDOW|_VENT", u):
            return "windows"
        elif re.search(r"STAIR|ESCAL|ELEV|ASCENS|LIFT|CORE", u):
            return "stairs"
        elif re.search(r"FURN|MUEBL|BED|CAMA|WC|BANO|EQUIP|KITCH|COCIN|SOFA|TABLE|MESA|DESK|CHAIR", u):
            return "furniture"
        elif re.search(r"DIM|COTA|TEXT|ANNO", u):
            return "dimensions"
        return "other"

    def _extract_opening_dimension(self, block_name: str, attribs: dict[str, str]) -> tuple[float, float, str]:
        """Infers opening width and height in meters from block name or attributes."""
        upper_name = block_name.upper()

        # Check explicit attributes if available
        if "WIDTH" in attribs and "HEIGHT" in attribs:
            try:
                w = float(attribs["WIDTH"])
                h = float(attribs["HEIGHT"])
                w_m = w * 0.001 if w > 10 else w
                h_m = h * 0.001 if h > 10 else h
                return w_m, h_m, "Attribute"
            except ValueError:
                pass

        # Check dimension patterns like 1000X2100, 3X7, 1200X1500, 3000X2400
        dim_match = re.search(r"(\d+)[X_](\d+)", upper_name)
        if dim_match:
            d1 = float(dim_match.group(1))
            d2 = float(dim_match.group(2))
            if d1 > 200 and d2 > 200:  # in millimeters
                return d1 * 0.001, d2 * 0.001, "Name mm"
            elif d1 <= 15 and d2 <= 15:  # in feet (e.g. 3x7)
                return d1 * 0.3048, d2 * 0.3048, "Name ft"

        # Check for large French doors / Balcony sliding doors (> 3.0 sq.m)
        if re.search(r"FRENCH|BALCONY|PATIO", upper_name) or (
            "SLIDING" in upper_name and ("LARGE" in upper_name or "BALC" in upper_name or "3000" in upper_name or "3M" in upper_name)
        ):
            return 3.0, 2.4, "Large French / Balcony Sliding Door (3.0m x 2.4m)"

        # Standard residential architectural opening norms:
        if re.search(r"DOOR|^D\d|MAIN_DOOR|PUERT", upper_name):
            if "D2" in upper_name or "TOILET" in upper_name:
                return 0.75, 2.1, "Standard Toilet Door"
            return 1.0, 2.1, "Standard Door (1.0m x 2.1m)"
        elif re.search(r"VENT|^V\d", upper_name):
            return 0.6, 0.6, "Standard Ventilator (0.6m x 0.6m)"
        elif re.search(r"WINDOW|^W\d|VENTAN", upper_name):
            if "W2" in upper_name:
                return 1.2, 1.2, "Standard Window W2 (1.2m x 1.2m)"
            return 1.5, 1.2, "Standard Window W1 (1.5m x 1.2m)"
        elif re.search(r"SLIDING", upper_name):
            return 1.8, 2.1, "Standard Sliding Door (1.8m x 2.1m)"

        return 1.0, 2.1, "Default Opening"

    def parse_dxf_file(self, dxf_path: str) -> ParsedCadTakeoff:
        """Parses a local .DXF file and returns comprehensive quantitative takeoff data."""
        if not os.path.exists(dxf_path):
            raise FileNotFoundError(f"CAD DXF file not found: {dxf_path}")

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        units, linear_scale, area_scale = self._resolve_drawing_units(doc, msp)
        file_name = os.path.basename(dxf_path)

        block_counts: dict[str, int] = {}
        classified_blocks: dict[str, dict[str, Any]] = {}
        hatch_areas_sqm: dict[str, float] = {}
        polyline_areas_sqm: dict[str, float] = {}
        openings: list[OpeningItem] = []
        detected_layers = sorted({layer.dxf.name for layer in doc.layers})

        # Geometric entities for interactive visualization & highlights
        block_instances: list[dict[str, Any]] = []
        wall_segments: list[dict[str, Any]] = []
        room_polygons: list[dict[str, Any]] = []

        # Collect full 2D vector linework for detailed architectural visualization
        from ezdxf import path as epath

        architectural_linework: dict[str, list[list[tuple[float, float]]]] = {
            "walls": [],
            "doors": [],
            "windows": [],
            "stairs": [],
            "furniture": [],
            "dimensions": [],
            "other": [],
        }

        for e in msp.query("LINE LWPOLYLINE POLYLINE ARC CIRCLE ELLIPSE SPLINE"):
            cat = self._categorize_layer_for_linework(e.dxf.layer)
            if cat in architectural_linework:
                try:
                    p = epath.make_path(e)
                    pts = [(round(v.x, 3), round(v.y, 3)) for v in p.flattening(distance=0.08)]
                    if len(pts) >= 2:
                        architectural_linework[cat].append(pts)
                except Exception:
                    pass

        # 1. Parse Block References (INSERT entities) with Recursive Nested Block Traversal
        opening_counter = 1

        def _process_insert(insert: Any, parent_x: float = 0.0, parent_y: float = 0.0, depth: int = 0) -> None:
            nonlocal opening_counter
            if depth > 5:
                return

            raw_name = insert.dxf.name
            clean_name = raw_name.strip()
            block_counts[clean_name] = block_counts.get(clean_name, 0) + 1

            attrib_dict: dict[str, str] = {}
            if hasattr(insert, "attribs"):
                for attrib in insert.attribs:
                    attrib_dict[attrib.dxf.tag.upper()] = attrib.dxf.text

            trade = self._classify_block_name(clean_name)
            if clean_name not in classified_blocks:
                classified_blocks[clean_name] = {
                    "count": 0,
                    "trade": trade,
                    "attributes": attrib_dict,
                }
            classified_blocks[clean_name]["count"] += 1

            ins_pt = getattr(insert.dxf, "insert", None)
            ins_x = (ins_pt.x if ins_pt else 0.0) + parent_x
            ins_y = (ins_pt.y if ins_pt else 0.0) + parent_y

            block_instances.append(
                {
                    "name": clean_name,
                    "trade": trade,
                    "x": round(ins_x, 3),
                    "y": round(ins_y, 3),
                    "rotation": getattr(insert.dxf, "rotation", 0.0),
                    "layer": insert.dxf.layer,
                    "attributes": attrib_dict,
                }
            )

            # Detect if this block is an opening (Door/Window)
            if trade == "Openings - Doors & Windows" or self._matches_layer_category(insert.dxf.layer, "Openings"):
                w_m, h_m, src = self._extract_opening_dimension(clean_name, attrib_dict)
                op_type = (
                    "Ventilator"
                    if "VENT" in clean_name.upper()
                    else ("Window" if "WIN" in clean_name.upper() else "Door")
                )
                op_area = w_m * h_m
                openings.append(
                    OpeningItem(
                        id=f"OP-{opening_counter:03d}",
                        type=op_type,
                        width_m=w_m,
                        height_m=h_m,
                        area_sqm=op_area,
                        layer=insert.dxf.layer,
                        cad_ref=f"Block: {clean_name} ({src})",
                    )
                )
                opening_counter += 1

            # Traverse nested block definitions recursively
            try:
                blk_def = doc.blocks.get(raw_name)
                if blk_def:
                    for child_ins in blk_def.query("INSERT"):
                        _process_insert(child_ins, parent_x=ins_x, parent_y=ins_y, depth=depth + 1)
            except Exception:
                pass

        for insert in msp.query("INSERT"):
            _process_insert(insert)

        # 1b. Exploded Geometry Detection: Circles on electrical/lighting layers
        for circle in msp.query("CIRCLE"):
            c_layer = circle.dxf.layer.upper()
            c_rad_m = circle.dxf.radius * linear_scale
            if 0.04 <= c_rad_m <= 0.40 and (
                "LIGHT" in c_layer or "ELEC" in c_layer or "LGT" in c_layer or "SPOT" in c_layer or "LAMP" in c_layer
            ):
                exp_name = f"EXPLODED_LIGHT_{circle.dxf.layer}"
                block_counts[exp_name] = block_counts.get(exp_name, 0) + 1
                if exp_name not in classified_blocks:
                    classified_blocks[exp_name] = {
                        "count": 0,
                        "trade": "Electrical - Lighting",
                        "attributes": {"radius_m": f"{c_rad_m:.2f}"},
                    }
                classified_blocks[exp_name]["count"] += 1
                block_instances.append(
                    {
                        "name": exp_name,
                        "trade": "Electrical - Lighting",
                        "x": round(circle.dxf.center.x, 3),
                        "y": round(circle.dxf.center.y, 3),
                        "rotation": 0.0,
                        "layer": circle.dxf.layer,
                        "attributes": {},
                    }
                )

        # 2. Parse HATCH Entities
        for hatch in msp.query("HATCH"):
            layer = hatch.dxf.layer.upper()
            area = 0.0
            try:
                area = hatch.dxf.area
            except Exception:
                try:
                    from ezdxf.path import from_hatch

                    paths = list(from_hatch(hatch))
                    area = sum(abs(p.area()) for p in paths)
                except Exception:
                    area = 0.0

            area_sqm = area * area_scale
            if area_sqm > 0:
                hatch_areas_sqm[layer] = hatch_areas_sqm.get(layer, 0.0) + area_sqm

        # 3. Parse Closed & Unclosed LWPOLYLINE / POLYLINE Entities (Rooms, Walls, Ceilings)
        wall_length_units = 0.0
        for poly in msp.query("LWPOLYLINE POLYLINE"):
            layer = poly.dxf.layer.upper()
            is_closed = getattr(poly, "is_closed", False) or bool(poly.dxf.flags & 1)

            # Flatten 3D or 2D coordinates to (x, y) float tuples
            pts: list[tuple[float, float]] = []
            if hasattr(poly, "get_points"):
                try:
                    pts = [(float(p[0]), float(p[1])) for p in poly.get_points(format="xy")]
                except Exception:
                    pass
            elif hasattr(poly, "vertices"):
                try:
                    pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in poly.vertices]
                except Exception:
                    pass

            if len(pts) >= 2:
                # Accumulate perimeter / length for wall calculations
                for i in range(len(pts) - 1):
                    dx = pts[i + 1][0] - pts[i][0]
                    dy = pts[i + 1][1] - pts[i][1]
                    dist = math.hypot(dx, dy)
                    if self._matches_layer_category(layer, "Walls"):
                        wall_length_units += dist
                        wall_segments.append(
                            {
                                "x1": round(pts[i][0], 3),
                                "y1": round(pts[i][1], 3),
                                "x2": round(pts[i + 1][0], 3),
                                "y2": round(pts[i + 1][1], 3),
                                "length_m": round(dist * linear_scale, 3),
                                "layer": poly.dxf.layer,
                            }
                        )

            # Check gap between first and last vertex for unclosed polylines
            dist_gap_m = 0.0
            if len(pts) >= 2:
                dist_gap_m = math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) * linear_scale
                # If gap <= 0.20m, treat as closed drafting polygon
                if dist_gap_m <= 0.20:
                    is_closed = True

            # Calculate area gracefully for closed loops or floor/ceiling layers
            should_calc_area = is_closed or self._matches_layer_category(layer, "Flooring") or self._matches_layer_category(layer, "Ceiling")
            if len(pts) >= 3 and should_calc_area:
                try:
                    raw_area = abs(ezdxf.math.area(pts))
                    area_sqm = raw_area * area_scale
                    if area_sqm > 0.05:  # Ignore micro noise
                        polyline_areas_sqm[layer] = polyline_areas_sqm.get(layer, 0.0) + area_sqm
                        room_polygons.append(
                            {
                                "points": [[round(p[0], 3), round(p[1], 3)] for p in pts],
                                "layer": poly.dxf.layer,
                                "area_sqm": round(area_sqm, 2),
                                "category": "Flooring" if self._matches_layer_category(layer, "Flooring") else layer,
                            }
                        )
                except Exception:
                    pass

        # 4. Parse LINE Entities for Walls (accumulates with polylines for mixed-entity drawings)
        for line in msp.query("LINE"):
            layer = line.dxf.layer.upper()
            if self._matches_layer_category(layer, "Walls"):
                p1 = line.dxf.start
                p2 = line.dxf.end
                l_dist = math.hypot(p2.x - p1.x, p2.y - p1.y)
                wall_length_units += l_dist
                wall_segments.append(
                    {
                        "x1": round(p1.x, 3),
                        "y1": round(p1.y, 3),
                        "x2": round(p2.x, 3),
                        "y2": round(p2.y, 3),
                        "length_m": round(l_dist * linear_scale, 3),
                        "layer": line.dxf.layer,
                    }
                )

        wall_length_m = wall_length_units * linear_scale

        # 5. Aggregate Surface Area Totals
        floor_area = 0.0
        ceiling_area = 0.0
        wall_area = 0.0

        for layer, area in {**hatch_areas_sqm, **polyline_areas_sqm}.items():
            if self._matches_layer_category(layer, "Flooring"):
                floor_area = max(floor_area, area)
            elif self._matches_layer_category(layer, "Ceiling"):
                ceiling_area = max(ceiling_area, area)
            elif self._matches_layer_category(layer, "Walls"):
                wall_area = max(wall_area, area)

        # Fallbacks based on architectural geometry:
        # If floor area was not explicitly closed/hatched, estimate from wall bounding box:
        if floor_area == 0.0 and wall_length_m > 0.0:
            wall_xs, wall_ys = [], []
            for line in msp.query("LINE"):
                if self._matches_layer_category(line.dxf.layer.upper(), "Walls"):
                    wall_xs.extend([line.dxf.start.x, line.dxf.end.x])
                    wall_ys.extend([line.dxf.start.y, line.dxf.end.y])
            for poly in msp.query("LWPOLYLINE"):
                if self._matches_layer_category(poly.dxf.layer.upper(), "Walls"):
                    pts = poly.get_points(format="xy") if hasattr(poly, "get_points") else []
                    wall_xs.extend([p[0] for p in pts])
                    wall_ys.extend([p[1] for p in pts])

            if wall_xs and wall_ys:
                span_w = (max(wall_xs) - min(wall_xs)) * linear_scale
                span_h = (max(wall_ys) - min(wall_ys)) * linear_scale
                if 2.0 <= span_w <= 200.0 and 2.0 <= span_h <= 200.0:
                    floor_area = round(span_w * span_h * 0.75, 2)
                    if not room_polygons:
                        min_wx, max_wx = min(wall_xs), max(wall_xs)
                        min_wy, max_wy = min(wall_ys), max(wall_ys)
                        room_polygons.append(
                            {
                                "points": [
                                    [round(min_wx, 3), round(min_wy, 3)],
                                    [round(max_wx, 3), round(min_wy, 3)],
                                    [round(max_wx, 3), round(max_wy, 3)],
                                    [round(min_wx, 3), round(max_wy, 3)],
                                ],
                                "layer": "ESTIMATED_FLOOR_ENVELOPE",
                                "area_sqm": floor_area,
                                "category": "Flooring",
                            }
                        )

            if floor_area == 0.0:
                est_side = wall_length_m / 4.5
                floor_area = round(est_side * est_side, 2)

        # If ceiling area wasn't explicitly hatched, ceiling area equals floor area
        if ceiling_area == 0.0 and floor_area > 0.0:
            ceiling_area = floor_area

        # If wall area wasn't hatched in elevation/surface, compute vertical gross wall area:
        # Gross Wall Area = Wall Centerline Length * Wall Height
        if wall_area == 0.0 and wall_length_m > 0.0:
            wall_area = wall_length_m * self.wall_height_m

        # If wall length wasn't explicit, estimate from room perimeter:
        # Perimeter approx 4.5 * sqrt(Floor Area)
        if wall_area == 0.0 and floor_area > 0.0:
            est_perimeter = 4.5 * math.sqrt(floor_area)
            wall_area = est_perimeter * self.wall_height_m

        # If openings were not drawn as blocks, create synthetic standard openings from door/window layers
        if not openings:
            for layer in detected_layers:
                if self._matches_layer_category(layer, "Openings"):
                    # Add standard residential opening defaults
                    openings.extend(
                        [
                            OpeningItem("OP-001", "Door", 1.0, 2.1, 2.1, layer, "Layer: " + layer),
                            OpeningItem("OP-002", "Door", 0.9, 2.1, 1.89, layer, "Layer: " + layer),
                            OpeningItem("OP-003", "Door", 0.75, 2.1, 1.575, layer, "Layer: " + layer),
                            OpeningItem("OP-004", "Window", 1.5, 1.2, 1.8, layer, "Layer: " + layer),
                            OpeningItem("OP-005", "Window", 1.5, 1.2, 1.8, layer, "Layer: " + layer),
                            OpeningItem("OP-006", "Ventilator", 0.6, 0.6, 0.36, layer, "Layer: " + layer),
                        ]
                    )
                    break

        # Compute bounding box
        all_xs = [b["x"] for b in block_instances] + [w["x1"] for w in wall_segments] + [w["x2"] for w in wall_segments]
        all_ys = [b["y"] for b in block_instances] + [w["y1"] for w in wall_segments] + [w["y2"] for w in wall_segments]
        bounding_box = {
            "min_x": round(min(all_xs), 3) if all_xs else 0.0,
            "max_x": round(max(all_xs), 3) if all_xs else 0.0,
            "min_y": round(min(all_ys), 3) if all_ys else 0.0,
            "max_y": round(max(all_ys), 3) if all_ys else 0.0,
        }

        return ParsedCadTakeoff(
            file_name=file_name,
            units=units,
            scale_factor_to_meters=linear_scale,
            area_scale_factor=area_scale,
            block_counts=block_counts,
            classified_blocks=classified_blocks,
            hatch_areas_sqm=hatch_areas_sqm,
            polyline_areas_sqm=polyline_areas_sqm,
            openings=openings,
            total_floor_area_sqm=floor_area,
            total_wall_area_sqm=wall_area,
            total_ceiling_area_sqm=ceiling_area,
            wall_length_m=wall_length_m,
            detected_layers=detected_layers,
            raw_summary={
                "total_insert_entities": sum(block_counts.values()),
                "total_unique_blocks": len(block_counts),
                "total_openings_detected": len(openings),
                "total_layers": len(detected_layers),
            },
            block_instances=block_instances,
            wall_segments=wall_segments,
            room_polygons=room_polygons,
            bounding_box=bounding_box,
            architectural_linework=architectural_linework,
        )

    def parse_cad_file(
        self,
        file_input: str | bytes,
        filename: str | None = None,
    ) -> ParsedCadTakeoff:
        """Parses a 2D CAD drawing (.DXF or .DWG).

        If a .DWG file is supplied, it is automatically converted to .DXF in a temporary
        file via the local air-gapped LibreDWG dwg2dxf engine.
        """
        temp_dxf = None
        is_dwg = False

        if isinstance(file_input, str):
            if filename is None:
                filename = os.path.basename(file_input)
            if file_input.lower().endswith(".dwg"):
                is_dwg = True
                temp_dxf = convert_dwg_to_dxf(file_input)
                target_path = temp_dxf
            else:
                target_path = file_input
        else:
            fname = filename or "drawing.dxf"
            if fname.lower().endswith(".dwg"):
                is_dwg = True
                temp_dxf = convert_dwg_to_dxf(file_input)
                target_path = temp_dxf
            else:
                fd, temp_dxf = tempfile.mkstemp(suffix=".dxf")
                with os.fdopen(fd, "wb") as f:
                    f.write(file_input)
                target_path = temp_dxf

        try:
            takeoff = self.parse_dxf_file(target_path)
            if filename:
                takeoff.file_name = filename
            return takeoff
        finally:
            if temp_dxf and os.path.exists(temp_dxf) and (is_dwg or not isinstance(file_input, str)):
                try:
                    os.remove(temp_dxf)
                except Exception:
                    pass


def parse_dxf_file(
    dxf_path: str, units: str = "auto", wall_height: float = 3.0, wall_thickness: float = 0.23
) -> ParsedCadTakeoff:
    """Convenience functional wrapper for CadParser."""
    parser = CadParser(default_units=units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
    return parser.parse_dxf_file(dxf_path)


def parse_cad_file(
    cad_path_or_bytes: str | bytes,
    filename: str | None = None,
    units: str = "auto",
    wall_height: float = 3.0,
    wall_thickness: float = 0.23,
) -> ParsedCadTakeoff:
    """Convenience functional wrapper supporting both .DXF and .DWG formats."""
    parser = CadParser(default_units=units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
    return parser.parse_cad_file(cad_path_or_bytes, filename=filename)
