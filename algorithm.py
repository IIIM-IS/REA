import cvxpy as cp
import numpy as np
from datetime import datetime, timedelta

def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    """
    Allocates each employee's daily research hours (including non-R&D portions)
    across projects and topics. Full allocation is enforced by constraints
    ensuring that the sum of allocated hours equals the total research hours
    for each (employee, day).

    Rather than penalizing cost that exceeds a project's target, this version
    penalizes cost that is below the target (and below any matching fund
    threshold). Costs above the target are allowed without penalty.

    A small regularization term is added to help avoid degenerate solutions,
    and an objective coefficient is included to encourage maximizing non-R&D
    allocations (Y) while avoiding under-target spending.

    Parameters
    ----------
    employees : list
        A list of EmployeeModel objects. Each EmployeeModel typically has:
          - employee_name
          - research_hours (dict of date->hours)
          - meeting_hours (dict of date->hours) [not used directly here]
          - nonRnD_hours (dict of date->hours) [not used directly]
          - research_topics (dict of date-> {topic-> hrs})
          - salary_levels (dict of date-> {"amount": float})
    projects : list
        A list of ProjectModel objects. Each ProjectModel can have:
          - name
          - max_nonrnd_percentage
          - operational_overhead
          - grant_contractual (the target cost)
          - matching_fund_type ("Percentage" or "Absolute")
          - matching_fund_value
          - research_topics (list of allowed topics)
    start_date : str
        The start date in "MM-DD-YYYY" format (inclusive).
    end_date : str
        The end date in "MM-DD-YYYY" format (inclusive).
    all_topics : list
        The global list of *all* recognized R&D topics.

    Returns
    -------
    dict
        A dictionary with the following keys:
         - "solver_status": The solver's exit status (e.g. "optimal").
         - "final_objective": The final value of the objective function.
         - "final_costs": A dict of {project_name -> final computed cost (float)}
         - "allocations": A nested dict
             allocations[employee_name][date_str][project_name] = {
                 "topics": {topic: hrs, ...},
                 "nonRnD": some_hours_float
             }

    Notes
    -----
    1) We now penalize under-target cost, ignoring overspending.
       That is, if the cost for a project is below its grant_contractual,
       we incur a squared penalty based on the *relative* shortfall
       (cost_expr / target < 1). The same logic is applied for matching
       fund thresholds.

    2) If you want to severely penalize under-target cost, increase
       beta and gamma in the objective. If you want less emphasis on
       maximizing Non-R&D hours, lower alpha.

    3) The solver chosen is ECOS with up to 100k iterations. If you
       experience numerical issues, consider a different solver (e.g. SCS,
       OSQP, or a commercial one).
    """

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

    num_days      = len(date_list)
    num_employees = len(employees)
    num_projects  = len(projects)
    num_topics    = len(all_topics)

    # -------------------------------------------------------------------------
    # 2. Map topics to indices for easier referencing in CVXPY
    # -------------------------------------------------------------------------
    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}

    # -------------------------------------------------------------------------
    # 3. Build salary matrix (num_employees x num_days), from employees' salary_levels
    # -------------------------------------------------------------------------
    salary_matrix = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            day_info = emp.salary_levels.get(d_str, {})
            # 'amount' is the daily or hourly pay rate
            salary_matrix[i, j] = (float(day_info.get("amount", 0.0)) / 160.0) * 1.25

    # -------------------------------------------------------------------------
    # 4. Build research hours array (num_employees x num_days)
    #    This is how many hours each employee has available to allocate
    # -------------------------------------------------------------------------
    research_hours_array = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            if d_str in emp.research_hours:
                research_hours_array[i, j] = emp.research_hours[d_str]
            else:
                # Not necessarily an error, but we print a warning for debugging
                # print(f"Warning: Missing research hours for {emp.employee_name} on {d_str}")
                research_hours_array[i, j] = 0.0
    
    # -------------------------------------------------------------------------
    # 4b. Build non-R&D hours array (num_employees x num_days)
    #     This is how many non-R&D hours each employee has available to allocate
    # -------------------------------------------------------------------------
    nonrnd_hours_array = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            if d_str in emp.nonRnD_hours:
                nonrnd_hours_array[i, j] = emp.nonRnD_hours[d_str]
            else:
                # print(f"Warning: Missing nonRnD hours for {emp.employee_name} on {d_str}")
                nonrnd_hours_array[i, j] = 0.0

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
    # X: R&D hours for (employee, day, project, topic)
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    # Y_cap: Non-R&D hours allocated initially per project (subject to the per-project cap)
    Y_cap = cp.Variable((num_employees, num_days, num_projects), nonneg=True)
    # Y_extra: Extra non-R&D hours allocated from the remaining pool (can exceed the per-project cap)
    Y_extra = cp.Variable((num_employees, num_days, num_projects), nonneg=True)

    constraints = []

    # 6a. R&D Allocation Constraint:
    #     For each (employee, day), all available R&D hours must be allocated.
    constraints.append(cp.sum(X, axis=(2,3)) + cp.sum(Y_cap + Y_extra, axis=2) == research_hours_array)

    # 6a-alt. Non-R&D Allocation Constraint:
    #     Non-R&D hours are optional; allocated non-R&D (both initial and extra) cannot exceed what is available.
    constraints.append(cp.sum(Y_cap + Y_extra, axis=2) <= nonrnd_hours_array)

    # 6b. Non-R&D Cap for each project:
    #     For each (employee, day), Y <= (project.max_nonrnd_percentage * available_hours).
    #     If none is set, we use 25% as the default cap.
    for p_idx, proj in enumerate(projects):
        cap = getattr(proj, 'max_nonrnd_percentage', 0.25)
        if cap <= 0:
            cap = 0.25
        constraints.append(
            cp.multiply(Y_cap[:, :, p_idx], (nonrnd_hours_array > 0)) <=
            cap * cp.multiply(nonrnd_hours_array, (nonrnd_hours_array > 0))
        )

    # 6c. Topic Constraints:
    #     For each project, only allowed topics may have R&D hours > 0.
    #     If a topic is not in proj.research_topics, X must be 0 for that topic.
    for p_idx, proj in enumerate(projects):
        allowed_topic_indices = [topic_to_idx[t] for t in proj.research_topics if t in topic_to_idx]
        for k_idx in range(num_topics):
            if k_idx not in allowed_topic_indices:
                constraints.append(X[:, :, p_idx, k_idx] == 0)

    # -------------------------------------------------------------------------
    # 7. Soft Penalties for Cost Being BELOW the Target/Matching Threshold
    # -------------------------------------------------------------------------
    project_cost_exprs = {}
    target_costs = {}
    rel_cost_penalties = []   # Penalties for cost being below project target
    # rel_match_penalties = []  # Penalties for cost being below matching threshold

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"

        # If no explicit grant_contractual is set, assume 0 to avoid errors
        if proj.grant_contractual is None:
            print(f"Warning: grant_contractual is None for {pname}, setting to 0")
            proj.grant_contractual = 0.0
        target_costs[pname] = float(proj.grant_contractual)

        # Sum allocated hours for project 'p_idx' across employees/days
        sum_topics = cp.sum(X[:, :, p_idx, :], axis=2)  # shape: (num_employees, num_days)
        sum_nonrnd = Y_cap[:, :, p_idx] + Y_extra[:, :, p_idx]
        combined_hours = sum_topics + sum_nonrnd

        # Direct cost = sum of (salary_matrix * allocated_hours)
        direct_cost_expr = cp.sum(cp.multiply(salary_matrix, combined_hours))

        # Overhead cost
        if proj.operational_overhead is None:
            print(f"Warning: operational_overhead is None for {pname}, setting to 0")
            proj.operational_overhead = 0.0
        overhead_expr = proj.operational_overhead * direct_cost_expr

        # Total cost for this project
        cost_expr = direct_cost_expr - overhead_expr
        project_cost_exprs[pname] = cost_expr

        # ---------------------------
        # Penalty if cost_expr < target
        #   "below_dev" = max(1 - cost_expr/target, 0)
        #   we square it for a stronger penalty
        # ---------------------------
        target_val = target_costs[pname] + 1e-6
        below_dev = cp.maximum(1 - cost_expr / target_val, 0)
        rel_cost_penalties.append(cp.square(below_dev))

    # -------------------------------------------------------------------------
    # 8. Composite Objective
    #    - Maximize Non-R&D hours (via -alpha * sum(Y))
    #    - Penalize cost below target (beta * sum(rel_cost_penalties))
    #    - Penalize cost below matching threshold (gamma * sum(rel_match_penalties))
    #    - Small regularization to keep solution stable
    # -------------------------------------------------------------------------
    alpha = 1.0   # Weight for maximizing non-R&D hours
    beta = 1e-3   # Weight for penalizing being below cost target
    # gamma = 1e-3  # Weight for penalizing being below matching threshold
    reg_lambda = 1e-6  # Small regularization

    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y_cap) + cp.sum_squares(Y_extra))

    obj_expr = -alpha * cp.sum(Y_cap)

    if rel_cost_penalties:
        obj_expr += beta * cp.sum(rel_cost_penalties)
    # if rel_match_penalties:
    #     obj_expr += gamma * cp.sum(rel_match_penalties)

    obj_expr += reg_expr

    objective = cp.Minimize(obj_expr)

    # -------------------------------------------------------------------------
    # 9. Solve the Problem with CVXPY
    # -------------------------------------------------------------------------
    problem = cp.Problem(objective, constraints)
    solver_opts = {"max_iters": 100000}
    try:
        problem.solve(solver=cp.ECOS, **solver_opts)
    except Exception as e:
        print(f"Solver error: {e}")
        problem.status = "solver_error"

    # If the solver failed or is not optimal, we return a fallback structure
    if problem.status not in ["optimal", "optimal_inaccurate"]:
        print(f"Warning: Solver ended with status: {problem.status}")
        return {
            "solver_status": problem.status,
            "final_objective": None,
            "final_costs": {
                proj.name if proj.name else f"Project_{i}": float("nan")
                for i, proj in enumerate(projects)
            },
            "allocations": {
                emp.employee_name: {} for emp in employees
            }
        }

    # -------------------------------------------------------------------------
    # 10. Extract and Format Results
    # -------------------------------------------------------------------------
    X_val = X.value
    Y_cap_val = Y_cap.value
    Y_extra_val = Y_extra.value
    final_costs = {}
    for pname, expr in project_cost_exprs.items():
        val = expr.value
        final_costs[pname] = float(val) if val is not None else float("nan")

    # Reconstruct allocations in a human-readable nested dict
    allocations = {}
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        allocations[emp_name] = {}
        for j, d_str in enumerate(date_list):
            allocations[emp_name][d_str] = {}
            for p_idx, proj in enumerate(projects):
                pname = proj.name if proj.name else f"Project_{p_idx}"

                # Collect R&D topic allocations
                topic_allocs = {}
                for k_idx, topic_name in enumerate(all_topics):
                    val_ijpk = X_val[i, j, p_idx, k_idx]
                    if val_ijpk > 1e-10:
                        topic_allocs[topic_name] = float(val_ijpk)

                # Non-R&D hours
                nonrnd_val = float(Y_cap_val[i, j, p_idx] + Y_extra_val[i, j, p_idx])

                if topic_allocs or (nonrnd_val > 1e-10):
                    allocations[emp_name][d_str][pname] = {
                        "topics": topic_allocs,
                        "nonRnD": nonrnd_val
                    }

    # -------------------------------------------------------------------------
    # DIAGNOSTICS
    # -------------------------------------------------------------------------

    # 1. Allocation Consistency Check (Daily)
    print("\n================= DIAGNOSTIC: ALLOCATION CONSISTENCY CHECK =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        for j, d_str in enumerate(date_list):
            allocated_total = 0.0
            for p_name, alloc_data in allocations[emp_name][d_str].items():
                allocated_total += alloc_data.get("nonRnD", 0.0)
                allocated_total += sum(alloc_data.get("topics", {}).values())
            available_total = emp.research_hours.get(d_str, 0.0)
            if abs(allocated_total - available_total) > 1e-3:
                print(f"WARNING: {emp_name} on {d_str}: allocated = {allocated_total:.2f} hrs, "
                    f"available = {available_total:.2f} hrs")
    print("==========================================================================\n")


    # 2. Detailed Daily Allocations per Employee
    print("\n================= DIAGNOSTIC: DETAILED DAILY ALLOCATIONS =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        print(f"\nEmployee: {emp_name}")
        for j, d_str in enumerate(date_list):
            # Total research hours available (for both R&D and Non‑R&D)
            available = emp.research_hours.get(d_str, 0.0)
            # R&D allocated: sum over all projects and topics
            rnd_alloc = sum(X_val[i, j, p_idx, k_idx] for p_idx in range(num_projects)
                            for k_idx in range(num_topics))
            # Non‑R&D allocated: sum of Y_cap and Y_extra over projects
            nonrnd_alloc = float(np.sum(Y_cap_val[i, j, :]) + np.sum(Y_extra_val[i, j, :]))
            overall_alloc = rnd_alloc + nonrnd_alloc
            overall_remainder = available - overall_alloc

            # Non‑R&D available (maximum allowed)
            max_nonrnd = nonrnd_hours_array[i, j]
            nonrnd_remainder = max_nonrnd - nonrnd_alloc

            # For R&D, assume the full research hours would be available if no Non‑R&D were used.
            rnd_remainder = available - rnd_alloc

            # print(f"Date {d_str}:")
            # print(f"  Total Available Research Hours: {available:6.2f} hrs")
            # print("  [R&D]")
            # print(f"    Allocated R&D:                {rnd_alloc:6.2f} hrs")
            # print(f"    R&D Remainder:                {rnd_remainder:6.2f} hrs")
            # print("  [Non-R&D]")
            # print(f"    Maximum Allowed Non-R&D:      {max_nonrnd:6.2f} hrs")
            # print(f"    Allocated Non-R&D:            {nonrnd_alloc:6.2f} hrs")
            # print(f"    Non-R&D Remainder:            {nonrnd_remainder:6.2f} hrs")
            # print("  [Overall]")
            # print(f"    Total Allocated:              {overall_alloc:6.2f} hrs")
            # print(f"    Overall Remainder:            {overall_remainder:6.2f} hrs")
    print("==========================================================================\n")


    # 3. Summary Allocations per Employee (Aggregated Over All Days)
    print("\n================= DIAGNOSTIC: SUMMARY ALLOCATIONS PER EMPLOYEE =================")
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        total_available = 0.0
        total_rnd_alloc = 0.0
        total_nonrnd_alloc = 0.0
        total_max_nonrnd = 0.0
        for j, d_str in enumerate(date_list):
            available = emp.research_hours.get(d_str, 0.0)
            total_available += available
            rnd_alloc = sum(X_val[i, j, p_idx, k_idx] for p_idx in range(num_projects)
                            for k_idx in range(num_topics))
            nonrnd_alloc = float(np.sum(Y_cap_val[i, j, :]) + np.sum(Y_extra_val[i, j, :]))
            total_rnd_alloc += rnd_alloc
            total_nonrnd_alloc += nonrnd_alloc
            total_max_nonrnd += nonrnd_hours_array[i, j]
        overall_alloc = total_rnd_alloc + total_nonrnd_alloc
        overall_remainder = total_available - overall_alloc
        rnd_remainder = total_available - total_rnd_alloc  # (This equals total_nonrnd_alloc if fully allocated)
        nonrnd_remainder = total_max_nonrnd - total_nonrnd_alloc
        print(f"Employee: {emp_name}")
        print(f"  Total Available Research Hours: {total_available:6.2f} hrs")
        print("  [R&D]")
        print(f"    Total Allocated R&D:            {total_rnd_alloc:6.2f} hrs")
        print(f"    Total R&D Remainder:            {rnd_remainder:6.2f} hrs")
        print("  [Non-R&D]")
        print(f"    Total Available Non-R&D:  {total_max_nonrnd:6.2f} hrs")
        print(f"    Total Allocated Non-R&D:        {total_nonrnd_alloc:6.2f} hrs")
        print(f"    Total Non-R&D Remainder:        {nonrnd_remainder:6.2f} hrs")
        print("  [Overall]")
        print(f"    Total Allocated:                {overall_alloc:6.2f} hrs")
        print(f"    Total Overall Remainder:        {overall_remainder:6.2f} hrs")
        print("-------------------------------------------------------------")
    print("==========================================================================\n")

    # 5. Project Cost Details & Topic Allocations
    print("\n================= DIAGNOSTIC: PROJECT COST DETAILS & TOPIC ALLOCATIONS =================")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        computed_cost = final_costs[pname]
        target_cost = target_costs[pname]
        overhead_rate = proj.operational_overhead or 0.0
        rel_dev = 1 - (computed_cost / (target_cost + 1e-6)) if target_cost > 0 else np.nan

        print(f"Project '{pname}':")
        print(f"  Computed Cost:               {computed_cost:.2f}")
        print(f"  Target Cost:                 {target_cost:.2f}")
        print(f"  Overhead Rate:               {100 * overhead_rate:.2f} (%)")
        print(f"  Percent Deviation from Target: {100 * rel_dev:.2f}")

        # Aggregate R&D hours allocated per topic for this project.
        topic_hours = {}
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
