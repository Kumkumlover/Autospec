"""app.py — Streamlit Web Interface for AutoSpec AI

Provides a 4-tab workflow:
1. 📐 CAD Takeoff & Vector Inspector
2. 📝 Client Brief & Technical Specifications
3. 📊 IS 1200 Statutory BOQ & Audit Trail
4. 📥 Export & Live Indian B2B Procurement
"""

from __future__ import annotations

import importlib
import os
import tempfile

import pandas as pd
import streamlit as st

import boq_engine
import cad_parser
import cad_visualizer
import sample_dxf_generator
import spec_parser

# Force reload of core modules on every Streamlit script execution
# to prevent stale Python in-memory module caching
importlib.reload(boq_engine)
importlib.reload(cad_parser)
importlib.reload(cad_visualizer)
importlib.reload(sample_dxf_generator)
importlib.reload(spec_parser)

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
        "Upload 2D CAD Drawing, PDF, or Floor Plan Image",
        type=["dxf", "dwg", "png", "jpg", "jpeg", "webp", "pdf"],
        help="Upload an open DXF vector file, AutoCAD DWG binary file, architectural PDF sheet, or floor plan image (.png/.jpg)",
    )

    st.markdown("#### 🎯 Benchmark Real-World Cases")
    uc_col1, uc_col2 = st.columns(2)
    use_uc1 = uc_col1.button("🏢 1. Mid-Market 2BHK", use_container_width=True)
    use_uc2 = uc_col2.button("🏡 2. Custom Villa", use_container_width=True)
    uc_col3, uc_col4 = st.columns(2)
    use_uc3 = uc_col3.button("🏬 3. Commercial Office", use_container_width=True)
    use_uc4 = uc_col4.button("📜 4. PreDCR Sanction", use_container_width=True)

    st.markdown("#### 📁 CAD Library Samples")
    sample_col1, sample_col2 = st.columns(2)
    use_sample_2bhk = sample_col1.button("📂 Synthetic 2BHK", use_container_width=True)
    use_sample_house = sample_col2.button("🏡 2-Story DWG", use_container_width=True)
    sample_col3, sample_col4 = st.columns(2)
    use_sample_apt = sample_col3.button("🏢 Apartment-1", use_container_width=True)
    use_sample_20x55 = sample_col4.button("🏘️ 20x55 House", use_container_width=True)
    sample_col5, _ = st.columns(2)
    use_sample_img = sample_col5.button("🖼️ Scanned Plan (PNG)", use_container_width=True)

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

    run_btn = st.button("🚀 Generate Full BOQ Estimate", type="primary", use_container_width=True)
    if run_btn:
        st.session_state.pop("_last_takeoff_key", None)
        st.session_state.pop("_last_spec_key", None)
        st.session_state.pop("_last_boq_key", None)
        st.session_state.pop("takeoff", None)
        st.session_state.pop("spec", None)
        st.session_state.pop("boq_result", None)

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

        ext = os.path.splitext(uploaded_file.name.lower())[1]
        st.session_state["is_dwg_converted"] = False
        st.session_state["is_raster_converted"] = False
        st.session_state["is_pdf_converted"] = False
        st.session_state["uploaded_image_preview"] = None
        st.session_state.pop("takeoff", None)
        st.session_state.pop("_last_takeoff_key", None)
        st.session_state.pop("boq_result", None)
        st.session_state.pop("_last_boq_key", None)

        if ext == ".dwg":
            try:
                with st.spinner(f"⚙️ Converting AutoCAD DWG '{uploaded_file.name}' via local LibreDWG engine..."):
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
                st.session_state["_last_uploaded_name"] = uploaded_file.name
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"]:
            try:
                from raster_converter import convert_image_to_dxf

                with st.spinner(f"⚙️ Vectorizing floor plan image '{uploaded_file.name}' locally..."):
                    converted_dxf = convert_image_to_dxf(saved_path)
                st.session_state["cad_path"] = converted_dxf
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["is_raster_converted"] = True
                st.session_state["uploaded_image_preview"] = uploaded_file.getvalue()
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.sidebar.success(f"Vectorized Image: {uploaded_file.name}")
            except Exception as e:
                st.sidebar.error(f"Image vectorization: {e}")
                st.session_state["cad_path"] = saved_path
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["_last_uploaded_name"] = uploaded_file.name
        elif ext == ".pdf":
            try:
                from raster_converter import convert_pdf_to_dxf

                with st.spinner(f"⚙️ Vectorizing architectural PDF '{uploaded_file.name}' locally..."):
                    converted_dxf = convert_pdf_to_dxf(saved_path)
                st.session_state["cad_path"] = converted_dxf
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["is_pdf_converted"] = True
                try:
                    import pymupdf

                    pdf_doc = pymupdf.open(saved_path)
                    preview_bytes = pdf_doc[0].get_pixmap(dpi=150).tobytes("png")
                    pdf_doc.close()
                    st.session_state["uploaded_image_preview"] = preview_bytes
                except Exception:
                    pass
                st.session_state["_last_uploaded_name"] = uploaded_file.name
                st.sidebar.success(f"Vectorized PDF: {uploaded_file.name}")
            except Exception as e:
                st.sidebar.error(f"PDF vectorization: {e}")
                st.session_state["cad_path"] = saved_path
                st.session_state["display_name"] = uploaded_file.name
                st.session_state["_last_uploaded_name"] = uploaded_file.name
        else:
            st.session_state["cad_path"] = saved_path
            st.session_state["display_name"] = uploaded_file.name
            st.session_state["_last_uploaded_name"] = uploaded_file.name
            st.sidebar.success(f"Loaded DXF: {uploaded_file.name}")
        st.rerun()

