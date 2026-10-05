# Code Quality & Engineering Guidelines

This rule file specifies the coding, testing, and defensive execution guidelines for the AutoSpec AI repository.

---

## 1. Python Standards
- **Version Compatibility**: Compatible with Python 3.12+ (tested on Python 3.14 on Windows).
- **Type Annotations**: All public functions and module exports must include strict type annotations (`typing` / built-in generics).
- **Data Models**: Use `pydantic` or `@dataclass` for structured configurations and schemas.
- **Pure Functions**: Isolate computational algorithms (IS 1200 rules, unit converters) into pure, side-effect-free functions to simplify unit testing.

---

## 2. Defensive Execution & Resilience
- **API Fault-Tolerance**: Network calls to external LLMs (e.g. Anthropic API) must be wrapped with timeouts, retry logic, and automatic fallback to local heuristic parsing.
- **Fail-Safe UI**: The Streamlit interface must never crash with unhandled tracebacks. Ingestion errors must be caught and rendered as actionable UI alerts with file inspection suggestions.
- **Excel Spreadsheet Compliance**:
  - Always set explicit column widths in `openpyxl`.
  - Format monetary numbers with commas (e.g., `#,##0.00`).
  - Generate dynamic Excel formula strings (e.g., `=D2*F2`) while preserving raw numeric values for programmatic consumption.

---

## 3. Testing & Verification Gate
- Every module (`cad_parser.py`, `spec_parser.py`, `boq_engine.py`) must have corresponding unit tests in `tests/`.
- Test coverage for statutory rules (IS 1200 Part 4 & 12) must cover exact threshold edge cases:
  - $0.09 \text{ m}^2$, $0.10 \text{ m}^2$, $0.11 \text{ m}^2$ (Masonry)
  - $0.49 \text{ m}^2$, $0.50 \text{ m}^2$, $0.51 \text{ m}^2$ (Plaster Tier 1 vs Tier 2)
  - $2.99 \text{ m}^2$, $3.00 \text{ m}^2$, $3.01 \text{ m}^2$ (Plaster Tier 2 vs Tier 3)
- All tests must pass before declaring milestone completion.
