"""boq_engine.py — Statutory IS 1200 Rules Engine & Procurement Matcher

Implements:
1. Bureau of Indian Standards (IS 1200) statutory measurement and deduction logic:
   - IS 1200 Part 4: Brickwork & Masonry
   - IS 1200 Part 12: Plastering & Pointing
   - IS 1200 Part 11: Flooring & Ceilings
2. B2B Price & Catalog SKU Matcher (joining CAD geometry + Client Specifications).
3. Corporate-grade Openpyxl Excel spreadsheet generator with dynamic formulas and active hyperlinks.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from cad_parser import OpeningItem, ParsedCadTakeoff
from spec_parser import ClientSpecification


@dataclass
class BoqLineItem:
    """Represents a billable line item in the Bill of Quantities."""

    item_no: str
    trade: str
    category: str
    description: str
    cad_reference: str
    quantity: float
    unit: str
    unit_rate_inr: float
    total_cost_inr: float
    buy_url: str
    audit_notes: str
    sku_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_no": self.item_no,
            "trade": self.trade,
            "category": self.category,
            "description": self.description,
            "cad_reference": self.cad_reference,
            "quantity": round(self.quantity, 2),
            "unit": self.unit,
            "unit_rate_inr": round(self.unit_rate_inr, 2),
            "total_cost_inr": round(self.total_cost_inr, 2),
            "buy_url": self.buy_url,
            "audit_notes": self.audit_notes,
            "sku_id": self.sku_id,
        }


class BoqEngine:
    """Compiles a fully-priced, IS 1200 compliant Bill of Quantities."""

    def __init__(self, catalog_path: str | None = None) -> None:
        if catalog_path is None:
            catalog_path = os.path.join(os.path.dirname(__file__), "catalog.json")
        self.catalog_path = catalog_path
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> dict[str, Any]:
        if not os.path.exists(self.catalog_path):
            return {"items": []}
        with open(self.catalog_path, encoding="utf-8") as f:
            return json.load(f)

    def _find_sku(self, trade: str, category: str, **kwargs: Any) -> dict[str, Any] | None:
        """Matches an item in catalog.json based on trade, category, and preferred specifications."""
        sku_id = kwargs.get("sku_id")
        if sku_id:
            for it in self.catalog.get("items", []):
                if it.get("sku_id") == sku_id:
                    return it

        items = self.catalog.get("items", [])
        candidates = [it for it in items if it.get("trade", "").lower() == trade.lower()]

        if category:
            matched_cat = [
                it
                for it in candidates
                if category.lower() in it.get("category", "").lower()
                or category.lower() in it.get("sub_category", "").lower()
            ]
            if matched_cat:
                candidates = matched_cat

        # Filter by brand if specified
        brand = kwargs.get("brand")
        if brand and brand.lower() != "any":
            brand_matched = [it for it in candidates if brand.lower() in it.get("brand", "").lower()]
            if brand_matched:
                candidates = brand_matched

        # Filter by wattage / motor / color temp if relevant
        wattage = kwargs.get("wattage")
        if wattage:
            w_matched = [it for it in candidates if it.get("specifications", {}).get("wattage") == wattage]
            if w_matched:
                candidates = w_matched

        cct = kwargs.get("color_temp")
        if cct:
            cct_matched = [it for it in candidates if it.get("specifications", {}).get("color_temp") == cct]
            if cct_matched:
                candidates = cct_matched

        motor = kwargs.get("fan_type")
        if motor:
            m_matched = [it for it in candidates if it.get("specifications", {}).get("motor_type") == motor]
            if m_matched:
                candidates = m_matched

        return candidates[0] if candidates else None

    # =========================================================================
    # STATUTORY IS 1200 CALCULATIONS
    # =========================================================================

    def calculate_is1200_masonry(
        self,
        wall_length_m: float,
        wall_height_m: float,
        wall_thickness_m: float,
        openings: list[OpeningItem],
    ) -> dict[str, Any]:
        """Calculates masonry volume applying IS 1200 Part 4 deduction rules.

        Statutory Invariant:
        - Openings <= 0.1 sq.m: ZERO deduction.
        - Openings > 0.1 sq.m: Deduct opening area * wall thickness.
        """
        gross_wall_area = wall_length_m * wall_height_m
        gross_volume = gross_wall_area * wall_thickness_m

        deducted_area = 0.0
        opening_audits = []

        for op in openings:
            area = op.area_sqm
            if area <= 0.10:
                # IS 1200 Part 4: No deduction for opening <= 0.1 m2
                statutory_tier = "Exempt (<= 0.1 m2)"
                deduction = 0.0
                clause = "IS 1200 Part 4 Clause 3.8.1 (Zero Deduction)"
            else:
                statutory_tier = "Deductible (> 0.1 m2)"
                deduction = area
                clause = "IS 1200 Part 4 Clause 3.8.1 (Full Area Deduction)"

            deducted_area += deduction
            opening_audits.append(
                {
                    "opening_id": op.id,
                    "type": op.type,
                    "dimensions": f"{op.width_m:.2f}m x {op.height_m:.2f}m",
                    "area_sqm": round(area, 3),
                    "statutory_tier": statutory_tier,
                    "clause": clause,
                    "deduction_area_sqm": round(deduction, 3),
                    "deduction_volume_cum": round(deduction * wall_thickness_m, 3),
                }
            )

        net_area = max(0.0, gross_wall_area - deducted_area)
        net_volume = net_area * wall_thickness_m

        return {
            "gross_wall_length_m": round(wall_length_m, 2),
            "gross_wall_area_sqm": round(gross_wall_area, 2),
            "gross_volume_cum": round(gross_volume, 2),
            "total_deducted_area_sqm": round(deducted_area, 2),
            "total_deducted_volume_cum": round(deducted_area * wall_thickness_m, 2),
            "net_masonry_volume_cum": round(net_volume, 2),
            "openings_audit": opening_audits,
        }

    def calculate_is1200_plaster(
        self,
        gross_wall_area_sqm: float,
        openings: list[OpeningItem],
        wall_thickness_m: float = 0.23,
    ) -> dict[str, Any]:
        """Calculates wall plaster area applying IS 1200 Part 12 statutory 3-tier deduction rules.

        Statutory Invariant:
        Plaster is applied to both faces of the wall (Gross Plaster Area = 2 * Gross Wall Area).
        - Tier 1 (<= 0.5 sq.m): ZERO deduction, no reveals added.
        - Tier 2 (0.5 < A <= 3.0 sq.m): Deduct ONE face (1.0 * Area), no reveals added.
        - Tier 3 (> 3.0 sq.m): Deduct BOTH faces (2.0 * Area), and add reveals/jambs.
        """
        both_faces_area = gross_wall_area_sqm * 2.0
        total_deduction = 0.0
        total_reveal_addition = 0.0
        opening_audits = []

        for op in openings:
            area = op.area_sqm
            perimeter = 2.0 * (op.width_m + op.height_m)
            # Jamb depth typically wall thickness
            jamb_addition = perimeter * wall_thickness_m

            if area <= 0.50:
                tier = "Tier 1 (<= 0.5 m2)"
                deduction = 0.0
                addition = 0.0
                clause = "IS 1200 Part 12 Cl. 4.3.1 (Zero Deduction, No Reveals)"
            elif 0.50 < area <= 3.00:
                tier = "Tier 2 (0.5 m2 to 3.0 m2)"
                deduction = area * 1.0  # Deduct single face
                addition = 0.0  # Jambs not added
                clause = "IS 1200 Part 12 Cl. 4.3.1 (Deduct Single Face Only)"
            else:
                tier = "Tier 3 (> 3.0 m2)"
                deduction = area * 2.0  # Deduct both faces
                addition = jamb_addition  # Add reveals
                clause = "IS 1200 Part 12 Cl. 4.3.1 (Deduct Both Faces & Add Reveals)"

            total_deduction += deduction
            total_reveal_addition += addition

            opening_audits.append(
                {
                    "opening_id": op.id,
                    "type": op.type,
                    "dimensions": f"{op.width_m:.2f}m x {op.height_m:.2f}m",
                    "area_sqm": round(area, 3),
                    "statutory_tier": tier,
                    "clause": clause,
                    "face_deduction_sqm": round(deduction, 3),
                    "reveal_addition_sqm": round(addition, 3),
                    "net_impact_sqm": round(-deduction + addition, 3),
                }
            )

        net_plaster_area = max(0.0, both_faces_area - total_deduction + total_reveal_addition)

        return {
            "gross_wall_area_one_face_sqm": round(gross_wall_area_sqm, 2),
            "gross_plaster_area_both_faces_sqm": round(both_faces_area, 2),
            "total_opening_deduction_sqm": round(total_deduction, 2),
            "total_reveal_addition_sqm": round(total_reveal_addition, 2),
            "net_plaster_area_sqm": round(net_plaster_area, 2),
            "openings_audit": opening_audits,
        }

    # =========================================================================
    # BOQ COMPILATION PIPELINE
    # =========================================================================

    def generate_boq(
        self,
        cad_takeoff: ParsedCadTakeoff,
        spec: ClientSpecification,
        wall_height_m: float = 3.0,
        wall_thickness_m: float = 0.23,
    ) -> dict[str, Any]:
        """Compiles full BOQ joining CAD vectors, IS 1200 deductions, and client specifications."""
        line_items: list[BoqLineItem] = []
        item_counter = 1

        # 1. Statutory Calculations
        masonry_res = self.calculate_is1200_masonry(
            cad_takeoff.wall_length_m or (cad_takeoff.total_wall_area_sqm / max(wall_height_m, 1.0)),
            wall_height_m,
            wall_thickness_m,
            cad_takeoff.openings,
        )

        plaster_res = self.calculate_is1200_plaster(
            cad_takeoff.total_wall_area_sqm,
            cad_takeoff.openings,
            wall_thickness_m,
        )

        # 2. Civil Trade: 230mm Brickwork
        brick_sku = self._find_sku("Civil", "Masonry")
        if brick_sku and masonry_res["net_masonry_volume_cum"] > 0:
            qty = masonry_res["net_masonry_volume_cum"]
            rate = brick_sku.get("unit_rate_inr", 5400.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"CIV-{item_counter:03d}",
                    trade="Civil",
                    category="Masonry",
                    description=f"{brick_sku.get('model_name')}",
                    cad_reference=f"Wall Length: {cad_takeoff.wall_length_m:.1f}m, H: {wall_height_m}m",
                    quantity=qty,
                    unit=brick_sku.get("unit", "Cu.m"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=brick_sku.get("buy_url", ""),
                    audit_notes=f"IS 1200 Part 4: Gross {masonry_res['gross_volume_cum']} m3 minus {masonry_res['total_deducted_volume_cum']} m3 openings",
                    sku_id=brick_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 3. Finishes Trade: 12mm Internal Plaster
        plaster_sku = self._find_sku("Finishes", "Plastering")
        if plaster_sku and plaster_res["net_plaster_area_sqm"] > 0:
            qty = plaster_res["net_plaster_area_sqm"]
            rate = plaster_sku.get("unit_rate_inr", 240.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"FIN-{item_counter:03d}",
                    trade="Finishes",
                    category="Plastering",
                    description=f"{plaster_sku.get('model_name')}",
                    cad_reference=f"Gross Both Faces: {plaster_res['gross_plaster_area_both_faces_sqm']:.1f} sqm",
                    quantity=qty,
                    unit=plaster_sku.get("unit", "Sq.m"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=plaster_sku.get("buy_url", ""),
                    audit_notes=f"IS 1200 Part 12: Deducted {plaster_res['total_opening_deduction_sqm']} sqm for {len(cad_takeoff.openings)} openings",
                    sku_id=plaster_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 4. Finishes Trade: Interior Painting
        paint_sku = self._find_sku("Finishes", "Painting", brand="Asian Paints")
        if spec.paint_preference == "Tractor Emulsion":
            alt_paint = self._find_sku("Finishes", "Painting", sub_category="Tractor")
            if alt_paint:
                paint_sku = alt_paint

        if paint_sku and plaster_res["net_plaster_area_sqm"] > 0:
            # Interior paint applied to inner plaster face (~50% of total both-faces plaster area)
            qty = plaster_res["net_plaster_area_sqm"] * 0.5
            rate = paint_sku.get("unit_rate_inr", 310.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"FIN-{item_counter:03d}",
                    trade="Finishes",
                    category="Painting",
                    description=f"Internal Wall Painting with {paint_sku.get('model_name')} over 2 coats putty and primer",
                    cad_reference="Matched to Net Internal Plaster Area",
                    quantity=qty,
                    unit=paint_sku.get("unit", "Sq.m"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=paint_sku.get("buy_url", ""),
                    audit_notes=f"Client Brief Preference: {spec.paint_preference}",
                    sku_id=paint_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 5. Finishes Trade: Flooring
        flooring_sku = self._find_sku("Finishes", "Flooring")
        if spec.flooring_preference == "Italian Marble":
            alt_flr = self._find_sku("Finishes", "Flooring", sub_category="Natural Stone")
            if alt_flr:
                flooring_sku = alt_flr
        elif spec.flooring_preference == "Ceramic":
            alt_flr = self._find_sku("Finishes", "Flooring", brand="Somany")
            if alt_flr:
                flooring_sku = alt_flr

        if flooring_sku and cad_takeoff.total_floor_area_sqm > 0:
            qty = cad_takeoff.total_floor_area_sqm
            rate = flooring_sku.get("unit_rate_inr", 1150.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"FIN-{item_counter:03d}",
                    trade="Finishes",
                    category="Flooring",
                    description=f"Flooring Works: {flooring_sku.get('model_name')} with cement slurry and epoxy grouting",
                    cad_reference="Hatch/Polyline Floor Boundary Area",
                    quantity=qty,
                    unit=flooring_sku.get("unit", "Sq.m"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=flooring_sku.get("buy_url", ""),
                    audit_notes=f"Client Brief Preference: {spec.flooring_preference} (IS 1200 Part 11)",
                    sku_id=flooring_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 6. Finishes Trade: False Ceiling
        ceiling_sku = self._find_sku("Finishes", "Ceilings")
        if ceiling_sku and cad_takeoff.total_ceiling_area_sqm > 0:
            qty = cad_takeoff.total_ceiling_area_sqm
            rate = ceiling_sku.get("unit_rate_inr", 1150.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"FIN-{item_counter:03d}",
                    trade="Finishes",
                    category="Ceilings",
                    description=f"{ceiling_sku.get('model_name')}",
                    cad_reference=f"Ceiling Plan Area: {qty:.1f} sqm",
                    quantity=qty,
                    unit=ceiling_sku.get("unit", "Sq.m"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=ceiling_sku.get("buy_url", ""),
                    audit_notes="IS 1200 Part 11: Net ceiling plan area",
                    sku_id=ceiling_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 7. Electrical: Lighting Downlights
        downlight_count = 0
        for _blk, info in cad_takeoff.classified_blocks.items():
            if info["trade"] == "Electrical - Lighting":
                downlight_count += info["count"]

        # Default fallback count if blocks weren't tagged: ~1 light per 4.5 sqm
        if downlight_count == 0 and cad_takeoff.total_floor_area_sqm > 0:
            downlight_count = max(4, int(cad_takeoff.total_floor_area_sqm / 4.5))

        light_sku = self._find_sku(
            "Electrical",
            "Lighting",
            brand=spec.preferred_lighting_brand,
            wattage=spec.lighting_wattage,
            color_temp=spec.lighting_color_temp,
        )
        if not light_sku:
            light_sku = self._find_sku("Electrical", "Lighting")

        if light_sku and downlight_count > 0:
            qty = float(downlight_count)
            rate = light_sku.get("unit_rate_inr", 420.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"ELE-{item_counter:03d}",
                    trade="Electrical",
                    category="Lighting",
                    description=f"Supply and fixing of {light_sku.get('model_name')}",
                    cad_reference=f"{downlight_count} INSERT entities / architectural layout points",
                    quantity=qty,
                    unit=light_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=light_sku.get("buy_url", ""),
                    audit_notes=f"Brief: {spec.preferred_lighting_brand} {spec.lighting_wattage}W {spec.lighting_color_temp}",
                    sku_id=light_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 8. Electrical: Ceiling Fans
        fan_count = 0
        for _blk, info in cad_takeoff.classified_blocks.items():
            if info["trade"] == "Electrical - Fans":
                fan_count += info["count"]

        if fan_count == 0 and cad_takeoff.total_floor_area_sqm > 0:
            fan_count = max(2, int(cad_takeoff.total_floor_area_sqm / 25.0))

        fan_sku = self._find_sku(
            "Electrical",
            "Fans",
            brand=spec.preferred_fan_brand,
            fan_type=spec.fan_type,
        )
        if not fan_sku:
            fan_sku = self._find_sku("Electrical", "Fans")

        if fan_sku and fan_count > 0:
            qty = float(fan_count)
            rate = fan_sku.get("unit_rate_inr", 3690.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"ELE-{item_counter:03d}",
                    trade="Electrical",
                    category="Fans",
                    description=f"Supply and installation of {fan_sku.get('model_name')}",
                    cad_reference=f"{fan_count} Ceiling Fan block insertions",
                    quantity=qty,
                    unit=fan_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=fan_sku.get("buy_url", ""),
                    audit_notes=f"Brief: {spec.preferred_fan_brand} {spec.fan_type} Energy Saving",
                    sku_id=fan_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 9. Electrical: Modular Switches
        switch_count = 0
        for _blk, info in cad_takeoff.classified_blocks.items():
            if info["trade"] == "Electrical - Switches & Sockets":
                switch_count += info["count"]

        if switch_count == 0 and downlight_count > 0:
            switch_count = int(downlight_count * 1.5)

        switch_sku = self._find_sku(
            "Electrical",
            "Switches",
            brand=spec.preferred_switch_brand,
        )
        if not switch_sku:
            switch_sku = self._find_sku("Electrical", "Switches")

        if switch_sku and switch_count > 0:
            qty = float(switch_count)
            rate = switch_sku.get("unit_rate_inr", 68.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"ELE-{item_counter:03d}",
                    trade="Electrical",
                    category="Switches",
                    description=f"Supply and installation of {switch_sku.get('model_name')} on modular base plate",
                    cad_reference=f"{switch_count} Modular switch points",
                    quantity=qty,
                    unit=switch_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=switch_sku.get("buy_url", ""),
                    audit_notes=f"Brief: {spec.preferred_switch_brand} {spec.switch_grade}",
                    sku_id=switch_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 10. Plumbing & Sanitaryware: Basin Mixers & EWCs
        plumb_count = sum(
            info["count"]
            for info in cad_takeoff.classified_blocks.values()
            if info["trade"] == "Plumbing - Sanitaryware"
        )
        if plumb_count == 0 and cad_takeoff.total_floor_area_sqm > 0:
            plumb_count = 2  # Standard 2BHK bathrooms

        ewc_sku = self._find_sku("Plumbing", "Sanitaryware", brand=spec.sanitaryware_brand)
        if not ewc_sku:
            ewc_sku = self._find_sku("Plumbing", "Sanitaryware")

        if ewc_sku and plumb_count > 0:
            qty = float(plumb_count)
            rate = ewc_sku.get("unit_rate_inr", 12450.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"PLB-{item_counter:03d}",
                    trade="Plumbing",
                    category="Sanitaryware",
                    description=f"Supply and installation of {ewc_sku.get('model_name')}",
                    cad_reference=f"{plumb_count} Toilet/Bathroom core fixtures",
                    quantity=qty,
                    unit=ewc_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=ewc_sku.get("buy_url", ""),
                    audit_notes=f"Brief: {spec.sanitaryware_brand} Premium Sanitary Suite",
                    sku_id=ewc_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 11. Commercial 2x2 LED Grid Panels
        grid_light_count = sum(
            info["count"]
            for blk, info in cad_takeoff.classified_blocks.items()
            if any(k in blk.upper() for k in ["GRID_LIGHT", "2X2", "PANEL_LIGHT", "LED_PANEL"])
        )
        if grid_light_count == 0 and (
            "36w" in spec.raw_brief.lower()
            or "grid panel" in spec.raw_brief.lower()
            or "2x2" in spec.raw_brief.lower()
        ):
            grid_light_count = max(8, int(cad_takeoff.total_floor_area_sqm / 6.0)) if cad_takeoff.total_floor_area_sqm > 0 else 12

        grid_sku = self._find_sku("Electrical", "Lighting", sku_id="LGT-WIP-36W-2X2")
        if grid_sku and grid_light_count > 0:
            qty = float(grid_light_count)
            rate = grid_sku.get("unit_rate_inr", 1250.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"ELE-{item_counter:03d}",
                    trade="Electrical",
                    category="Lighting",
                    description=f"Supply and fixing of {grid_sku.get('model_name')}",
                    cad_reference=f"{grid_light_count} Grid Light fixtures",
                    quantity=qty,
                    unit=grid_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=grid_sku.get("buy_url", ""),
                    audit_notes="Commercial ceiling grid layout",
                    sku_id=grid_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 12. Magnetic Track Lights
        track_light_count = sum(
            info["count"] for blk, info in cad_takeoff.classified_blocks.items() if "TRACK" in blk.upper()
        )
        if track_light_count == 0 and "track light" in spec.raw_brief.lower():
            track_light_count = 6

        track_sku = self._find_sku("Electrical", "Lighting", sku_id="LGT-MAG-TRK-20W")
        if track_sku and track_light_count > 0:
            qty = float(track_light_count)
            rate = track_sku.get("unit_rate_inr", 1850.0)
            line_items.append(
                BoqLineItem(
                    item_no=f"ELE-{item_counter:03d}",
                    trade="Electrical",
                    category="Lighting",
                    description=f"Supply and installation of {track_sku.get('model_name')}",
                    cad_reference=f"{track_light_count} Magnetic track fixture points",
                    quantity=qty,
                    unit=track_sku.get("unit", "Pcs"),
                    unit_rate_inr=rate,
                    total_cost_inr=qty * rate,
                    buy_url=track_sku.get("buy_url", ""),
                    audit_notes="Accent/Architectural track lighting",
                    sku_id=track_sku.get("sku_id", ""),
                )
            )
            item_counter += 1

        # 13. Acoustic Mineral Fibre False Ceiling
        has_acoustic_brief = "acoustic" in spec.raw_brief.lower()
        has_acoustic_layer = any(
            "ACOUSTIC" in lyr.upper() or "GRID_CEIL" in lyr.upper() for lyr in cad_takeoff.detected_layers
        )
        if (has_acoustic_brief or has_acoustic_layer) and cad_takeoff.total_ceiling_area_sqm > 0:
            ac_sku = self._find_sku("Finishes", "False Ceiling", sku_id="FIN-CLG-ACO-2X2")
            if ac_sku:
                qty = cad_takeoff.total_ceiling_area_sqm
                rate = ac_sku.get("unit_rate_inr", 850.0)
                line_items.append(
                    BoqLineItem(
                        item_no=f"FIN-{item_counter:03d}",
                        trade="Finishes",
                        category="False Ceiling",
                        description=f"{ac_sku.get('model_name')}",
                        cad_reference=f"Ceiling Plan Grid: {qty:.1f} sqm",
                        quantity=qty,
                        unit=ac_sku.get("unit", "Sq.m"),
                        unit_rate_inr=rate,
                        total_cost_inr=qty * rate,
                        buy_url=ac_sku.get("buy_url", ""),
                        audit_notes="Commercial acoustic false ceiling (IS 1200 Part 11)",
                        sku_id=ac_sku.get("sku_id", ""),
                    )
                )
                item_counter += 1

        # 14. Commercial Carpet Tiles
        has_carpet_brief = "carpet" in spec.raw_brief.lower()
        carpet_layer_area = sum(
            area
            for lyr, area in {**cad_takeoff.hatch_areas_sqm, **cad_takeoff.polyline_areas_sqm}.items()
            if "CARPET" in lyr.upper()
        )
        carpet_area = (
            carpet_layer_area
            if carpet_layer_area > 0
            else (cad_takeoff.total_floor_area_sqm if has_carpet_brief else 0.0)
        )
        if carpet_area > 0 and (has_carpet_brief or carpet_layer_area > 0):
            crpt_sku = self._find_sku("Finishes", "Flooring", sku_id="FIN-CRPT-MOD-500")
            if crpt_sku:
                qty = carpet_area
                rate = crpt_sku.get("unit_rate_inr", 1200.0)
                line_items.append(
                    BoqLineItem(
                        item_no=f"FIN-{item_counter:03d}",
                        trade="Finishes",
                        category="Flooring",
                        description=f"{crpt_sku.get('model_name')}",
                        cad_reference=f"Carpet Layout Area: {qty:.1f} sqm",
                        quantity=qty,
                        unit=crpt_sku.get("unit", "Sq.m"),
                        unit_rate_inr=rate,
                        total_cost_inr=qty * rate,
                        buy_url=crpt_sku.get("buy_url", ""),
                        audit_notes="Heavy commercial duty nylon carpet tiles",
                        sku_id=crpt_sku.get("sku_id", ""),
                    )
                )
                item_counter += 1

        # 15. Aluminium Glass Partitions
        has_part_brief = "aluminium partition" in spec.raw_brief.lower() or "partition" in spec.raw_brief.lower()
        part_layer_len = sum(
            seg["length_m"]
            for seg in cad_takeoff.wall_segments
            if "PARTITION" in seg.get("layer", "").upper()
        )
        part_area = (part_layer_len * wall_height_m) if part_layer_len > 0 else (18.0 if has_part_brief else 0.0)
        if part_area > 0 and (has_part_brief or part_layer_len > 0):
            part_sku = self._find_sku("Civil", "Partitions", sku_id="CIV-ALU-GLS-50MM")
            if part_sku:
                qty = part_area
                rate = part_sku.get("unit_rate_inr", 2200.0)
                line_items.append(
                    BoqLineItem(
                        item_no=f"CIV-{item_counter:03d}",
                        trade="Civil",
                        category="Partitions",
                        description=f"{part_sku.get('model_name')}",
                        cad_reference=f"Partition Linework: {qty:.1f} sqm",
                        quantity=qty,
                        unit=part_sku.get("unit", "Sq.m"),
                        unit_rate_inr=rate,
                        total_cost_inr=qty * rate,
                        buy_url=part_sku.get("buy_url", ""),
                        audit_notes="Internal acoustic office partition framing",
                        sku_id=part_sku.get("sku_id", ""),
                    )
                )
                item_counter += 1

        # 16. Sunken Slab Drainage & Trap
        has_sunken = any("SUNKEN" in lyr.upper() for lyr in cad_takeoff.detected_layers) or "sunken" in spec.raw_brief.lower()
        if has_sunken and cad_takeoff.total_floor_area_sqm > 0:
            sunken_sku = self._find_sku("Plumbing", "Sanitaryware", sku_id="PLB-SNK-SUN-100")
            if sunken_sku:
                qty = 4.0
                rate = sunken_sku.get("unit_rate_inr", 750.0)
                line_items.append(
                    BoqLineItem(
                        item_no=f"PLB-{item_counter:03d}",
                        trade="Plumbing",
                        category="Sanitaryware",
                        description=f"{sunken_sku.get('model_name')}",
                        cad_reference="Sunken toilet/balcony drainage nodes",
                        quantity=qty,
                        unit=sunken_sku.get("unit", "Pcs"),
                        unit_rate_inr=rate,
                        total_cost_inr=qty * rate,
                        buy_url=sunken_sku.get("buy_url", ""),
                        audit_notes="Multi-floor sunken slab drainage trap (IS 1200 Part 16)",
                        sku_id=sunken_sku.get("sku_id", ""),
                    )
                )
                item_counter += 1

        grand_total = sum(it.total_cost_inr for it in line_items)

        # Trade Summary Subtotals
        trade_subtotals: dict[str, float] = {}
        for it in line_items:
            trade_subtotals[it.trade] = trade_subtotals.get(it.trade, 0.0) + it.total_cost_inr

        return {
            "items": [it.to_dict() for it in line_items],
            "grand_total_inr": round(grand_total, 2),
            "trade_subtotals_inr": {k: round(v, 2) for k, v in trade_subtotals.items()},
            "is1200_masonry_audit": masonry_res,
            "is1200_plaster_audit": plaster_res,
            "spec_summary": spec.to_dict(),
        }

    # =========================================================================
    # OPENPYXL EXCEL SPREADSHEET EXPORT
    # =========================================================================

    def export_to_excel(self, boq_result: dict[str, Any], output_path: str) -> str:
        """Generates a styled, corporate .xlsx spreadsheet with formulas and active hyperlinks."""
        wb = openpyxl.Workbook()

        # Styles
        navy_header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        trade_sub_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        total_fill = PatternFill(start_color="B4C6E7", end_color="B4C6E7", fill_type="solid")

        white_bold_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        trade_font = Font(name="Calibri", size=11, bold=True, color="1F4E79")
        bold_font = Font(name="Calibri", size=11, bold=True)
        Font(name="Calibri", size=10)
        link_font = Font(name="Calibri", size=10, color="0000FF", underline="single")

        thin_border = Border(
            left=Side(style="thin", color="D3D3D3"),
            right=Side(style="thin", color="D3D3D3"),
            top=Side(style="thin", color="D3D3D3"),
            bottom=Side(style="thin", color="D3D3D3"),
        )
        double_bottom_border = Border(
            top=Side(style="thin", color="000000"),
            bottom=Side(style="double", color="000000"),
        )

        # ---------------------------------------------------------------------
        # Sheet 1: Bill of Quantities (BOQ)
        # ---------------------------------------------------------------------
        ws_boq = wb.active
        ws_boq.title = "Priced BOQ (IS 1200)"
        ws_boq.views.sheetView[0].showGridLines = True

        # Document Header
        ws_boq.merge_cells("A1:H1")
        title_cell = ws_boq["A1"]
        title_cell.value = "AUTOSPEC AI — PRE-CONSTRUCTION BILL OF QUANTITIES"
        title_cell.font = Font(name="Calibri", size=15, bold=True, color="1F4E79")
        title_cell.alignment = Alignment(horizontal="left", vertical="center")

        ws_boq.merge_cells("A2:H2")
        sub_cell = ws_boq["A2"]
        sub_cell.value = "Statutory BIS IS 1200 Measurement Compliance & Live B2B Indian Procurement Matching"
        sub_cell.font = Font(name="Calibri", size=10, italic=True, color="595959")
        sub_cell.alignment = Alignment(horizontal="left", vertical="center")

        headers = [
            "Item No",
            "Trade",
            "Description of Works & Specifications",
            "Quantity",
            "Unit",
            "Unit Rate (₹)",
            "Total Cost (₹)",
            "Procurement Buy Link",
            "Statutory Deduction & Audit Reference",
        ]

        row_idx = 4
        for col_idx, header in enumerate(headers, start=1):
            cell = ws_boq.cell(row=row_idx, column=col_idx, value=header)
            cell.fill = navy_header_fill
            cell.font = white_bold_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        items = boq_result.get("items", [])
        current_trade = ""

        row_idx = 5
        for item in items:
            trade = item["trade"]
            # Insert trade group section header if new trade
            if trade != current_trade:
                current_trade = trade
                ws_boq.cell(row=row_idx, column=1, value="")
                ws_boq.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers))
                sec_cell = ws_boq.cell(row=row_idx, column=1)
                sec_cell.value = f"TRADE: {trade.upper()}"
                sec_cell.fill = trade_sub_fill
                sec_cell.font = trade_font
                sec_cell.alignment = Alignment(horizontal="left", vertical="center")
                row_idx += 1

            ws_boq.cell(row=row_idx, column=1, value=item["item_no"]).alignment = Alignment(horizontal="center")
            ws_boq.cell(row=row_idx, column=2, value=item["trade"]).alignment = Alignment(horizontal="center")
            ws_boq.cell(row=row_idx, column=3, value=item["description"]).alignment = Alignment(
                horizontal="left", wrap_text=True
            )

            q_cell = ws_boq.cell(row=row_idx, column=4, value=float(item["quantity"]))
            q_cell.number_format = "#,##0.00"
            q_cell.alignment = Alignment(horizontal="right")

            ws_boq.cell(row=row_idx, column=5, value=item["unit"]).alignment = Alignment(horizontal="center")

            r_cell = ws_boq.cell(row=row_idx, column=6, value=float(item["unit_rate_inr"]))
            r_cell.number_format = "₹ #,##0.00"
            r_cell.alignment = Alignment(horizontal="right")

            # Formula for total: = Quantity * Unit Rate
            t_cell = ws_boq.cell(row=row_idx, column=7)
            t_cell.value = f"=D{row_idx}*F{row_idx}"
            t_cell.number_format = "₹ #,##0.00"
            t_cell.font = bold_font
            t_cell.alignment = Alignment(horizontal="right")

            # Buy Link
            link_cell = ws_boq.cell(row=row_idx, column=8, value="Buy Now ↗")
            link_cell.hyperlink = item.get("buy_url", "#")
            link_cell.font = link_font
            link_cell.alignment = Alignment(horizontal="center")

            ws_boq.cell(row=row_idx, column=9, value=item.get("audit_notes", "")).alignment = Alignment(
                horizontal="left"
            )

            for c in range(1, len(headers) + 1):
                ws_boq.cell(row=row_idx, column=c).border = thin_border

            row_idx += 1

        # Grand Total Row
        row_idx += 1
        ws_boq.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=6)
        gt_label = ws_boq.cell(row=row_idx, column=1, value="ESTIMATED GRAND TOTAL (INR):")
        gt_label.font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        gt_label.alignment = Alignment(horizontal="right", vertical="center")
        gt_label.fill = total_fill

        gt_cell = ws_boq.cell(row=row_idx, column=7, value=f"=SUM(G5:G{row_idx - 1})")
        gt_cell.font = Font(name="Calibri", size=12, bold=True, color="1F4E79")
        gt_cell.number_format = "₹ #,##0.00"
        gt_cell.alignment = Alignment(horizontal="right")
        gt_cell.fill = total_fill
        gt_cell.border = double_bottom_border

        for c in range(1, len(headers) + 1):
            ws_boq.cell(row=row_idx, column=c).border = double_bottom_border

        # Auto-adjust column widths
        col_widths = {1: 12, 2: 14, 3: 45, 4: 12, 5: 10, 6: 15, 7: 18, 8: 16, 9: 38}
        for col, width in col_widths.items():
            ws_boq.column_dimensions[get_column_letter(col)].width = width

        # ---------------------------------------------------------------------
        # Sheet 2: IS 1200 Statutory Audit Trail
        # ---------------------------------------------------------------------
        ws_audit = wb.create_sheet(title="IS 1200 Deduction Audit")
        ws_audit.views.sheetView[0].showGridLines = True

        ws_audit.merge_cells("A1:G1")
        aud_title = ws_audit["A1"]
        aud_title.value = "IS 1200 STATUTORY OPENING DEDUCTION AUDIT TRAIL"
        aud_title.font = Font(name="Calibri", size=14, bold=True, color="1F4E79")

        audit_headers = [
            "Opening ID",
            "Type",
            "Dimensions (W x H)",
            "Area (m²)",
            "Statutory Tier",
            "BIS Clause Applied",
            "Net Deduction Impact (m²)",
        ]

        for col_idx, h in enumerate(audit_headers, start=1):
            c = ws_audit.cell(row=3, column=col_idx, value=h)
            c.fill = navy_header_fill
            c.font = white_bold_font
            c.alignment = Alignment(horizontal="center", vertical="center")

        a_row = 4
        plaster_audits = boq_result.get("is1200_plaster_audit", {}).get("openings_audit", [])
        for aud in plaster_audits:
            ws_audit.cell(row=a_row, column=1, value=aud["opening_id"]).alignment = Alignment(horizontal="center")
            ws_audit.cell(row=a_row, column=2, value=aud["type"]).alignment = Alignment(horizontal="center")
            ws_audit.cell(row=a_row, column=3, value=aud["dimensions"]).alignment = Alignment(horizontal="center")
            ws_audit.cell(row=a_row, column=4, value=aud["area_sqm"]).alignment = Alignment(horizontal="right")
            ws_audit.cell(row=a_row, column=5, value=aud["statutory_tier"]).alignment = Alignment(horizontal="center")
            ws_audit.cell(row=a_row, column=6, value=aud["clause"]).alignment = Alignment(horizontal="left")
            ws_audit.cell(row=a_row, column=7, value=aud["net_impact_sqm"]).alignment = Alignment(horizontal="right")
            for col in range(1, len(audit_headers) + 1):
                ws_audit.cell(row=a_row, column=col).border = thin_border
            a_row += 1

        audit_widths = {1: 14, 2: 14, 3: 20, 4: 12, 5: 25, 6: 42, 7: 25}
        for col, width in audit_widths.items():
            ws_audit.column_dimensions[get_column_letter(col)].width = width

        wb.save(output_path)
        return output_path
