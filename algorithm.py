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
    # We'll just use the project list index for 'p'
    # p_idx = index of that project in 'projects'.

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
    # 5. Define 4D variable X for research (i, j, p, k),
    #    and 3D variable Y for nonR&D (i, j, p).
    #
    #    X[i,j,p,k] = hours of topic k, day j, by employee i, allocated to project p
    #    Y[i,j,p]   = nonR&D hours (day j, employee i) billed to project p
    # -------------------------------------------------------------------------
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)

    # -------------------------------------------------------------------------
    # 6. Constraints
    # -------------------------------------------------------------------------
    constraints = []

    # 6a) sum_{p,k} X[i,j,p,k] + sum_{p} Y[i,j,p] == research_hours_array[i,j].
    constraints.append(
        cp.sum(X, axis=(2,3)) + cp.sum(Y, axis=2) == research_hours_array
    )

    # 6b) NonR&D <= 25% of daily research hours
    constraints.append(
        cp.sum(Y, axis=2) <= 0.25 * research_hours_array
    )

    # 6c) If a project does *not* have topic k, force X=0 for that topic
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
    # 7. Objective: Minimize sum of (cost_p - target_p)^2 + small reg
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

        # DEBUG: check shapes for this project
        # salary_matrix is (num_employees, num_days)
        # We want cost_p = sum_{i,j} salary[i,j] * ( sum_{k} X[i,j,p_idx,k] + Y[i,j,p_idx] )

        # sum_topics over axis=3 => shape: (num_employees, num_days, num_projects)
        # But we are slicing p_idx, so first do X[:, :, p_idx, :]
        #
        # *Important fix:* sum over axis=2 if shape is (num_employees, num_days, num_topics)
        # after slicing.

        # Let's do a debug print to confirm the slice shape:
        print("\n[DEBUG] For project:", pname, "(p_idx =", p_idx, ")")
        print("X.shape =", X.shape)  # Expect (num_employees, num_days, num_projects, num_topics)
        print("Slicing X[:, :, p_idx, :].shape =>", X[:, :, p_idx, :].shape)

        # Now sum over topics dimension, which is axis=2 in the slice (since shape is (E, D, T)):
        sum_topics = cp.sum(X[:, :, p_idx, :], axis=2)

        # Also debug the result shape:
        print("sum_topics.shape after sum(axis=2) =>", sum_topics.shape)

        # Then Y[:, :, p_idx] has shape (num_employees, num_days).
        sum_nonrnd = Y[:, :, p_idx]
        print("sum_nonrnd.shape =>", sum_nonrnd.shape)

        # Now they should match shapes => (num_employees, num_days)
        combined = sum_topics + sum_nonrnd
        print("combined.shape =>", combined.shape)

        cost_expr = cp.sum(cp.multiply(salary_matrix, combined))
        project_cost_exprs[pname] = cost_expr

    # Build sum of squared differences: sum_p (cost_p - target_p)^2
    diffs = []
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        diff_expr = project_cost_exprs[pname] - target_costs[pname]
        diffs.append(cp.square(diff_expr))

    # tiny regularization
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
    X_val = X.value  # shape (num_employees, num_days, num_projects, num_topics)
    Y_val = Y.value  # shape (num_employees, num_days, num_projects)

    final_costs = {}
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        final_costs[pname] = float(project_cost_exprs[pname].value)

    # Build nested allocation dictionary:
    # allocations[employee_name][date_str][project_name] = { 'topics': {...}, 'nonRnD': float }
    allocations = {}
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        allocations[emp_name] = {}

        for j, d_str in enumerate(date_list):
            allocations[emp_name][d_str] = {}

            for p_idx, proj in enumerate(projects):
                pname = proj.name if proj.name else f"Project_{p_idx}"

                # gather topic hours
                topic_allocs = {}
                for k_idx, topic_name in enumerate(all_topics):
                    hours_val = X_val[i, j, p_idx, k_idx]
                    if hours_val > 1e-10:
                        topic_allocs[topic_name] = float(hours_val)

                nonrnd_val = float(Y_val[i, j, p_idx])
                # store only if there's something
                if topic_allocs or nonrnd_val > 1e-10:
                    allocations[emp_name][d_str][pname] = {
                        'topics': topic_allocs,
                        'nonRnD': nonrnd_val
                    }

    return {
        'solver_status'   : problem.status,
        'final_objective' : problem.value,
        'final_costs'     : final_costs,
        'allocations'     : allocations
    }
