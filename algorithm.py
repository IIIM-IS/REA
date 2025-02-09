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
    Optimizes the allocation of research hours (per topic and nonRnD) across employees and days,
    so that for each project the salary-weighted cost is as close as possible to the project's target.
    
    This version reformulates the allocation as a quadratic program and uses CVXPY with enhanced,
    vectorized constraints, regularization, and solver options.
    
    Parameters:
      employees: List of EmployeeModel objects.
      projects: List of ProjectModel objects.
      start_date: string in "YYYY-MM-DD" format.
      end_date: string in "YYYY-MM-DD" format.
      all_topics: List of all recognized research topics.
      
    Returns:
      A dictionary with:
         - solver_status: CVXPY problem status.
         - final_objective: The final objective value.
         - final_costs: A dict of computed project costs.
         - allocations: A nested dictionary with allocations per employee per day.
    """
    # -------------------------------------------------------------------------
    # 1. Build Date Range and Dimensions
    # -------------------------------------------------------------------------
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    num_days = len(date_list)
    num_employees = len(employees)
    
    # -------------------------------------------------------------------------
    # 2. Build Topic Mapping and Salary Matrix
    # -------------------------------------------------------------------------
    topic_to_index = {topic: i for i, topic in enumerate(all_topics)}
    num_topics = len(all_topics)
    
    # Build the salary matrix (num_employees x num_days).
    salary_list = []
    for emp in employees:
        for day_str in date_list:
            day_salary_info = emp.salary_levels.get(day_str, {})
            salary_list.append(float(day_salary_info.get("amount", 0.0)))
    salaries = np.array(salary_list)
    salary_matrix = salaries.reshape((num_employees, num_days))
    
    # -------------------------------------------------------------------------
    # 3. Build Project Targets and Project-Topic Mapping
    # -------------------------------------------------------------------------
    target_costs = {}
    project_topics = {}
    for proj in projects:
        proj_name = proj.name if proj.name else "Unnamed"
        target_costs[proj_name] = float(proj.grant_contractual)
        topic_indices = [topic_to_index[t] for t in proj.research_topics if t in topic_to_index]
        project_topics[proj_name] = topic_indices
    
    # -------------------------------------------------------------------------
    # 4. Build Daily Research Hours Array
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days), dtype=float)
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            research_hours_array[i, j] = emp.research_hours[d_str]
    
    # -------------------------------------------------------------------------
    # 5. Define Optimization Variables
    # -------------------------------------------------------------------------
    # X: allocated hours per employee, day, and topic (shape: num_employees x num_days x num_topics)
    X = cp.Variable((num_employees, num_days, num_topics), nonneg=True)
    # Y: allocated nonRnD hours per employee, day (shape: num_employees x num_days)
    Y = cp.Variable((num_employees, num_days), nonneg=True)
    
    # -------------------------------------------------------------------------
    # 6. Define Constraints (Vectorized)
    # -------------------------------------------------------------------------
    constraints = []
    # Total research hours allocated (across topics) must equal reported research hours.
    constraints.append(cp.sum(X, axis=2) == research_hours_array)
    # NonRnD hours are capped at 25% of research hours.
    constraints.append(Y <= 0.25 * research_hours_array)
    
    # -------------------------------------------------------------------------
    # 7. Build Project Cost Expressions and Objective Function
    # -------------------------------------------------------------------------
    # For each project, the cost is the salary-weighted sum of:
    #   (a) allocated hours for topics relevant to the project, plus
    #   (b) the nonRnD hours (which contribute to every project).
    project_cost_exprs = {}
    for proj_name, topic_indices in project_topics.items():
        if topic_indices:
            # Sum allocations over the relevant topics.
            topic_expr = cp.sum(X[:, :, topic_indices], axis=2)
        else:
            topic_expr = 0
        cost_expr = cp.sum(cp.multiply(salary_matrix, (topic_expr + Y)))
        project_cost_exprs[proj_name] = cost_expr

    # Define the objective as the sum of squared differences between cost and target
    # plus a small regularization on X and Y to improve numerical conditioning.
    reg_lambda = 1e-6
    objective_terms = []
    for proj_name in project_topics.keys():
        diff_expr = project_cost_exprs[proj_name] - target_costs[proj_name]
        objective_terms.append(cp.square(diff_expr))
    regularization = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))
    objective = cp.Minimize(cp.sum(objective_terms) + regularization)
    
    # -------------------------------------------------------------------------
    # 8. Solve the QP Problem with Solver Options and (optional) Warm Start
    # -------------------------------------------------------------------------
    solver_options = {
        "eps_abs": 1e-4,
        "eps_rel": 1e-4,
        # Additional options can be specified here.
    }
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.OSQP, **solver_options)
    
    if problem.status not in ["optimal", "optimal_inaccurate"]:
        print("Warning: Solver did not reach an optimal solution. Status:", problem.status)
    
    # -------------------------------------------------------------------------
    # 9. Retrieve the Optimized Values and Build the Output
    # -------------------------------------------------------------------------
    X_val = X.value  # Allocated research topic hours
    Y_val = Y.value  # Allocated nonRnD hours
    
    # Build a nested allocations dictionary: per employee, per day.
    allocations = {}
    for i, emp in enumerate(employees):
        emp_alloc = {"name": emp.employee_name, "daily_allocations": {}}
        for j, d_str in enumerate(date_list):
            day_alloc = {}
            for t_idx, t_name in enumerate(all_topics):
                day_alloc[t_name] = float(X_val[i, j, t_idx])
            day_alloc["nonRnD"] = float(Y_val[i, j])
            emp_alloc["daily_allocations"][d_str] = day_alloc
            # Also save into EmployeeModel
            if not hasattr(emp, "optimized_hours"):
                emp.optimized_hours = {}
            emp.optimized_hours[d_str] = day_alloc.copy()
        allocations[emp.employee_name] = emp_alloc
    
    # Compute final costs for reporting.
    final_costs = {}
    for proj_name, topic_indices in project_topics.items():
        if topic_indices:
            topic_alloc = np.sum(X_val[:, :, topic_indices], axis=2)
        else:
            topic_alloc = 0
        cost = float(np.sum(salary_matrix * (topic_alloc + Y_val)))
        final_costs[proj_name] = cost
    
    return {
        "solver_status": problem.status,
        "final_objective": problem.value,
        "final_costs": final_costs,
        "allocations": allocations
    }
