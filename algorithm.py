import cvxpy as cp
import numpy as np
from datetime import datetime, timedelta

def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    """
    Allocates each employee's daily research hours (including non-R&D portions)
    across projects and topics. Full allocation is enforced.
    
    Soft penalties are applied to encourage project costs (including overhead)
    to be near target (grant_contractual) and within matching fund thresholds.
    Relative (normalized) cost deviations are penalized so that the solution
    always allocates all available hours.
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
    # 2. Map topics to indices
    # -------------------------------------------------------------------------
    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}
    
    # -------------------------------------------------------------------------
    # 3. Build salary matrix (num_employees x num_days)
    # -------------------------------------------------------------------------
    salary_matrix = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            day_info = emp.salary_levels.get(d_str, {})
            salary_matrix[i, j] = float(day_info.get("amount", 0.0))
    
    # -------------------------------------------------------------------------
    # 4. Build research hours array (num_employees x num_days)
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            if d_str in emp.research_hours:
                research_hours_array[i, j] = emp.research_hours[d_str]
            else:
                print(f"Warning: Missing research hours for {emp.employee_name} on {d_str}")
                research_hours_array[i, j] = 0.0
    
    # -------------------------------------------------------------------------
    # 5. Debug Info: Print total hours and salary per employee
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
    # 6. Define CVXPY Variables
    # -------------------------------------------------------------------------
    # X: R&D hours per (employee, day, project, topic)
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    # Y: Non-R&D hours per (employee, day, project)
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)
    
    constraints = []
    
    # 6a. Full Allocation: For every employee and day, the sum of allocated hours equals available hours.
    constraints.append(cp.sum(X, axis=(2,3)) + cp.sum(Y, axis=2) == research_hours_array)
    
    # 6b. Non-R&D Cap: For each project and every employee/day, non-R&D hours <= project cap * available hours.
    for p_idx, proj in enumerate(projects):
        cap = proj.max_nonrnd_percentage if (hasattr(proj, 'max_nonrnd_percentage') and proj.max_nonrnd_percentage > 0) else 0.25
        constraints.append(cp.multiply(Y[:, :, p_idx], (research_hours_array > 0)) <= 
                           cap * cp.multiply(research_hours_array, (research_hours_array > 0)))
    
    # 6c. Topic Constraints: For each project, only allowed topics may have nonzero R&D hours.
    for p_idx, proj in enumerate(projects):
        allowed_topic_indices = [topic_to_idx[t] for t in proj.research_topics if t in topic_to_idx]
        for k in range(num_topics):
            if k not in allowed_topic_indices:
                constraints.append(X[:, :, p_idx, k] == 0)
    
    # -------------------------------------------------------------------------
    # 7. Soft Penalties for Cost Target and Matching Funds (Relative)
    # -------------------------------------------------------------------------
    project_cost_exprs = {}
    target_costs = {}
    rel_cost_penalties = []    # Penalty for cost exceeding target (relative)
    rel_match_penalties = []   # Penalty for cost exceeding matching threshold (relative)
    
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        if proj.grant_contractual is None:
            print(f"Warning: grant_contractual is None for {pname}, setting to 0")
            proj.grant_contractual = 0.0
        target_costs[pname] = float(proj.grant_contractual)
    
        # Total allocated hours for project p (sum over employees & days)
        sum_topics = cp.sum(X[:, :, p_idx, :], axis=2)
        sum_nonrnd = Y[:, :, p_idx]
        combined = sum_topics + sum_nonrnd
        direct_cost_expr = cp.sum(cp.multiply(salary_matrix, combined))
        if proj.operational_overhead is None:
            print(f"Warning: operational_overhead is None for {pname}, setting to 0")
            proj.operational_overhead = 0.0
        overhead_expr = proj.operational_overhead * direct_cost_expr
        cost_expr = direct_cost_expr + overhead_expr
        project_cost_exprs[pname] = cost_expr
    
        # Relative cost deviation penalty: if cost exceeds target, penalize the relative excess.
        rel_dev = cp.maximum(cost_expr / (target_costs[pname] + 1e-6) - 1, 0)
        rel_cost_penalties.append(cp.square(rel_dev))
    
        # Matching Fund Penalty: if defined, compute relative deviation from matching threshold.
        if proj.matching_fund_type.lower() == "percentage":
            m_frac = proj.matching_fund_value / 100.0
            if m_frac < 1.0:
                threshold = float(proj.grant_contractual) / (1.0 - m_frac)
                rel_match = cp.maximum(cost_expr / (threshold + 1e-6) - 1, 0)
                rel_match_penalties.append(cp.square(rel_match))
        elif proj.matching_fund_type.lower() == "absolute":
            threshold = float(proj.grant_contractual) + proj.matching_fund_value
            rel_match = cp.maximum(cost_expr / (threshold + 1e-6) - 1, 0)
            rel_match_penalties.append(cp.square(rel_match))
    
    # -------------------------------------------------------------------------
    # 8. Composite Objective
    # -------------------------------------------------------------------------
    # We want to maximize non-R&D allocation (i.e. full allocation is forced) and
    # softly penalize relative cost excess and matching fund deviations.
    alpha = 1.0   # Weight for maximizing non-R&D allocation.
    beta = 1e-3   # Weight for relative cost penalty.
    gamma = 1e-3  # Weight for relative matching fund penalty.
    reg_lambda = 1e-6
    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))
    
    obj_expr = -alpha * cp.sum(Y) + beta * cp.sum(rel_cost_penalties)
    if rel_match_penalties:
        obj_expr += gamma * cp.sum(rel_match_penalties)
    obj_expr += reg_expr
    
    objective = cp.Minimize(obj_expr)
    
    # -------------------------------------------------------------------------
    # 9. Solve the Problem
    # -------------------------------------------------------------------------
    problem = cp.Problem(objective, constraints)
    solver_opts = {"max_iters": 100000}
    try:
        problem.solve(solver=cp.ECOS, **solver_opts)
    except Exception as e:
        print(f"Solver error: {e}")
        problem.status = "solver_error"
    
    if problem.status not in ["optimal", "optimal_inaccurate"]:
        print(f"Warning: Solver ended with status: {problem.status}")
        return {
            "solver_status": problem.status,
            "final_objective": None,
            "final_costs": {proj.name if proj.name else f"Project_{i}": float("nan") 
                            for i, proj in enumerate(projects)},
            "allocations": {emp.employee_name: {} for emp in employees}
        }
    
    # -------------------------------------------------------------------------
    # 10. Extract and Format Results
    # -------------------------------------------------------------------------
    X_val = X.value
    Y_val = Y.value
    final_costs = {}
    for pname, expr in project_cost_exprs.items():
        final_costs[pname] = float(expr.value) if expr.value is not None else float("nan")
    
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
                    val = X_val[i, j, p_idx, k_idx]
                    if val > 1e-10:
                        topic_allocs[topic_name] = float(val)
                nonrnd_val = float(Y_val[i, j, p_idx])
                if topic_allocs or nonrnd_val > 1e-10:
                    allocations[emp_name][d_str][pname] = {
                        "topics": topic_allocs,
                        "nonRnD": nonrnd_val
                    }
    
    # -------------------------------------------------------------------------
    # 11. Diagnostics: Print additional info.
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
            if int(round(allocated_total)) != int(round(available_total)):
                print(f"WARNING: {emp_name} on {d_str}: allocated={allocated_total:.2f}, available={available_total:.2f}")
    print("================================================================\n")
    
    # Additional diagnostics per employee for non-R&D allocation:
    print("\n================= DIAGNOSTIC: NON-R&D ALLOCATION PER EMPLOYEE =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        total_nonrnd = 0.0
        for j in range(num_days):
            total_nonrnd += np.sum(Y.value[i, j, :])
        print(f"Employee '{emp_name}' total non-R&D hours: {total_nonrnd:.2f}")
    print("================================================================\n")
    
    # Additional diagnostics per project: cost details and overhead, matching funds.
    print("\n================= DIAGNOSTIC: PROJECT COST DETAILS =================")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        computed_cost = final_costs[pname]
        target = target_costs[pname]
        overhead_rate = proj.operational_overhead if proj.operational_overhead is not None else 0.0
        # Relative deviation from target:
        rel_dev = (computed_cost / (target + 1e-6) - 1) if target > 0 else np.nan
        print(f"Project '{pname}':")
        print(f"  Computed Cost: {computed_cost:.2f}")
        print(f"  Target Cost: {target:.2f}")
        print(f"  Overhead Rate: {overhead_rate:.2f}")
        print(f"  Relative Cost Deviation: {rel_dev:.2f}")
        if proj.matching_fund_type.lower() == "percentage":
            m_frac = proj.matching_fund_value / 100.0
            threshold = target / (1.0 - m_frac) if m_frac < 1.0 else np.nan
            rel_match = (computed_cost / (threshold + 1e-6) - 1) if threshold and threshold>0 else np.nan
            print(f"  Matching Fund Type: Percentage")
            print(f"  Matching Fund Value: {proj.matching_fund_value:.2f}%")
            print(f"  Matching Threshold: {threshold:.2f}")
            print(f"  Relative Matching Deviation: {rel_match:.2f}")
        elif proj.matching_fund_type.lower() == "absolute":
            threshold = target + proj.matching_fund_value
            rel_match = (computed_cost / (threshold + 1e-6) - 1) if threshold and threshold>0 else np.nan
            print(f"  Matching Fund Type: Absolute")
            print(f"  Matching Fund Value: {proj.matching_fund_value:.2f}")
            print(f"  Matching Threshold: {threshold:.2f}")
            print(f"  Relative Matching Deviation: {rel_match:.2f}")
        print("-------------------------------------------------------------")
    print("================================================================\n")
    
    return {
        "solver_status": problem.status,
        "final_objective": problem.value,
        "final_costs": final_costs,
        "allocations": allocations
    }
