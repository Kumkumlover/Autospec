"""cad_visualizer.py — Interactive 2D CAD Vector & Symbol Highlight Visualizer

Zero-Cloud / Air-Gap Guarantee:
All CAD vector rendering and symbol mapping execute 100% locally in-memory via Plotly
and ezdxf/matplotlib. No drawings, geometry, or coordinates are transmitted externally.
"""

from __future__ import annotations

import io
import os
from typing import Any

import ezdxf
import plotly.graph_objects as go

from cad_parser import ParsedCadTakeoff


class CadVisualizer:
    """Renders 2D CAD floor plans with two-tier vector linework and clean takeoff overlays."""

    # High-Contrast Trade Color Palette for Dark / Blueprint Canvas (Neon & Luminous)
    TRADE_PALETTE_DARK = {
        "Electrical - Lighting": {"color": "#FACC15", "symbol": "diamond", "name": "Lighting"},
        "Electrical - Fans": {"color": "#22D3EE", "symbol": "triangle-up", "name": "Fans"},
        "Electrical - Switches & Sockets": {"color": "#C084FC", "symbol": "square", "name": "Switches & Sockets"},
        "Plumbing - Sanitaryware": {"color": "#FB7185", "symbol": "circle", "name": "Sanitaryware"},
        "Openings - Doors & Windows": {"color": "#FB923C", "symbol": "square-cross", "name": "Openings (IS 1200)"},
        "Furniture & Equipment": {"color": "#4ADE80", "symbol": "hexagon", "name": "Furniture"},
        "Other Architectural Fittings": {"color": "#2DD4BF", "symbol": "circle-open", "name": "Fittings"},
    }

    # High-Contrast Trade Color Palette for Light Canvas (Deep Saturated Ink, Zero Blending)
    TRADE_PALETTE_LIGHT = {
        "Electrical - Lighting": {"color": "#B45309", "symbol": "diamond", "name": "Lighting"},
        "Electrical - Fans": {"color": "#0284C7", "symbol": "triangle-up", "name": "Fans"},
        "Electrical - Switches & Sockets": {"color": "#7E22CE", "symbol": "square", "name": "Switches & Sockets"},
        "Plumbing - Sanitaryware": {"color": "#BE123C", "symbol": "circle", "name": "Sanitaryware"},
        "Openings - Doors & Windows": {"color": "#C2410C", "symbol": "square-cross", "name": "Openings (IS 1200)"},
        "Furniture & Equipment": {"color": "#15803D", "symbol": "hexagon", "name": "Furniture"},
        "Other Architectural Fittings": {"color": "#0F766E", "symbol": "circle-open", "name": "Fittings"},
    }

    # Backward compatibility
    TRADE_PALETTE = TRADE_PALETTE_DARK

    def __init__(self, takeoff: ParsedCadTakeoff) -> None:
        self.takeoff = takeoff

    @staticmethod
    def _adjust_color_for_theme(color_hex: str, theme: str) -> str:
        """Adjusts CAD entity colors so they remain high-contrast on light or dark canvas."""
        c = (color_hex or "#FFFFFF").lower().strip()
        if theme == "light":
            # If CAD color is white/light, convert to dark charcoal ink
            if c in ("#ffffff", "#fff", "#f8fafc", "#f1f5f9", "#e2e8f0", "#cbd5e1", "white"):
                return "#1E293B"
            elif c in ("#ffff00", "#ff0", "yellow"):
                return "#D97706"
            elif c in ("#00ffff", "#0ff", "cyan"):
                return "#0284C7"
            elif c in ("#00ff00", "#0f0", "lime"):
                return "#15803D"
        else:  # dark or blueprint
            # If CAD color is black/dark, convert to crisp bright white
            if c in ("#000000", "#000", "#0f172a", "#1e293b", "black"):
                return "#F8FAFC"
            elif c in ("#0000ff", "#00f", "blue"):
                return "#38BDF8"
            elif c in ("#7f6f3f", "#7f5f3f", "#7f3f00"):
                return "#FDE047" if theme == "dark" else "#E0F2FE"
        return color_hex

    @classmethod
    def _layer_friendly_name(cls, layer_name: str) -> str:
        """Assigns an architectural category prefix to native CAD layers for intuitive legend display."""
        import re

        u = layer_name.upper()
        if re.search(r"WALL|MURO|PARED|BRICK|COL|PILAR|STRUCTURE|_MARGINLINE|_WALL|PARTITION", u):
            return f"🏛️ Walls ({layer_name})"
        elif re.search(r"DOOR|PUERT|ENTRY|_DOOR", u):
            return f"🚪 Doors ({layer_name})"
        elif re.search(r"WINDOW|VENTAN|GLAZ|^W$|_WINDOW|_VENT", u):
            return f"🪟 Windows ({layer_name})"
        elif re.search(r"STAIR|ESCAL|ELEV|ASCENS|LIFT|CORE", u):
            return f"🪜 Stairs ({layer_name})"
        elif re.search(r"FURN|MUEBL|BED|CAMA|WC|BANO|EQUIP|KITCH|COCIN|SOFA|TABLE|MESA|DESK|CHAIR", u):
            return f"🛋️ Furniture ({layer_name})"
        elif re.search(r"DIM|COTA|TEXT|ANNO", u):
            return f"📏 Dimensions ({layer_name})"
        return f"📐 Layer: {layer_name}"

    @staticmethod
    def _flatten_paths_to_xy(paths: list[list[tuple[float, float]]]) -> tuple[list[float | None], list[float | None]]:
        """Flattens a list of 2D coordinate paths into single Plotly line arrays separated by None."""
        xs: list[float | None] = []
        ys: list[float | None] = []
        for p in paths:
            if len(p) >= 2:
                for pt in p:
                    xs.append(pt[0])
                    ys.append(pt[1])
                xs.append(None)
                ys.append(None)
        return xs, ys

    def build_interactive_figure(
        self,
        visible_trades: list[str] | None = None,
        visible_layers: list[str] | None = None,
        visible_cad_layers: list[str] | None = None,
        label_mode: str = "none",
        focus_mode: str = "blueprint",
        show_opening_labels: bool | None = None,
        show_block_labels: bool | None = None,
        show_cad_text: bool = True,
        highlight_walls: bool = True,
        highlight_floors: bool = True,
        highlight_openings: bool = True,
        highlight_fixtures: bool = True,
        plot_height: int = 650,
        dark_mode: bool = True,
        theme: str = "dark",  # "dark", "blueprint", "light"
    ) -> go.Figure:
        """Constructs a two-tier interactive Plotly CAD vector canvas.

        Tier A: Native AutoCAD Model Space Linework (100% Vector Fidelity across all CAD layers)
        Tier B: AutoSpec Takeoff Highlights (Differentiable Colored Markups linked to the BOQ)
        """
        # Backward-compatibility parameter mapping
        if show_block_labels is True:
            label_mode = "all"
        elif show_opening_labels is False and label_mode == "openings":
            label_mode = "none"
        elif show_opening_labels is True and label_mode == "none":
            label_mode = "openings"

        fig = go.Figure()

        # Resolve Theme & High-Contrast Palette
        theme_lower = (theme or "dark").lower()
        if "light" in theme_lower or (not dark_mode and "blue" not in theme_lower and "dark" not in theme_lower):
            active_theme = "light"
        elif "blue" in theme_lower:
            active_theme = "blueprint"
        else:
            active_theme = "dark"

        if active_theme == "blueprint":
            bg_color = "#0B1D3A"
            grid_color = "#162E55"
            wall_color = "#FFFFFF"
            door_color = "#FDBA74"
            window_color = "#7DD3FC"
            stair_color = "#CBD5E1"
            furniture_color = "#60A5FA" if focus_mode != "takeoff_focus" else "rgba(96, 165, 250, 0.25)"
            plan_line_color = "#E0F2FE"
            room_fill_color = "rgba(56, 189, 248, 0.14)"
            room_line_color = "#38BDF8"
            trade_palette = self.TRADE_PALETTE_DARK
            marker_border = "#FFFFFF"
            title_color = "#38BDF8"
            axis_color = "#94A3B8"
            legend_bg = "rgba(11, 29, 58, 0.90)"
            legend_border = "#1E3A8A"
        elif active_theme == "light":
            bg_color = "#FFFFFF"
            grid_color = "#E2E8F0"
            wall_color = "#0F172A"  # Bold Jet Black - high contrast, zero blending!
            door_color = "#C2410C"  # Deep Terracotta
            window_color = "#1D4ED8"  # Deep Royal Blue
            stair_color = "#475569"  # Deep Slate
            furniture_color = "#64748B" if focus_mode != "takeoff_focus" else "rgba(100, 116, 139, 0.25)"
            plan_line_color = "#1E293B"  # Architectural Ink
            room_fill_color = "rgba(16, 185, 129, 0.14)"
            room_line_color = "#059669"
            trade_palette = self.TRADE_PALETTE_LIGHT
            marker_border = "#0F172A"
            title_color = "#0F172A"
            axis_color = "#475569"
            legend_bg = "rgba(255, 255, 255, 0.92)"
            legend_border = "#CBD5E0"
        else:  # "dark" / AutoCAD Model Space (DEFAULT!)
            bg_color = "#0D1117"  # Deep midnight dark matching AutoCAD / Streamlit!
            grid_color = "#1E293B"
            wall_color = "#F8FAFC"  # Crisp bright white!
            door_color = "#FB923C"  # Vibrant amber orange!
            window_color = "#38BDF8"  # Electric sky cyan!
            stair_color = "#94A3B8"  # Crisp silver slate!
            furniture_color = "#64748B" if focus_mode != "takeoff_focus" else "rgba(100, 116, 139, 0.25)"
            plan_line_color = "#E2E8F0"  # Bright crisp linework!
            room_fill_color = "rgba(16, 185, 129, 0.16)"
            room_line_color = "#10B981"
            trade_palette = self.TRADE_PALETTE_DARK
            marker_border = "#000000"
            title_color = "#F8FAFC"
            axis_color = "#94A3B8"
            legend_bg = "rgba(13, 17, 23, 0.90)"
            legend_border = "#30363D"

        cad_layers = getattr(self.takeoff, "cad_layers", {})
        cad_texts = getattr(self.takeoff, "cad_texts", [])
        linework = getattr(self.takeoff, "architectural_linework", {})
        wall_segments = getattr(self.takeoff, "wall_segments", [])
        room_polygons = getattr(self.takeoff, "room_polygons", [])
        openings = getattr(self.takeoff, "openings", [])
        block_instances = getattr(self.takeoff, "block_instances", [])
        bounding_box = getattr(self.takeoff, "bounding_box", {})

        # =====================================================================
        # TIER A: BASE AUTOCAD MODEL SPACE LINEWORK (100% Vector Fidelity)
        # =====================================================================
        if focus_mode != "takeoff_only":
            opacity = 0.22 if focus_mode == "takeoff_focus" else 1.0

            if cad_layers:
                # 1. Primary path: Render each native AutoCAD layer with its native CAD color!
                for layer_name, layer_data in sorted(cad_layers.items()):
                    if visible_cad_layers is not None and layer_name not in visible_cad_layers:
                        continue
                    friendly_name = self._layer_friendly_name(layer_name)

                    # Trade filter check if visible_trades is passed
                    if visible_trades is not None:
                        has_civil = any("Wall" in t or "Civil" in t or "Arch" in t for t in visible_trades)
                        has_door = any("Door" in t or "Opening" in t for t in visible_trades)
                        has_win = any("Window" in t or "Opening" in t for t in visible_trades)
                        has_furn = any("Furn" in t for t in visible_trades)

                        if "Walls" in friendly_name and not has_civil:
                            continue
                        if "Doors" in friendly_name and not has_door:
                            continue
                        if "Windows" in friendly_name and not has_win:
                            continue
                        if "Furniture" in friendly_name and not has_furn:
                            continue

                    paths = layer_data.get("paths", [])
                    if not paths:
                        continue
                    xs, ys = self._flatten_paths_to_xy(paths)
                    if not xs:
                        continue

                    raw_color = layer_data.get("color", "#FFFFFF")
                    layer_color = self._adjust_color_for_theme(raw_color, active_theme)
                    line_w = 1.6 if "WALL" in layer_name.upper() or "MURO" in layer_name.upper() else 1.1

                    fig.add_trace(
                        go.Scatter(
                            x=xs,
                            y=ys,
                            mode="lines",
                            line={"color": layer_color, "width": line_w},
                            opacity=opacity,
                            name=f"{friendly_name} ({len(paths)} segs)",
                            legendgroup="AutoCAD Linework",
                            legendgrouptitle_text="🏛️ AutoCAD Model Space Layers",
                            hoverinfo="text",
                            hovertext=f"<b>AutoCAD Layer: {layer_name}</b><br>Entities: {len(paths)}<br>Native Color: {raw_color}",
                        )
                    )

                # Native Text & Dimension Annotations
                if show_cad_text and cad_texts:
                    txs = [t["x"] for t in cad_texts]
                    tys = [t["y"] for t in cad_texts]
                    ttxts = [t["text"] for t in cad_texts]
                    thovers = [f"<b>{t['text']}</b><br>CAD Layer: {t.get('layer', '')}" for t in cad_texts]

                    fig.add_trace(
                        go.Scatter(
                            x=txs,
                            y=tys,
                            mode="text" if label_mode in ("all", "text") else "markers",
                            text=ttxts,
                            textposition="middle center",
                            textfont={"size": 9, "color": title_color},
                            marker={"size": 4, "color": axis_color, "opacity": 0.5},
                            opacity=opacity,
                            hovertext=thovers,
                            hoverinfo="text",
                            name=f"📝 CAD Text & Dimensions ({len(cad_texts)} items)",
                            legendgroup="AutoCAD Linework",
                            visible=True if label_mode in ("all", "text") else "legendonly",
                        )
                    )
            else:
                # 2. Fallback path for synthetic/mock CAD without cad_layers
                if visible_layers is None or "Walls" in visible_layers:
                    wall_paths = linework.get("walls", [])
                    if wall_paths:
                        w_xs, w_ys = self._flatten_paths_to_xy(wall_paths)
                    else:
                        w_xs, w_ys = [], []
                        for w in wall_segments:
                            w_xs.extend([w["x1"], w["x2"], None])
                            w_ys.extend([w["y1"], w["y2"], None])
                    if w_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=w_xs,
                                y=w_ys,
                                mode="lines",
                                line={"color": wall_color, "width": 2.2},
                                opacity=opacity,
                                name=f"🏛️ Walls ({len(wall_segments) or len(wall_paths)} segs)",
                                legendgroup="AutoCAD Linework",
                                legendgrouptitle_text="🏛️ Architectural Linework",
                                hoverinfo="text",
                                hovertext=f"<b>Civil Masonry Wall</b><br>Gross Wall Length: {getattr(self.takeoff, 'wall_length_m', 0.0):.1f} m",
                            )
                        )
                # Doors
                if (visible_layers is None or "Doors" in visible_layers) and linework.get("doors"):
                    d_xs, d_ys = self._flatten_paths_to_xy(linework["doors"])
                    if d_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=d_xs,
                                y=d_ys,
                                mode="lines",
                                line={"color": door_color, "width": 1.3},
                                opacity=opacity,
                                name=f"🚪 Doors & Swings ({len(linework['doors'])} paths)",
                                legendgroup="AutoCAD Linework",
                            )
                        )
                # Windows
                if (visible_layers is None or "Windows" in visible_layers) and linework.get("windows"):
                    win_xs, win_ys = self._flatten_paths_to_xy(linework["windows"])
                    if win_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=win_xs,
                                y=win_ys,
                                mode="lines",
                                line={"color": window_color, "width": 1.5},
                                opacity=opacity,
                                name=f"🪟 Windows ({len(linework['windows'])} paths)",
                                legendgroup="AutoCAD Linework",
                            )
                        )
                # Stairs
                if (visible_layers is None or "Stairs" in visible_layers) and linework.get("stairs"):
                    st_xs, st_ys = self._flatten_paths_to_xy(linework["stairs"])
                    if st_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=st_xs,
                                y=st_ys,
                                mode="lines",
                                line={"color": stair_color, "width": 1.1},
                                opacity=opacity,
                                name=f"🪜 Stairs & Core ({len(linework['stairs'])} paths)",
                                legendgroup="AutoCAD Linework",
                            )
                        )
                # Furniture
                if (visible_layers is None or "Furniture" in visible_layers) and linework.get("furniture"):
                    f_xs, f_ys = self._flatten_paths_to_xy(linework["furniture"])
                    if f_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=f_xs,
                                y=f_ys,
                                mode="lines",
                                line={"color": furniture_color, "width": 0.8},
                                opacity=opacity,
                                name=f"🛋️ Furniture ({len(linework['furniture'])} paths)",
                                legendgroup="AutoCAD Linework",
                            )
                        )
                # Other
                if linework.get("other"):
                    o_xs, o_ys = self._flatten_paths_to_xy(linework["other"][:5000])
                    if o_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=o_xs,
                                y=o_ys,
                                mode="lines",
                                line={"color": plan_line_color, "width": 1.5},
                                opacity=opacity,
                                name=f"🏛️ Plan Linework ({len(linework['other'])} segs)",
                                legendgroup="AutoCAD Linework",
                            )
                        )

        # =====================================================================
        # TIER B: AUTOSPEC TAKEOFF MEASUREMENT OVERLAYS & HIGHLIGHTS
        # =====================================================================
        if focus_mode != "linework_only":
            # 1. Civil Wall Takeoff Measurements (Gross Wall Area)
            if highlight_walls and wall_segments and (visible_trades is None or any("Wall" in t or "Civil" in t or "Masonry" in t or "Plaster" in t for t in visible_trades)):
                w_xs: list[float | None] = []
                w_ys: list[float | None] = []
                for w in wall_segments:
                    w_xs.extend([w["x1"], w["x2"], None])
                    w_ys.extend([w["y1"], w["y2"], None])

                wall_hl_color = "#FF3366"  # Glowing Neon Coral
                fig.add_trace(
                    go.Scatter(
                        x=w_xs,
                        y=w_ys,
                        mode="lines",
                        line={"color": wall_hl_color, "width": 3.0},
                        name=f"🧱 Measured Walls ({getattr(self.takeoff, 'wall_length_m', 0.0):.1f}m / {getattr(self.takeoff, 'total_wall_area_sqm', 0.0):.1f}m²)",
                        legendgroup="Takeoff Highlights",
                        legendgrouptitle_text="🎯 AutoSpec Takeoff Highlights (BOQ Link)",
                        hoverinfo="text",
                        hovertext=(
                            f"<b>Civil Masonry Wall Takeoff</b><br>"
                            f"Total Wall Length: {getattr(self.takeoff, 'wall_length_m', 0.0):.1f} m<br>"
                            f"Standard Wall Height: 3.00 m<br>"
                            f"Gross Wall Area: {getattr(self.takeoff, 'total_wall_area_sqm', 0.0):.1f} m²<br>"
                            f"BOQ Trade: Civil Masonry & Internal Plastering"
                        ),
                    )
                )

            # 2. Flooring & Room Polygon Takeoff (Net Floor Area)
            if highlight_floors and room_polygons:
                sorted_rooms = sorted(room_polygons, key=lambda r: r.get("area_sqm", 0.0), reverse=True)
                top_rooms = sorted_rooms[:25]
                remaining_rooms = sorted_rooms[25:]

                for idx, room in enumerate(top_rooms):
                    pts = room.get("points", [])
                    if len(pts) >= 3:
                        rx = [p[0] for p in pts] + [pts[0][0]]
                        ry = [p[1] for p in pts] + [pts[0][1]]
                        area = room.get("area_sqm", 0.0)
                        layer = room.get("layer", "FLOR")

                        fig.add_trace(
                            go.Scatter(
                                x=rx,
                                y=ry,
                                mode="lines",
                                fill="toself",
                                fillcolor=room_fill_color,
                                line={"color": room_line_color, "width": 2.0, "dash": "dot"},
                                name=f"📐 Measured Floor ({area:.1f} m²)",
                                legendgroup="Takeoff Highlights",
                                legendgrouptitle_text="🎯 AutoSpec Takeoff Highlights (BOQ Link)" if not (highlight_walls and wall_segments) else None,
                                showlegend=(idx == 0),
                                hovertext=(
                                    f"<b>Flooring Takeoff Zone</b><br>"
                                    f"Layer: {layer}<br>"
                                    f"Net Floor Area: {area:.2f} m² ({(area * 10.764):.1f} sq.ft)<br>"
                                    f"BOQ Trade: Flooring & Finishes<br>"
                                    f"Matched SKU: Vitrified Tiles / Granite"
                                ),
                                hoverinfo="text",
                            )
                        )

                if remaining_rooms:
                    rem_xs: list[float | None] = []
                    rem_ys: list[float | None] = []
                    for room in remaining_rooms:
                        pts = room.get("points", [])
                        if len(pts) >= 3:
                            for p in pts:
                                rem_xs.append(p[0])
                                rem_ys.append(p[1])
                            rem_xs.append(pts[0][0])
                            rem_xs.append(pts[0][1])
                            rem_xs.append(None)
                            rem_xs.append(None)
                    if rem_xs:
                        fig.add_trace(
                            go.Scatter(
                                x=rem_xs,
                                y=rem_ys,
                                mode="lines",
                                line={"color": room_line_color, "width": 1.2, "dash": "dot"},
                                name=f"📐 Additional Floor Polygons ({len(remaining_rooms)})",
                                legendgroup="Takeoff Highlights",
                                showlegend=False,
                                hoverinfo="skip",
                            )
                        )

            # 3. IS 1200 Statutory Deduction Openings (Tier-Coded Markers)
            if highlight_openings and openings:
                tier1_xs, tier1_ys, tier1_texts, tier1_hovers = [], [], [], []
                tier2_xs, tier2_ys, tier2_texts, tier2_hovers = [], [], [], []
                tier3_xs, tier3_ys, tier3_texts, tier3_hovers = [], [], [], []

                for op in openings:
                    if getattr(op, "x", None) is not None and getattr(op, "y", None) is not None:
                        x, y = op.x, op.y
                    else:
                        x = (bounding_box.get("min_x", 0) + bounding_box.get("max_x", 10)) / 2
                        y = (bounding_box.get("min_y", 0) + bounding_box.get("max_y", 10)) / 2

                    lbl = f"{op.id}: {op.width_m:.1f}×{op.height_m:.1f}m" if label_mode in ("openings", "all") else ""

                    if op.area_sqm <= 0.5:
                        tier_label = "Tier 1 (<= 0.5 m²)"
                        stat_rule = "Zero Deduction (Exempt from Plaster & Masonry)"
                        tier1_xs.append(x)
                        tier1_ys.append(y)
                        tier1_texts.append(lbl)
                        tier1_hovers.append(
                            f"<b>{op.id} — {op.type} Opening</b><br>"
                            f"Dimensions: {op.width_m:.2f}m × {op.height_m:.2f}m = {op.area_sqm:.2f} m²<br>"
                            f"<b>IS 1200 Part 12:</b> {tier_label} — {stat_rule}<br>"
                            f"CAD Reference: {op.cad_ref}"
                        )
                    elif op.area_sqm <= 3.0:
                        tier_label = "Tier 2 (0.5 to 3.0 m²)"
                        stat_rule = f"Single Face Deducted (-{op.area_sqm:.2f} m²)"
                        tier2_xs.append(x)
                        tier2_ys.append(y)
                        tier2_texts.append(lbl)
                        tier2_hovers.append(
                            f"<b>{op.id} — {op.type} Opening</b><br>"
                            f"Dimensions: {op.width_m:.2f}m × {op.height_m:.2f}m = {op.area_sqm:.2f} m²<br>"
                            f"<b>IS 1200 Part 12:</b> {tier_label} — {stat_rule}<br>"
                            f"CAD Reference: {op.cad_ref}"
                        )
                    else:
                        tier_label = "Tier 3 (> 3.0 m²)"
                        stat_rule = f"Both Faces Deducted (-{2 * op.area_sqm:.2f} m²) + Reveals Added"
                        tier3_xs.append(x)
                        tier3_ys.append(y)
                        tier3_texts.append(lbl)
                        tier3_hovers.append(
                            f"<b>{op.id} — {op.type} Opening</b><br>"
                            f"Dimensions: {op.width_m:.2f}m × {op.height_m:.2f}m = {op.area_sqm:.2f} m²<br>"
                            f"<b>IS 1200 Part 12:</b> {tier_label} — {stat_rule}<br>"
                            f"CAD Reference: {op.cad_ref}"
                        )

                # Tier 1 Openings
                if tier1_xs:
                    fig.add_trace(
                        go.Scatter(
                            x=tier1_xs,
                            y=tier1_ys,
                            mode="markers+text" if label_mode in ("openings", "all") else "markers",
                            marker={"size": 13, "color": "#10B981", "symbol": "square-open-dot", "line": {"color": "#059669", "width": 2}},
                            text=tier1_texts,
                            textposition="bottom center",
                            textfont={"size": 9, "color": "#10B981"},
                            hovertext=tier1_hovers,
                            hoverinfo="text",
                            name=f"🟢 Openings (IS 1200 Tier 1: Exempt) ({len(tier1_xs)} nos)",
                            legendgroup="Takeoff Highlights",
                        )
                    )
                # Tier 2 Openings
                if tier2_xs:
                    fig.add_trace(
                        go.Scatter(
                            x=tier2_xs,
                            y=tier2_ys,
                            mode="markers+text" if label_mode in ("openings", "all") else "markers",
                            marker={"size": 14, "color": "#F59E0B", "symbol": "diamond-wide", "line": {"color": "#B45309", "width": 2}},
                            text=tier2_texts,
                            textposition="bottom center",
                            textfont={"size": 9, "color": "#F59E0B"},
                            hovertext=tier2_hovers,
                            hoverinfo="text",
                            name=f"🟠 Openings (IS 1200 Tier 2: 1-Face Deduct) ({len(tier2_xs)} nos)",
                            legendgroup="Takeoff Highlights",
                        )
                    )
                # Tier 3 Openings
                if tier3_xs:
                    fig.add_trace(
                        go.Scatter(
                            x=tier3_xs,
                            y=tier3_ys,
                            mode="markers+text" if label_mode in ("openings", "all") else "markers",
                            marker={"size": 16, "color": "#EF4444", "symbol": "hexagon", "line": {"color": "#991B1B", "width": 2}},
                            text=tier3_texts,
                            textposition="bottom center",
                            textfont={"size": 9, "color": "#EF4444"},
                            hovertext=tier3_hovers,
                            hoverinfo="text",
                            name=f"🔴 Openings (IS 1200 Tier 3: 2-Faces + Reveals) ({len(tier3_xs)} nos)",
                            legendgroup="Takeoff Highlights",
                        )
                    )

            # 4. Classified Fixtures / Block Symbols (MEP & B2B Pins)
            if highlight_fixtures and block_instances:
                trade_groups: dict[str, list[dict[str, Any]]] = {}
                for inst in block_instances:
                    trade = inst.get("trade", "Other Architectural Fittings")
                    trade_groups.setdefault(trade, []).append(inst)

                trade_icons = {
                    "Electrical - Lighting": "💡",
                    "Electrical - Fans": "🌀",
                    "Electrical - Switches & Sockets": "🔌",
                    "Plumbing - Sanitaryware": "🚿",
                    "Furniture & Equipment": "🪑",
                    "Other Architectural Fittings": "📦",
                }

                for trade, instances in sorted(trade_groups.items()):
                    if visible_trades is not None:
                        short_name = trade.split(" - ")[-1]
                        if trade not in visible_trades and short_name not in visible_trades and not any(short_name in vt for vt in visible_trades):
                            continue

                    style = trade_palette.get(trade, trade_palette.get("Other Architectural Fittings", {}))
                    icon = trade_icons.get(trade, "📍")
                    bx = [b["x"] for b in instances]
                    by = [b["y"] for b in instances]
                    b_texts = [b["name"] if label_mode == "all" else "" for b in instances]
                    b_hovers = [
                        f"<b>{b['name']}</b><br>"
                        f"Trade: {trade}<br>"
                        f"Layer: {b['layer']}<br>"
                        f"Position: ({b['x']:.2f}, {b['y']:.2f})<br>"
                        f"Rotation: {b.get('rotation', 0):.0f}°"
                        for b in instances
                    ]

                    fig.add_trace(
                        go.Scatter(
                            x=bx,
                            y=by,
                            mode="markers+text" if label_mode == "all" else "markers",
                            marker={
                                "size": 11,
                                "color": style.get("color", "#FACC15"),
                                "symbol": style.get("symbol", "circle"),
                                "line": {"color": marker_border, "width": 1.5},
                            },
                            text=b_texts,
                            textposition="top right",
                            textfont={"size": 8, "color": style.get("color", title_color)},
                            hovertext=b_hovers,
                            hoverinfo="text",
                            name=f"{icon} {trade.split(' - ')[-1]} ({len(instances)} pcs)",
                            legendgroup="Takeoff Highlights",
                        )
                    )

        # =====================================================================
        # CAMERA & FOCUS BOUNDS (Auto-focus strictly to building geometry)
        # =====================================================================
        if bounding_box and bounding_box.get("width", 0.0) > 0.1:
            min_x = bounding_box["min_x"]
            max_x = bounding_box["max_x"]
            min_y = bounding_box["min_y"]
            max_y = bounding_box["max_y"]
            pad_x = max(1.5, (max_x - min_x) * 0.05)
            pad_y = max(1.5, (max_y - min_y) * 0.05)
            range_x = [min_x - pad_x, max_x + pad_x]
            range_y = [min_y - pad_y, max_y + pad_y]
        else:
            focus_xs, focus_ys = [], []
            if linework.get("walls"):
                for p in linework["walls"][:500]:
                    for pt in p:
                        focus_xs.append(pt[0])
                        focus_ys.append(pt[1])
            elif linework.get("other"):
                for p in linework["other"][:500]:
                    for pt in p:
                        focus_xs.append(pt[0])
                        focus_ys.append(pt[1])
            elif wall_segments:
                for w in wall_segments:
                    focus_xs.extend([w["x1"], w["x2"]])
                    focus_ys.extend([w["y1"], w["y2"]])

            if not focus_xs and block_instances:
                focus_xs = [b["x"] for b in block_instances]
                focus_ys = [b["y"] for b in block_instances]

            if focus_xs and focus_ys:
                min_x, max_x = min(focus_xs), max(focus_xs)
                min_y, max_y = min(focus_ys), max(focus_ys)
                pad_x = max(1.5, (max_x - min_x) * 0.05)
                pad_y = max(1.5, (max_y - min_y) * 0.05)
                range_x = [min_x - pad_x, max_x + pad_x]
                range_y = [min_y - pad_y, max_y + pad_y]
            else:
                range_x = [-2, 40]
                range_y = [-2, 30]

        unit_label = getattr(self.takeoff, "units", "m").upper()
        file_name = getattr(self.takeoff, "file_name", "CAD Drawing")

        fig.update_layout(
            title={
                "text": f"<b>Interactive Vector Visualizer</b> — {file_name} ({unit_label})",
                "x": 0.02,
                "y": 0.98,
                "font": {"size": 15, "color": title_color},
            },
            xaxis={
                "title": f"X Coordinate ({unit_label})",
                "showgrid": True,
                "zeroline": False,
                "gridcolor": grid_color,
                "range": range_x,
                "scaleanchor": "y",
                "scaleratio": 1,  # 1:1 True Isometric CAD Scale
            },
            yaxis={
                "title": f"Y Coordinate ({unit_label})",
                "showgrid": True,
                "zeroline": False,
                "gridcolor": grid_color,
                "range": range_y,
            },
            plot_bgcolor=bg_color,
            paper_bgcolor=bg_color,
            height=plot_height,
            margin={"l": 40, "r": 230, "t": 50, "b": 40},  # Right margin for orderly vertical legend
            legend={
                "orientation": "v",
                "yanchor": "top",
                "y": 1.0,
                "xanchor": "left",
                "x": 1.02,
                "bgcolor": legend_bg,
                "bordercolor": legend_border,
                "borderwidth": 1,
                "font": {"size": 10, "color": title_color},
                "tracegroupgap": 8,
            },
            dragmode="pan",
            hovermode="closest",
        )

        return fig

    def generate_blueprint_image(self, dxf_path: str, dpi: int = 120) -> bytes | None:
        """Renders a high-resolution 2D CAD vector blueprint PNG using ezdxf matplotlib backend."""
        if not os.path.exists(dxf_path):
            return None

        try:
            import matplotlib.pyplot as plt
            from ezdxf.addons.drawing import Frontend, RenderContext
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()

            fig = plt.figure(figsize=(12, 8), dpi=dpi)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_facecolor("#FFFFFF")

            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp, finalize=True)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="#FFFFFF")
            plt.close(fig)
            buf.seek(0)
            return buf.getvalue()
        except Exception:
            return None
