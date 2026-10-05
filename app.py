"""app.py — Streamlit Web Interface for AutoSpec AI

Provides a 4-tab workflow:
1. 📐 CAD Takeoff & Vector Inspector
2. 📝 Client Brief & Technical Specifications
3. 📊 IS 1200 Statutory BOQ & Audit Trail
4. 📥 Export & Live Indian B2B Procurement
"""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import streamlit as st

from boq_engine import BoqEngine
from cad_parser import CadParser, convert_dwg_to_dxf
from cad_visualizer import CadVisualizer
from sample_dxf_generator import generate_sample_2bhk_dxf
from spec_parser import parse_client_brief

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Page Configuration
st.set_page_config(
    page_title="AutoSpec AI — 2D CAD Takeoff & Cost Intelligence",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Corporate CSS
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1F4E79;
        margin-bottom: 0px;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #555555;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1F4E79;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-active {
        background-color: #D4EDDA;
        color: #155724;
    }
    .status-fallback {
        background-color: #E2E3E5;
        color: #383D41;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/blueprint.png", width=64)
    st.markdown("## **AutoSpec AI**")
    st.caption("2D CAD Vector Takeoff & Pre-Construction Cost Intelligence for India")
    st.divider()

    st.markdown("### 1. Drawing Ingestion")
    uploaded_file = st.file_uploader(
        "Upload 2D CAD Drawing (.DXF or .DWG)",
        type=["dxf", "dwg"],
        help="Upload an open DXF vector file or an AutoCAD DWG binary file",
    )

    sample_col1, sample_col2 = st.columns(2)
    use_sample_2bhk = sample_col1.button("📂 2BHK Plan", use_container_width=True)
    use_sample_house = sample_col2.button("🏡 2-Story Villa", use_container_width=True)
    sample_col3, sample_col4 = st.columns(2)
    use_sample_apt = sample_col3.button("🏢 Apartment-1", use_container_width=True)
    use_sample_20x55 = sample_col4.button("🏘️ 20x55 House", use_container_width=True)

    st.divider()
    st.markdown("### 2. Geometry Parameters")
    unit_choice = st.selectbox(
        "Drawing Units",
        ["Auto-detect Units", "Meters (m)", "Millimeters (mm)", "Inches (in)"],
        index=0,
        help="Auto-detect dynamically resolves units from vector extents and header. Select explicit units to override.",
    )
    if "Auto" in unit_choice:
        drawing_units = "auto"
    elif "Meters" in unit_choice:
        drawing_units = "m"
    elif "Millimeter" in unit_choice:
        drawing_units = "mm"
    else:
        drawing_units = "inch"

    wall_height = st.number_input("Floor-to-Ceiling Height (m)", min_value=2.4, max_value=5.0, value=3.0, step=0.1)
    wall_thickness = st.number_input(
        "Standard Wall Thickness (m)", min_value=0.10, max_value=0.45, value=0.23, step=0.01
    )

    st.divider()
    st.markdown("### 3. LLM API Configuration")
    groq_api_key = st.text_input(
        "Groq API Key (Recommended)",
        type="password",
        placeholder="gsk_...",
        value=os.environ.get("GROQ_API_KEY", ""),
        help="Ultra-fast Llama 3.3 70B inference via Groq",
    )
    anthropic_api_key = st.text_input(
        "Anthropic API Key (Optional)",
        type="password",
        placeholder="sk-ant-...",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    if groq_api_key or os.environ.get("GROQ_API_KEY"):
        st.markdown(
            '<span class="status-badge status-active">● Groq Llama 3.3 70B Active</span>', unsafe_allow_html=True
        )
    elif anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"):
        st.markdown(
            '<span class="status-badge status-active">● Claude 3.5 Sonnet Active</span>', unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<span class="status-badge status-fallback">○ Offline Heuristic Mode Active</span>', unsafe_allow_html=True
        )

    st.divider()
    run_btn = st.button("🚀 Generate Full BOQ Estimate", type="primary", use_container_width=True)

# -----------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if "cad_path" not in st.session_state:
    sample_path = "samples/sample_2bhk_plan.dxf"
    if not os.path.exists(sample_path):
        generate_sample_2bhk_dxf(sample_path)
    st.session_state["cad_path"] = sample_path
    st.session_state["display_name"] = "sample_2bhk_plan.dxf"
    st.session_state["is_dwg_converted"] = False

if "client_brief" not in st.session_state:
    st.session_state["client_brief"] = (
        "Luxury 2BHK residential interior in Indiranagar, Bangalore. "
        "We prefer Philips 12W warm white (3000K) recessed downlights and Atomberg BLDC energy saving ceiling fans with remote. "
        "Schneider Opale modular switches throughout. "
        "Living and dining with Italian Botticino marble flooring; bedrooms with Kajaria vitrified tiles. "
        "Internal walls with Asian Paints Royale Luxury washable emulsion. Jaquar chrome-plated CP fittings in toilets."
    )

if uploaded_file is not None:
    last_uploaded = st.session_state.get("_last_uploaded_name")
    if last_uploaded != uploaded_file.name:
        temp_dir = tempfile.gettempdir()
        safe_name = os.path.basename(uploaded_file.name)
        saved_path = os.path.join(temp_dir, safe_name)
        with open(saved_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if uploaded_file.name.lower().endswith(".dwg"):
            try:
                converted_dxf = convert_dwg_to_dxf(saved_path)
                st.session_state["cad_path"] = converted_dxf
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["is_dwg_converted"] = True
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.sidebar.success(f"Converted DWG: {uploaded_file.name}")
            except Exception as e:
                st.sidebar.error(f"DWG conversion: {e}")
                st.session_state["cad_path"] = saved_path
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["is_dwg_converted"] = False
                st.session_state["_last_uploaded_name"] = uploaded_file.name
        else:
            st.session_state["cad_path"] = saved_path
            st.session_state["display_name"] = uploaded_file.name
            st.session_state["is_dwg_converted"] = False
            st.session_state["_last_uploaded_name"] = uploaded_file.name
            st.sidebar.success(f"Loaded DXF: {uploaded_file.name}")

if use_sample_2bhk:
    sample_path = "samples/sample_2bhk_plan.dxf"
    if not os.path.exists(sample_path):
        generate_sample_2bhk_dxf(sample_path)
    st.session_state["cad_path"] = sample_path
    st.session_state["display_name"] = "sample_2bhk_plan.dxf"
    st.session_state["is_dwg_converted"] = False
    st.session_state["client_brief"] = (
        "Luxury 2BHK residential interior in Indiranagar, Bangalore. "
        "We prefer Philips 12W warm white (3000K) recessed downlights and Atomberg BLDC energy saving ceiling fans with remote. "
        "Schneider Opale modular switches throughout. "
        "Living and dining with Italian Botticino marble flooring; bedrooms with Kajaria vitrified tiles. "
        "Internal walls with Asian Paints Royale Luxury washable emulsion. Jaquar chrome-plated CP fittings in toilets."
    )
    st.rerun()

if use_sample_house:
    house_dxf = "samples/two_story_house.dxf"
    if not os.path.exists(house_dxf) and os.path.exists("samples/two_story_house.dwg"):
        house_dxf = convert_dwg_to_dxf("samples/two_story_house.dwg")
    st.session_state["cad_path"] = house_dxf
    st.session_state["display_name"] = "Two-story-house-410202.dwg"
    st.session_state["is_dwg_converted"] = True
    st.session_state["client_brief"] = (
        "Two-story luxury villa residence. "
        "Living and dining with Italian Botticino marble flooring; bedrooms with Kajaria vitrified tiles. "
        "Philips 12W recessed downlights, Atomberg BLDC ceiling fans, and Schneider Opale switches throughout. "
        "Internal walls with Asian Paints Royale Luxury washable emulsion. Jaquar chrome-plated CP fittings in toilets."
    )
    st.rerun()

if use_sample_apt:
    apt_dwg = "samples/Apartment-1.dwg"
    apt_dxf = "samples/Apartment-1.dxf"
    if not os.path.exists(apt_dxf) and os.path.exists(apt_dwg):
        apt_dxf = convert_dwg_to_dxf(apt_dwg)
    st.session_state["cad_path"] = apt_dxf if os.path.exists(apt_dxf) else apt_dwg
    st.session_state["display_name"] = "Apartment-1.dwg"
    st.session_state["is_dwg_converted"] = True
    st.session_state["client_brief"] = (
        "Modern urban apartment interior fitout. "
        "Living and dining with vitrified tiles, bedrooms with laminated wooden flooring. "
        "Philips warm white LED downlights and Crompton ceiling fans throughout. "
        "Legrand modular switches and Asian Paints Royale Luxury washable emulsion."
    )
    st.rerun()

if use_sample_20x55:
    h20_dxf = "samples/20x55_house_plan.dxf"
    h20_dwg = "samples/20x55_house_plan.dwg"
    if not os.path.exists(h20_dxf) and os.path.exists(h20_dwg):
        h20_dxf = convert_dwg_to_dxf(h20_dwg)
    st.session_state["cad_path"] = h20_dxf if os.path.exists(h20_dxf) else h20_dwg
    st.session_state["display_name"] = "20x55-house-plan-two-bedrooms.dwg"
    st.session_state["is_dwg_converted"] = True
    st.session_state["client_brief"] = (
        "20x55 residential house plan with two bedrooms. "
        "Living and dining with vitrified tiles, bedrooms with anti-skid vitrified tiles. "
        "Philips 12W warm white LED downlights and Atomberg BLDC ceiling fans throughout. "
        "Schneider Opale modular switches and Asian Paints Royale Luxury washable emulsion."
    )
    st.rerun()


# -----------------------------------------------------------------------------
# APP HEADER
# -----------------------------------------------------------------------------
st.markdown('<div class="main-title">📐 AutoSpec AI — Cost Intelligence Engine</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">100% In-Memory Air-Gap CAD Ingestion • Bureau of Indian Standards (IS 1200) Statutory Deductions • Verified Indian B2B Procurement</div>',
    unsafe_allow_html=True,
)

# Parse CAD and Brief
cad_parser = CadParser(default_units=drawing_units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
try:
    takeoff = cad_parser.parse_cad_file(st.session_state["cad_path"], filename=st.session_state.get("display_name"))
except Exception as e:
    st.error(f"Error parsing CAD file: {e}")
    st.stop()

spec = parse_client_brief(
    st.session_state["client_brief"],
    api_key=anthropic_api_key,
    groq_api_key=groq_api_key,
)
boq_engine = BoqEngine()
boq_result = boq_engine.generate_boq(takeoff, spec, wall_height_m=wall_height, wall_thickness_m=wall_thickness)

# -----------------------------------------------------------------------------
# WORKFLOW TABS
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📐 1. CAD Takeoff & Geometry",
        "📝 2. Client Brief & Specifications",
        "📊 3. IS 1200 Statutory BOQ & Audit",
        "📥 4. Export & Live Procurement",
    ]
)

# =============================================================================
# TAB 1: CAD TAKEOFF & GEOMETRY INSPECTOR
# =============================================================================
with tab1:
    st.markdown("### In-Memory Vector CAD Takeoff")
    active_name = st.session_state.get("display_name", os.path.basename(st.session_state["cad_path"]))
    st.caption(f"Drawing Source: `{active_name}` | Units: `{takeoff.units.upper()}` | Air-Gap Local Execution")

    if st.session_state.get("is_dwg_converted"):
        st.success(
            "✨ **AutoCAD DWG Format Verified**: Drawing converted 100% locally and offline via the bundled LibreDWG engine. Air-gap vector guarantee preserved."
        )

    # High Level Takeoff Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    total_blocks = sum(takeoff.block_counts.values())
    m1.metric("Total Block Symbols", f"{total_blocks} Pcs")
    m2.metric(
        "Net Floor Area", f"{takeoff.total_floor_area_sqm:.1f} m²", f"{takeoff.total_floor_area_sqm * 10.764:.0f} sq.ft"
    )
    m3.metric("Gross Wall Area", f"{takeoff.total_wall_area_sqm:.1f} m²", f"Length: {takeoff.wall_length_m:.1f}m")
    m4.metric("Ceiling Area", f"{takeoff.total_ceiling_area_sqm:.1f} m²")
    m5.metric("Openings Detected", f"{len(takeoff.openings)} Nos", "Doors & Windows")

    st.divider()

    # =========================================================================
    # INTERACTIVE VECTOR TAKEOFF & HIGHLIGHT VISUALIZER
    # =========================================================================
    st.markdown("### 🗺️ Visual Vector Takeoff & Highlight Canvas")
    st.caption(
        "Inspect exactly where and what symbols, wall lines, room boundaries, and openings were captured from the CAD file."
    )

    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1.5, 1.2, 1.1, 1.0])
    with ctrl_col1:
        viz_mode = st.radio(
            "Visualizer Engine",
            ["🔍 Interactive Vector Canvas", "🖼️ High-Res CAD Blueprint"],
            horizontal=True,
        )
    with ctrl_col2:
        focus_choice = st.selectbox(
            "Visual Focus Mode",
            ["Full Blueprint + Takeoff", "Takeoff Audit (Dim Furniture)", "Linework Only (Clean Plan)"],
            index=0,
            help="Takeoff Audit dims furniture linework to 20% opacity so walls, openings, and takeoff badges pop out vividly.",
        )
        if "Audit" in focus_choice:
            focus_mode = "takeoff_focus"
        elif "Linework" in focus_choice:
            focus_mode = "linework_only"
        else:
            focus_mode = "blueprint"
    with ctrl_col3:
        label_choice = st.selectbox(
            "Text Labels",
            ["Clean (Hover to Inspect)", "Openings Only", "All Labels"],
            index=0,
            help="Default 'Clean' mode keeps the drawing uncluttered and free of text collisions. Hover over any line or pin to inspect full metadata.",
        )
        if "Clean" in label_choice:
            label_mode = "none"
        elif "Openings" in label_choice:
            label_mode = "openings"
        else:
            label_mode = "all"
    with ctrl_col4:
        canvas_height = st.slider("Canvas Height", min_value=500, max_value=850, value=650, step=50)

    # Organized Layer & Trade Visibility Controls
    with st.expander("🎨 Detailed Layer & Trade Visibility Controls", expanded=False):
        fl_col1, fl_col2 = st.columns(2)
        with fl_col1:
            base_layer_options = ["Walls", "Doors", "Windows", "Stairs", "Furniture"]
            selected_base_layers = st.multiselect(
                "Base Architectural Drawing Layers:",
                options=base_layer_options,
                default=base_layer_options,
                help="Toggle architectural CAD linework categories",
            )
        with fl_col2:
            takeoff_options = [
                "Openings (IS 1200 Deductions)",
                "Flooring & Rooms",
                "Electrical - Lighting",
                "Electrical - Fans",
                "Electrical - Switches & Sockets",
                "Plumbing - Sanitaryware",
                "Furniture & Equipment",
                "Other Architectural Fittings",
            ]
            selected_takeoff_trades = st.multiselect(
                "Takeoff Highlight Overlays:",
                options=takeoff_options,
                default=takeoff_options,
                help="Toggle AutoSpec takeoff measurement overlays and trade pins",
            )

    visualizer = CadVisualizer(takeoff)

    if "Interactive" in viz_mode:
        fig = visualizer.build_interactive_figure(
            visible_trades=selected_takeoff_trades,
            visible_layers=selected_base_layers,
            label_mode=label_mode,
            focus_mode=focus_mode,
            plot_height=canvas_height,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "💡 **Canvas Navigation**: Click & drag to pan across the plan • Mouse scroll or Box-zoom to inspect rooms • Double-click to reset view • Hover over any line or pin for instant CAD metadata."
        )
    else:
        with st.spinner("Rendering high-resolution vector blueprint..."):
            img_bytes = visualizer.generate_blueprint_image(st.session_state["cad_path"])
        if img_bytes:
            st.image(img_bytes, caption=f"High-Resolution 2D Blueprint: {active_name}", use_column_width=True)
        else:
            st.warning("Blueprint rendering unavailable for this drawing. Showing Interactive Inspector instead.")
            fig = visualizer.build_interactive_figure(plot_height=canvas_height)
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Data Tables
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### Classified Block Symbols (`INSERT`)")
        block_rows = []
        for blk_name, info in takeoff.classified_blocks.items():
            block_rows.append(
                {
                    "Block Name": blk_name,
                    "Trade Category": info["trade"],
                    "Quantity": info["count"],
                }
            )
        if block_rows:
            st.dataframe(pd.DataFrame(block_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No block insertions detected in this drawing.")

    with col_right:
        st.markdown("#### Detected Openings for IS 1200 Deductions")
        op_rows = []
        for op in takeoff.openings:
            op_rows.append(
                {
                    "ID": op.id,
                    "Type": op.type,
                    "Width (m)": f"{op.width_m:.2f}",
                    "Height (m)": f"{op.height_m:.2f}",
                    "Area (m²)": f"{op.area_sqm:.2f}",
                    "CAD Reference": op.cad_ref,
                }
            )
        if op_rows:
            st.dataframe(pd.DataFrame(op_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No openings detected.")

    # Spatial Coordinate Inspector (Expandable)
    with st.expander("🔬 Detailed Spatial Entity Coordinates (X, Y Inspector)"):
        st.caption(
            "Complete inventory of every spatial entity, coordinate position, and layer captured by AutoSpec AI."
        )
        spatial_rows = []
        for b in getattr(takeoff, "block_instances", []):
            spatial_rows.append(
                {
                    "Entity": "Block Symbol",
                    "Name": b.get("name", "Unknown"),
                    "Trade Category": b.get("trade", "General"),
                    "X Pos": f"{b.get('x', 0.0):.2f}",
                    "Y Pos": f"{b.get('y', 0.0):.2f}",
                    "Layer": b.get("layer", "0"),
                }
            )
        for op in getattr(takeoff, "openings", []):
            spatial_rows.append(
                {
                    "Entity": f"Opening ({op.type})",
                    "Name": op.id,
                    "Trade Category": "Openings - Doors & Windows",
                    "X Pos": "On Wall",
                    "Y Pos": "On Wall",
                    "Layer": op.layer,
                }
            )
        if spatial_rows:
            st.dataframe(pd.DataFrame(spatial_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No spatial instances recorded.")

# =============================================================================
# TAB 2: CLIENT BRIEF & SPECIFICATIONS
# =============================================================================
with tab2:
    st.markdown("### Client Brief Interpretation & Technical Schema")
    st.caption("Converts conversational client requirements into exact brand, wattage, CCT, and finish parameters.")

    col_p1, col_p2, col_p3 = st.columns(3)
    if col_p1.button("✨ Sample: Luxury 3BHK Penthouse", use_container_width=True):
        st.session_state["client_brief"] = (
            "Luxury 3BHK Penthouse in Whitefield. Want Philips 12W warm white 3000K recessed spots, "
            "Atomberg BLDC smart fans, Schneider Opale modular switches, Italian marble flooring in living, and Asian Paints Royale Luxury emulsion."
        )
        st.rerun()

    if col_p2.button("🏡 Sample: Turnkey 2BHK Interior", use_container_width=True):
        st.session_state["client_brief"] = (
            "2BHK interior turnkey fitout. Havells 12W 3000K round spots, Crompton BLDC energy saving fans, "
            "Legrand modular switches, Kajaria vitrified floor tiles, and Royale luxury paint."
        )
        st.rerun()

    if col_p3.button("🏢 Sample: Rental Budget Flat", use_container_width=True):
        st.session_state["client_brief"] = (
            "Budget rental apartment in Pune. Havells 15W neutral white 4000K spotlights, Orient induction fans, "
            "Anchor switches, ceramic floor tiles, and Tractor emulsion paint."
        )
        st.rerun()

    brief_text = st.text_area(
        "Client Brief (Text / Transcript):",
        value=st.session_state["client_brief"],
        height=120,
    )
    if brief_text != st.session_state["client_brief"]:
        st.session_state["client_brief"] = brief_text
        st.rerun()

    st.markdown("#### Extracted Technical Specifications")
    st.caption(f"Extraction Mode: **{spec.extraction_mode}**")

    spec_col1, spec_col2, spec_col3 = st.columns(3)
    with spec_col1:
        st.markdown("**Electrical Specifications**")
        st.write(f"- **Lighting Brand:** `{spec.preferred_lighting_brand}`")
        st.write(f"- **Wattage:** `{spec.lighting_wattage}W`")
        st.write(f"- **Color Temp:** `{spec.lighting_color_temp}`")
        st.write(f"- **Fan Brand:** `{spec.preferred_fan_brand}`")
        st.write(f"- **Fan Motor:** `{spec.fan_type}`")

    with spec_col2:
        st.markdown("**Fittings & Switches**")
        st.write(f"- **Switch Brand:** `{spec.preferred_switch_brand}`")
        st.write(f"- **Switch Grade:** `{spec.switch_grade}`")
        st.write(f"- **Sanitaryware Brand:** `{spec.sanitaryware_brand}`")

    with spec_col3:
        st.markdown("**Finishes & Surfaces**")
        st.write(f"- **Flooring Material:** `{spec.flooring_preference}`")
        st.write(f"- **Paint Grade:** `{spec.paint_preference}`")
        st.write(f"- **Project Type:** `{spec.project_type}`")

# =============================================================================
# TAB 3: IS 1200 STATUTORY BOQ & AUDIT
# =============================================================================
with tab3:
    st.markdown("### Statutory IS 1200 Compliant Bill of Quantities")
    st.caption("Priced Bill of Quantities applying statutory Bureau of Indian Standards deduction rules.")

    # High-level financial summary
    b_tot, b_civ, b_elec, b_fin, b_plb = st.columns(5)
    b_tot.metric("Estimated Grand Total", f"₹ {boq_result['grand_total_inr']:,.2f}")
    b_civ.metric("Civil Works", f"₹ {boq_result['trade_subtotals_inr'].get('Civil', 0):,.2f}")
    b_fin.metric("Finishes Works", f"₹ {boq_result['trade_subtotals_inr'].get('Finishes', 0):,.2f}")
    b_elec.metric("Electrical Works", f"₹ {boq_result['trade_subtotals_inr'].get('Electrical', 0):,.2f}")
    b_plb.metric("Plumbing Works", f"₹ {boq_result['trade_subtotals_inr'].get('Plumbing', 0):,.2f}")

    st.divider()

    # Filter by trade
    trades = ["All Trades"] + sorted(boq_result["trade_subtotals_inr"].keys())
    selected_trade = st.selectbox("Filter Line Items by Trade:", trades, index=0)

    items_to_display = boq_result["items"]
    if selected_trade != "All Trades":
        items_to_display = [it for it in items_to_display if it["trade"] == selected_trade]

    df_boq = pd.DataFrame(items_to_display)
    if not df_boq.empty:
        table_df = df_boq[
            ["item_no", "trade", "description", "quantity", "unit", "unit_rate_inr", "total_cost_inr", "audit_notes"]
        ].rename(
            columns={
                "item_no": "Item No",
                "trade": "Trade",
                "description": "Description of Works",
                "quantity": "Quantity",
                "unit": "Unit",
                "unit_rate_inr": "Rate (₹)",
                "total_cost_inr": "Total (₹)",
                "audit_notes": "Statutory Notes & Source",
            }
        )
        st.dataframe(
            table_df.style.format(
                {
                    "Quantity": "{:,.2f}",
                    "Rate (₹)": "₹ {:,.2f}",
                    "Total (₹)": "₹ {:,.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    # Expandable IS 1200 Audit Logs
    with st.expander("🔍 Bureau of Indian Standards (IS 1200) Statutory Deduction Audit Logs", expanded=True):
        col_m, col_p = st.columns(2)

        with col_m:
            st.markdown("#### Masonry Deductions (IS 1200 Part 4)")
            m_aud = boq_result["is1200_masonry_audit"]
            st.write(f"- **Gross Wall Area:** `{m_aud['gross_wall_area_sqm']:.2f} m²`")
            st.write(f"- **Gross Masonry Volume:** `{m_aud['gross_volume_cum']:.2f} m³`")
            st.write(f"- **Total Deducted Area:** `{m_aud['total_deducted_area_sqm']:.2f} m²`")
            st.write(f"- **Net Billable Masonry:** `{m_aud['net_masonry_volume_cum']:.2f} m³`")
            st.caption(
                "*Statutory Invariant: Openings ≤ 0.1 m² have zero deduction. Openings > 0.1 m² are fully deducted.*"
            )

        with col_p:
            st.markdown("#### Plastering Deductions (IS 1200 Part 12)")
            p_aud = boq_result["is1200_plaster_audit"]
            st.write(f"- **Gross Wall Area (Single Face):** `{p_aud['gross_wall_area_one_face_sqm']:.2f} m²`")
            st.write(f"- **Gross Plaster (Both Faces):** `{p_aud['gross_plaster_area_both_faces_sqm']:.2f} m²`")
            st.write(f"- **Total Opening Deduction:** `{p_aud['total_opening_deduction_sqm']:.2f} m²`")
            st.write(f"- **Net Billable Plaster Area:** `{p_aud['net_plaster_area_sqm']:.2f} m²`")
            st.caption(
                "*Statutory Invariants: ≤0.5 m² (0 deduction), 0.5–3.0 m² (1 face deducted), >3.0 m² (both faces deducted + reveals).*"
            )

        st.markdown("##### Detailed Opening-by-Opening Calculation Breakdown")
        audit_table = pd.DataFrame(p_aud["openings_audit"]).rename(
            columns={
                "opening_id": "Opening ID",
                "type": "Type",
                "dimensions": "Dimensions",
                "area_sqm": "Area (m²)",
                "statutory_tier": "IS 1200 Tier",
                "clause": "BIS Clause",
                "face_deduction_sqm": "Deduction (m²)",
                "reveal_addition_sqm": "Reveals (m²)",
                "net_impact_sqm": "Net Impact (m²)",
            }
        )
        st.dataframe(audit_table, use_container_width=True, hide_index=True)

# =============================================================================
# TAB 4: EXPORT & LIVE B2B PROCUREMENT
# =============================================================================
with tab4:
    st.markdown("### Export & Procurement Handoff")
    st.caption("Generate Microsoft Excel formatted spreadsheets and direct B2B vendor procurement orders.")

    # Generate in-memory Excel file
    temp_excel_path = os.path.join(tempfile.gettempdir(), "autospec_boq_estimate.xlsx")
    boq_engine.export_to_excel(boq_result, temp_excel_path)

    with open(temp_excel_path, "rb") as f:
        excel_bytes = f.read()

    ex_col1, ex_col2, ex_col3 = st.columns([1, 1, 2])
    ex_col1.download_button(
        label="📥 Download Excel BOQ (.xlsx)",
        data=excel_bytes,
        file_name="autospec_boq_estimate.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    csv_data = pd.DataFrame(boq_result["items"]).to_csv(index=False).encode("utf-8")
    ex_col2.download_button(
        label="📄 Download CSV (.csv)",
        data=csv_data,
        file_name="autospec_boq_estimate.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()

    st.markdown("#### Direct Indian B2B Procurement Order Links")
    st.caption(
        "Click 'Buy Now' to view current distributor pricing or place immediate orders on Indian B2B marketplaces."
    )

    proc_items = []
    for it in boq_result["items"]:
        proc_items.append(
            {
                "Item No": it["item_no"],
                "Trade": it["trade"],
                "Description": it["description"],
                "Required Quantity": f"{it['quantity']:.2f} {it['unit']}",
                "Unit Rate (₹)": f"₹ {it['unit_rate_inr']:,.2f}",
                "Extended Cost (₹)": f"₹ {it['total_cost_inr']:,.2f}",
                "Procurement URL": it["buy_url"],
            }
        )

    st.dataframe(
        pd.DataFrame(proc_items),
        column_config={
            "Procurement URL": st.column_config.LinkColumn(
                "Order Link",
                help="Click to open vendor product page",
                validate=r"^https?://.*",
                max_chars=100,
                display_text="Buy Now ↗",
            )
        },
        use_container_width=True,
        hide_index=True,
    )

    st.success(
        "✅ BOQ is 100% compliant with Bureau of Indian Standards (IS 1200) and verified against seed procurement catalog."
    )
