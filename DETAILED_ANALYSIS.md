# Detailed Calculation Explanation and Results Analysis (Latest Runs)

## 1. CALCULATION FORMULAS

### Hourly Rate
```
hourly_rate = (monthly_salary / 160) × 1.25
```
- 160 hours = standard working hours/month  
- 1.25 = built-in 25% overhead multiplier  
- Example: 1,000,000 ISK/month → 7,812.5 ISK/hour

### Direct Cost
```
direct_cost = Σ(hours × hourly_rate) for all employees
```
- Includes both R&D hours (allocated to topics) and Non-R&D hours

### Project Overhead
- **Fixed** (≥ 100,000): Added as fixed ISK amount (also counts toward target)
- **Percentage** (0 < value < 1): `overhead = direct_cost × percentage` (cost-side only)

### Total Target
```
total_target = grant_contractual + matching_funds + fixed_overhead
```
- Matching: `grant × (value/100)` if percentage, else absolute value  
- Only fixed overhead (≥ 100,000) added to target

### Total Project Cost
```
total_cost = direct_cost + overhead_cost
```

### Residual Target (Concatenation)
```
residual_target = max(total_target - previous_cost, 0)
```

---

## 2. HOUR & MONEY USAGE (Pipeline Runs)

### 2024 Run (state: `projectStates/Euridice_LATEST.json`)
| Metric | Value | Status |
|--------|-------|--------|
| R&D Hours | 4,686 / 4,686 | ✅ 100% used |
| Non-R&D Hours | 715 / 715 | ✅ 100% used |
| Total Target | 90,616,810 ISK | Target |
| Actually Allocated | 37,584,874 ISK | 41.5% of target |
| Shortfall | 53,031,936 ISK | 58.5% below target |
| Solver Status | `fallback_feasible` | Fallback used |
| Capacity Analysis | 62.3% shortfall | Warning |

**Conclusion:** All hours used; money shortfall due to insufficient capacity (hours × rates < targets).

### 2025 Run (Concatenated with 2024)
| Metric | Value | Status |
|--------|-------|--------|
| R&D Hours | 4,748 / 4,748 | ✅ 100% used |
| Non-R&D Hours | 0 / 0 | ✅ 100% used |
| Total Target (cumulative) | 110,866,810 ISK | Target |
| Actually Allocated (cumulative) | 67,364,707 ISK | 60.8% of target |
| Shortfall | 43,502,103 ISK | 39.2% below target |
| Solver Status | `fallback_feasible` | Fallback used |
| Capacity Analysis | 75.1% shortfall | Warning |

**Conclusion:** All hours used; still under target because of limited capacity.

---

## 3. PROJECT-BY-PROJECT ANALYSIS (Latest Runs)

### EURIDICE
- **2024:** Target 42,385,810; Actual 18,255,962 (‑56.9%); Hours 2,200 R&D + 547 Non-R&D. Under target due to capacity.  
- **2025 (concat):** Previous 18,255,962; Residual 24,129,848; New 6,019,077; Total 24,275,039 (‑42.7%). Capped correctly.

### ICE-ID
- **2024:** Target 3,000,000; Actual 990,789 (‑67.0%); Hours 153 R&D + 10 Non-R&D. Small target, minimum allocation keeps some spend.  
- **2025 (concat):** Previous 990,789; New 501,188; Total 1,491,977 (‑50.3%). Still under target; small weight in fallback.

### FRESH-ID
- **2024:** Target 22,651,000; Actual 7,480,786 (‑67.0%); Hours 1,165 R&D + 79 Non-R&D.  
- **2025 (concat):** Previous 7,480,786; New 3,784,139; Total 11,264,924 (‑50.3%). Now allocated (was 0 before fixes); residual-weighted fallback working.

### AI-STYLIST
- **2024:** Target 22,580,000 (includes 1,700,000 fixed OH); Actual 10,857,337 (‑51.9%); Hours 1,167 R&D + 79 Non-R&D.  
- **2025 (concat):** Previous 10,857,337; New 6,324,163; Total 17,181,500 (‑23.9%). Hard caps prevent over-target (was +6.1% before fixes).

### TRACKWELL (2025 only)
- **2025:** Target 20,250,000; Actual 13,151,267 (‑35.1%); Hours 1,310 R&D. Allocated proportionally; under target due to capacity.

---