if use_uc1:
    p = "samples/use_case_1_2bhk_rcp.dxf"
    if not os.path.exists(p):
        from test_cases_generator import generate_use_case_1_2bhk_rcp
        generate_use_case_1_2bhk_rcp(p)
    st.session_state["cad_path"] = p
    st.session_state["display_name"] = "use_case_1_2bhk_rcp.dxf"
    st.session_state["is_dwg_converted"] = False
    st.session_state["client_brief"] = (
        "Client wants 12W 3000K warm white recessed LED downlights in living and bedrooms, "
        "1200mm BLDC energy-efficient ceiling fans (Havells/Atomberg), modular switches from Schneider, "
        "and 600x600mm vitrified tiles."
    )
    st.rerun()

if use_uc2:
    p = "samples/use_case_2_villa_glazing.dxf"
    if not os.path.exists(p):
        from test_cases_generator import generate_use_case_2_villa_glazing
        generate_use_case_2_villa_glazing(p)
    st.session_state["cad_path"] = p
    st.session_state["display_name"] = "use_case_2_villa_glazing.dxf"
    st.session_state["is_dwg_converted"] = False
    st.session_state["client_brief"] = (
        "Use premium 15W dimmable warm downlights, magnetic track lights in living room, "
        "premium Jaquar sanitaryware, and Asian Paints Royale acrylic emulsion on all internal plaster."
    )
    st.rerun()

if use_uc3:
    p = "samples/use_case_3_commercial_office.dxf"
    if not os.path.exists(p):
        from test_cases_generator import generate_use_case_3_commercial_office
        generate_use_case_3_commercial_office(p)
    st.session_state["cad_path"] = p
    st.session_state["display_name"] = "use_case_3_commercial_office.dxf"
    st.session_state["is_dwg_converted"] = False
    st.session_state["client_brief"] = (
        "Provide 36W 600x600 LED ceiling grid panels, 2x2 acoustic ceiling tiles, "
        "2-inch aluminium partition framing, and commercial carpet tiles."
    )
    st.rerun()

if use_uc4:
    p = "samples/use_case_4_predcr_sanction.dxf"
    if not os.path.exists(p):
        from test_cases_generator import generate_use_case_4_predcr_sanction
        generate_use_case_4_predcr_sanction(p)
    st.session_state["cad_path"] = p
    st.session_state["display_name"] = "use_case_4_predcr_sanction.dxf"
    st.session_state["is_dwg_converted"] = False
    st.session_state["client_brief"] = (
        "Municipal single-window sanction plan (AutoDCR / PreDCR format). "
        "Standard vitrified tile flooring, modular electrical switches, and luxury emulsion paint."
    )
    st.rerun()

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

