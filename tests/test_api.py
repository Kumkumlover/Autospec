"""Unit and integration tests for FastAPI Vercel Serverless Endpoints (api/index.py)."""

from fastapi.testclient import TestClient

from api.index import app
from sample_dxf_generator import generate_sample_2bhk_dxf

client = TestClient(app)


def test_api_healthcheck():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["catalog_items_loaded"] >= 30


def test_api_parse_brief():
    payload = {
        "brief_text": "Penthouse in Indiranagar. Philips 12W 3000K spots, Atomberg BLDC fans, Italian marble flooring.",
    }
    response = client.post("/api/parse-brief", json=payload)
    assert response.status_code == 200
    spec = response.json()["spec"]
    assert spec["preferred_lighting_brand"] == "Philips"
    assert spec["preferred_fan_brand"] == "Atomberg"
    assert spec["flooring_preference"] == "Italian Marble"


def test_api_cad_takeoff_and_boq(tmp_path):
    dxf_file = tmp_path / "test_plan.dxf"
    generate_sample_2bhk_dxf(str(dxf_file))

    with open(dxf_file, "rb") as f:
        response = client.post(
            "/api/generate-boq",
            files={"file": ("test_plan.dxf", f, "application/dxf")},
            data={"brief_text": "Standard 2BHK interior", "units": "mm"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["boq"]["items"]) >= 8


def test_api_takeoff(tmp_path):
    dxf_file = tmp_path / "takeoff_plan.dxf"
    generate_sample_2bhk_dxf(str(dxf_file))

    with open(dxf_file, "rb") as f:
        response = client.post(
            "/api/takeoff",
            files={"file": ("takeoff_plan.dxf", f, "application/dxf")},
            data={"units": "mm", "wall_height": "3.0", "wall_thickness": "0.23"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "takeoff" in data
    assert data["takeoff"]["total_floor_area_sqm"] > 0


def test_api_export_excel(tmp_path):
    dxf_file = tmp_path / "excel_plan.dxf"
    generate_sample_2bhk_dxf(str(dxf_file))

    with open(dxf_file, "rb") as f:
        response = client.post(
            "/api/export-excel",
            files={"file": ("excel_plan.dxf", f, "application/dxf")},
            data={"brief_text": "2BHK residence", "units": "mm"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=autospec_boq_estimate.xlsx" in response.headers["content-disposition"]
    assert len(response.content) > 1000  # Valid Excel binary


def test_api_invalid_extension(tmp_path):
    fake_file = tmp_path / "malicious.txt"
    fake_file.write_text("not a cad file")

    with open(fake_file, "rb") as f:
        response = client.post(
            "/api/takeoff",
            files={"file": ("malicious.txt", f, "text/plain")},
        )

    assert response.status_code == 400
    assert "Only .dxf and .dwg CAD files are supported" in response.json()["detail"]
