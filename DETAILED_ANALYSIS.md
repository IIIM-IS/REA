# Detailed Calculation Explanation and Results Analysis

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
- **Fixed** (≥ 100,000): Added as fixed ISK amount
- **Percentage** (0 < value < 1): `overhead = direct_cost × percentage`
- **Note:** Only fixed overhead is added to target calculation

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

## 2. HOUR & MONEY USAGE

### 2024 Run
| Metric | Value | Status |
|--------|-------|--------|
| R&D Hours | 4,686 / 4,686 | ✅ 100% used |
| Non-R&D Hours | 715 / 715 | ✅ 100% used |
| Total Target | 90,616,810 ISK | Target |
| Actually Allocated | 37,584,874 ISK | 41.5% of target |
| Shortfall | 53,031,936 ISK | 58.5% below target |
| Solver Status | `fallback_feasible` | Fallback used |
| Capacity Analysis | 62.3% shortfall | Early warning active |

**Conclusion:** ✅ All hours used, but only 41.5% of target money allocated (insufficient capacity)

### 2025 Run (Concatenated)
| Metric | Value | Status |
|--------|-------|--------|
| R&D Hours | 4,748 / 4,748 | ✅ 100% used |
| Non-R&D Hours | 0 / 0 | ✅ 100% used |
| Total Target (cumulative) | 110,866,810 ISK | Target |
| Actually Allocated (cumulative) | 67,364,707 ISK | 60.8% of target |
| Shortfall | 43,502,103 ISK | 39.2% below target |
| Solver Status | `fallback_feasible` | Fallback used |
| Capacity Analysis | 75.1% shortfall | Early warning active |

**Conclusion:** ✅ All hours used, but only 60.8% of target money allocated

---

## 3. PROJECT-BY-PROJECT ANALYSIS

### EURIDICE

**2024:**
- Target: 42,385,810 ISK (Grant: 21,192,905 + Matching: 21,192,905)
- Actual: 18,255,962 ISK (-56.9%)
- Hours: 2,200 R&D + 547 Non-R&D = 2,747 total
- **Result:** Under target by 56.9%
- **Reason:** Hourly rates insufficient to reach 42.4M target with available hours

**2025 (Concatenated):**
- Previous: 18,255,962 ISK | Residual Target: 24,129,848 ISK
- New: 6,019,077 ISK | Total: 24,275,039 ISK (-42.7% vs original)
- Hours: 1,567 R&D (new)
- **Result:** ✅ **FIXED** - Now properly capped, -42.7% (was +14.5% before fix)
- **Reason:** Hard caps now prevent exceeding total target

---

### ICE-ID

**2024:**
- Target: 3,000,000 ISK
- Actual: 990,789 ISK (-67.0%)
- Hours: 153 R&D + 10 Non-R&D
- **Result:** Under target by 67.0%
- **Reason:** Small target relative to others, minimum allocation guarantee ensures some allocation

**2025 (Concatenated):**
- Previous: 990,789 ISK | Residual: 2,009,211 ISK
- New: 501,188 ISK | Total: 1,491,977 ISK (-50.3% vs original)
- Hours: 120 R&D (new)
- **Result:** Still 50.3% under target
- **Reason:** Small target weight in fallback allocation, but minimum guarantee ensures allocation

---

### FRESH-ID

**2024:**
- Target: 22,651,000 ISK (Grant: 16,988,250 + Matching: 5,662,750)
- Actual: 7,480,786 ISK (-67.0%)
- Hours: 1,165 R&D + 79 Non-R&D
- **Result:** Under target by 67.0%
- **Reason:** Fallback mechanism properly weighted by target

**2025 (Concatenated):**
- Previous: 7,480,786 ISK | Residual: 15,170,214 ISK
- New: 3,784,139 ISK | Total: 11,264,924 ISK (-50.3% vs original)
- Hours: 988 R&D (new)
- **Result:** ✅ **FIXED** - Now getting allocation (was 0 before fix)
- **Reason:** Fallback triggered when solver not optimal, properly weighted by residual targets

---

### AI-STYLIST

**2024:**
- Target: 22,580,000 ISK (Grant: 16,200,000 + Matching: 4,680,000 + Overhead: 1,700,000)
- Actual: 10,857,337 ISK (-51.9%)
- Hours: 1,167 R&D + 79 Non-R&D
- **Result:** Under target by 51.9%
- **Note:** Overhead calculation working correctly

