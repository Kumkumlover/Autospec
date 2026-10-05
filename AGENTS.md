# AGENTS.md — AutoSpec AI Agent & Contributor Guide

## Project Summary
**AutoSpec AI** is a 2D CAD vector takeoff and pre-construction cost intelligence engine designed for Indian architectural studios, interior designers, and cost consultants. It ingests 2D `.DXF` CAD drawings, interprets unstructured client natural language briefs, applies statutory **IS 1200** opening deductions, and compiles a priced Bill of Quantities (BOQ) linked to verified Indian B2B procurement catalogs.

---

## Technical Stack
- **Language**: Python 3.12+ (tested with Python 3.14 on Windows)
- **CAD Parsing & Conversion**: `ezdxf` (100% in-memory vector analysis) & bundled LibreDWG `dwg2dxf` (local offline air-gapped DWG-to-DXF conversion)
- **LLM Engine**: Groq Llama 3.3 70B (`llama-3.3-70b-versatile`) / Anthropic Claude 3.5 Sonnet (`claude-3-5-sonnet-20241022`) with deterministic offline heuristic fallback
- **Statutory Rules**: Bureau of Indian Standards (IS 1200 Part 2, Part 4, Part 12)
- **Data & Excel**: `pandas`, `openpyxl`
- **Frontend & Deployment**: `streamlit` (Local UI) & `fastapi` Serverless (`api/index.py` for Vercel deployment)
- **Validation & Test**: `pydantic`, `pytest`

---

## Directory Structure
```
d:/Autospec/
├── .agents/
│   └── rules/
│       ├── is1200_standards.md     # Indian Standard measurement invariants
│       ├── cad_parsing_rules.md    # ezdxf layer & entity conventions
│       └── code_quality.md         # Python standards & defensive execution
├── api/
│   └── index.py                    # FastAPI ASGI Serverless App for Vercel
├── samples/
│   ├── sample_2bhk_plan.dxf        # Synthetic test CAD drawing
│   ├── two_story_house.dwg         # Real two-story villa CAD drawing
│   ├── two_story_house.dxf         # Converted DXF floor plan
│   └── test_boq.xlsx               # Sample generated openpyxl spreadsheet
├── tests/
│   ├── test_api.py                 # FastAPI Vercel serverless tests
│   ├── test_cad_parser.py          # ezdxf block & area unit tests (DXF & DWG)
│   ├── test_cad_visualizer.py      # Plotly interactive canvas unit tests
│   ├── test_spec_parser.py         # Brief extraction unit tests (Groq & fallback)
│   ├── test_is1200_engine.py       # Statutory deduction edge cases
│   └── test_excel_export.py        # openpyxl formatting & formula checks
├── tools/
│   └── libredwg/                   # Standalone LibreDWG 0.14 binaries (dwg2dxf)
├── app.py                          # Streamlit UI Application (Local Testing)
├── cad_parser.py                   # DXF/DWG vector extraction engine
├── cad_visualizer.py               # Interactive Plotly & blueprint CAD visualizer
├── spec_parser.py                  # Brief interpreter (Groq / Claude / Fallback)
├── boq_engine.py                   # IS 1200 rules & price matcher
├── sample_dxf_generator.py         # Programmatic CAD test floor plan generator
├── benchmark_audit.py              # 7-day concierge RAT accuracy runner
├── catalog.json                    # 32 verified Indian B2B SKUs
├── vercel.json                     # Vercel serverless deployment config
├── requirements.txt                # Pinned dependencies
├── LIFECYCLE.md                    # Project phase gates & milestone criteria
├── PRD.md                          # Converted Markdown PRD
└── README.md                       # Developer setup & user guide
```

---

## Core Invariants & Engineering Constraints

1. **Air-Gap CAD Guarantee**:
   Proprietary CAD files (`.DXF`, `.DWG`) must **never** be sent to external cloud APIs or third-party servers. All entity inspection, polyline tracing, and block counting must execute 100% locally in-memory via `ezdxf`.

2. **IS 1200 Strict Adherence**:
   - **Masonry (IS 1200 Part 4)**: Openings $\le 0.1 \text{ m}^2$ have zero deduction. Openings $> 0.1 \text{ m}^2$ deduct opening volume ($A \times t$).
   - **Plastering (IS 1200 Part 12)**:
     - Openings $\le 0.5 \text{ m}^2$: Zero deduction, no reveals added.
     - Openings $0.5 < A \le 3.0 \text{ m}^2$: Deduct single face ($1.0 \times A$).
     - Openings $> 3.0 \text{ m}^2$: Deduct both faces ($2.0 \times A$) and add jambs/reveals/sills allowance.
   - Any deduction must record an explicit audit trace in the generated line item notes.

3. **Hybrid LLM Reliability**:
   The brief interpreter must remain functional under zero-network or unkeyed conditions. When `ANTHROPIC_API_KEY` is not set, the system seamlessly falls back to regex/token heuristics without crashing.

4. **Excel Output Integrity**:
   Generated `.xlsx` spreadsheets must be 100% compliant with standard spreadsheet engines (Microsoft Excel, Google Sheets, LibreOffice Calc) without repair warnings. All numeric columns must use genuine numeric data types (not stringified numbers) and include valid formula calculations.

---

## Operational Commands

### Environment Setup
```powershell
python -m pip install -r requirements.txt
```

### Generate Sample Architectural CAD Plan
```powershell
python sample_dxf_generator.py
```

### Run Unit & Integration Tests
```powershell
python -m pytest tests/ -v
```

### Run 7-Day Concierge RAT Accuracy Benchmark
```powershell
python benchmark_audit.py
```

### Launch Streamlit Web UI
```powershell
streamlit run app.py
```
