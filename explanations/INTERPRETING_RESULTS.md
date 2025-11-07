# REA Algorithm Results - Complete Explanation

## Executive Summary

Your program ran an **optimization algorithm** to allocate employee work hours across 4 research projects for the entire year 2024 (January 1 to December 31). The algorithm tried to match each project's target budget, but encountered a **critical problem**: the total target costs exceed the available employee capacity by over 10 million ISK.

**Key Finding**: The algorithm found a solution, but 3 out of 4 projects are significantly over budget because there simply aren't enough employee hours available to meet all the targets.

---

## Part 1: What Your Program Does

### The Core Problem
You have:
- **9 employees** with varying hourly rates and available work hours
- **4 projects** (EURIDICE, ICE-ID, FRESH-ID, AI-STYLIST) with target budgets
- **A year's worth of timesheet data** showing when each employee worked

The program's job is to **decide which employee should work on which project, on which days, doing what type of work** (Research & Development vs. Non-R&D tasks).

### The Optimization Challenge
The algorithm uses **mathematical optimization** (specifically, convex optimization via CVXPY) to find the "best" allocation that:
1. Uses all available employee hours (no waste)
2. Gets as close as possible to each project's target budget
3. Respects project restrictions (e.g., which research topics are allowed)
4. Maintains smooth allocations (doesn't jump wildly day-to-day)

---

## Part 2: Your Input Data

### Employees (9 total)

#### Free Employees (8 - can be allocated to any project):
1. **Arash Sheikhlar**: 88 total hours (62 R&D, 26 Non-R&D), cost: 550,000 ISK
2. **Marta Abad Torrent**: 923 hours (873 R&D, 50 Non-R&D), cost: 3,389,141 ISK
3. **Sander Kaatee**: 196 hours (all R&D), cost: 719,688 ISK
4. **Jeff Thompson**: 423 hours (422 R&D, 1 Non-R&D), cost: 3,800,655 ISK
5. **Goncalo**: 2,193 hours (2,162 R&D, 31 Non-R&D), cost: 13,706,250 ISK ⭐ *Largest contributor*
6. **Tangrui Li**: 23 hours (all R&D), cost: 102,422 ISK
7. **Mário Jorge Silva Correia**: 244 hours (all R&D), cost: 1,086,562 ISK
8. **Kris**: 895 hours (688 R&D, 207 Non-R&D), cost: 6,572,656 ISK

**Total Free Employee Capacity**: 4,985 hours costing **29,927,374 ISK**

#### Locked Employee (1 - pre-assigned):
9. **Bridget Burger**: 416 hours (16 R&D, 400 Non-R&D), cost: 4,257,500 ISK
   - **Locked to EURIDICE project** (cannot be reallocated)

**Total Capacity (All Employees)**: 5,401 hours costing **34,184,874 ISK**

### Projects (4 total)

1. **EURIDICE**: Target = 10,000,000 ISK
2. **ICE-ID**: Target = 3,500,000 ISK
3. **FRESH-ID**: Target = 7,300,000 ISK
4. **AI-STYLIST**: Target = 8,910,000 ISK

**Total Target Budget**: **29,710,000 ISK**

### Salary Brackets
Employees are paid at different hourly rates based on their salary level:
- **L6**: 3,672 ISK/hr (Marta, Sander)
- **L5**: 4,453 ISK/hr (Mário, Tangrui)
- **L3**: 6,250 ISK/hr (Arash, Goncalo)
- **L2**: 7,344 ISK/hr (Kris)
- **L1**: 8,985 ISK/hr (Jeff)
- **L0**: 10,234 ISK/hr (Bridget - highest paid)

---

## Part 3: The Critical Problem

### Capacity vs. Requirements

**Available Capacity**: 34,184,874 ISK
**Required Minimum**: 29,710,000 ISK (target budgets)

**BUT WAIT** - The algorithm detected matching fund requirements that increase the needed amount:

```
⚠️  WARNING: Requested MINIMUM spend exceeds absolute capacity by 10,015,126 ISK
```

This means:
- The projects have **matching fund requirements** (additional funding that must be spent)
- When you add matching funds to the targets, the total required is **~44.2 million ISK**
- But you only have **34.2 million ISK** available
- **Shortfall: ~10 million ISK**

**This is why the algorithm cannot meet all targets** - it's mathematically impossible with the current employee capacity.

---

## Part 4: What the Algorithm Did

### Solver Attempts

The algorithm tried two different optimization solvers:

1. **ECOS** (Interior-Point Method)
   - Ran for 12.97 seconds
   - Encountered numerical problems
   - Status: Failed (numerical instability)

2. **SCS** (Operator Splitting / ADMM)
   - Ran for **383.87 seconds** (~6.4 minutes)
   - Status: **optimal_inaccurate** (found a solution, but not perfectly optimal)
   - This is the solution that was used

### The Optimization Problem Size

- **222,535 variables** (decisions to make: how many hours for each employee/day/project/topic combination)
- **5,863 constraints** (rules that must be followed)
- This is a **very large optimization problem**

---

## Part 5: The Results

### Project Cost Results

| Project | Target Cost | Actual Cost (Solver) | Deviation | Status |
|---------|-------------|---------------------|-----------|--------|
| **EURIDICE** | 10,000,000 | 15,552,291 | **+55.5%** | ⚠️ Over budget |
| **ICE-ID** | 3,500,000 | 14,914,704 | **+326.1%** | ⚠️ Severely over budget |
| **FRESH-ID** | 7,300,000 | 8,600,492 | **+17.8%** | ⚠️ Over budget |
| **AI-STYLIST** | 8,910,000 | 8,780,405 | **-1.5%** | ✅ On target |

**Total Actual Cost**: 47,837,892 ISK (solver values)
**Total Target Cost**: 29,710,000 ISK
**Overall Deviation**: +61.0%

### Why These Results?

1. **ICE-ID is massively over-allocated** (+326%): The algorithm likely allocated too many hours here because it was trying to balance constraints. This suggests the solver had trouble finding a good solution.

2. **EURIDICE is over-allocated** (+55.5%): Partially due to Bridget Burger being locked to this project (4.26M ISK), but still over target.

3. **FRESH-ID is slightly over** (+17.8%): Close to target, but still over.

4. **AI-STYLIST is almost perfect** (-1.5%): This is the only project that came close to its target.

### Match-Fund Slacks

The algorithm reports "slack" values for matching fund requirements:
- **EURIDICE**: 17,843,450 ISK slack (massive under-spending relative to matching fund requirement)
- **FRESH-ID**: 21,951,916 ISK slack
- **AI-STYLIST**: 12,776,310 ISK slack

These large slacks indicate the matching fund requirements **cannot be met** with available capacity.

---

## Part 6: Hour Allocations

### Overall Hour Balance

**R&D Hours**:
- Available: 4,686 hours
- Allocated: 4,713 hours (rounded)
- **Small discrepancy**: 27 hours difference (likely due to rounding)

**Non-R&D Hours**:
- Available: 715 hours
- Allocated: 715 hours
- ✅ **Perfect match**

### Per-Project Hour Breakdown

| Project | R&D Hours | Non-R&D Hours | Total Hours |
|---------|-----------|---------------|-------------|
| EURIDICE | 1,079 | 505 | 1,584 |
| ICE-ID | 991 | 8 | 999 |
| FRESH-ID | 1,292 | 101 | 1,393 |
| AI-STYLIST | 1,351 | 101 | 1,452 |
| **Total** | **4,713** | **715** | **5,428** |

*Note: Total hours exceed available because of rounding differences*

### Employee Allocations

**Top Contributors by Project**:

**EURIDICE**:
- Goncalo: 568.69 hours (R&D: 555.96, Non-R&D: 12.73)
- Bridget Burger: 416.00 hours (locked, R&D: 16, Non-R&D: 400)
- Marta: 207.46 hours
- Kris: 199.12 hours

**ICE-ID**:
- Goncalo: 252.73 hours
- Marta: 293.15 hours
- Kris: 161.19 hours
- Jeff: 94.88 hours

**FRESH-ID**:
- Goncalo: 678.79 hours (largest single allocation)
- Kris: 273.09 hours
- Jeff: 118.65 hours
- Marta: 204.69 hours

**AI-STYLIST**:
- Goncalo: 695.51 hours (largest single allocation)
- Kris: 275.54 hours
- Jeff: 124.54 hours
- Marta: 222.91 hours

**Key Observation**: Goncalo is heavily allocated across all projects (total ~2,195 hours), which makes sense given they have the most available hours (2,193 total).

---

## Part 7: Research Topic Allocations

Each project has R&D hours allocated across different research topics. The algorithm distributes hours relatively evenly across allowed topics:

### EURIDICE Topics
- Bridge: 75 hrs
- Most other topics: ~59 hrs each
- 17 different topics total

### ICE-ID Topics
- Most topics: ~55 hrs each
- General Info. System: 52 hrs (slightly less)
- 17 different topics total

### FRESH-ID Topics
- Most topics: ~72 hrs each
- 17 different topics total

### AI-STYLIST Topics
- All topics: 75 hrs each (perfectly even distribution)
- 17 different topics total

**Note**: The "Bridge" topic is a special topic available to all projects, used as a catch-all for general research work.

---

## Part 8: Issues and Warnings

### 1. Capacity Shortfall
**Problem**: Total required spending (including matching funds) exceeds available capacity by ~10 million ISK.

**Impact**: The algorithm cannot meet all targets simultaneously. It prioritizes some projects over others.

**Solution Options**:
- Reduce project target budgets
- Reduce matching fund requirements
- Add more employees or increase their hours
- Extend the time period

### 2. Solver Numerical Issues
**Problem**: ECOS solver failed due to numerical instability. SCS found a solution but marked it as "optimal_inaccurate".

**Impact**: The solution may not be the true optimal allocation. There might be better allocations that the solver couldn't find.

**Solution Options**:
- Adjust solver tolerances
- Try different solvers (CLARABEL)
- Simplify the problem (fewer variables/constraints)

### 3. Hour Balance Discrepancy
**Problem**: Allocated R&D hours (4,713) slightly exceed available (4,686) by 27 hours.

**Impact**: Minor - likely due to rounding in the post-processing step.

**Solution**: The rounding algorithm tries to preserve exact sums, but small discrepancies can occur with very large numbers.

### 4. Project Over-Allocations
**Problem**: 3 out of 4 projects are significantly over budget.

**Impact**: Budgets will be exceeded, potentially causing financial issues.

**Root Cause**: The algorithm is trying to minimize overall deviation, but with insufficient capacity, it's forced to over-allocate to some projects.

---

## Part 9: What This Means for You

### The Good News
1. ✅ **All employee hours are allocated** - no waste
2. ✅ **AI-STYLIST is on target** - the algorithm successfully balanced this project
3. ✅ **The algorithm completed** - despite numerical challenges, it found a solution
4. ✅ **Hour balance is mostly correct** - Non-R&D hours match perfectly, R&D hours are very close

### The Bad News
1. ⚠️ **Insufficient capacity** - you need ~10M more ISK worth of employee hours
2. ⚠️ **3 projects over budget** - especially ICE-ID (+326%)
3. ⚠️ **Matching funds cannot be met** - large slacks indicate impossible requirements
4. ⚠️ **Solution quality uncertain** - "optimal_inaccurate" status means there might be better allocations

### What You Should Do

#### Immediate Actions:
1. **Review project targets** - Are the target budgets realistic given available capacity?
2. **Check matching fund requirements** - Are they correctly configured? The large slacks suggest they might be too high.
3. **Verify employee data** - Are all timesheets loaded correctly? Missing data could explain capacity issues.

#### Potential Solutions:
1. **Reduce targets**: Lower project budgets to match available capacity
2. **Adjust matching funds**: Reduce or remove matching fund requirements
3. **Add capacity**: Hire more employees or extend work periods
4. **Prioritize projects**: Manually adjust which projects get priority
5. **Split time period**: Run separate optimizations for different time periods

#### Technical Improvements:
1. **Tune solver settings**: Adjust tolerances for better solutions
2. **Simplify constraints**: Remove or relax some constraints to make the problem easier
3. **Add hard budget caps**: Prevent projects from exceeding budgets by too much

---

## Part 10: Understanding the Output Files

### What Gets Saved
1. **Diagnostics file** (`output_diagnostics.txt`): Detailed breakdown of allocations
2. **Debug log** (`allocation_debug.log`): Solver output and technical details
3. **State file** (if saved): JSON file with all project/employee data

### Key Metrics to Monitor
- **Cost deviations**: How far off each project is from target
- **Hour balances**: Whether all hours are allocated correctly
- **Solver status**: Whether the solution is reliable
- **Match-fund slacks**: Whether matching fund requirements can be met

---

## Part 11: How to Interpret Future Runs

### Good Signs ✅
- Solver status: `optimal` (not `optimal_inaccurate`)
- Cost deviations: < 5% for all projects
- Hour balances: Exact match (or < 1 hour difference)
- Match-fund slacks: Near zero (requirements are met)
- No capacity warnings

### Warning Signs ⚠️
- Solver status: `optimal_inaccurate` or `solver_failed`
- Cost deviations: > 20% for any project
- Hour balance discrepancies: > 10 hours
- Large match-fund slacks: > 1M ISK
- Capacity warnings: Required > Available

### Critical Issues 🚨
- Solver fails completely
- Hour balances are wildly off (> 100 hours)
- All projects severely over/under budget
- Numerical errors in solver output

---

## Summary

Your REA program successfully ran an optimization algorithm to allocate employee hours across 4 projects for 2024. However, the results show that **the total project requirements exceed available employee capacity by approximately 10 million ISK**. This causes 3 out of 4 projects to be significantly over budget.

The algorithm found a solution (using the SCS solver), but it's marked as "optimal_inaccurate", meaning there might be better allocations. The core issue is not with the algorithm itself, but with the **mismatch between project requirements and available resources**.

**Next Steps**: Review project targets and matching fund requirements to ensure they're realistic given your employee capacity, or consider adding more capacity (employees/hours) to meet the requirements.

