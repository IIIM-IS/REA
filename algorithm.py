import cvxpy as cp
import numpy as np
from datetime import datetime, timedelta

def round_vector_preserve_sum(v, target_total):
    """
    Given a 1D numpy array v (the continuous allocation) and an integer target_total,
    returns an integer array of the same shape that sums to target_total using a largest-remainder method.
    """
    floor_vals = np.floor(v)
    int_vals = floor_vals.astype(int)
    remainder = v - floor_vals
    current_total = int(np.sum(int_vals))
    remainder_needed = target_total - current_total
    if remainder_needed > 0:
        sorted_indices = np.argsort(-remainder)
        for idx in sorted_indices[:remainder_needed]:
            int_vals[idx] += 1
    return int_vals

def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    locked_allocations = {"Bridget Burger": "EURIDICE"}

    # -------------------------------------------------------------------------
    # Add a common topic "Bridge" that is available for all personnel and projects.
    # -------------------------------------------------------------------------
    common_topic = "Bridge"
    if common_topic not in all_topics:
        all_topics.append(common_topic)

    # -------------------------------------------------------------------------
    # 1. Build the date range from start_date to end_date inclusive
    # -------------------------------------------------------------------------
    dt_start = datetime.strptime(start_date, "%m-%d-%Y")
    dt_end = datetime.strptime(end_date, "%m-%d-%Y")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%m-%d-%Y"))
        current += timedelta(days=1)

    # Partition employees into locked and free lists.
    locked_employee_list = []
    free_employee_list = []
    locked_allocs_output = {}  # Pre-assigned allocations for locked employees.
    for emp in employees:
        if emp.employee_name in locked_allocations:
            locked_employee_list.append(emp)
            locked_project = locked_allocations[emp.employee_name]
            locked_allocs_output[emp.employee_name] = {}
            for d in date_list:
                locked_allocs_output[emp.employee_name][d] = {
                    locked_project: {
                        "topics": {"total": emp.research_hours.get(d, 0.0)},
                        "nonRnD": emp.nonRnD_hours.get(d, 0.0)
                    }
                }
        else:
            free_employee_list.append(emp)

    employees = free_employee_list  # Use only free employees for optimization.
    num_days      = len(date_list)
    num_employees = len(employees)
    num_projects  = len(projects)
    num_topics    = len(all_topics)

    # -------------------------------------------------------------------------
    # 2. Map topics to indices for easier referencing in CVXPY
    # -------------------------------------------------------------------------
    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}

    # -------------------------------------------------------------------------
    # 3. Build salary matrix (num_employees x num_days)
    # -------------------------------------------------------------------------
    salary_matrix = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            day_info = emp.salary_levels.get(d_str, {})
            salary_matrix[i, j] = (float(day_info.get("amount", 0.0)) / 160.0) * 1.25

    # -------------------------------------------------------------------------
    # 4. Build research and non-R&D hours arrays (num_employees x num_days)
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days))
    nonrnd_hours_array   = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            research_hours_array[i, j] = emp.research_hours.get(d_str, 0.0)
            nonrnd_hours_array[i, j]   = emp.nonRnD_hours.get(d_str, 0.0)

    # -------------------------------------------------------------------------
    # 5. Debug Info: Print total hours and salary cost per employee
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
    # 6. Define CVXPY Variables for allocations
    # -------------------------------------------------------------------------
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)  # R&D hours (employee, day, project, topic)
    Y_cap = cp.Variable((num_employees, num_days, num_projects), nonneg=True)            # Initial non‑R&D allocation
    Y_extra = cp.Variable((num_employees, num_days, num_projects), nonneg=True)          # Extra non‑R&D allocation

    constraints = []

    # (a) R&D allocation: assign all available R&D hours.
    constraints.append(cp.sum(cp.sum(X, axis=3), axis=2) == research_hours_array)

    # (b) Full utilization of non‑R&D hours per employee and day.
    constraints.append(cp.sum(Y_cap + Y_extra, axis=2) == nonrnd_hours_array)

    # (c) Topic constraints: only allowed topics get R&D hours.
    for p_idx, proj in enumerate(projects):
        # Build the list of allowed topics from the project specification.
        allowed_topic_indices = [topic_to_idx[t] for t in proj.research_topics if t in topic_to_idx]
        # Always include the common "Bridge" topic.
        if topic_to_idx[common_topic] not in allowed_topic_indices:
            allowed_topic_indices.append(topic_to_idx[common_topic])
        for k_idx in range(num_topics):
            if k_idx not in allowed_topic_indices:
                constraints.append(X[:, :, p_idx, k_idx] == 0)

    # -------------------------------------------------------------------------
    # 7. Cost, Non‑R&D, and R&D Penalties
    # -------------------------------------------------------------------------
    project_cost_exprs = {}
    target_costs = {}
    rel_cost_penalties = []   # Cost penalty for projects below target.
    nonrnd_shortfall_expr = 0 # Non‑R&D shortfall penalty.

    # New R&D penalties:
    lambda_smooth = 1e-3      # Weight for temporal smoothing of R&D allocations.
    lambda_topic = 1e-2       # Weight for target topic distribution penalty.
    smooth_penalty = cp.sum_squares(X[:, 1:, :, :] - X[:, :-1, :, :])  # Vectorized temporal smoothing.
    topic_penalty = 0         # Initialize topic penalty.

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        if proj.grant_contractual is None:
            print(f"Warning: grant_contractual is None for {pname}, setting to 0")
            proj.grant_contractual = 0.0
        target_costs[pname] = float(proj.grant_contractual)
        sum_topics = cp.sum(X[:, :, p_idx, :], axis=2)
        sum_nonrnd = Y_cap[:, :, p_idx] + Y_extra[:, :, p_idx]
        combined_hours = sum_topics + sum_nonrnd
        direct_cost_expr = cp.sum(cp.multiply(salary_matrix, combined_hours))
        if proj.operational_overhead is None:
            print(f"Warning: operational_overhead is None for {pname}, setting to 0")
            proj.operational_overhead = 0.0
        cost_expr = direct_cost_expr  # Using only direct cost.
        project_cost_exprs[pname] = cost_expr

        target_val = target_costs[pname] + 1e-6
        below_dev = cp.maximum(1 - cost_expr / target_val, 0)
        rel_cost_penalties.append(cp.square(below_dev))
        
        # Non‑R&D shortfall penalty (as before)
        desired_frac = getattr(proj, 'nonrnd_percentage', 0) / 100.0  
        nonrnd_shortfall_expr += cp.sum(cp.pos(desired_frac * nonrnd_hours_array - (Y_cap[:,:,p_idx] + Y_extra[:,:,p_idx])))

        # Vectorized target topic mix penalty (if provided)
        if hasattr(proj, 'rnd_topic_ratios'):
            target_vector = np.array([proj.rnd_topic_ratios.get(topic, 0) for topic in all_topics])
            allocated = X[:, :, p_idx, :]  # shape (num_employees, num_days, num_topics)
            total_allocated = cp.sum(allocated, axis=2, keepdims=True)
            target_alloc = total_allocated * target_vector  # Broadcasting target_vector.
            topic_penalty += cp.sum_squares(allocated - target_alloc)

    # -------------------------------------------------------------------------
    # 8. Composite Objective
    # -------------------------------------------------------------------------
    alpha = 1.0   # Not used since full utilization is forced.
    beta  = 1e-3  # Weight for cost penalty.
    gamma = 1e2   # Weight for non‑R&D penalty.
    reg_lambda = 1e-6

    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y_cap) + cp.sum_squares(Y_extra))
    
    obj_expr = beta * cp.sum(rel_cost_penalties) \
               + gamma * nonrnd_shortfall_expr \
               + lambda_smooth * smooth_penalty \
               + lambda_topic * topic_penalty \
               + reg_expr
    objective = cp.Minimize(obj_expr)

    # -------------------------------------------------------------------------
    # 9. Solve the Problem with CVXPY
    # -------------------------------------------------------------------------

    problem = cp.Problem(objective, constraints)
    # Increase maximum iterations and tighten tolerances.
    solver_opts = {
        "max_iters": 1000000,    # Increase maximum iterations.
        "abstol": 1e-8,
        "reltol": 1e-8,
        "feastol": 1e-8
    }
    try:
        # Option 1: Use ECOS with the updated options.
        problem.solve(solver=cp.ECOS, **solver_opts)
    except Exception as e:
        print(f"Solver error: {e}")
        print("Solver error occurred.")

    # NEW: Guard clause to ensure solver returned valid values.
    if X.value is None or Y_cap.value is None or Y_extra.value is None:
        print("Solver did not return valid solution values for some variables.")
        return {
            "solver_status": problem.status,
            "final_objective": None,
            "final_costs": {proj.name if proj.name else f"Project_{i}": float("nan") for i, proj in enumerate(projects)},
            "allocations": {emp.employee_name: {} for emp in employees}
        }

    # -------------------------------------------------------------------------
    # 10. Extract and Format Results with Rounding
    # -------------------------------------------------------------------------
    X_val = X.value
    Y_cap_val = Y_cap.value
    Y_extra_val = Y_extra.value
    final_costs = {}
    for pname, expr in project_cost_exprs.items():
        val = expr.value
        final_costs[pname] = float(val) if val is not None else float("nan")

    # Post-process allocations: round continuous allocations to full hours.
    allocations = {}
    if X_val is not None and Y_cap_val is not None and Y_extra_val is not None:
        for i, emp in enumerate(employees):
            emp_name = emp.employee_name
            allocations[emp_name] = {}
            for j, d_str in enumerate(date_list):
                rd_continuous = X_val[i, j, :, :].flatten()
                target_rd = int(round(emp.research_hours.get(d_str, 0)))
                rd_int_flat = round_vector_preserve_sum(rd_continuous, target_rd)
                rd_int = rd_int_flat.reshape((num_projects, num_topics))
                
                nrnd_continuous = np.array([Y_cap_val[i, j, p] + Y_extra_val[i, j, p] for p in range(num_projects)])
                target_nrnd = int(round(np.sum(nrnd_continuous)))  # equals available non‑R&D for that day.
                nrnd_int = round_vector_preserve_sum(nrnd_continuous, target_nrnd)
                
                allocations[emp_name][d_str] = {}
                for p_idx, proj in enumerate(projects):
                    pname = proj.name if proj.name else f"Project_{p_idx}"
                    topic_allocs = {}
                    for k_idx, topic_name in enumerate(all_topics):
                        if rd_int[p_idx, k_idx] > 0:
                            topic_allocs[topic_name] = int(rd_int[p_idx, k_idx])
                    if topic_allocs or (nrnd_int[p_idx] > 0):
                        allocations[emp_name][d_str][pname] = {
                            "topics": topic_allocs,
                            "nonRnD": int(nrnd_int[p_idx])
                        }
    else:
        print("Warning: Solver did not return valid values for X, Y_cap, or Y_extra.")
    
    # Merge pre-assigned locked allocations.
    for emp_name, locked_data in locked_allocs_output.items():
        allocations[emp_name] = locked_data
    
    # -------------------------------------------------------------------------
    # DIAGNOSTICS
    # -------------------------------------------------------------------------
    print("\n================= DIAGNOSTIC: ALLOCATION CONSISTENCY CHECK =================")
    warning_flag = False
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        for j, d_str in enumerate(date_list):
            allocated_rnd = 0
            allocated_nonrnd = 0
            for p_name, alloc_data in allocations[emp_name][d_str].items():
                allocated_rnd += sum(alloc_data.get("topics", {}).values())
                allocated_nonrnd += alloc_data.get("nonRnD", 0)
            available_rnd = int(round(emp.research_hours.get(d_str, 0)))
            available_nonrnd = int(round(emp.nonRnD_hours.get(d_str, 0)))
            if abs(allocated_rnd - available_rnd) > 0:
                print(f"WARNING: {emp_name} on {d_str} (R&D): allocated = {allocated_rnd} hrs, available = {available_rnd} hrs")
                warning_flag = True
            if allocated_nonrnd > available_nonrnd:
                print(f"WARNING: {emp_name} on {d_str} (Non-R&D): allocated = {allocated_nonrnd} hrs, available = {available_nonrnd} hrs")
                warning_flag = True
    if not warning_flag:
        print("All allocations are consistent.")
    print("==========================================================================\n")

    # 2. Detailed Daily Allocations per Employee
    print("\n================= DIAGNOSTIC: DETAILED DAILY ALLOCATIONS =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        print(f"\nEmployee: {emp_name}")
        for j, d_str in enumerate(date_list):
            available_rnd = emp.research_hours.get(d_str, 0.0)
            allocated_rnd = sum(X_val[i, j, p_idx, k_idx] 
                                for p_idx in range(num_projects)
                                for k_idx in range(num_topics))
            rnd_remainder = available_rnd - allocated_rnd

            available_nonrnd = nonrnd_hours_array[i, j]
            if Y_cap_val is not None and Y_extra_val is not None:
                allocated_nonrnd = float(np.sum(Y_cap_val[i, j, :]) + np.sum(Y_extra_val[i, j, :]))
            else:
                allocated_nonrnd = 0.0
            nonrnd_remainder = available_nonrnd - allocated_nonrnd
    print("==========================================================================\n")

    # 3. Summary Allocations per Employee (Aggregated Over All Days)
    print("\n================= DIAGNOSTIC: SUMMARY ALLOCATIONS PER EMPLOYEE =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        total_available_rnd = 0.0
        total_allocated_rnd = 0.0
        total_available_nonrnd = 0.0
        total_allocated_nonrnd = 0.0
        for j, d_str in enumerate(date_list):
            total_available_rnd += emp.research_hours.get(d_str, 0.0)
            if X_val is not None:
                total_allocated_rnd += sum(X_val[i, j, p_idx, k_idx] 
                                        for p_idx in range(num_projects)
                                        for k_idx in range(num_topics))
            total_available_nonrnd += nonrnd_hours_array[i, j]
            if Y_cap_val is not None and Y_extra_val is not None:
                total_allocated_nonrnd += float(np.sum(Y_cap_val[i, j, :]) + np.sum(Y_extra_val[i, j, :]))

        rnd_remainder = total_available_rnd - total_allocated_rnd
        nonrnd_remainder = total_available_nonrnd - total_allocated_nonrnd

        print(f"Employee: {emp_name}")
        print(f"  Total Available R&D Hours:   {total_available_rnd:6.2f} hrs")
        print(f"  Total Allocated R&D:         {total_allocated_rnd:6.2f} hrs")
        print("----------------------------------------------------------------")
        print(f"  Total R&D Remainder:         {rnd_remainder:6.2f} hrs")
        print("----------------------------------------------------------------")
        print("----------------------------------------------------------------")
        print(f"  Total Available Non-R&D:     {total_available_nonrnd:6.2f} hrs")
        print(f"  Total Allocated Non-R&D:     {total_allocated_nonrnd:6.2f} hrs")
        print("----------------------------------------------------------------")
        print(f"  Total Non-R&D Remainder:     {nonrnd_remainder:6.2f} hrs")
    print("==========================================================================\n")

    # 4. Per-Project Employee Allocations
    print("\n================= DIAGNOSTIC: PER-PROJECT EMPLOYEE ALLOCATIONS =================")
    for p_idx, proj in enumerate(projects):
        proj_name = proj.name if proj.name else f"Project_{p_idx}"
        allocations_per_employee = {}
        for emp in employees:
            emp_name = emp.employee_name
            total_allocated = 0.0
            for d_str in date_list:
                if emp_name in allocations and d_str in allocations[emp_name]:
                    if proj_name in allocations[emp_name][d_str]:
                        alloc_data = allocations[emp_name][d_str][proj_name]
                        total_allocated += alloc_data.get("nonRnD", 0.0) + sum(alloc_data.get("topics", {}).values())
            if total_allocated > 1e-3:
                allocations_per_employee[emp_name] = total_allocated

        print(f"\nProject: {proj_name}")
        if allocations_per_employee:
            for emp_name, hours in allocations_per_employee.items():
                print(f"  {emp_name:20s}: {hours:6.2f} hrs")
        else:
            print("  No allocations found for this project.")
    print("==========================================================================\n")

    # 5. Project Cost Details & Topic Allocations
    print("\n================= DIAGNOSTIC: PROJECT COST DETAILS & TOPIC ALLOCATIONS =================")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        computed_cost = final_costs[pname]
        target_cost = target_costs[pname]
        overhead_rate = proj.operational_overhead or 0.0
        rel_dev = (computed_cost / (target_cost + 1e-6)) - 1 if target_cost > 0 else np.nan

        print(f"Project '{pname}':")
        # Aggregate R&D hours allocated per topic for this project.
        topic_hours = {}
        if X_val is not None:
            for k_idx, topic_name in enumerate(all_topics):
                total_topic_hours = np.sum(X_val[:, :, p_idx, k_idx])
                if total_topic_hours > 1e-10:
                    topic_hours[topic_name] = total_topic_hours
            if topic_hours:
                print("  Topic Allocations:")
                for topic, hours in topic_hours.items():
                    print(f"    {topic}: {hours:.2f} hrs")
        print("-------------------------------------------------------------")
    print("==========================================================================\n")

    return {
        "solver_status": problem.status,
        "final_objective": problem.value,
        "final_costs": final_costs,
        "allocations": allocations
    }


# 2785838875 - 28210000