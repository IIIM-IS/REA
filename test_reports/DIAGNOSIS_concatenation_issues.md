# Diagnosis: Concatenation Results vs Actual Project Budgets

## Summary of Issues

The algorithm is using `grant_contractual` as the target, but it should be using the **TOTAL project cost** which includes:
- Grant (contractual)
- Matching funds
- Overhead

## Actual Project Budgets (Total Cost)

| Project | Grant | Matching Funds | Overhead | **Total Target** |
|---------|-------|----------------|----------|------------------|
| **ICE-ID** | 3,000,000 | 0 | 0 | **3,000,000** |
| **FRESH-ID** | 16,988,250 | 5,662,750 | 0 | **22,651,000** |
| **AI-STYLIST** | 16,200,000 | 4,680,000 | 1,700,000 | **22,580,000** |
| **TW*** | 13,500,000 | 2,700,000 | 4,050,000 | **20,250,000** |
| **EURIDICE** | 21,192,905 | 21,192,905 | 0 | **42,385,811** |

## Current Algorithm Targets (from state files)

| Project | grant_contractual | matching_fund | overhead | **What Algorithm Uses** |
|---------|-------------------|---------------|----------|------------------------|
| **ICE-ID** | 3,500,000 | 0 | 0 | **3,500,000** ❌ (should be 3,000,000) |
| **FRESH-ID** | 7,300,000 | 5,662,750 | 0 | **7,300,000** ❌ (should be 22,651,000) |
| **AI-STYLIST** | 8,910,000 | 4,680,000 | 0.07 | **8,910,000** ❌ (should be 22,580,000) |
| **TW*** | 0 | 0 | 0 | **0** ❌ (should be 20,250,000) |
| **EURIDICE** | 10,000,000 | 50% | 0 | **10,000,000** ❌ (should be 42,385,811) |

## 2024 Results Analysis

| Project | Actual Cost | Target Used | Actual Target | Status |
|---------|-------------|-------------|---------------|--------|
| **ICE-ID** | 4,152,149 | 3,500,000 | 3,000,000 | ❌ 38% over actual target |
| **FRESH-ID** | 10,261,113 | 7,300,000 | 22,651,000 | ❌ 55% under actual target |
| **AI-STYLIST** | 7,175,700 | 8,910,000 | 22,580,000 | ❌ 68% under actual target |
| **EURIDICE** | 12,595,912 | 10,000,000 | 42,385,811 | ❌ 70% under actual target |

## 2025 Concatenation Results Analysis

| Project | 2024 Cost | 2025 New | Total | Actual Target | Status |
|---------|-----------|----------|-------|---------------|--------|
| **ICE-ID** | 4,152,149 | 0 | 4,152,149 | 3,000,000 | ❌ 38% over (already exceeded in 2024) |
| **FRESH-ID** | 10,261,113 | 0 | 10,261,113 | 22,651,000 | ❌ 55% under (still far from target) |
| **AI-STYLIST** | 7,175,700 | 18,279,834 | 25,455,535 | 22,580,000 | ❌ 13% over (exceeded total) |
| **TW*** | 0 | 0 | 0 | 20,250,000 | ❌ 100% under (nothing allocated) |
| **EURIDICE** | 12,595,912 | 0 | 12,595,912 | 42,385,811 | ❌ 70% under (still far from target) |

## Root Causes

### 1. **Target Calculation Issue**
The algorithm uses `grant_contractual` as the target, but it should calculate:
```
Total Target = grant_contractual + matching_funds + overhead
```

Currently:
- **FRESH-ID**: Uses 7,300,000 (grant only) instead of 22,651,000 (grant + matching)
- **AI-STYLIST**: Uses 8,910,000 (grant only) instead of 22,580,000 (grant + matching + overhead)
- **TW***: Uses 0 instead of 20,250,000 (grant + matching + overhead)
- **EURIDICE**: Uses 10,000,000 (grant only) instead of 42,385,811 (grant + matching)

### 2. **Matching Funds Not Included in Target**
The algorithm treats matching funds as a soft constraint (penalty if violated), but they should be part of the hard target:
- EURIDICE: 50% matching = 5,000,000 additional → total should be 15,000,000 (but actual is 42,385,811)
- FRESH-ID: 5,662,750 matching not included in target
- AI-STYLIST: 4,680,000 matching not included in target

### 3. **Overhead Calculation Issue**
Overhead is stored as a percentage (0.07 = 7%) but should be calculated as:
```
Total Cost = Direct Cost × (1 + overhead_rate) + fixed_overhead
```

For AI-STYLIST:
- Overhead stored: 0.07 (7%)
- But actual overhead: 1,700,000 ISK (fixed amount, not percentage)
- This suggests overhead should be stored as a fixed amount, not a percentage

### 4. **State File Configuration Errors**
The state files have incorrect values:
- **ICE-ID**: `grant_contractual` is 3,500,000 but should be 3,000,000
- **FRESH-ID**: `grant_contractual` is 7,300,000 but should be 16,988,250
- **AI-STYLIST**: `grant_contractual` is 8,910,000 but should be 16,200,000
- **TW***: `grant_contractual` is 0 but should be 13,500,000
- **EURIDICE**: `grant_contractual` is 10,000,000 but should be 21,192,905

## Recommendations

1. **Fix Target Calculation**: The algorithm should calculate total target as:
   ```python
   total_target = grant_contractual + matching_funds + overhead
   ```

2. **Update State Files**: Correct the `grant_contractual` values in the state files to match actual grant amounts

3. **Handle Overhead Properly**: 
   - If overhead is a percentage: `total = direct_cost × (1 + overhead_rate)`
   - If overhead is a fixed amount: `total = direct_cost + overhead_amount`
   - Need to distinguish between percentage and fixed overhead

4. **Include Matching Funds in Target**: Matching funds should be part of the hard target, not just a soft constraint

5. **Fix EURIDICE Exchange Rate**: EURIDICE is in Euros, need to convert properly:
   - Grant: €141,191 = ISK 21,192,905 (at ~150 ISK/EUR)
   - Matching: €141,191 = ISK 21,192,905
   - Total: €282,382 = ISK 42,385,811

## Expected vs Actual

| Project | Expected Total | Actual Total | Difference |
|---------|----------------|--------------|------------|
| **ICE-ID** | 3,000,000 | 4,152,149 | +1,152,149 (38% over) |
| **FRESH-ID** | 22,651,000 | 10,261,113 | -12,389,887 (55% under) |
| **AI-STYLIST** | 22,580,000 | 25,455,535 | +2,875,535 (13% over) |
| **TW*** | 20,250,000 | 0 | -20,250,000 (100% under) |
| **EURIDICE** | 42,385,811 | 12,595,912 | -29,789,899 (70% under) |

**Total Expected**: 111,866,811 ISK
**Total Actual**: 52,464,708 ISK
**Difference**: -59,402,103 ISK (53% under)