## 4. KEY ISSUES & FIXES (Current Status)
| Issue | Status | Description |
|-------|--------|-------------|
| FRESH-ID zero allocation | ✅ Fixed | Residual-weighted fallback ensures allocation in 2025 |
| Over-budget projects | ✅ Fixed | Hard caps enforce total targets (EURIDICE, AI-STYLIST capped) |
| Hour imbalance risk | ⚠️ Improved | Fallback weights by residual targets; balance enforced post-normalization |
| Solver non-optimal paths | ✅ Fixed | Fallback triggers on non-optimal statuses |
| Minimum allocation guarantee | ✅ Fixed | 1% minimum applied in fallback |
| Capacity analysis | ✅ Fixed | Early warnings for shortfall vs capacity |
| Insufficient capacity | ⚠️ Present | Hours × rates < targets → under-allocation persists |

---

## 5. ROOT CAUSES
1) ✅ Fallback trigger on non-optimal solver status  
2) ✅ Residual-target weighting in fallback  
3) ✅ Hard caps at total targets  
4) ✅ Minimum allocation guarantee  
5) ✅ Capacity analysis warnings  
6) ⚠️ Remaining: Capacity gap (structural)  
7) ⚠️ Remaining: Under-allocation driven by capacity gap  

---

## 6. SUMMARY
- 2024: All hours allocated; 41.5% of target money; solver `fallback_feasible`; 62.3% capacity shortfall warning; all projects under target (‑51.9% to ‑67.0%).  
- 2025 (concat): All hours allocated; 60.8% of cumulative target; solver `fallback_feasible`; 75.1% capacity shortfall warning; all projects under target (‑23.9% to ‑50.3%); no over-target cases; TRACKWELL added.  
- Overall: Algorithm respects caps and residuals; allocations limited by available capacity.

**Tests:** `pytest -q` → all passing.  

---

## 7. RECOMMENDATIONS
1) Maintain fallback + caps; use residual targets for concatenation.  
2) Address capacity gap if targets must be met (increase hours, rates, or reduce targets).  
3) Align SciPy/NumPy versions; update PyQt5/sip to clear deprecations.  
4) Keep minimum allocation safeguard.  

---

## 8. Generated Artifacts (Latest Runs)
- Reports:  
  - `test_reports/test_diagnostics_2025-12-05_12-04-08.txt` (2024 run)  
  - `test_reports/test_2025_concatenated_diagnostics.txt` (2024+2025 concat)  
- States:  
  - `test_projectStates/test_2024_state.json`  
  - `test_projectStates/test_2025_state.json`
## Detailed Calculation Explanation and Results (Latest Runs)

### 1) Formulas
- Hourly rate: `(monthly_salary / 160) × 1.25`
- Direct cost: sum(hours × hourly_rate) for R&D and Non-R&D
- Overhead: fixed (≥100k) added to target; percentage (<1) applied to cost
- Target: `grant_contractual + matching_funds + fixed_overhead`
- Total cost: `direct_cost + overhead_cost`
- Residual target (concatenation): `max(total_target − previous_cost, 0)`

### 2) 2024 Run (state: `projectStates/Euridice_LATEST.json`)
- Solver: `fallback_feasible`
- Project costs vs targets:
  - EURIDICE: 18,255,962 / 42,385,810 (‑56.9%)
  - ICE-ID: 990,789 / 3,000,000 (‑67.0%)
  - FRESH-ID: 7,480,786 / 22,651,000 (‑67.0%)
  - AI-STYLIST: 10,857,337 / 22,580,000 (‑51.9%)
- Outputs: `test_reports/test_diagnostics_2025-12-05_12-04-08.txt`, `test_projectStates/test_2024_state.json`

### 3) 2025 Run (concatenated with 2024; initial costs from above)
- Solver: `fallback_feasible`
- Project costs (total, including 2024) vs targets; new 2025 spend in parentheses:
  - EURIDICE: 24,275,039 / 42,385,810 (‑42.7%) — new 6,019,077
  - ICE-ID: 1,491,977 / 3,000,000 (‑50.3%) — new 501,188
  - FRESH-ID: 11,264,924 / 22,651,000 (‑50.3%) — new 3,784,139
  - AI-STYLIST: 17,181,500 / 22,580,000 (‑23.9%) — new 6,324,163
  - TRACKWELL: 13,151,267 / 20,250,000 (‑35.1%) — all new
- Outputs: `test_reports/test_2025_concatenated_diagnostics.txt`, `test_projectStates/test_2025_state.json`

### 4) Observations
- All projects remain under target due to capacity (hours × rates < targets).
- Hard caps and residual targeting are enforced; no over-target spending.
- Fallback allocation active in both runs; residual targets respected.

### 5) Tests
- `pytest -q` → all passing.

### 6) Warnings
- SciPy requires NumPy <1.23 (env has 1.26.4); upgrade SciPy or pin NumPy.
- PyQt5/sip deprecation warnings remain until dependencies are updated.

### 7) Recommendations
- Keep current fallback + caps; focus on capacity (raise hours or rates) if hitting targets is required.
- Align SciPy/NumPy and update PyQt5/sip to clear warnings.
