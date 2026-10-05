# 2D CAD Vector Ingestion & Parsing Rules

This rule file defines the parsing standards and architectural conventions for `cad_parser.py` using `ezdxf`.

---

## 1. Zero-Cloud / In-Memory Processing
- All CAD parsing operations must take place 100% in-memory via `ezdxf`.
- Under no circumstances may raw geometry, coordinates, or floor plans be sent over public networks or external APIs.

---

## 2. Drawing Units & Scale Normalization
- Indian architectural drawings are predominantly drawn in **millimeters (mm)** (95%+), occasionally in meters or feet/inches.
- **Unit Resolution**:
  1. Inspect `$INSUNITS` in DXF header:
     - `4` = Millimeters $\rightarrow \text{Scale factor } 0.001 \text{ m/unit}$ ($\text{Area scale } 10^{-6}$)
     - `6` = Meters $\rightarrow \text{Scale factor } 1.0 \text{ m/unit}$ ($\text{Area scale } 1.0$)
     - `1` = Inches $\rightarrow \text{Scale factor } 0.0254 \text{ m/unit}$
  2. If `$INSUNITS` is undefined or 0, analyze bounding box extents:
     - Extents $> 500$ units indicate millimeter scaling.
     - Extents $< 100$ units indicate meter scaling.
  3. Default fallback: **Millimeters (mm)** with UI override option.

---

## 3. Entity Classification & Layer Mapping
The parser must support standard Indian architectural layer and block nomenclature:

### Block Symbols (`INSERT`)
- **Lighting**: `LIGHT_DOWNLIGHT`, `DOWNLIGHT`, `DL`, `COVE_LIGHT`, `STRIP_LIGHT`, `PANEL_LIGHT`
- **Fans**: `FAN_CEILING`, `CEILING_FAN`, `CFAN`, `EXHAUST_FAN`, `VENT_FAN`
- **Switches & Power**: `SWITCH_MODULAR`, `MODULAR_SWITCH`, `SW_6A`, `SW_16A`, `SOCKET_16A`, `DB_BOX`
- **Sanitaryware**: `WC_COMMODE`, `EWC`, `WASH_BASIN`, `BASIN`, `SINK_KITCHEN`, `SHOWER`

### Polylines & Hatches (`LWPOLYLINE`, `POLYLINE`, `HATCH`)
- **Walls**: Layers matching `WALL`, `A-WALL`, `CIVIL_WALL`, `BRICKWORK`
- **Flooring**: Layers matching `FLOOR`, `A-FLOR`, `FLOORING`, `TILES`, `MARBLE`
- **Ceiling**: Layers matching `CEILING`, `A-CLNG`, `FALSE_CEILING`, `GYPSUM`
- **Openings**: Layers matching `DOOR`, `A-DOOR`, `WINDOW`, `A-GLAZ`, `VENT`

---

## 4. Error Tolerance & Graceful Degradation
- If a hatch lacks pre-calculated `dxf.area`, calculate area from boundary paths.
- Self-intersecting or unclosed polylines should be logged and closed virtually if gap $< 5\text{mm}$.
- Non-standard block names should be grouped under an "Unclassified / Custom" section in the output rather than discarded.
