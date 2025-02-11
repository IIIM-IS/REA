# -----------------------------------------------------------------------------
# Authors: Arash Sheikhlar and Kristinn Thorisson
# Project: Research Expenditure Allocation (REA)
# -----------------------------------------------------------------------------
# Copyright (c) 2025, Arash Sheikhlar and Kristinn Thorisson. All rights reserved.
#
# This software is provided "as is", without warranty of any kind, express or
# implied, including but not limited to the warranties of merchantability,
# fitness for a particular purpose, and noninfringement. In no event shall
# the authors be liable for any claim, damages, or other liability, whether
# in an action of contract, tort, or otherwise, arising from, out of, or in
# connection with the software or the use or other dealings in the software.
#
# Unauthorized copying, distribution, or modification of this code, via any
# medium, is strictly prohibited unless prior written permission is obtained
# from the authors.
# -----------------------------------------------------------------------------
import cvxpy as cp
import numpy as np
from datetime import datetime, timedelta

def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    """
    Allocates each employee's daily research hours (plus some portion as nonR&D)
    to one or more projects/topics, without ever exceeding the timesheet hours
    and preventing "double-billing" of the same hour to multiple projects.

    We enforce:
      1) sum of hours across all projects/topics == timesheet hours for each (employee, day).
      2) NonR&D <= 25% of that day's research hours.
      3) Minimizing sum of squared (ProjectCost - ProjectTarget).

    Debug/Insight prints at the end:
      - Solver status, final objective
      - Per-project cost vs. target, difference
      - Per-day constraints check for each employee (including any mismatch)
      - Aggregate checks: total hours allocated, total hours from timesheets, etc.

    Parameters
    ----------
    employees : list of EmployeeModel
        Each employee has research_hours[date], meeting_hours[date], etc.
        Must also have 'salary_levels[date]' that includes {'amount': some_value}.
    projects : list of ProjectModel
        Each project has 'research_topics' plus a 'grant_contractual' for target cost.
    start_date : str (YYYY-MM-DD)
    end_date   : str (YYYY-MM-DD)
    all_topics : list of all recognized topics

    Returns
    -------
    dict with keys:
        solver_status
        final_objective
        final_costs       (dict of {project_name: cost_value})
        allocations       (nested dict with allocated hours per (employee, date, project))
    """

    # -------------------------------------------------------------------------
    # 1. Build the date range
    # -------------------------------------------------------------------------
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end   = datetime.strptime(end_date,   "%Y-%m-%d")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    num_days      = len(date_list)
    num_employees = len(employees)
    num_projects  = len(projects)
    num_topics    = len(all_topics)

    # -------------------------------------------------------------------------
    # 2. Mappings: topic -> index
    # -------------------------------------------------------------------------
    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}

    # -------------------------------------------------------------------------
    # 3. Salary Matrix (num_employees x num_days)
    # -------------------------------------------------------------------------
    salaries = []
    for emp in employees:
        for d_str in date_list:
            day_info = emp.salary_levels.get(d_str, {})
            amt = float(day_info.get("amount", 0.0))
            salaries.append(amt)
    salary_array = np.array(salaries, dtype=float)
    salary_matrix = salary_array.reshape((num_employees, num_days))

    # -------------------------------------------------------------------------
    # 4. Daily research hours from timesheets
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days), dtype=float)
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            research_hours_array[i, j] = emp.research_hours[d_str]

    # -------------------------------------------------------------------------
    # 5. Define 4D variable X and 3D variable Y
    # -------------------------------------------------------------------------
    #  X[i,j,p,k] = hours employee i, day j, project p, topic k
    #  Y[i,j,p]   = nonR&D hours employee i, day j, billed to project p
    # -------------------------------------------------------------------------
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)

    # -------------------------------------------------------------------------
    # 6. Constraints
    # -------------------------------------------------------------------------
    constraints = []

    # 6a) Sum of allocated hours == daily timesheet hours
    constraints.append(
        cp.sum(X, axis=(2,3)) + cp.sum(Y, axis=2) == research_hours_array
    )

    # 6b) NonR&D <= 25% of daily research hours
    constraints.append(
        cp.sum(Y, axis=2) <= 0.25 * research_hours_array
    )

    # 6c) If project doesn't have a topic, set X=0 for that project/topic
    for p_idx, proj in enumerate(projects):
        allowed_topic_indices = [
            topic_to_idx[t]
            for t in proj.research_topics
            if t in topic_to_idx
        ]
        for k in range(num_topics):
            if k not in allowed_topic_indices:
                constraints.append(
                    X[:, :, p_idx, k] == 0
                )

    # -------------------------------------------------------------------------
    # 7. Objective: Minimizing sum of squares (cost_p - target_p) + tiny reg
    # -------------------------------------------------------------------------
    project_cost_exprs = {}
    target_costs = {}

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        try:
            t_val = float(proj.grant_contractual)
        except:
            t_val = 0.0
        target_costs[pname] = t_val

        # cost_p = sum over i,j of salary[i,j]* (sum_{k} X[i,j,p,k] + Y[i,j,p])
        sum_topics = cp.sum(X[:, :, p_idx, :], axis=3)
        sum_nonrnd = Y[:, :, p_idx]
        combined   = sum_topics + sum_nonrnd
        cost_expr  = cp.sum(cp.multiply(salary_matrix, combined))
        project_cost_exprs[pname] = cost_expr

    diffs = []
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        diff_expr = project_cost_exprs[pname] - target_costs[pname]
        diffs.append(cp.square(diff_expr))

    reg_lambda = 1e-6
    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))
    objective = cp.Minimize(cp.sum(diffs) + reg_expr)

    # -------------------------------------------------------------------------
    # 8. Solve
    # -------------------------------------------------------------------------
    problem = cp.Problem(objective, constraints)
    solver_opts = {
        "eps_abs": 1e-7,
        "eps_rel": 1e-7,
        "max_iter": 100000
    }
    problem.solve(solver=cp.OSQP, **solver_opts)

    # -------------------------------------------------------------------------
    # 9. Extract results & debugging info
    # -------------------------------------------------------------------------
    X_val = X.value
    Y_val = Y.value

    final_costs = {}
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        final_costs[pname] = float(project_cost_exprs[pname].value)

    # Build nested allocations dictionary
    allocations = {}
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        allocations[emp_name] = {}
        for j, d_str in enumerate(date_list):
            allocations[emp_name][d_str] = {}
            for p_idx, proj in enumerate(projects):
                pname = proj.name if proj.name else f"Project_{p_idx}"
                topic_allocs = {}
                for k_idx, topic_name in enumerate(all_topics):
                    hours_val = X_val[i, j, p_idx, k_idx]
                    if hours_val > 1e-10:
                        topic_allocs[topic_name] = float(hours_val)

                nonrnd_val = float(Y_val[i, j, p_idx])
                if topic_allocs or nonrnd_val > 1e-10:
                    allocations[emp_name][d_str][pname] = {
                        'topics': topic_allocs,
                        'nonRnD': nonrnd_val
                    }

    results = {
        'solver_status': problem.status,
        'final_objective': problem.value,
        'final_costs': final_costs,
        'allocations': allocations
    }

    # -------------------------------------------------------------------------
    # 10. Print/Debug/Insight Info
    # -------------------------------------------------------------------------
    print("==== DEBUG / INSIGHTS ====")
    print(f"Solver status: {problem.status}")
    print(f"Final objective value: {problem.value:.4f}")

    # Per-project costs vs. targets
    print("\nProject Costs vs. Targets:")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        cost = final_costs[pname]
        target = target_costs[pname]
        diff  = cost - target
        print(f"  {pname}: cost={cost:.2f}, target={target:.2f}, diff={diff:.2f}")

    # Check daily constraints: sum_{p,k} X_val + sum_{p} Y_val
    # We'll measure the max absolute difference from timesheet hours
    max_abs_diff = 0.0
    total_allocated = 0.0
    total_timesheet = 0.0
    for i in range(num_employees):
        emp_name = employees[i].employee_name
        for j, d_str in enumerate(date_list):
            allocated_day = 0.0
            # sum over all p, k
            allocated_day += np.sum(X_val[i, j, :, :])
            allocated_day += np.sum(Y_val[i, j, :])

            timesheet_day = research_hours_array[i, j]
            diff = allocated_day - timesheet_day
            total_allocated += allocated_day
            total_timesheet += timesheet_day

            if abs(diff) > max_abs_diff:
                max_abs_diff = abs(diff)

    print(f"\nTotal timesheet hours: {total_timesheet:.2f}")
    print(f"Total allocated hours: {total_allocated:.2f}")
    print(f"Max absolute difference in day constraints: {max_abs_diff:.4e}")
    if max_abs_diff > 1e-5:
        print("WARNING: Some day constraints are off by more than 1e-5 (check solver tolerance).")
    else:
        print("Day constraints satisfied within tolerance.")

    # Check how close we are to the 25% nonR&D limit
    # We'll just do a quick check for each day & employee
    # sum_{p} Y[i,j,p] <= 0.25 * research_hours_array[i,j]
    max_nond_rd_ratio = 0.0
    for i in range(num_employees):
        for j in range(num_days):
            total_nond = np.sum(Y_val[i, j, :])
            rhours = research_hours_array[i, j]
            if rhours > 0:
                ratio = total_nond / rhours
                if ratio > max_nond_rd_ratio:
                    max_nond_rd_ratio = ratio

    print(f"Max NonR&D fraction (across all employees/days): {max_nond_rd_ratio*100:.2f}% (limit=25%)\n")

    print("==== END DEBUG ====")

    return results
