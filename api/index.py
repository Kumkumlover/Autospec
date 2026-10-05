"""api/index.py — Vercel Serverless ASGI Application (FastAPI)

Enables AutoSpec AI to run on Vercel as serverless micro-endpoints:
- GET  /api/health       -> System healthcheck and SKU catalog status
- POST /api/parse-brief  -> Extracts specifications using Groq LLM (or heuristic fallback)
- POST /api/takeoff      -> Parses uploaded .DXF vector drawing in-memory
- POST /api/generate-boq -> End-to-end IS 1200 statutory BOQ generation
- POST /api/export-excel -> Generates styled openpyxl Excel spreadsheet (.xlsx)
"""

import os
import sys
import tempfile
from typing import Any

# Ensure project root is in sys.path for Vercel serverless execution
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from boq_engine import BoqEngine
from cad_parser import CadParser
from spec_parser import parse_client_brief

app = FastAPI(
    title="AutoSpec AI Serverless API",
    description="2D CAD Vector Takeoff & IS 1200 Cost Intelligence Engine",
    version="1.0.0",
)

# Enable CORS for web clients (e.g. Next.js on Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

boq_engine = BoqEngine()


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB limit


class BriefRequest(BaseModel):
    brief_text: str
    groq_api_key: str | None = None


@app.get("/api/health")
def healthcheck() -> dict[str, Any]:
    return {
        "status": "online",
        "service": "AutoSpec AI",
        "architecture": "Air-Gap In-Memory Vector Parser",
        "catalog_items_loaded": len(boq_engine.catalog.get("items", [])),
        "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
        "standards": ["IS 1200 Part 4 (Masonry)", "IS 1200 Part 12 (Plastering)"],
    }


@app.post("/api/parse-brief")
def parse_brief_endpoint(payload: BriefRequest) -> dict[str, Any]:
    try:
        spec = parse_client_brief(payload.brief_text, groq_api_key=payload.groq_api_key)
        return {"status": "success", "spec": spec.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/takeoff")
async def cad_takeoff_endpoint(
    file: UploadFile = File(...),
    units: str = Form("auto"),
    wall_height: float = Form(3.0),
    wall_thickness: float = Form(0.23),
) -> dict[str, Any]:
    raw_name = file.filename or "drawing.dxf"
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in (".dxf", ".dwg"):
        raise HTTPException(status_code=400, detail="Only .dxf and .dwg CAD files are supported.")

    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="autospec_")
    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (maximum allowed size is 50MB)")
        with os.fdopen(fd, "wb") as f:
            f.write(contents)

        safe_filename = os.path.basename(raw_name)
        parser = CadParser(default_units=units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        takeoff = parser.parse_cad_file(temp_path, filename=safe_filename)
        return {"status": "success", "takeoff": takeoff.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CAD parsing failed: {e}") from e
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/generate-boq")
async def generate_boq_endpoint(
    file: UploadFile = File(...),
    brief_text: str = Form(""),
    groq_api_key: str | None = Form(None),
    units: str = Form("auto"),
    wall_height: float = Form(3.0),
    wall_thickness: float = Form(0.23),
) -> dict[str, Any]:
    raw_name = file.filename or "drawing.dxf"
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in (".dxf", ".dwg"):
        raise HTTPException(status_code=400, detail="Only .dxf and .dwg CAD files are supported.")

    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="autospec_")
    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (maximum allowed size is 50MB)")
        with os.fdopen(fd, "wb") as f:
            f.write(contents)

        safe_filename = os.path.basename(raw_name)
        parser = CadParser(default_units=units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        takeoff = parser.parse_cad_file(temp_path, filename=safe_filename)
        spec = parse_client_brief(brief_text, groq_api_key=groq_api_key)
        boq = boq_engine.generate_boq(takeoff, spec, wall_height_m=wall_height, wall_thickness_m=wall_thickness)

        return {
            "status": "success",
            "boq": boq,
            "takeoff_summary": {
                "floor_area_sqm": takeoff.total_floor_area_sqm,
                "wall_area_sqm": takeoff.total_wall_area_sqm,
                "openings_count": len(takeoff.openings),
                "blocks_count": sum(takeoff.block_counts.values()),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BOQ generation failed: {e}") from e
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/export-excel")
async def export_excel_endpoint(
    file: UploadFile = File(...),
    brief_text: str = Form(""),
    groq_api_key: str | None = Form(None),
    units: str = Form("auto"),
    wall_height: float = Form(3.0),
    wall_thickness: float = Form(0.23),
) -> Response:
    raw_name = file.filename or "drawing.dxf"
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in (".dxf", ".dwg"):
        raise HTTPException(status_code=400, detail="Only .dxf and .dwg CAD files are supported.")

    fd_cad, temp_cad = tempfile.mkstemp(suffix=ext, prefix="autospec_cad_")
    fd_xlsx, temp_xlsx = tempfile.mkstemp(suffix=".xlsx", prefix="autospec_boq_")
    os.close(fd_xlsx)

    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (maximum allowed size is 50MB)")
        with os.fdopen(fd_cad, "wb") as f:
            f.write(contents)

        safe_filename = os.path.basename(raw_name)
        parser = CadParser(default_units=units, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        takeoff = parser.parse_cad_file(temp_cad, filename=safe_filename)
        spec = parse_client_brief(brief_text, groq_api_key=groq_api_key)
        boq = boq_engine.generate_boq(takeoff, spec, wall_height_m=wall_height, wall_thickness_m=wall_thickness)
        boq_engine.export_to_excel(boq, temp_xlsx)

        with open(temp_xlsx, "rb") as f:
            xlsx_bytes = f.read()

        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=autospec_boq_estimate.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {e}") from e
    finally:
        for p in [temp_cad, temp_xlsx]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
