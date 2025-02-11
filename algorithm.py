# -----------------------------------------------------------------------------
# Authors: Arash Sheikhlar and Kristinn Thorisson (Further Improved QP version)
# Project: Research Expenditure Allocation (REA)
# -----------------------------------------------------------------------------
# This software is provided "as is", without warranty of any kind.
# In no event shall the authors be liable for any claim, damages, or
# other liability.
#
# Unauthorized copying, distribution, or modification of this code is strictly
# prohibited unless prior written permission is obtained from the authors.
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

    Parameters
    ----------
    employees : list of EmployeeModel
        Each employee has research_hours[date], meeting_hours[date], etc.
        Must also have 'salary_levels[date]' that includes {'amount': some_value}.
    projects : list of ProjectModel
        Each project has 'research_topics' plus a 'grant_contractual' for target cost.
    start_date : str (MM-DD-YYYY)
    end_date   : str (MM-DD-YYYY)
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
    dt_start = datetime.strptime(start_date, "%m-%d-%Y")
    dt_end   = datetime.strptime(end_date,   "%m-%d-%Y")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%m-%d-%Y"))
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
    # 4. Daily research hours from timesheets (num_employees x num_days)
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days), dtype=float)
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            research_hours_array[i, j] = emp.research_hours[d_str]

    # -------------------------------------------------------------------------
    # === Debug: Print Per-Employee Totals (Hours & Money) ===
    # -------------------------------------------------------------------------
    print("\n================= DEBUG INFO: HOURS & SALARY =================")
    grand_total_hours = 0.0
    grand_total_salary = 0.0

    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        emp_hours = float(np.sum(research_hours_array[i, :]))
        daily_costs = salary_matrix[i, :] * research_hours_array[i, :]
        emp_cost = float(np.sum(daily_costs))

        grand_total_hours += emp_hours
        grand_total_salary += emp_cost

        print(f"Employee '{emp_name}': total hours = {emp_hours:.2f}, total salary = {emp_cost:.2f}")

    print(f"\nALL EMPLOYEES COMBINED: total hours = {grand_total_hours:.2f}, total salary = {grand_total_salary:.2f}")
    print("==============================================================\n")

    # -------------------------------------------------------------------------
    # 5. Define CVXPY Variables
    # -------------------------------------------------------------------------
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)

    # -------------------------------------------------------------------------
    # 6. Constraints
    # -------------------------------------------------------------------------
    constraints = []

    # 6a) sum_{p,k} X[i,j,p,k] + sum_{p} Y[i,j,p] = daily hours
    constraints.append(
        cp.sum(X, axis=(2,3)) + cp.sum(Y, axis=2) == research_hours_array
    )

    # 6b) NonR&D <= 25% of daily research hours
    constraints.append(
        cp.sum(Y, axis=2) <= 0.25 * research_hours_array
    )

    # 6c) If a project does not include a topic, force X=0 for that topic
    for p_idx, proj in enumerate(projects):
        allowed_topic_indices = [
            topic_to_idx[t] for t in proj.research_topics if t in topic_to_idx
        ]
        for k in range(num_topics):
            if k not in allowed_topic_indices:
                constraints.append(X[:, :, p_idx, k] == 0)

    # -------------------------------------------------------------------------
    # 7. Objective: Minimize sum of squared differences from targets + small reg
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

        sum_topics = cp.sum(X[:, :, p_idx, :], axis=2)  # shape (E, D)
        sum_nonrnd = Y[:, :, p_idx]                     # shape (E, D)
        combined = sum_topics + sum_nonrnd

        cost_expr = cp.sum(cp.multiply(salary_matrix, combined))
        project_cost_exprs[pname] = cost_expr

    diffs = []
    for pname, cost_expr in project_cost_exprs.items():
        diffs.append(cp.square(cost_expr - target_costs[pname]))

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

    if problem.status not in ["optimal", "optimal_inaccurate"]:
        print("Warning: Solver ended with status:", problem.status)

    # -------------------------------------------------------------------------
    # 9. Extract results
    # -------------------------------------------------------------------------
    X_val = X.value
    Y_val = Y.value

    final_costs = {}
    for pname, expr in project_cost_exprs.items():
        final_costs[pname] = float(expr.value)

    # Build nested allocation dictionary
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
                        "topics": topic_allocs,
                        "nonRnD": nonrnd_val
                    }

    # -------------------------------------------------------------------------
    # 10. Diagnostics: Convert to int for the check
    # -------------------------------------------------------------------------
    print("\n================= DIAGNOSTIC: ALLOCATION CHECK (INTEGERS) =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        for j, d_str in enumerate(date_list):
            allocated_total = 0.0
            for pname, alloc_data in allocations[emp_name][d_str].items():
                allocated_total += alloc_data.get("nonRnD", 0.0)
                allocated_total += sum(alloc_data.get("topics", {}).values())

            available_total = emp.research_hours.get(d_str, 0.0)

            # Convert both to integers using round() then int():
            alloc_int = int(round(allocated_total))
            avail_int = int(round(available_total))

            if alloc_int > avail_int:
                print(f"WARNING: Over-allocation for {emp_name} on {d_str} "
                      f"(allocated={alloc_int}, available={avail_int})")
            elif alloc_int < avail_int:
                print(f"WARNING: Under-allocation for {emp_name} on {d_str} "
                      f"(allocated={alloc_int}, available={avail_int})")
    print("================================================================\n")

    return {
        "solver_status": problem.status,
        "final_objective": problem.value,
        "final_costs": final_costs,
        "allocations": allocations
    }