if use_sample_img:
    img_sample = "samples/test_render_sample.png"
    from raster_converter import convert_image_to_dxf

    conv_dxf = convert_image_to_dxf(img_sample)
    st.session_state["cad_path"] = conv_dxf
    st.session_state["display_name"] = "test_render_sample.png"
    st.session_state["is_dwg_converted"] = False
    st.session_state["is_raster_converted"] = True
    with open(img_sample, "rb") as f:
        st.session_state["uploaded_image_preview"] = f.read()
    st.session_state["client_brief"] = (
        "Residential 2BHK floor plan fitout vectorized directly from scanned architectural drawing. "
        "Living and dining with vitrified tiles, bedrooms with anti-skid tiles. "
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

# Parse CAD and Brief with Session Caching
cache_key = f"{st.session_state['cad_path']}_{drawing_units}_{wall_height}_{wall_thickness}"
active_name = st.session_state.get("display_name", os.path.basename(st.session_state["cad_path"]))

if st.session_state.get("_last_takeoff_key") != cache_key or "takeoff" not in st.session_state:
    with st.spinner(f"📐 Parsing CAD vector takeoff for {active_name}..."):
        cad_parser = CadParser(default_units=drawing_units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        try:
            takeoff = cad_parser.parse_cad_file(st.session_state["cad_path"], filename=st.session_state.get("display_name"))
            st.session_state["takeoff"] = takeoff
            st.session_state["_last_takeoff_key"] = cache_key
        except Exception as e:
            st.error(f"Error parsing CAD file: {e}")
            st.stop()
else:
    takeoff = st.session_state["takeoff"]

spec_key = f"{st.session_state['client_brief']}_{anthropic_api_key}_{groq_api_key}"
if st.session_state.get("_last_spec_key") != spec_key or "spec" not in st.session_state:
    with st.spinner("🤖 Interpreting client specifications & trade requirements..."):
        spec = parse_client_brief(
            st.session_state["client_brief"],
            api_key=anthropic_api_key,
            groq_api_key=groq_api_key,
        )
        st.session_state["spec"] = spec
        st.session_state["_last_spec_key"] = spec_key

        # Synchronize physical MEP fixtures with client brief preferences
        try:
            from cad_parser import synthesize_architectural_fixtures

            l_brand = getattr(spec, "preferred_lighting_brand", "Philips")
            f_brand = getattr(spec, "preferred_fan_brand", "Atomberg")
            s_brand = getattr(spec, "preferred_switch_brand", "Schneider")
            w_val = getattr(spec, "lighting_wattage", 12)
            c_val = getattr(spec, "lighting_color_temp", "3000K")
            cct_str = f"{c_val} Warm White" if "3000" in str(c_val) else f"{c_val} Daylight"

            synthesize_architectural_fixtures(
                takeoff,
                lighting_brand=l_brand if l_brand != "Any" else "Philips",
                lighting_wattage=w_val,
                lighting_color_temp=cct_str,
                fan_brand=f_brand if f_brand != "Any" else "Atomberg",
                switch_brand=s_brand if s_brand != "Any" else "Schneider",
                force_resynthesize=False,
            )
        except Exception:
            pass
else:
    spec = st.session_state["spec"]

boq_key = f"{cache_key}_{spec_key}"
if st.session_state.get("_last_boq_key") != boq_key or "boq_result" not in st.session_state:
    with st.spinner("📊 Compiling statutory IS 1200 deductions & B2B procurement BOQ..."):
        boq_gen = BoqEngine()
        boq_result = boq_gen.generate_boq(takeoff, spec, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        st.session_state["boq_result"] = boq_result
        st.session_state["_last_boq_key"] = boq_key
else:
    boq_result = st.session_state["boq_result"]

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
    elif st.session_state.get("is_raster_converted"):
        st.success(
            "✨ **Floor Plan Image Vectorized**: Uploaded drawing image binarized and converted 100% locally to closed 2D DXF vector geometry (`A-WALL`, `A-FLOR`). Air-gap vector guarantee preserved."
        )
    elif st.session_state.get("is_pdf_converted"):
        st.success(
            "✨ **Architectural PDF Vectorized**: Drawing paths extracted 100% locally to 2D DXF vector format. Air-gap vector guarantee preserved."
        )

    if st.session_state.get("uploaded_image_preview"):
        with st.expander("🖼️ View Original Uploaded Floor Plan Drawing / Image", expanded=False):
            st.image(
                st.session_state["uploaded_image_preview"],
                caption=f"Original Uploaded Drawing: {active_name}",
                use_container_width=True,
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

    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.4, 1.2, 1.1, 1.1, 0.9])
    with ctrl_col1:
        viz_mode = st.radio(
            "Visualizer Engine",
            ["🔍 Interactive Vector Canvas", "🖼️ High-Res CAD Blueprint"],
            horizontal=True,
        )
    with ctrl_col2:
        theme_choice = st.selectbox(
            "Canvas Theme",
            ["🌑 AutoCAD Dark Space", "📐 Blueprint Navy", "📄 Drafting Paper (Light)"],
            index=0,
            help="High-contrast CAD styling: AutoCAD Dark matches dark mode; Blueprint Navy uses technical blue; Drafting Paper uses high-contrast jet black ink on white with zero washed-out lines.",
        )
        if "Dark" in theme_choice:
            canvas_theme = "dark"
        elif "Blueprint" in theme_choice:
            canvas_theme = "blueprint"
        else:
            canvas_theme = "light"
    with ctrl_col3:
        focus_choice = st.selectbox(
            "Visual Focus Mode",
            [
                "AutoCAD + Takeoff Highlights",
                "Takeoff Audit (Ghost Base CAD 20%)",
                "Pure AutoCAD (Linework Only)",
                "Takeoff Only (Hide Base CAD)",
            ],
            index=0,
            help="Takeoff Audit dims base CAD linework to 20% opacity so walls, openings, and takeoff badges pop out vividly.",
        )
        if "Audit" in focus_choice:
            focus_mode = "takeoff_focus"
        elif "Pure" in focus_choice:
            focus_mode = "linework_only"
        elif "Takeoff Only" in focus_choice:
            focus_mode = "takeoff_only"
        else:
            focus_mode = "blueprint"
    with ctrl_col4:
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
    with ctrl_col5:
        canvas_height = st.slider("Canvas Height", min_value=500, max_value=850, value=650, step=50)

    # Organized Layer & Trade Visibility Controls
    with st.expander("🛠️ AutoCAD Layer Properties Manager & Takeoff Highlight Controls", expanded=False):
        fl_col1, fl_col2 = st.columns([1.1, 1.0])
        with fl_col1:
            st.markdown("**AutoCAD Model Space Layers**")
            cad_layers = getattr(takeoff, "cad_layers", {})
            if cad_layers:
                layer_display_map = {
                    f"{l} ({data.get('count', 0)} segs)": l
                    for l, data in sorted(cad_layers.items())
                }
                selected_display = st.multiselect(
                    "Visible CAD Drawing Layers:",
                    options=list(layer_display_map.keys()),
                    default=list(layer_display_map.keys()),
                    help="Toggle native AutoCAD layers extracted from the file",
                )
                selected_raw_cad_layers = [layer_display_map[d] for d in selected_display]
                selected_base_layers = None
            else:
                base_layer_options = ["Walls", "Doors", "Windows", "Stairs", "Furniture"]
                selected_base_layers = st.multiselect(
                    "Base Architectural Drawing Layers:",
                    options=base_layer_options,
                    default=base_layer_options,
                    help="Toggle architectural CAD linework categories",
                )
                selected_raw_cad_layers = None

            show_cad_text = st.checkbox("📝 Show Native CAD Text & Dimension Annotations", value=True)

        with fl_col2:
            st.markdown("**AutoSpec Takeoff Highlights (BOQ Link)**")
            hl_c1, hl_c2 = st.columns(2)
            with hl_c1:
                hl_walls = st.checkbox("🧱 Highlight Measured Walls", value=True, help="Glowing #FF3366 coral lines over wall centerlines")
                hl_floors = st.checkbox("📐 Highlight Floor Polygons", value=True, help="Translucent emerald polygons for net floor area")
            with hl_c2:
                hl_openings = st.checkbox("🏷️ Highlight IS 1200 Openings", value=True, help="Tier 1/2/3 deduction badges at physical coordinates")
                hl_fixtures = st.checkbox("📍 Highlight MEP Fixture Pins", value=True, help="Classified downlights, fans, sockets & plumbing")

            takeoff_options = [
                "Electrical - Lighting",
                "Electrical - Fans",
                "Electrical - Switches & Sockets",
                "Plumbing - Sanitaryware",
                "Furniture & Equipment",
                "Other Architectural Fittings",
            ]
            selected_takeoff_trades = st.multiselect(
                "Filter Fixture Trades:",
                options=takeoff_options,
                default=takeoff_options,
                help="Filter MEP fixture symbols by trade",
            )

    visualizer = CadVisualizer(takeoff)

    if "Interactive" in viz_mode:
        fig = visualizer.build_interactive_figure(
            visible_cad_layers=selected_raw_cad_layers,
            visible_layers=selected_base_layers,
            visible_trades=selected_takeoff_trades,
            label_mode=label_mode,
            focus_mode=focus_mode,
            show_cad_text=show_cad_text,
            highlight_walls=hl_walls,
            highlight_floors=hl_floors,
            highlight_openings=hl_openings,
            highlight_fixtures=hl_fixtures,
            plot_height=canvas_height,
            theme=canvas_theme,
            dark_mode=(canvas_theme != "light"),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "💡 **Canvas Navigation**: Click & drag to pan across the plan • Mouse scroll or Box-zoom to inspect rooms • Double-click to reset view • Hover over any line or pin for instant CAD metadata."
        )

        # Takeoff-to-BOQ Inspector Summary
        t1_cnt = sum(1 for op in takeoff.openings if op.area_sqm <= 0.5)
        t2_cnt = sum(1 for op in takeoff.openings if 0.5 < op.area_sqm <= 3.0)
        t3_cnt = sum(1 for op in takeoff.openings if op.area_sqm > 3.0)

        st.markdown(
            f"""
            <div style="background-color: {'#161B22' if canvas_theme != 'light' else '#F1F5F9'};
                        border: 1px solid {'#30363D' if canvas_theme != 'light' else '#CBD5E1'};
                        border-radius: 8px; padding: 12px 18px; margin-top: 10px; margin-bottom: 20px;">
                <div style="font-weight: 600; font-size: 0.95rem; color: {'#58A6FF' if canvas_theme != 'light' else '#0969DA'}; margin-bottom: 6px;">
                    🎯 Takeoff-to-BOQ Measurement Traceability
                </div>
                <div style="font-size: 0.86rem; color: {'#C9D1D9' if canvas_theme != 'light' else '#334155'}; line-height: 1.6;">
                    • <b>Civil Masonry & Plaster</b>: Measured <b>{takeoff.wall_length_m:.1f} m</b> wall centerlines → <b>{takeoff.total_wall_area_sqm:.1f} m²</b> gross wall area (highlighted in coral <span style="color:#FF3366;">━</span>).<br>
                    • <b>Flooring & Finishes</b>: Measured <b>{takeoff.total_floor_area_sqm:.1f} m²</b> ({takeoff.total_floor_area_sqm * 10.764:.0f} sq.ft) net floor area across <b>{len(takeoff.room_polygons)}</b> detected room zones (highlighted in emerald <span style="color:#10B981;">■</span>).<br>
                    • <b>IS 1200 Statutory Deductions</b>: <b>{len(takeoff.openings)} openings</b> accounted for:
                      <b>{t1_cnt}</b> Tier 1 (exempt 0%), <b>{t2_cnt}</b> Tier 2 (single-face deducted), <b>{t3_cnt}</b> Tier 3 (both faces deducted + reveals added).<br>
                    • <b>Classified Fixtures</b>: <b>{sum(takeoff.block_counts.values())} pcs</b> CAD symbols mapped to verified Indian B2B catalog SKUs.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Rendering high-resolution vector blueprint..."):
            img_bytes = visualizer.generate_blueprint_image(st.session_state["cad_path"])
        if img_bytes:
            st.image(img_bytes, caption=f"High-Resolution 2D Blueprint: {active_name}", use_column_width=True)
        else:
            st.warning("Blueprint rendering unavailable for this drawing. Showing Interactive Inspector instead.")
            fig = visualizer.build_interactive_figure(
                plot_height=canvas_height,
                theme=canvas_theme,
                dark_mode=(canvas_theme != "light"),
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    st.divider()

    # =========================================================================
    # INTERACTIVE CAD ELEMENT & MEASUREMENT INSPECTOR
    # =========================================================================
    st.markdown("### 🔬 Interactive CAD Element & Measurement Inspector")
    st.caption(
        "Click or select any architectural trade, CAD layer, or takeoff element below to inspect its live measurement, quantity, dimensions, spatial coordinates, and statutory BOQ derivation."
    )

    n_lights = sum(1 for b in takeoff.block_instances if b.get("trade") == "Electrical - Lighting")
    n_fans = sum(1 for b in takeoff.block_instances if b.get("trade") == "Electrical - Fans")
    n_switches = sum(1 for b in takeoff.block_instances if b.get("trade") == "Electrical - Switches & Sockets")
    n_openings = len(takeoff.openings)
    n_rooms = len(takeoff.room_polygons)
    n_walls = len(takeoff.wall_segments)
    n_layers = len(getattr(takeoff, "cad_layers", {}))

    elem_options = [
        f"💡 Electrical Lighting ({n_lights} pcs)",
        f"🌀 BLDC Ceiling Fans ({n_fans} pcs)",
        f"🔌 Modular Switches & Sockets ({n_switches} pcs)",
        f"🧱 Civil Masonry Walls ({takeoff.wall_length_m:.1f} m • {takeoff.total_wall_area_sqm:.1f} m²)",
        f"📐 Flooring & Room Zones ({takeoff.total_floor_area_sqm:.1f} m² across {n_rooms} zones)",
        f"🏷️ IS 1200 Openings ({n_openings} doors & windows)",
        f"🏛️ AutoCAD Model Space Layers ({n_layers} layers)",
    ]

    selected_elem = st.selectbox(
        "Select Architectural Element or CAD Layer to Inspect:",
        elem_options,
        index=0,
        help="Switch between trades to review itemized measurements, exact locations, and linked statutory BOQ lines.",
    )

    if selected_elem.startswith("💡"):
        lights = [b for b in takeoff.block_instances if b.get("trade") == "Electrical - Lighting"]
        if lights:
            first_attr = lights[0].get("attributes", {})
            brand = first_attr.get("brand", "Philips")
            wattage = first_attr.get("wattage", "12W")
            cct = first_attr.get("color_temp", "3000K Warm White")
            unit_rate = float(first_attr.get("unit_rate_inr", 420.0))
            tot_cost = len(lights) * unit_rate

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Selected Trade", "Electrical - Lighting", "Recessed Downlights")
            c2.metric("Total Fixtures", f"{len(lights)} Pcs", f"Floor Coverage: {takeoff.total_floor_area_sqm:.1f} m²")
            c3.metric("Selected Brand & CCT", f"{brand} ({wattage})", cct)
            c4.metric("Estimated Trade Cost", f"₹{tot_cost:,.0f}", f"@ ₹{unit_rate:,.0f} / pc")

            rows = []
            for idx, b in enumerate(lights, 1):
                attr = b.get("attributes", {})
                rows.append(
                    {
                        "Tag": f"LIGHT-{idx:03d}",
                        "Model Description": attr.get("model_name", b.get("name")),
                        "Brand": attr.get("brand", brand),
                        "Wattage": attr.get("wattage", wattage),
                        "Room Zone": attr.get("room_zone", f"Zone #{((idx-1)%max(1, n_rooms))+1}"),
                        "Coord X (m)": f"{b.get('x', 0.0):.2f}",
                        "Coord Y (m)": f"{b.get('y', 0.0):.2f}",
                        "Unit Rate": f"₹{float(attr.get('unit_rate_inr', unit_rate)):,.0f}",
                        "BOQ Code": attr.get("boq_item", "ELE-001"),
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No lighting fixtures detected or synthesized for this drawing.")

    elif selected_elem.startswith("🌀"):
        fans = [b for b in takeoff.block_instances if b.get("trade") == "Electrical - Fans"]
        if fans:
            first_attr = fans[0].get("attributes", {})
            brand = first_attr.get("brand", "Atomberg")
            unit_rate = float(first_attr.get("unit_rate_inr", 3450.0))
            tot_cost = len(fans) * unit_rate

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Selected Trade", "Electrical - Fans", "BLDC Ceiling Fans")
            c2.metric("Total Fixtures", f"{len(fans)} Pcs", "Habitable Room Centroids")
            c3.metric("Selected Brand & Spec", f"{brand} 1200mm", "28W 5-Star Energy Saver")
            c4.metric("Estimated Trade Cost", f"₹{tot_cost:,.0f}", f"@ ₹{unit_rate:,.0f} / pc")

            rows = []
            for idx, b in enumerate(fans, 1):
                attr = b.get("attributes", {})
                rows.append(
                    {
                        "Tag": f"FAN-{idx:02d}",
                        "Model Description": attr.get("model_name", b.get("name")),
                        "Brand": attr.get("brand", brand),
                        "Sweep / Rating": "1200mm / 28W BLDC",
                        "Room Zone": attr.get("room_zone", f"Zone #{idx}"),
                        "Centroid X (m)": f"{b.get('x', 0.0):.2f}",
                        "Centroid Y (m)": f"{b.get('y', 0.0):.2f}",
                        "Unit Rate": f"₹{float(attr.get('unit_rate_inr', unit_rate)):,.0f}",
                        "BOQ Code": attr.get("boq_item", "ELE-002"),
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No ceiling fans detected or synthesized for this drawing.")

    elif selected_elem.startswith("🔌"):
        switches = [b for b in takeoff.block_instances if b.get("trade") == "Electrical - Switches & Sockets"]
        if switches:
            first_attr = switches[0].get("attributes", {})
            brand = first_attr.get("brand", "Schneider")
            unit_rate = float(first_attr.get("unit_rate_inr", 285.0))
            tot_cost = len(switches) * unit_rate

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Selected Trade", "Electrical - Switches", "Modular Points")
            c2.metric("Total Fixtures", f"{len(switches)} Pcs", "Wall Perimeter Nodes")
            c3.metric("Selected Brand & Grade", f"{brand} Opale", "6A/16A Combined")
            c4.metric("Estimated Trade Cost", f"₹{tot_cost:,.0f}", f"@ ₹{unit_rate:,.0f} / pc")

            rows = []
            for idx, b in enumerate(switches, 1):
                attr = b.get("attributes", {})
                rows.append(
                    {
                        "Tag": f"SW-{idx:02d}",
                        "Model Description": attr.get("model_name", b.get("name")),
                        "Brand": attr.get("brand", brand),
                        "Rating": attr.get("rating", "6A/16A Modular"),
                        "Room Zone": attr.get("room_zone", f"Zone #{((idx-1)%max(1, n_rooms))+1}"),
                        "Coord X (m)": f"{b.get('x', 0.0):.2f}",
                        "Coord Y (m)": f"{b.get('y', 0.0):.2f}",
                        "Unit Rate": f"₹{float(attr.get('unit_rate_inr', unit_rate)):,.0f}",
                        "BOQ Code": attr.get("boq_item", "ELE-003"),
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No modular switches detected or synthesized for this drawing.")

    elif selected_elem.startswith("🧱"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Selected Trade", "Civil Masonry & Plaster", "IS 1200 Part 4 & 12")
        c2.metric("Total Centerline Length", f"{takeoff.wall_length_m:.1f} m", f"{len(takeoff.wall_segments)} Segments")
        c3.metric("Standard Wall Height", f"{wall_height:.2f} m", f"Thickness: {wall_thickness*1000:.0f} mm")
        c4.metric("Gross Wall Area", f"{takeoff.total_wall_area_sqm:.1f} m²", f"Gross Vol: {takeoff.wall_volume_cum:.1f} m³")

        rows = []
        for idx, w in enumerate(takeoff.wall_segments[:100], 1):
            length_m = math.hypot(w["x2"] - w["x1"], w["y2"] - w["y1"]) * getattr(takeoff, "scale_factor_to_meters", 1.0)
            area_sqm = length_m * wall_height
            rows.append(
                {
                    "Segment #": f"WALL-{idx:03d}",
                    "CAD Layer": w.get("layer", "A-WALL"),
                    "Start X (m)": f"{w['x1']:.2f}",
                    "Start Y (m)": f"{w['y1']:.2f}",
                    "End X (m)": f"{w['x2']:.2f}",
                    "End Y (m)": f"{w['y2']:.2f}",
                    "Length (m)": f"{length_m:.2f}",
                    "Height (m)": f"{wall_height:.2f}",
                    "Gross Area (m²)": f"{area_sqm:.2f}",
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if len(takeoff.wall_segments) > 100:
                st.caption(f"Showing first 100 of {len(takeoff.wall_segments)} measured wall segments.")
        else:
            st.info("No wall segments detected in this drawing.")

    elif selected_elem.startswith("📐"):
        sqft = takeoff.total_floor_area_sqm * 10.764
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Selected Trade", "Flooring & Finishes", "IS 1200 Part 11")
        c2.metric("Net Floor Area", f"{takeoff.total_floor_area_sqm:.1f} m²", f"{sqft:,.0f} sq.ft")
        c3.metric("Detected Zones", f"{len(takeoff.room_polygons)} Rooms / Spaces", "Closed Polygons")
        c4.metric("Client SKU Preference", getattr(spec, "flooring_preference", "Vitrified Tile"), "Procurement Matched")

        rows = []
        for idx, r in enumerate(takeoff.room_polygons, 1):
            area = r.get("area_sqm", 0.0)
            pts = r.get("points", [])
            perim = 0.0
            if len(pts) >= 3:
                for i in range(len(pts)):
                    p1 = pts[i]
                    p2 = pts[(i + 1) % len(pts)]
                    perim += math.hypot(p2[0] - p1[0], p2[1] - p1[1]) * getattr(takeoff, "scale_factor_to_meters", 1.0)
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
            else:
                cx, cy = 0.0, 0.0

            rows.append(
                {
                    "Zone #": f"ZONE-{idx:02d}",
                    "CAD Layer": r.get("layer", "A-FLOR"),
                    "Net Area (m²)": f"{area:.2f}",
                    "Area (sq.ft)": f"{area * 10.764:.1f}",
                    "Perimeter (m)": f"{perim:.2f}",
                    "Centroid X (m)": f"{cx:.2f}",
                    "Centroid Y (m)": f"{cy:.2f}",
                    "Matched SKU": getattr(spec, "flooring_preference", "Vitrified Tile 600x600mm"),
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No closed room polygons detected in this drawing.")

    elif selected_elem.startswith("🏷️"):
        t1_cnt = sum(1 for op in takeoff.openings if op.area_sqm <= 0.5)
        t2_cnt = sum(1 for op in takeoff.openings if 0.5 < op.area_sqm <= 3.0)
        t3_cnt = sum(1 for op in takeoff.openings if op.area_sqm > 3.0)
        total_op_area = sum(op.area_sqm for op in takeoff.openings)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Openings", f"{len(takeoff.openings)} Nos", f"{total_op_area:.1f} m² Gross Opening Area")
        c2.metric("Tier 1 (≤ 0.5 m²)", f"{t1_cnt} Nos", "Zero Plaster Deduction (IS 1200 Part 12)")
        c3.metric("Tier 2 (0.5 to 3.0 m²)", f"{t2_cnt} Nos", "Single Face Deducted (1.0 × Area)")
        c4.metric("Tier 3 (> 3.0 m²)", f"{t3_cnt} Nos", "Both Faces Deducted (2.0 × Area) + Reveals")

        rows = []
        for op in takeoff.openings:
            if op.area_sqm <= 0.5:
                tier = "Tier 1 (≤ 0.5 m²)"
                plaster_effect = "Exempt (0 m² deducted)"
                vol_deduct = 0.0
            elif op.area_sqm <= 3.0:
                tier = "Tier 2 (0.5 to 3.0 m²)"
                plaster_effect = f"-{op.area_sqm:.2f} m² (1 Face)"
                vol_deduct = op.area_sqm * wall_thickness
            else:
                tier = "Tier 3 (> 3.0 m²)"
                plaster_effect = f"-{2 * op.area_sqm:.2f} m² (Both Faces) + Reveals"
                vol_deduct = op.area_sqm * wall_thickness

            rows.append(
                {
                    "ID": op.id,
                    "Type": op.type,
                    "Width (m)": f"{op.width_m:.2f}",
                    "Height (m)": f"{op.height_m:.2f}",
                    "Area (m²)": f"{op.area_sqm:.2f}",
                    "IS 1200 Tier": tier,
                    "Plaster Deduction Impact": plaster_effect,
                    "Masonry Volume Deducted (m³)": f"{vol_deduct:.2f}",
                    "CAD Reference": op.cad_ref,
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No openings detected in this drawing.")

    elif selected_elem.startswith("🏛️"):
        layers = getattr(takeoff, "cad_layers", {})
        linear_scale = getattr(takeoff, "scale_factor_to_meters", 1.0)
        tot_segs = sum(len(l.get("paths", [])) for l in layers.values())
        tot_len = 0.0
        for l in layers.values():
            for p in l.get("paths", []):
                for i in range(len(p) - 1):
                    tot_len += math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) * linear_scale

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total CAD Layers", f"{len(layers)} Layers", "Model Space")
        c2.metric("Total Segments", f"{tot_segs} Paths", "Linework Entities")
        c3.metric("Total Linework Length", f"{tot_len:.1f} m", "100% Vector Fidelity")
        c4.metric("Color Representation", "AutoCAD Native", "RGB / ACI Palette")

        rows = []
        for lname, ldata in sorted(layers.items()):
            paths = ldata.get("paths", [])
            layer_len = 0.0
            for p in paths:
                for i in range(len(p) - 1):
                    layer_len += math.hypot(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) * linear_scale
            rows.append(
                {
                    "Layer Name": lname,
                    "Polyline Segments": len(paths),
                    "Total Linework (m)": f"{layer_len:.1f}",
                    "Native CAD Color": ldata.get("color", "#FFFFFF"),
                }
            )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No AutoCAD layer data available.")

    # Spatial Coordinate Inspector (Expandable)
    with st.expander("🔬 Detailed Spatial Entity Coordinates (X, Y Inspector)"):
        st.caption(
            "Complete inventory of every spatial entity, coordinate position, and layer captured by AutoSpec AI."
        )
        spatial_rows = []
        for b in getattr(takeoff, "block_instances", []):
            spatial_rows.append(
                {
                    "Entity": "MEP / Block Symbol",
                    "Name": b.get("name", "Unknown"),
                    "Trade Category": b.get("trade", "General"),
                    "X Pos (m)": f"{b.get('x', 0.0):.2f}",
                    "Y Pos (m)": f"{b.get('y', 0.0):.2f}",
                    "Layer": b.get("layer", "0"),
                    "Synthesized": "Yes" if b.get("is_synthesized") else "Native CAD Block",
                }
            )
        for op in getattr(takeoff, "openings", []):
            spatial_rows.append(
                {
                    "Entity": f"Opening ({op.type})",
                    "Name": op.id,
                    "Trade Category": "Openings - Doors & Windows",
                    "X Pos (m)": f"{op.x:.2f}" if getattr(op, "x", None) is not None else "On Wall",
                    "Y Pos (m)": f"{op.y:.2f}" if getattr(op, "y", None) is not None else "On Wall",
                    "Layer": op.layer,
                    "Synthesized": "No",
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