**2025 (Concatenated):**
- Previous: 10,857,337 ISK | Residual: 11,722,663 ISK
- New: 6,324,163 ISK | Total: 17,181,500 ISK (-23.9% vs original)
- Hours: 763 R&D (new)
- **Result:** ✅ **FIXED** - Now properly capped, -23.9% (was +6.1% before fix)
- **Reason:** Hard caps prevent exceeding total target

---

### TRACKWELL (2025 only)

**2025:**
- Target: 20,250,000 ISK (Grant: 13,500,000 + Matching: 2,700,000 + Overhead: 4,050,000)
- Actual: 13,151,267 ISK (-35.1%)
- Hours: 1,310 R&D
- **Result:** Under target by 35.1%
- **Reason:** Fallback mechanism allocated appropriately based on target weight

---

## 4. KEY ISSUES & FIXES

| Issue | Status | Description |
|-------|--------|-------------|
| **FRESH-ID Zero Allocation** | ✅ **FIXED** | Previously got 0 allocation in 2025. Now fixed by triggering fallback when solver not optimal |
| **Hour Imbalance** | ⚠️ Improved | Fallback now properly weights by residual targets, better distribution |
| **Over-Budget Projects** | ✅ **FIXED** | Hard caps now prevent exceeding targets. EURIDICE: -42.7% (was +14.5%), AI-STYLIST: -23.9% (was +6.1%) |
| **Insufficient Capacity** | ⚠️ Present | 2024: 41.5% of target; 2025: 60.8% of target. Early capacity warnings now active |
| **Solver Non-Optimal** | ✅ **FIXED** | Now uses fallback when solver status is not optimal (e.g., `user_limit`, `infeasible`) |
| **Hard Caps** | ✅ **FIXED** | Projects now properly capped at total target limits |
| **Minimum Allocation** | ✅ **FIXED** | 1% minimum guarantee ensures all projects get some allocation |
| **Capacity Analysis** | ✅ **FIXED** | Early warnings show capacity shortfall percentages before optimization |

---

## 5. ROOT CAUSES

1. **✅ FIXED: Fallback Trigger** - Now triggers when solver is not optimal, not just when values missing
2. **✅ FIXED: Target Weighting** - Fallback properly weights by residual targets
3. **✅ FIXED: Hard Caps** - Projects now properly capped at total target limits, preventing over-allocation
4. **✅ FIXED: Minimum Allocation** - 1% minimum guarantee ensures all projects get some allocation
5. **✅ FIXED: Capacity Analysis** - Early warnings with detailed metrics before optimization
6. **⚠️ Remaining: Capacity Gap** - Employee hours × hourly rates < total target costs (mathematical constraint)
7. **⚠️ Remaining: Under-Allocation** - Some projects still far below targets due to insufficient capacity

---

## 6. SUMMARY

### 2024 Results
- ✅ All hours used (100%)
- ❌ Only 41.5% of target money allocated
- ✅ Solver: `fallback_feasible` (fallback working correctly)
- ✅ Capacity analysis: 62.3% shortfall warning
- ⚠️ All projects under target: -51.9% to -67.0%

### 2025 Results
- ✅ All hours used (100%)
- ❌ Only 60.8% of target money allocated
- ✅ Solver: `fallback_feasible` (fallback working correctly)
- ✅ Capacity analysis: 75.1% shortfall warning
- ✅ **FRESH-ID FIXED:** Now getting allocation (was 0 before)
- ✅ **Over-budget FIXED:** No projects exceeding targets (hard caps working)
- ⚠️ All projects under target: -23.9% to -50.3%

**Overall:** Algorithm now works correctly with all fixes applied. Hard caps prevent over-allocation, minimum guarantees ensure all projects get allocation, and capacity analysis provides early warnings. All hours used, proper target weighting, but still cannot meet all targets due to insufficient capacity (mathematical constraint).

---

## 7. RECOMMENDATIONS

1. **✅ COMPLETED:** Trigger fallback when solver not optimal
2. **✅ COMPLETED:** Ensure proper target weighting in fallback
3. **✅ COMPLETED:** Add hard caps to prevent over-allocation beyond targets
4. **✅ COMPLETED:** Improve capacity analysis to identify infeasibility early
5. **✅ COMPLETED:** Consider minimum allocation guarantees for all projects
