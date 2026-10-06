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
        label_mode: str = "none",
        focus_mode: str = "blueprint",
        show_opening_labels: bool | None = None,
        show_block_labels: bool | None = None,
        plot_height: int = 650,
        dark_mode: bool = True,
        theme: str = "dark",  # "dark", "blueprint", "light"
    ) -> go.Figure:
        """Constructs a two-tier interactive Plotly CAD vector canvas.

        Tier A: Base Architectural CAD Linework (Walls, Doors, Windows, Stairs, Furniture)
        Tier B: AutoSpec Takeoff Highlights (Statutory IS 1200 Openings, Floor Boundaries, SKUs)
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
        # Normalize theme choice
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
            room_fill_color = "rgba(56, 189, 248, 0.12)"
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
            room_fill_color = "rgba(16, 185, 129, 0.12)"
            room_line_color = "#059669"
            trade_palette = self.TRADE_PALETTE_LIGHT
            marker_border = "#0F172A"
            title_color = "#0F172A"
            axis_color = "#475569"
            legend_bg = "rgba(255, 255, 255, 0.92)"
            legend_border = "#CBD5E0"
        else:  # "dark" / AutoCAD Model Space (DEFAULT!)
            bg_color = "#0D1117"  # Deep midnight dark matching Streamlit!
            grid_color = "#1E293B"
            wall_color = "#F8FAFC"  # Crisp bright white!
            door_color = "#FB923C"  # Vibrant amber orange!
            window_color = "#38BDF8"  # Electric sky cyan!
            stair_color = "#94A3B8"  # Crisp silver slate!
            furniture_color = "#64748B" if focus_mode != "takeoff_focus" else "rgba(100, 116, 139, 0.25)"
            plan_line_color = "#E2E8F0"  # Bright crisp linework!
            room_fill_color = "rgba(16, 185, 129, 0.14)"
            room_line_color = "#10B981"
            trade_palette = self.TRADE_PALETTE_DARK
            marker_border = "#000000"
            title_color = "#F8FAFC"
            axis_color = "#94A3B8"
            legend_bg = "rgba(13, 17, 23, 0.90)"
            legend_border = "#30363D"

        linework = getattr(self.takeoff, "architectural_linework", {})
        wall_segments = getattr(self.takeoff, "wall_segments", [])
        room_polygons = getattr(self.takeoff, "room_polygons", [])
        openings = getattr(self.takeoff, "openings", [])
        block_instances = getattr(self.takeoff, "block_instances", [])
        bounding_box = getattr(self.takeoff, "bounding_box", {})

        # Default visible layers if not provided
        if visible_layers is None:
            visible_layers = ["Walls", "Doors", "Windows", "Stairs", "Furniture"]

        # =====================================================================
        # TIER A: BASE ARCHITECTURAL CAD LINEWORK
        # =====================================================================

        # 1. Civil Masonry Walls
        if "Walls" in visible_layers and (visible_trades is None or any("Wall" in t for t in visible_trades)):
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
                        line={"color": wall_color, "width": 2.4},
                        name=f"🏛️ Walls ({len(wall_segments) or len(wall_paths)} segs)",
                        legendgroup="Base Linework",
                        legendgrouptitle_text="🏛️ Architectural Linework",
                        hoverinfo="text",
                        hovertext=f"<b>Civil Masonry Wall</b><br>Gross Wall Length: {getattr(self.takeoff, 'wall_length_m', 0.0):.1f} m<br>Gross Wall Area: {getattr(self.takeoff, 'total_wall_area_sqm', 0.0):.1f} m²",
                    )
                )

        # 2. Doors & Swing Arcs
        if (
            "Doors" in visible_layers
            and (visible_trades is None or any("Door" in t or "Opening" in t for t in visible_trades))
            and linework.get("doors")
        ):
            d_paths = linework["doors"]
            d_xs, d_ys = self._flatten_paths_to_xy(d_paths)
            if d_xs:
                fig.add_trace(
                    go.Scatter(
                        x=d_xs,
                        y=d_ys,
                        mode="lines",
                        line={"color": door_color, "width": 1.3},
                        name=f"🚪 Doors & Swings ({len(d_paths)} paths)",
                        legendgroup="Base Linework",
                        hoverinfo="text",
                        hovertext="<b>Door Leaf & Swing Arc</b><br>Layer: Puertas / A-DOOR",
                    )
                )

        # 3. Windows & Glazing Mullions
        if (
            "Windows" in visible_layers
            and (visible_trades is None or any("Window" in t or "Opening" in t for t in visible_trades))
            and linework.get("windows")
        ):
            win_paths = linework["windows"]
            win_xs, win_ys = self._flatten_paths_to_xy(win_paths)
            if win_xs:
                fig.add_trace(
                    go.Scatter(
                        x=win_xs,
                        y=win_ys,
                        mode="lines",
                        line={"color": window_color, "width": 1.5},
                        name=f"🪟 Windows ({len(win_paths)} paths)",
                        legendgroup="Base Linework",
                        hoverinfo="text",
                        hovertext="<b>Window Frame & Glazing</b><br>Layer: WINDOW / A-GLAZ",
                    )
                )

        # 4. Stairs & Vertical Core Shafts
        if (
            "Stairs" in visible_layers
            and (visible_trades is None or any("Stair" in t or "Wall" in t for t in visible_trades))
            and linework.get("stairs")
        ):
            st_paths = linework["stairs"]
            st_xs, st_ys = self._flatten_paths_to_xy(st_paths)
            if st_xs:
                fig.add_trace(
                    go.Scatter(
                        x=st_xs,
                        y=st_ys,
                        mode="lines",
                        line={"color": stair_color, "width": 1.1},
                        name=f"🪜 Stairs & Core ({len(st_paths)} paths)",
                        legendgroup="Base Linework",
                        hoverinfo="text",
                        hovertext="<b>Stairs & Elevator Shaft</b><br>Layer: STAIR / CORE",
                    )
                )

        # 5. Built-in Furniture, Equipment & Fixtures
        if (
            "Furniture" in visible_layers
            and (visible_trades is None or any("Furn" in t for t in visible_trades))
            and linework.get("furniture")
        ):
            f_paths = linework["furniture"]
            f_xs, f_ys = self._flatten_paths_to_xy(f_paths)
            if f_xs:
                fig.add_trace(
                    go.Scatter(
                        x=f_xs,
                        y=f_ys,
                        mode="lines",
                        line={"color": furniture_color, "width": 0.8},
                        name=f"🛋️ Furniture ({len(f_paths)} paths)",
                        legendgroup="Base Linework",
                        hoverinfo="text",
                        hovertext="<b>Built-in Furniture & Fixtures</b><br>Tables, Chairs, Beds, Sanitaries",
                    )
                )

        # 6. General / Unclassified Plan Linework (Layer 0, Geometry, etc.)
        other_paths = linework.get("other", [])
        if other_paths and (not linework.get("walls") or len(linework.get("walls")) < 10):
            o_xs, o_ys = self._flatten_paths_to_xy(other_paths[:8000])
            if o_xs:
                fig.add_trace(
                    go.Scatter(
                        x=o_xs,
                        y=o_ys,
                        mode="lines",
                        line={"color": plan_line_color, "width": 1.8},
                        name=f"🏛️ Plan Linework ({min(len(other_paths), 8000)} segs)",
                        legendgroup="Base Linework",
                        legendgrouptitle_text="🏛️ Architectural Linework",
                        hoverinfo="text",
                        hovertext="<b>Architectural Plan Geometry</b>",
                    )
                )

        # =====================================================================
        # TIER B: AUTOSPEC TAKEOFF OVERLAYS & HIGHLIGHTS
        # =====================================================================
        if focus_mode != "linework_only":
            # 1. Floor & Room Boundaries
            if visible_trades is None or any("Floor" in t or "Room" in t for t in visible_trades):
                sorted_rooms = sorted(room_polygons, key=lambda r: r.get("area_sqm", 0.0), reverse=True)
                top_rooms = sorted_rooms[:20]
                remaining_rooms = sorted_rooms[20:]

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
                                line={"color": room_line_color, "width": 1.6, "dash": "dot"},
                                name=f"📐 Floor Boundary ({area:.0f} m²)",
                                legendgroup="Takeoff Highlights",
                                legendgrouptitle_text="🎯 Takeoff Highlights",
                                showlegend=(idx == 0),
                                hovertext=f"<b>Measured Floor Area</b><br>Layer: {layer}<br>Area: {area:.2f} m² ({(area * 10.764):.1f} sq.ft)",
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

            # 2. IS 1200 Opening Deductions
            if visible_trades is None or any("Opening" in t for t in visible_trades):
                op_xs, op_ys, op_labels, op_hovers = [], [], [], []
                for op in openings:
                    if getattr(op, "x", None) is not None and getattr(op, "y", None) is not None:
                        x, y = op.x, op.y
                    else:
                        matched_inst = next(
                            (
                                b
                                for b in block_instances
                                if op.id in b.get("name", "")
                                or "DOOR" in b.get("name", "").upper()
                                or "PUERT" in b.get("name", "").upper()
                            ),
                            None,
                        )
                        if matched_inst:
                            x, y = matched_inst["x"], matched_inst["y"]
                        else:
                            x = (bounding_box.get("min_x", 0) + bounding_box.get("max_x", 10)) / 2
                            y = (bounding_box.get("min_y", 0) + bounding_box.get("max_y", 10)) / 2

                    op_xs.append(x)
                    op_ys.append(y)
                    op_labels.append(
                        f"{op.id}: {op.width_m:.1f}×{op.height_m:.1f}m" if label_mode in ("openings", "all") else ""
                    )
                    op_hovers.append(
                        f"<b>{op.id} — {op.type} Opening</b><br>"
                        f"Dimensions: {op.width_m:.2f} m × {op.height_m:.2f} m<br>"
                        f"Opening Area: {op.area_sqm:.2f} m²<br>"
                        f"<b>IS 1200 Status:</b> {'Deducted from Wall & Plaster' if op.area_sqm > 0.1 else 'Exempt (<= 0.1 m²)'}<br>"
                        f"CAD Reference: {op.cad_ref}"
                    )

                if op_xs:
                    op_marker_color = "#FB923C" if active_theme != "light" else "#C2410C"
                    op_border_color = "#C2410C" if active_theme != "light" else "#7C2D12"
                    fig.add_trace(
                        go.Scatter(
                            x=op_xs,
                            y=op_ys,
                            mode="markers+text" if label_mode in ("openings", "all") else "markers",
                            marker={
                                "size": 12,
                                "color": op_marker_color,
                                "symbol": "square-cross",
                                "line": {"color": op_border_color, "width": 1.5},
                            },
                            text=op_labels,
                            textposition="bottom center",
                            textfont={"size": 9, "color": op_marker_color},
                            hovertext=op_hovers,
                            hoverinfo="text",
                            name=f"🏷️ Openings ({len(op_xs)} Deductions)",
                            legendgroup="Takeoff Highlights",
                            legendgrouptitle_text="🎯 Takeoff Highlights" if not room_polygons else None,
                        )
                    )

            # 3. Block Symbols Grouped by Trade
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
                # Check trade visibility filter
                if visible_trades is not None:
                    short_name = trade.split(" - ")[-1]
                    if (
                        trade not in visible_trades
                        and short_name not in visible_trades
                        and not any(short_name in vt for vt in visible_trades)
                    ):
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
                            "size": 10,
                            "color": style.get("color", "#FACC15"),
                            "symbol": style.get("symbol", "circle"),
                            "line": {"color": marker_border, "width": 1.2},
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
        if bounding_box and bounding_box.get("max_x", 0.0) > bounding_box.get("min_x", 0.0):
            min_x = bounding_box["min_x"]
            max_x = bounding_box["max_x"]
            min_y = bounding_box["min_y"]
            max_y = bounding_box["max_y"]
            pad_x = max(2.0, (max_x - min_x) * 0.08)
            pad_y = max(2.0, (max_y - min_y) * 0.08)
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
                pad_x = max(2.0, (max_x - min_x) * 0.08)
                pad_y = max(2.0, (max_y - min_y) * 0.08)
                range_x = [min_x - pad_x, max_x + pad_x]
                range_y = [min_y - pad_y, max_y + pad_y]
            else:
                range_x = [-10, 50]
                range_y = [-10, 50]

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
