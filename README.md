# AutoSpec AI — 2D CAD Vector Takeoff & Pre-Construction Cost Intelligence Engine

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://python.org)
[![CAD Engine](https://img.shields.io/badge/CAD%20Engine-ezdxf%20In--Memory-orange.svg)](https://ezdxf.mozman.at)
[![Statutory Compliance](https://img.shields.io/badge/Statutory%20Rules-BIS%20IS%201200-green.svg)](https://bis.gov.in)
[![RAT Benchmark](https://img.shields.io/badge/RAT%20Accuracy-100%25-brightgreen.svg)](#7-day-concierge-rat-accuracy-benchmark)
[![Data Privacy](https://img.shields.io/badge/Air--Gap-100%25%20Local-red.svg)](#air-gap-cad-data-privacy-guarantee)

---

## 1. Executive Summary

**AutoSpec AI** is an AI-powered pre-construction cost intelligence engine designed specifically for boutique architectural practices, interior design studios, and freelance quantity surveyors in India.

The application bridges:
1. **Native 2D AutoCAD vector files (`.DXF` & `.DWG`)** parsed 100% locally in-memory via `ezdxf` with an air-gap guarantee and automated local conversion via bundled LibreDWG (`dwg2dxf`).
2. **Unstructured client conversational briefs** (written notes, transcripts) interpreted into typed technical schemas via Groq Llama 3.3 70B (with a deterministic offline fallback).
3. **Bureau of Indian Standards (IS 1200)** statutory measurement deduction rules (Part 4 Masonry, Part 11 Flooring, Part 12 Plastering).
4. **Verified Indian B2B Procurement Catalogs** (Amazon Business, Moglix, Industrybuying) supplying real-time INR unit rates and direct buy links.
5. **Corporate Excel BOQ Exporter** (`.xlsx`) via `openpyxl` with dynamic formulas, currency formats, and opening deduction audit trails.

---

## 2. Directory Layout

```
d:/Autospec/
├── .agents/
│   └── rules/
│       ├── is1200_standards.md     # Bureau of Indian Standards deduction rules
│       ├── cad_parsing_rules.md    # ezdxf layer & entity conventions
│       └── code_quality.md         # Python engineering standards
├── samples/
│   └── sample_2bhk_plan.dxf        # Synthetic 2BHK test CAD drawing
├── tests/
│   ├── test_cad_parser.py          # CAD block & area takeoff unit tests
│   ├── test_spec_parser.py         # Client brief extraction unit tests
│   ├── test_is1200_engine.py       # IS 1200 statutory deduction edge cases
│   └── test_excel_export.py        # openpyxl formatting & formula validation
├── app.py                          # Streamlit 4-Tab Web Application
├── cad_parser.py                   # DXF/DWG vector extraction engine
├── cad_visualizer.py               # Interactive Plotly & blueprint CAD visualizer
├── spec_parser.py                  # Brief interpreter (Claude / Fallback)
├── boq_engine.py                   # IS 1200 rules & price matcher
├── sample_dxf_generator.py         # Programmatic CAD test floor plan generator
├── benchmark_audit.py              # 7-day concierge RAT accuracy runner
├── catalog.json                    # 32 verified Indian B2B SKUs
├── requirements.txt                # Pinned dependencies
├── LIFECYCLE.md                    # Project phase gates & milestone criteria
├── PRD.md                          # Production-grade PRD specification
└── README.md                       # Developer setup & user guide
```

---

## 3. Quick Start & Setup

### 3.1 Installation
Clone or navigate to the repository and install dependencies:
```powershell
python -m pip install -r requirements.txt
```

### 3.2 Generate Synthetic Test CAD Floor Plan
Generate the bundled standard Indian 2BHK architectural drawing:
```powershell
python sample_dxf_generator.py
```
*Output: `samples/sample_2bhk_plan.dxf` (containing walls, doors, windows, downlights, ceiling fans, switches, sockets, and plumbing fixtures).*

### 3.3 Set Groq API Key (Optional / Recommended)
Set your Groq API key in your terminal session or enter it directly into the Streamlit sidebar:
```powershell
$env:GROQ_API_KEY = "gsk_..."
```
*(If no key is configured, AutoSpec AI automatically runs in deterministic offline heuristic mode with 100% functionality).*

### 3.4 Run Unit & Integration Tests
Execute the comprehensive `pytest` test suite:
```powershell
python -m pytest tests/ -v
```

### 3.5 Run 7-Day Concierge RAT Accuracy Benchmark
Validate the #1 Riskiest Assumption Test (RAT) achieving $\ge 95\%$ accuracy:
```powershell
python benchmark_audit.py
```

### 3.6 Local Testing with Streamlit
Launch the interactive 4-tab web application locally:
```powershell
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 4. Vercel Serverless Deployment Architecture

AutoSpec AI is structured for dual execution:
1. **Local Mode:** Interactive Streamlit web app (`app.py`).
2. **Vercel Serverless Cloud Mode:** Powered by FastAPI in `api/index.py` configured via `vercel.json`.

### Endpoints Available on Vercel:
- `GET  /api/health` — System healthcheck and catalog status
- `POST /api/parse-brief` — Extracts client specifications using Groq Llama 3.3 70B
- `POST /api/takeoff` — In-memory 2D CAD vector takeoff
- `POST /api/generate-boq` — Complete IS 1200 statutory BOQ compilation
- `POST /api/export-excel` — Streams styled `.xlsx` spreadsheet download

### Deploy to Vercel:
```bash
npm install -g vercel
vercel
```
Set `GROQ_API_KEY` in the Vercel Project Environment Variables dashboard.

---

## 5. Statutory IS 1200 Rules & Invariants

All calculations in `boq_engine.py` strictly adhere to the Bureau of Indian Standards (BIS):

### Masonry & Brickwork (IS 1200 Part 4)
- **Openings $\le 0.1 \text{ m}^2$:** Zero deduction.
- **Openings $> 0.1 \text{ m}^2$:** Deduct opening volume ($A_{\text{op}} \times \text{wall thickness}$).

### Plastering & Pointing (IS 1200 Part 12)
Plastering is measured across both vertical surfaces (Gross Area = $2.0 \times \text{Gross Wall Area}$):
- **Tier 1 ($\le 0.5 \text{ m}^2$):** **Zero deduction**, no reveals added.
- **Tier 2 ($0.5 < A \le 3.0 \text{ m}^2$):** **Deduct single face** ($1.0 \times A_{\text{op}}$), no reveals added.
- **Tier 3 ($> 3.0 \text{ m}^2$):** **Deduct both faces** ($2.0 \times A_{\text{op}}$), and add reveals, jambs, and sills.

---

## 6. Air-Gap CAD Data Privacy Guarantee

Proprietary AutoCAD drawings (`.DXF`, `.DWG`) represent sensitive intellectual property and client privacy. **AutoSpec AI processes all CAD geometry 100% in-memory via `ezdxf`.** Under no circumstances are raw drawing vectors, layers, or spatial geometries transmitted over public networks or uploaded to cloud storage.

---

## 7. LLM Brief Extraction: Groq & Heuristic Fallback

The natural language brief interpreter (`spec_parser.py`) features a robust multi-tiered design:
1. **Groq Llama 3.3 70B (`llama-3.3-70b-versatile`):** Sub-second, ultra-fast structured JSON extraction.
2. **Anthropic Claude 3.5 Sonnet:** Secondary cloud provider.
3. **Deterministic Heuristic Parser:** If unkeyed or offline, seamlessly extracts parameters via regex and keyword proximity without network latency.

---

## 7. License
Developed for Indian architectural practices, interior designers, and cost consultants. Open-core architecture under MIT License.
