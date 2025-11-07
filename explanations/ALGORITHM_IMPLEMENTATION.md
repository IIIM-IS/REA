# Research Expenditure Allocation (REA) Algorithm - In-Depth Explanation

## Table of Contents
1. [Overview](#overview)
2. [Input Data Structure](#input-data-structure)
3. [Data Preparation Phase](#data-preparation-phase)
4. [Optimization Variables](#optimization-variables)
5. [Constraints](#constraints)
6. [Objective Function](#objective-function)
7. [Solver Selection and Execution](#solver-selection-and-execution)
8. [Post-Processing and Rounding](#post-processing-and-rounding)
9. [Output Format](#output-format)
10. [Mathematical Formulation](#mathematical-formulation)

---

## Overview

The REA algorithm is a **convex optimization problem** that allocates employee work hours (both Research & Development and Non-R&D) across multiple projects while respecting various business constraints and minimizing deviations from target project costs.

### Core Problem
Given:
- A set of employees with available hours per day (R&D and Non-R&D)
- A set of projects with target costs and constraints
- Employee salary levels (varying by day)
- Project topic whitelists and other preferences

**Find:** An optimal allocation of hours that:
1. Uses all available employee hours (no waste)
2. Respects project topic restrictions
3. Minimizes deviation from target project costs
4. Satisfies matching fund requirements
5. Maintains smoothness across days
6. Respects R&D topic distribution preferences

### Optimization Framework
The algorithm uses **CVXPY**, a Python-embedded modeling language for convex optimization. The problem is solved using interior-point methods (ECOS, SCS) or first-order methods (CLARABEL).

---

## Input Data Structure

### Employee Objects (`EmployeeModel`)
Each employee contains:
- `employee_name`: String identifier
- `research_hours`: Dictionary mapping date strings (`"MM-DD-YYYY"`) to R&D hours (float)
- `nonRnD_hours`: Dictionary mapping date strings to Non-R&D hours (float)
- `salary_levels`: Dictionary mapping date strings to salary info:
  ```python
  {
      "MM-DD-YYYY": {
          "level": "L1",  # Salary bracket label
          "amount": 50000.0  # Monthly salary in ISK
      }
  }
  ```

### Project Objects (`ProjectModel`)
Each project contains:
- `name`: String identifier
- `grant_contractual`: Target cost in ISK (float)
- `allowed_topics`: List of research topics allowed for this project
- `nonrnd_percentage`: Desired percentage of Non-R&D hours (0-100)
- `rnd_topic_ratios`: Dictionary mapping topic names to desired ratios (sums to 1.0)
- `matching_fund_value`: Additional funding requirement (float)
- `matching_fund_type`: Either `"percentage"` or `"absolute"`

### Date Range
- `start_date`: String in `"MM-DD-YYYY"` format
- `end_date`: String in `"MM-DD-YYYY"` format (inclusive)

### Research Topics
- `all_topics`: List of all possible research topic names
- A special topic `"Bridge"` is automatically added and available to all projects

---

## Data Preparation Phase

### 1. Date List Generation
The algorithm generates a list of all dates from `start_date` to `end_date` (inclusive):
```python
date_list = ["01-01-2024", "01-02-2024", ..., "12-31-2024"]
num_days = len(date_list)
```

### 2. Employee Partitioning: Locked vs. Free
Some employees are **pre-assigned** to specific projects (hard-coded in `locked_allocations`):
```python
locked_allocations = {"Bridget Burger": "EURIDICE"}
```

- **Locked employees**: Pre-assigned to a project. Their hours are allocated directly without optimization.
- **Free employees**: Available for optimization across all projects.

The algorithm:
1. Separates employees into `locked_employee_list` and `free_employee_list`
2. Pre-computes locked allocations (all hours go to the assigned project, using "Bridge" topic for R&D)
3. Only optimizes allocations for free employees

### 3. Matrix Construction

#### Salary Matrix (`salary_matrix`)
Shape: `(num_free_employees, num_days)`

For each free employee `i` and day `j`:
```python
base_salary = employee.salary_levels[date_list[j]]["amount"]
hourly_rate = (base_salary / 160.0) * 1.25  # 160 hours/month, 25% overhead
salary_matrix[i, j] = hourly_rate
```

**Formula**: Monthly salary ÷ 160 hours × 1.25 overhead factor = hourly rate

#### Research Hours Array (`research_hours_array`)
Shape: `(num_free_employees, num_days)`

```python
research_hours_array[i, j] = employee.research_hours.get(date_list[j], 0.0)
```

#### Non-R&D Hours Array (`nonrnd_hours_array`)
Shape: `(num_free_employees, num_days)`

```python
nonrnd_hours_array[i, j] = employee.nonRnD_hours.get(date_list[j], 0.0)
```

### 4. Topic Index Mapping
Creates a mapping from topic names to indices:
```python
topic_to_idx = {"AI": 0, "Robotics": 1, "Bridge": 2, ...}
```

---

## Optimization Variables

The algorithm defines two CVXPY variables:

### 1. R&D Hours Variable (`X`)
**Shape**: `(num_free_employees, num_days, num_projects, num_topics)`
**Type**: Non-negative continuous (`nonneg=True`)

`X[i, j, p, t]` = R&D hours allocated to:
- Employee `i` (free employee index)
- Day `j` (date index)
- Project `p` (project index)
- Topic `t` (topic index)

### 2. Non-R&D Hours Variable (`Y`)
**Shape**: `(num_free_employees, num_days, num_projects)`
**Type**: Non-negative continuous (`nonneg=True`)

`Y[i, j, p]` = Non-R&D hours allocated to:
- Employee `i` (free employee index)
- Day `j` (date index)
- Project `p` (project index)

**Note**: Non-R&D hours are not topic-specific (unlike R&D hours).

---

## Constraints

### 1. Hard Constraints (Must be satisfied exactly)

#### (a) R&D Hours Balance
For each free employee `i` and day `j`, the sum of all R&D hours allocated across all projects and topics must equal the employee's available R&D hours:

```python
∑(over p, t) X[i, j, p, t] = research_hours_array[i, j]
```

**CVXPY Expression**:
```python
cp.sum(cp.sum(X, axis=3), axis=2) == research_hours_array
```

This ensures **no R&D hours are wasted or over-allocated**.

#### (b) Non-R&D Hours Balance
For each free employee `i` and day `j`, the sum of all Non-R&D hours allocated across all projects must equal the employee's available Non-R&D hours:

```python
∑(over p) Y[i, j, p] = nonrnd_hours_array[i, j]
```

**CVXPY Expression**:
```python
cp.sum(Y, axis=2) == nonrnd_hours_array
```

This ensures **no Non-R&D hours are wasted or over-allocated**.

### 2. Soft Constraints (Penalized but not strictly enforced)

#### (c) Topic Whitelist (Soft)
Each project has an `allowed_topics` list. Hours allocated to **disallowed topics** are penalized heavily, but not forbidden.

**Implementation**:
- For each project `p`, identify disallowed topic indices
- Create a slack variable `slack_topics[p]` (non-negative)
- Constraint: `∑(disallowed topics) X[:, :, p, disallowed_indices] ≤ slack_topics[p]`
- Penalty: `BIG_SLACK_PENALTY * slack_topics[p] / avg_target_cost`

**Why soft?** If the problem is infeasible with hard constraints (e.g., insufficient hours in allowed topics), the solver can still find a solution by using disallowed topics, but at a high penalty cost.

#### (d) Matching Fund Requirement (Soft)
If a project has a matching fund requirement, the total cost must meet:
```
total_cost ≥ grant_contractual + matching_fund_amount
```

**Matching Fund Calculation**:
- If `matching_fund_type == "percentage"`:
  ```python
  matching_amount = matching_fund_value / 100.0 * grant_contractual
  ```
- If `matching_fund_type == "absolute"`:
  ```python
  matching_amount = matching_fund_value
  ```

**Implementation**:
- Create slack variable `slack_under_spend[p]` (non-negative)
- Constraint: `project_cost[p] + slack_under_spend[p] ≥ required_total`
- Penalty: `BIG_SLACK_PENALTY * slack_under_spend[p] / avg_target_cost`

**Why soft?** If total available employee cost capacity is insufficient, the solver can still proceed but will be heavily penalized for under-spending.

---

## Objective Function

The objective is a **composite minimization** of multiple penalty terms:

```
minimize: β·(cost_penalties) + γ·(nonrnd_frac_penalty) + λ_smooth·(smooth_penalty) + λ_topic·(topic_penalty) + reg_expr
```

### 1. Cost Deviation Penalties

#### (a) Huber Loss for Target Cost Deviation
For each project `p`:
```python
huber(project_cost[p] - target_cost[p], M=avg_target_cost*0.1) / avg_target_cost
```

**Huber Loss** is a robust loss function that:
- Behaves like squared loss for small deviations (smooth, differentiable)
- Behaves like absolute loss for large deviations (less sensitive to outliers)

**Formula**:
```
huber(x, M) = {
    x²/2          if |x| ≤ M
    M·|x| - M²/2  if |x| > M
}
```

**Why Huber?** It encourages hitting target costs exactly, but doesn't explode for large deviations (more robust than pure squared loss).

#### (b) Matching Fund Slack Penalty
```python
BIG_SLACK_PENALTY * slack_under_spend[p] / avg_target_cost
```
Where `BIG_SLACK_PENALTY = 1e4` (very large to strongly discourage violations).

#### (c) Topic Whitelist Violation Penalty
```python
BIG_SLACK_PENALTY * slack_topics[p] / avg_target_cost
```

**Scaling**: All cost penalties are divided by `avg_target_cost` to normalize across projects of different sizes.

### 2. Non-R&D Fraction Penalty

For each project `p` with a desired Non-R&D percentage `desired_frac`:
```python
linear_target_deviation = (1.0 - desired_frac) * nonrnd_total - desired_frac * rnd_total
nonrnd_frac_penalty += square(linear_target_deviation)
```

**Intuition**: If `desired_frac = 0.3` (30% Non-R&D), we want:
```
nonrnd_total / (rnd_total + nonrnd_total) ≈ 0.3
```

Rearranging:
```
nonrnd_total ≈ 0.3 * (rnd_total + nonrnd_total)
nonrnd_total ≈ 0.3 * rnd_total + 0.3 * nonrnd_total
0.7 * nonrnd_total ≈ 0.3 * rnd_total
```

The penalty minimizes `(0.7 * nonrnd_total - 0.3 * rnd_total)²`.

**Weight**: `γ = 1e-5` (relatively small, secondary priority)

### 3. Smoothness Penalty

Encourages allocations to change smoothly across consecutive days:
```python
smooth_penalty = sum_squares(X[:, 1:, :, :] - X[:, :-1, :, :])
```

This penalizes large day-to-day changes in R&D hour allocations.

**Weight**: `λ_smooth = 1e-3`

**Why?** Prevents erratic allocations that jump dramatically between days (e.g., 8 hours on Monday, 0 on Tuesday, 8 on Wednesday).

### 4. Topic Distribution Penalty

For projects with `rnd_topic_ratios` defined, penalizes deviation from desired topic distribution:
```python
target_alloc = total_rd_alloc_per_emp_day @ target_vector.reshape((1, -1))
topic_penalty += sum_squares(allocated_rd_topics - target_alloc)
```

**Intuition**: If a project wants 60% "AI" and 40% "Robotics", the penalty encourages allocations to match these ratios.

**Weight**: `λ_topic = 1e-2`

### 5. Regularization Term

Prevents extreme values and improves numerical stability:
```python
reg_expr = reg_lambda * (sum_squares(X) + sum_squares(Y))
```

**Weight**: `reg_lambda = 1e-6` (very small, primarily for numerical stability)

### Final Objective Weights Summary
```python
β = 1e-2          # Cost deviation (primary)
γ = 1e-5          # Non-R&D fraction (secondary)
λ_smooth = 1e-3   # Smoothness
λ_topic = 1e-2    # Topic distribution
reg_lambda = 1e-6 # Regularization
```

---

## Solver Selection and Execution

### Solver Chain
The algorithm tries multiple solvers in order until one succeeds:

1. **ECOS** (Interior-Point Method)
   - Reformulates as homogeneous self-dual cone program
   - Uses primal-dual interior-point method
   - High accuracy, typically 20-50 iterations
   - Options: `max_iters=20000, abstol=1e-7, reltol=1e-7, feastol=1e-7`

2. **SCS** (Operator Splitting / ADMM)
   - First-order method (Alternating Direction Method of Multipliers)
   - Lower memory usage, can handle very large problems
   - Typically requires hundreds to thousands of iterations
   - Options: `max_iters=20000, eps=5e-4`

3. **CLARABEL** (First-Order Method)
   - Modern first-order solver
   - Options: `max_iter=10000`

### Success Criteria
A solver is considered successful if:
- Status is `OPTIMAL` or `OPTIMAL_INACCURATE`, OR
- The objective value is finite (even if status is not optimal)

### Solver Output
The algorithm captures:
- Objective value
- Solver status
- Variable values (`X.value`, `Y.value`)
- Constraint violations (for diagnostics)

---

## Post-Processing and Rounding

### 1. Continuous Solution Extraction
After solving, the algorithm extracts:
```python
X_val = np.nan_to_num(X.value)  # Replace NaN with 0
Y_val = np.nan_to_num(Y.value)
X_val = np.maximum(X_val, 0)    # Ensure non-negative
Y_val = np.maximum(Y_val, 0)
```

### 2. Rounding to Two Decimals

The algorithm uses a **largest-remainder method** to round allocations to 2 decimal places while preserving the exact sum of available hours.

#### Function: `round_vector_preserve_sum_two_decimals_two_decimals(v, target_total)`

**Algorithm**:
1. **Scale to integers**: Multiply by 100 (since we want 2 decimals)
   ```python
   v_scaled = v * 100
   target_scaled = int(round(target_total * 100))
   ```

2. **Floor all values**:
   ```python
   floor_vals = floor(v_scaled)
   int_vals = floor_vals.astype(int)
   ```

3. **Calculate remainders**:
   ```python
   remainder = v_scaled - floor_vals
   ```

4. **Calculate deficit**:
   ```python
   current_total = sum(int_vals)
   remainder_needed = target_scaled - current_total
   ```

5. **Distribute deficit**:
   - If `remainder_needed > 0`: Increment the values with the **largest remainders**
   - If `remainder_needed < 0`: Decrement the values with the **smallest remainders** (but only if value > 0)

6. **Convert back**:
   ```python
   result = int_vals / 100.0
   result = round(result, 2)  # Final cleanup
   ```

**Why this method?** Ensures the rounded allocations sum exactly to the target (no hour loss or creation).

### 3. Allocation Dictionary Construction

For each free employee `i` and day `j`:

1. **Extract continuous allocations**:
   ```python
   nonrnd_vector = Y_val[i, j, :]  # Shape: (num_projects,)
   rd_vector_flat = X_val[i, j, :, :].flatten()  # Shape: (num_projects * num_topics,)
   ```

2. **Round while preserving sums**:
   ```python
   nonrnd_rounded = round_vector_preserve_sum_two_decimals_two_decimals(
       nonrnd_vector, target_nonrnd_today
   )
   rd_rounded_flat = round_vector_preserve_sum_two_decimals_two_decimals(
       rd_vector_flat, target_rd_today
   )
   rd_rounded_matrix = rd_rounded_flat.reshape((num_projects, num_topics))
   ```

3. **Build nested dictionary structure**:
   ```python
   allocations[employee_name][date_string][project_name] = {
       "topics": {
           "AI": 4.5,
           "Robotics": 2.3
       },
       "nonRnD": 1.0
   }
   ```

4. **Merge locked allocations**: Add pre-computed locked employee allocations to the dictionary.

### 4. Cost Calculation

#### Solver Costs (Continuous)
For each project, compute cost from solver's continuous values:
```python
cost_expr_total = cost_expr_free + locked_cost_const
project_cost_solver[p] = cost_expr_total.value
```

#### Rounded Costs (Final Output)
For each project, compute cost from rounded allocations:
```python
for employee_name, daily_allocs in allocations.items():
    for date, project_data in daily_allocs.items():
        if project_name in project_data:
            hourly_rate = (base_salary / 160.0) * 1.25
            r_hours = sum(project_data[project_name]["topics"].values())
            nr_hours = project_data[project_name]["nonRnD"]
            project_cost_rounded += (r_hours + nr_hours) * hourly_rate
```

**Note**: The final output reports **solver costs** (from continuous solution), but the allocations dictionary uses **rounded values**.

---

## Output Format

The algorithm returns a dictionary:

```python
{
    "solver_status": "optimal" | "optimal_inaccurate" | "solver_error" | ...,
    "final_objective": float,  # Objective function value
    "final_costs": {           # Project costs (from solver, continuous)
        "Project1": 50000.0,
        "Project2": 75000.0,
        ...
    },
    "allocations": {          # Rounded allocations (2 decimals)
        "Employee1": {
            "01-01-2024": {
                "Project1": {
                    "topics": {"AI": 4.5, "Robotics": 2.3},
                    "nonRnD": 1.0
                },
                "Project2": {
                    "topics": {"Bridge": 0.2},
                    "nonRnD": 0.0
                }
            },
            ...
        },
        ...
    },
    "diagnostics": "..."      # Multi-line diagnostic string
}
```

### Diagnostics Include:
- Hours and salary breakdown (free, locked, all employees)
- Project targets and locked contributions
- Per-project, per-salary-bracket employee lists
- Cost capacity vs. project requirements
- Overall allocation summaries (rounded)
- Project cost details and topic allocations
- Match-fund slack values

---

## Mathematical Formulation

### Variables
- `X[i,j,p,t] ≥ 0`: R&D hours (employee `i`, day `j`, project `p`, topic `t`)
- `Y[i,j,p] ≥ 0`: Non-R&D hours (employee `i`, day `j`, project `p`)
- `slack_topics[p] ≥ 0`: Slack for topic whitelist violations
- `slack_under_spend[p] ≥ 0`: Slack for matching fund under-spending

### Constraints

**Hard Constraints**:
```
∀ i, j:  ∑(p,t) X[i,j,p,t] = research_hours_array[i,j]
∀ i, j:  ∑(p) Y[i,j,p] = nonrnd_hours_array[i,j]
```

**Soft Constraints** (with slacks):
```
∀ p:  ∑(i,j,t∈disallowed) X[i,j,p,t] ≤ slack_topics[p]
∀ p:  cost[p] + slack_under_spend[p] ≥ grant[p] + matching_fund[p]
```

### Cost Expression
For each project `p`:
```
cost[p] = locked_cost[p] + ∑(i,j) salary_matrix[i,j] * (
    ∑(t) X[i,j,p,t] + Y[i,j,p]
)
```

### Objective Function
```
minimize:
    β * [
        ∑(p) huber(cost[p] - target[p], M) / avg_target
        + BIG_PENALTY * slack_topics[p] / avg_target
        + BIG_PENALTY * slack_under_spend[p] / avg_target
    ]
    + γ * ∑(p) square((1-α[p])*nonrnd[p] - α[p]*rnd[p])
    + λ_smooth * ∑(i,j,p,t) square(X[i,j+1,p,t] - X[i,j,p,t])
    + λ_topic * ∑(p) sum_squares(allocated_topics[p] - target_ratios[p])
    + reg_lambda * [sum_squares(X) + sum_squares(Y)]
```

Where:
- `β = 1e-2`, `γ = 1e-5`, `λ_smooth = 1e-3`, `λ_topic = 1e-2`, `reg_lambda = 1e-6`
- `α[p] = nonrnd_percentage[p] / 100.0`
- `M = avg_target_cost * 0.1`

---

## Key Design Decisions

### 1. Why Separate R&D and Non-R&D?
- R&D hours are topic-specific (must be allocated to research topics)
- Non-R&D hours are generic (administrative, meetings, etc.)
- Different projects may have different R&D/Non-R&D requirements

### 2. Why Soft Constraints for Topic Whitelist?
- Hard constraints could make the problem infeasible
- Soft constraints allow the solver to find a solution even if hours are insufficient in allowed topics
- Heavy penalty discourages violations unless absolutely necessary

### 3. Why Huber Loss for Cost Deviation?
- More robust than squared loss (less sensitive to outliers)
- Still smooth and differentiable (better for optimization)
- Encourages hitting targets exactly for small deviations

### 4. Why Rounding with Sum Preservation?
- Continuous solutions may have many small fractional values
- Business requirements need 2-decimal precision
- Must preserve exact hour totals (no loss or creation of hours)

### 5. Why Multiple Solvers?
- Different solvers have different strengths
- ECOS: High accuracy, medium-sized problems
- SCS: Large problems, lower memory
- CLARABEL: Modern alternative
- Fallback chain ensures robustness

---

## Performance Characteristics

### Time Complexity
- **Setup**: O(employees × days × projects × topics) for matrix construction
- **Solver**: Depends on solver and problem size
  - ECOS: Typically O(iterations × variables²) per iteration
  - SCS: Typically O(iterations × variables) per iteration
- **Post-processing**: O(employees × days × projects × topics) for rounding

### Space Complexity
- **Variables**: O(employees × days × projects × topics) for `X`, O(employees × days × projects) for `Y`
- **Matrices**: O(employees × days) for salary and hours arrays
- **Total**: Dominated by variable storage

### Typical Problem Sizes
- Employees: 10-50
- Days: 30-365
- Projects: 5-20
- Topics: 5-15
- **Total variables**: ~100K - 10M (depending on size)

---

## Limitations and Future Improvements

### Current Limitations
1. **Fixed penalty weights**: Manually tuned, may not be optimal for all scenarios
2. **No integer constraints**: Allocations are continuous (rounded post-solve)
3. **No employee preferences**: Cannot express "Employee X prefers Project Y"
4. **No capacity constraints**: Projects don't have maximum hour limits
5. **Single objective**: Cannot trade off multiple objectives explicitly

### Potential Improvements
1. **Multi-objective optimization**: Pareto frontier exploration
2. **Integer programming**: Discrete hour allocations (e.g., 0.5-hour increments)
3. **Employee preferences**: Soft constraints for preferred projects
4. **Dynamic weights**: Adaptive penalty weights based on problem characteristics
5. **Uncertainty handling**: Robust optimization with uncertain hours/costs

---

## Conclusion

The REA algorithm is a sophisticated convex optimization system that balances multiple competing objectives (cost targets, topic restrictions, smoothness, etc.) while respecting hard constraints (hour balance). Its design prioritizes robustness (soft constraints, multiple solvers) and practical usability (rounding, diagnostics) over pure mathematical elegance.

The algorithm successfully handles real-world complexities like:
- Varying employee salaries over time
- Project-specific topic restrictions
- Matching fund requirements
- Smooth allocation patterns
- Pre-assigned employees

By using modern convex optimization techniques, it provides efficient, reliable solutions to a complex resource allocation problem.

