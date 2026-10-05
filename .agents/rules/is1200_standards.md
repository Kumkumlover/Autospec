# IS 1200 Measurement Standards & Invariants

This rule file specifies the statutory measurement rules defined by the **Bureau of Indian Standards (BIS)** under **IS 1200** (Method of Measurement of Building and Civil Engineering Works). All calculations in `boq_engine.py` must strictly comply with these formulas.

---

## 1. Concrete & Masonry Works (IS 1200 Part 2 & Part 4)

### Opening Deduction Thresholds
- **Threshold**: No deduction shall be made for openings up to **$0.1 \text{ m}^2$** ($1.076 \text{ sq.ft}$) in area.
- **Rule Formulation**:
  $$\text{Deduction Area} = \begin{cases} 0 & \text{if } A_{\text{opening}} \le 0.1 \text{ m}^2 \\ A_{\text{opening}} & \text{if } A_{\text{opening}} > 0.1 \text{ m}^2 \end{cases}$$
- **Volume Calculation**:
  $$\text{Deduction Volume} = \text{Deduction Area} \times \text{Wall Thickness}$$

---

## 2. Plastering & Pointing Works (IS 1200 Part 12)

Plastering is measured across both vertical surfaces (inner and outer faces) unless specified otherwise. Deductions for doors, windows, and openings follow a strict three-tier rule:

### Tier 1: Small Openings ($A_{\text{opening}} \le 0.5 \text{ m}^2$)
- **Action**: **Zero Deduction**.
- Neither face is deducted.
- No addition is made for jambs, soffits, or sills.

### Tier 2: Standard Openings ($0.5 \text{ m}^2 < A_{\text{opening}} \le 3.0 \text{ m}^2$)
- **Action**: **Deduct One Face Only**.
- Net deduction area: $1.0 \times A_{\text{opening}}$.
- The other face is retained to compensate for jambs, reveals, and soffits.
- No extra allowance added for jambs/sills.

### Tier 3: Large Openings ($A_{\text{opening}} > 3.0 \text{ m}^2$)
- **Action**: **Deduct Both Faces**.
- Deduction area: $2.0 \times A_{\text{opening}}$.
- An explicit addition must be made for jambs, soffits, and sills:
  $$\text{Reveal Addition} = (\text{Perimeter of Opening} - \text{Sill Width if at floor}) \times \text{Jamb Depth}$$

---

## 3. Ceiling & Flooring Works (IS 1200 Part 11)
- Measured net in plan area ($\text{m}^2$).
- No deduction for columns, piers, or pipes whose cross-sectional area does not exceed **$0.1 \text{ m}^2$**.
- Boundary perimeter of rooms measured along inner face of walls.

---

## 4. Audit Trail Invariant
Every calculated quantity subject to IS 1200 must include:
1. `gross_quantity`: The raw geometric quantity from CAD.
2. `opening_deductions`: Detailed breakdown of each opening area and tier applied.
3. `net_quantity`: The final billable quantity.
4. `statutory_reference`: Exact clause (e.g., `IS 1200 Part 12 Clause 4.3.1`).
