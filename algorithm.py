# Keep imports and round_vector_preserve_sum_two_decimals function as they were
import cvxpy as cp
import numpy as np
from datetime import datetime, timedelta

# --- [Include the round_vector_preserve_sum_two_decimals function from the previous response here] ---
def round_vector_preserve_sum_two_decimals_two_decimals(v, target_total):
    """
    Rounds a 1D numpy array `v` to two decimals such that the sum is equal to `target_total`
    (which is also given to two decimals), using a largest-remainder method.
    """
    # Ensure target_total is treated as having two decimal places for scaling
    target_total = round(target_total, 2)
    
    scale = 100
    v_scaled = v * scale
    # Round target_total * scale to handle potential floating point inaccuracies before casting to int
    target_scaled = int(round(target_total * scale))

    floor_vals = np.floor(v_scaled)
    int_vals = floor_vals.astype(int)
    # Calculate remainder carefully to avoid negative values due to precision
    remainder = v_scaled - floor_vals
    remainder = np.maximum(remainder, 0) # Ensure remainders are non-negative

    current_total = int(np.sum(int_vals)) # Sum of the floored integer parts
    remainder_needed = target_scaled - current_total # How many increments are needed

    # Debug print statements for intermediate values
    # print(f"  Initial vector (scaled): {v_scaled}")
    # print(f"  Target total (scaled): {target_scaled}")
    # print(f"  Floor vals: {floor_vals}")
    # print(f"  Int vals (initial): {int_vals}")
    # print(f"  Remainders: {remainder}")
    # print(f"  Current total (scaled): {current_total}")
    # print(f"  Remainder needed: {remainder_needed}")

    if remainder_needed > 0:
        # Add noise to break ties consistently during sorting
        noise = np.random.rand(len(remainder)) * 1e-9
        # Sort indices by remainder descending (largest remainder first)
        sorted_indices = np.argsort(-(remainder + noise))
        # print(f"  Indices sorted for increment: {sorted_indices}")
        # Increment the values corresponding to the largest remainders
        num_indices_to_increment = min(remainder_needed, len(sorted_indices))
        for i in range(num_indices_to_increment):
            int_vals[sorted_indices[i]] += 1
        # print(f"  Int vals after increment: {int_vals}")

    elif remainder_needed < 0: # Need to decrement
        # Add noise to break ties consistently during sorting
        noise = np.random.rand(len(remainder)) * 1e-9
        # Sort by remainder ascending (smallest remainder first), but prioritize non-zero values
        # If remainder is near zero, use the negative integer value as a secondary sort key (decrement larger numbers first if remainders are tied at zero)
        sort_key = np.where(remainder > 1e-9, remainder, -int_vals.astype(float))
        sorted_indices = np.argsort(sort_key + noise)
        # print(f"  Indices sorted for decrement: {sorted_indices}")

        num_indices_to_decrement = min(abs(remainder_needed), len(sorted_indices))
        decremented_count = 0
        idx_pointer = 0
        # Iterate through sorted indices and decrement if value > 0
        while decremented_count < num_indices_to_decrement and idx_pointer < len(sorted_indices):
            idx = sorted_indices[idx_pointer]
            if int_vals[idx] > 0: # Only decrement if the value is positive
                int_vals[idx] -= 1
                decremented_count += 1
            idx_pointer += 1
        # print(f"  Int vals after decrement: {int_vals}")

    # Convert back by dividing by the scale factor
    result = int_vals / scale
    # print(f"  Result before final sum check: {result}, Sum: {np.sum(result):.4f}")

    # Post-process: Check if the sum exactly matches the target_total due to floating point math.
    computed_sum = np.sum(result)
    # Use a small tolerance consistent with two decimal places (e.g., half of 0.01)
    diff = target_total - computed_sum
    # print(f"  Final check: Computed Sum: {computed_sum:.4f}, Target: {target_total:.4f}, Diff: {diff:.4f}")

    # Correct minor discrepancies by adjusting the element with the largest absolute value
    if abs(diff) > 1e-9: # Use a small epsilon to detect floating point errors
        # print(f"  Adjusting final sum difference: {diff:.4f}")
        if remainder_needed >= 0: # If we were adding or had exact sum initially
             # Find index of the largest value to add the difference
             idx_max = np.argmax(result)
             result[idx_max] += diff
        else: # If we were subtracting
             # Find index of the smallest non-zero value (or largest magnitude negative if applicable) to add the difference
             # This logic might need refinement depending on desired behavior when decrementing.
             # A safer approach might be to adjust the value that was *last* decremented,
             # or simply adjust the largest magnitude element like in the addition case.
             # Let's stick to adjusting the largest value for simplicity here.
             non_zero_indices = np.where(np.abs(result) > 1e-9)[0]
             if len(non_zero_indices) > 0:
                  idx_adjust = non_zero_indices[np.argmax(np.abs(result[non_zero_indices]))]
             else: # If all results are zero (e.g. rounding [0.001, 0.001] to sum 0)
                  idx_adjust = 0 # Adjust the first element
             result[idx_adjust] += diff


    # Final verification (optional debug)
    # final_sum = np.sum(result)
    # if abs(final_sum - target_total) > 1e-5:
    #    print(f"  WARNING: Final sum {final_sum:.4f} still differs significantly from target {target_total:.4f}")
    # print(f"  Final rounded vector: {result}, Final Sum: {np.sum(result):.4f}")

    # Round result again to 2 decimals to clean up potential floating point noise introduced by adjustment
    return np.round(result, 2)


def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    diag_lines = []
    locked_allocations = {"Bridget Burger": "EURIDICE"}

    # --- [Sections 1-6: Setup, Data Prep, Variables - Keep as is] ---
    # Add a common topic "Bridge" available for all personnel and projects.
    common_topic = "Bridge"
    if common_topic not in all_topics:
        all_topics.append(common_topic)

    # Build the date range from start_date to end_date inclusive
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
                r_hours = emp.research_hours.get(d, 0.0)
                nr_hours = emp.nonRnD_hours.get(d, 0.0)
                # Round hours here for the locked output consistency? No, keep internal precision.
                # Rounding only for display/integer checks.
                locked_allocs_output[emp.employee_name][d] = {
                    locked_project: {
                        "topics": {common_topic: r_hours} if r_hours > 1e-6 else {},
                        "nonRnD": nr_hours if nr_hours > 1e-6 else 0.0
                    }
                }
                # Clean up empty project entries
                if not locked_allocs_output[emp.employee_name][d][locked_project]["topics"] and \
                   locked_allocs_output[emp.employee_name][d][locked_project]["nonRnD"] == 0.0:
                    del locked_allocs_output[emp.employee_name][d][locked_project]
        else:
            free_employee_list.append(emp)

    employees = free_employee_list  # Use only free employees for optimization.
    num_days      = len(date_list)
    num_employees = len(employees)
    num_projects  = len(projects)
    num_topics    = len(all_topics)

    if num_employees == 0:
        print("Warning: No free employees to allocate. Returning only locked allocations.")
        # Calculate locked costs based on locked allocations
        locked_costs = {proj.name if proj.name else f"Project_{i}": 0.0 for i, proj in enumerate(projects)}
        for emp in locked_employee_list:
             locked_proj_name = locked_allocations[emp.employee_name]
             for d_str in date_list:
                 day_info = emp.salary_levels.get(d_str, {})
                 base_salary = float(day_info.get("amount", 0.0))
                 hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
                 r_hours = emp.research_hours.get(d_str, 0.0)
                 nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                 locked_costs[locked_proj_name] += (r_hours + nr_hours) * hourly_rate

        return {
            "solver_status": "no_free_employees",
            "final_objective": 0.0,
            "final_costs": locked_costs, # Return calculated locked costs
            "allocations": locked_allocs_output
        }

    # Map topics to indices for easier referencing in CVXPY
    topic_to_idx = {topic: i for i, topic in enumerate(all_topics)}

    # Build salary matrix (num_employees x num_days)
    salary_matrix = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            day_info = emp.salary_levels.get(d_str, {})
            base_salary = float(day_info.get("amount", 0.0))
            if base_salary > 0:
                 salary_matrix[i, j] = (base_salary / 160.0) * 1.25
            else:
                 salary_matrix[i, j] = 0.0

    # Build research and non-R&D hours arrays (num_employees x num_days)
    research_hours_array = np.zeros((num_employees, num_days))
    nonrnd_hours_array   = np.zeros((num_employees, num_days))
    total_avail_rd_free = 0.0
    total_avail_nonrnd_free = 0.0
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            r_hrs = emp.research_hours.get(d_str, 0.0)
            nr_hrs = emp.nonRnD_hours.get(d_str, 0.0)
            research_hours_array[i, j] = r_hrs
            nonrnd_hours_array[i, j]   = nr_hrs
            total_avail_rd_free += r_hrs
            total_avail_nonrnd_free += nr_hrs

    # --- DEBUG INFO: HOURS & SALARY (Free Employees) ---
    print("\n================= DEBUG INFO: HOURS & SALARY (Free Employees) =================")
    grand_total_hours_free = 0.0
    grand_potential_cost_free = 0.0
    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        emp_hours = float(np.sum(research_hours_array[i, :]) + np.sum(nonrnd_hours_array[i, :]))
        daily_costs = salary_matrix[i, :] * (research_hours_array[i, :] + nonrnd_hours_array[i, :])
        emp_cost = float(np.sum(daily_costs))
        grand_total_hours_free += emp_hours
        grand_potential_cost_free += emp_cost
        # --- CHANGE: Round for display ---
        print(f"Employee '{emp_name}': total hours = {round(emp_hours):d}, potential total cost = {round(emp_cost):d}")
    print(f"\nALL FREE EMPLOYEES COMBINED: total R&D hours = {round(total_avail_rd_free):d}")
    print(f"ALL FREE EMPLOYEES COMBINED: total NonR&D hours = {round(total_avail_nonrnd_free):d}")
    print(f"ALL FREE EMPLOYEES COMBINED: total hours = {round(grand_total_hours_free):d}")
    print(f"ALL FREE EMPLOYEES COMBINED: potential total cost = {round(grand_potential_cost_free):d}")
    # --- END CHANGE ---
    print("===============================================================================\n")

    # --- DEBUG INFO: HOURS & SALARY (Locked Employees) ---
    print("\n================= DEBUG INFO: HOURS & SALARY (Locked Employees) =================")
    grand_total_hours_locked = 0.0
    grand_potential_cost_locked = 0.0
    for emp in locked_employee_list:
        emp_name = emp.employee_name
        emp_hours = 0.0
        emp_cost = 0.0
        for d in date_list:
            r_hrs = emp.research_hours.get(d, 0.0)
            nr_hrs = emp.nonRnD_hours.get(d, 0.0)
            day_hours = r_hrs + nr_hrs
            emp_hours += day_hours
            day_info = emp.salary_levels.get(d, {})
            base_salary = float(day_info.get("amount", 0.0))
            daily_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
            emp_cost += daily_rate * day_hours
        grand_total_hours_locked += emp_hours
        grand_potential_cost_locked += emp_cost
        # --- CHANGE: Round for display ---
        print(f"Employee '{emp_name}': total hours = {round(emp_hours):d}, potential total cost = {round(emp_cost):d}")
    print(f"\nALL LOCKED EMPLOYEES COMBINED: total hours = {round(grand_total_hours_locked):d}, potential total cost = {round(grand_potential_cost_locked):d}")
    # --- END CHANGE ---
    print("===============================================================================\n")

    # --- DEBUG INFO: HOURS & SALARY (ALL Employees) ---
    print("\n================= DEBUG INFO: HOURS & SALARY (ALL Employees) =================")
    combined_total_hours = grand_total_hours_free + grand_total_hours_locked
    combined_total_cost = grand_potential_cost_free + grand_potential_cost_locked
    # --- CHANGE: Round for display ---
    print(f"ALL EMPLOYEES COMBINED: total hours = {round(combined_total_hours):d}, potential total cost = {round(combined_total_cost):d}")
    # --- END CHANGE ---
    print("===============================================================================\n")

    # -------------------------------------------------------------------------
    # 6. Define CVXPY Variables for allocations
    # -------------------------------------------------------------------------
    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)  # R&D hours
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)             # Non-R&D hours

    constraints = []

    # (a) R&D allocation: assign all available R&D hours.
    constraints.append(cp.sum(X, axis=(2, 3)) == research_hours_array)

    # (b) Non-R&D allocation: assign all available Non-R&D hours.
    constraints.append(cp.sum(Y, axis=2) == nonrnd_hours_array)

    # (c) Topic constraints: only allowed topics get R&D hours.
    for p_idx, proj in enumerate(projects):
        allowed_topic_indices = [topic_to_idx[t] for t in proj.research_topics if t in topic_to_idx]
        # Ensure common topic is allowed if it exists
        if common_topic in topic_to_idx and topic_to_idx[common_topic] not in allowed_topic_indices:
            allowed_topic_indices.append(topic_to_idx[common_topic])
        # Handle projects with no specific topics - allow only common topic
        if not proj.research_topics and common_topic in topic_to_idx:
             allowed_topic_indices = [topic_to_idx[common_topic]]
        # Fallback if common topic somehow isn't in topic_to_idx (shouldn't happen with current logic)
        elif not allowed_topic_indices and common_topic in topic_to_idx:
             allowed_topic_indices.append(topic_to_idx[common_topic])

        all_topic_indices = set(range(num_topics))
        disallowed_topic_indices = list(all_topic_indices - set(allowed_topic_indices))
        if disallowed_topic_indices:
             # Apply constraint only if there are topics to disallow
             constraints.append(X[:, :, p_idx, disallowed_topic_indices] == 0)

    # -------------------------------------------------------------------------
    # 7. Cost, Non‑R&D, and R&D Penalties
    # -------------------------------------------------------------------------
    project_cost_exprs = {}
    target_costs = {}
    cost_deviation_penalties = []
    nonrnd_frac_penalty_expr = 0  # DCP-Compliant version

    lambda_smooth = 1e-3 # Penalty for hour changes day-to-day per employee/project/topic
    lambda_topic = 1e-2  # Penalty for deviation from target R&D topic ratios
    smooth_penalty = cp.sum_squares(X[:, 1:, :, :] - X[:, :-1, :, :]) # Penalize difference between consecutive days
    topic_penalty = 0    # Initialize topic ratio penalty

    # Calculate average target cost for scaling huber loss M parameter
    all_target_costs = [float(p.grant_contractual or 0.0) for p in projects]
    non_zero_targets = [tc for tc in all_target_costs if tc > 1e-6]
    avg_target_cost = np.mean(non_zero_targets) if non_zero_targets else 1.0 # Use 1.0 if no targets > 0
    avg_target_cost = max(avg_target_cost, 1e-6) # Ensure it's positive
    print(f"--- Average Non-Zero Target Cost (for scaling penalties): {avg_target_cost:.2f} ---") # Keep decimal for context

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        target_costs[pname] = float(proj.grant_contractual or 0.0)

        # Calculate total cost for this project
        rnd_hours_proj_emp_day = cp.sum(X[:, :, p_idx, :], axis=2) # Sum R&D hours across topics for this project
        nonrnd_hours_proj_emp_day = Y[:, :, p_idx]                 # Non-R&D hours for this project
        combined_hours_proj_emp_day = rnd_hours_proj_emp_day + nonrnd_hours_proj_emp_day
        # Element-wise multiplication with salary matrix and sum over employees and days
        cost_expr = cp.sum(cp.multiply(salary_matrix, combined_hours_proj_emp_day))
        project_cost_exprs[pname] = cost_expr

        # Cost Deviation Penalty (Huber Loss)
        target_val = target_costs[pname]
        # Set M for Huber loss relative to average target cost (e.g., 10% of average)
        huber_M_cost = avg_target_cost * 0.1
        # Penalize deviation from target, scaled by average target cost
        cost_deviation_penalties.append(cp.huber(cost_expr - target_val, M=huber_M_cost) / avg_target_cost)

        # Non-R&D Percentage Penalty (Linearized Quadratic Penalty)
        desired_frac = getattr(proj, 'nonrnd_percentage', 0) / 100.0
        if desired_frac >= 0 and desired_frac <= 1: # Only apply if valid percentage
            rnd_hours_proj_total = cp.sum(X[:, :, p_idx, :]) # Total R&D hours for this project
            nonrnd_hours_proj_total = cp.sum(Y[:, :, p_idx]) # Total Non-R&D hours for this project
            # Linear target deviation: (1 - desired_frac) * NonR&D - desired_frac * R&D should be zero
            linear_target_deviation = (1.0 - desired_frac) * nonrnd_hours_proj_total - desired_frac * rnd_hours_proj_total
            # Penalize the square of this deviation
            nonrnd_frac_penalty_expr += cp.square(linear_target_deviation)

        # R&D Topic Ratio Penalty
        if hasattr(proj, 'rnd_topic_ratios') and proj.rnd_topic_ratios:
            # Build target ratio vector based on all_topics order
            target_vector = np.array([proj.rnd_topic_ratios.get(topic, 0) for topic in all_topics])
            sum_target_vector = np.sum(target_vector)
            if sum_target_vector > 1e-6: # Normalize if sum is non-zero
                 target_vector = target_vector / sum_target_vector
                 # Allocated R&D hours per employee, day, topic for this project
                 allocated_rd_topics = X[:, :, p_idx, :]
                 # Total R&D allocated per employee, day for this project
                 total_rd_alloc_per_emp_day = cp.sum(allocated_rd_topics, axis=2, keepdims=True)
                 # Target allocation per topic based on the total R&D and the target ratios
                 # Reshape target_vector for broadcasting: (1, 1, num_topics)
                 target_alloc = total_rd_alloc_per_emp_day @ target_vector.reshape((1, -1)) # Use matrix multiplication for broadcasting
                 # Penalize squared difference between actual and target topic allocations
                 topic_penalty += cp.sum_squares(allocated_rd_topics - target_alloc)


    # -------------------------------------------------------------------------
    # 8. Composite Objective
    # -------------------------------------------------------------------------
    beta  = 1e-2  # Weight for cost deviation penalty
    gamma = 1e-5  # Weight for non-R&D fraction penalty
    reg_lambda = 1e-6 # Weight for L2 regularization

    # L2 Regularization on allocation variables to encourage smaller values (helps stability)
    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))

    # Combine all penalty terms into the objective function
    obj_expr = beta * cp.sum(cost_deviation_penalties) \
               + gamma * nonrnd_frac_penalty_expr \
               + lambda_smooth * smooth_penalty \
               + lambda_topic * topic_penalty \
               + reg_expr
    objective = cp.Minimize(obj_expr)

    # -------------------------------------------------------------------------
    # 9. Solve the Problem with CVXPY
    # -------------------------------------------------------------------------
    problem = cp.Problem(objective, constraints)
    solver_opts = {
        "max_iters": 500000,
        "abstol": 1e-7,
        "reltol": 1e-7,
        "feastol": 1e-7,
        # Potential ECOS specific options if needed
        # "max_iters_ls": 20, # Max iterations for line search
        # "mi_max_iters": 1000 # If using ECOS_BB for mixed-integer problems (not the case here)
    }
    solver_to_use = cp.ECOS # ECOS is generally good for SOCPs which this might reduce to.
    # Alternatives: cp.SCS (can be faster but less accurate), cp.OSQP (good for QPs)
    try:
        print(f"Attempting to solve with {solver_to_use}...")
        # Consider adding verbose=True for more solver output during debugging
        opt_val = problem.solve(solver=solver_to_use, **solver_opts, verbose=False)
        print(f"Solver status: {problem.status}")
        if opt_val is not None and np.isfinite(opt_val):
            print(f"Optimal value: {opt_val:.6e}")
        else:
            print(f"Optimal value: {opt_val} (Non-finite or None)")
    except cp.error.SolverError as e:
        print(f"CVXPY SolverError with {solver_to_use}: {e}")
        print("This might indicate numerical issues, infeasibility, or unboundedness.")
        # Consider trying a different solver or adjusting parameters/problem formulation.
    except Exception as e:
        print(f"General Solver error with {solver_to_use}: {e}")

    # -------------------------------------------------------------------------
    # 10. Extract and Format Results using the continuous solution directly
    # -------------------------------------------------------------------------

    if problem.status not in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE]:
        print(f"ERROR: Solver status is '{problem.status}'. Cannot proceed reliably.")
        # Calculate locked costs even on error if possible
        locked_costs_err = {proj.name if proj.name else f"Project_{i}": 0.0 for i, proj in enumerate(projects)}
        for emp in locked_employee_list:
             locked_proj_name = locked_allocations[emp.employee_name]
             for d_str in date_list:
                 day_info = emp.salary_levels.get(d_str, {})
                 base_salary = float(day_info.get("amount", 0.0))
                 hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
                 r_hours = emp.research_hours.get(d_str, 0.0)
                 nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                 if locked_proj_name in locked_costs_err:
                     locked_costs_err[locked_proj_name] += (r_hours + nr_hours) * hourly_rate
        final_costs_err = {p.name if p.name else f"Project_{i}": locked_costs_err.get(p.name if p.name else f"Project_{i}", float('nan')) for i,p in enumerate(projects)}

        allocs_err = {emp.employee_name: {} for emp in employees} # Empty for free employees
        allocs_err.update(locked_allocs_output) # Include locked allocations
        return {
            "solver_status": problem.status,
            "final_objective": problem.value if problem.value is not None else float('nan'),
            "final_costs": final_costs_err,
            "allocations": allocs_err
        }
    if X.value is None or Y.value is None:
        print(f"ERROR: Solver status '{problem.status}', but variables have no values.")
        # Calculate locked costs even on error if possible (same as above)
        locked_costs_err = {proj.name if proj.name else f"Project_{i}": 0.0 for i, proj in enumerate(projects)}
        for emp in locked_employee_list:
             locked_proj_name = locked_allocations[emp.employee_name]
             for d_str in date_list:
                 day_info = emp.salary_levels.get(d_str, {})
                 base_salary = float(day_info.get("amount", 0.0))
                 hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
                 r_hours = emp.research_hours.get(d_str, 0.0)
                 nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                 if locked_proj_name in locked_costs_err:
                     locked_costs_err[locked_proj_name] += (r_hours + nr_hours) * hourly_rate
        final_costs_err = {p.name if p.name else f"Project_{i}": locked_costs_err.get(p.name if p.name else f"Project_{i}", float('nan')) for i,p in enumerate(projects)}

        allocs_err = {emp.employee_name: {} for emp in employees} # Empty for free employees
        allocs_err.update(locked_allocs_output) # Include locked allocations
        return {
            "solver_status": problem.status + "_VAR_NONE",
            "final_objective": problem.value if problem.value is not None else float('nan'),
            "final_costs": final_costs_err,
            "allocations": allocs_err
        }

    # Replace potential Nans/Infs in solution with 0 (might happen with inaccurate solves)
    X_val = np.nan_to_num(X.value)
    Y_val = np.nan_to_num(Y.value)

    # Ensure non-negativity after potential numerical issues
    X_val = np.maximum(X_val, 0)
    Y_val = np.maximum(Y_val, 0)

    print("\n--- Continuous Solution Sanity Check ---")
    cont_alloc_rd_sum = np.sum(X_val)
    cont_alloc_nonrnd_sum = np.sum(Y_val)
    print(f"Total Available R&D (Free Emps):   {total_avail_rd_free:.4f}")
    print(f"Total Allocated R&D (Continuous):  {cont_alloc_rd_sum:.4f}")
    print(f"Total Available NonR&D (Free Emps):{total_avail_nonrnd_free:.4f}")
    print(f"Total Allocated NonR&D (Continuous):{cont_alloc_nonrnd_sum:.4f}")
    rd_diff = abs(cont_alloc_rd_sum - total_avail_rd_free)
    nonrnd_diff = abs(cont_alloc_nonrnd_sum - total_avail_nonrnd_free)
    # Use a slightly larger tolerance for check due to solver inaccuracies
    if rd_diff > 1e-2 or nonrnd_diff > 1e-2:
        print(f"WARNING: Continuous allocation sum deviates significantly! R&D diff: {rd_diff:.2e}, NonR&D diff: {nonrnd_diff:.2e}")
    else:
        print("Continuous allocation sums match available hours within reasonable tolerance.")
    print("--------------------------------------\n")

    allocations = {} # For free employees first
    # Recalculate R&D hours per employee/day from the potentially adjusted X_val
    # This ensures the rounding target matches the (potentially corrected) solution values.
    research_hours_array_from_X = np.sum(X_val, axis=(2, 3))

    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        allocations[emp_name] = {}
        for j, d_str in enumerate(date_list):
            # Use the original available hours as the target for rounding,
            # as constraints enforce this sum.
            target_rd_today = research_hours_array[i, j]
            target_nonrnd_today = nonrnd_hours_array[i, j]

            # Only create entries for days where hours were available OR allocated
            # Check against original availability AND check if any allocation exists after rounding
            if target_rd_today > 1e-6 or target_nonrnd_today > 1e-6:
                day_allocations = {} # Temporary dict for the day

                # --- Sum-preserving rounding for non-R&D across projects for this day ---
                nonrnd_vector = Y_val[i, j, :]  # shape: (num_projects,)
                # Target sum is the available non-R&D for this employee/day
                nonrnd_rounded = round_vector_preserve_sum_two_decimals_two_decimals(nonrnd_vector, target_nonrnd_today)

                # --- Sum-preserving rounding for R&D across ALL projects/topics for this day ---
                # Flatten the R&D allocation for this emp/day across projects and topics
                # Shape: (num_projects * num_topics)
                rd_vector_flat = X_val[i, j, :, :].flatten()
                # Target sum is the available R&D for this employee/day
                rd_rounded_flat = round_vector_preserve_sum_two_decimals_two_decimals(rd_vector_flat, target_rd_today)
                # Reshape back to (num_projects, num_topics)
                rd_rounded_matrix = rd_rounded_flat.reshape((num_projects, num_topics))

                # --- Aggregate results into the output format ---
                day_has_allocation = False
                for p_idx, proj in enumerate(projects):
                    pname = proj.name if proj.name else f"Project_{p_idx}"
                    topic_allocs = {}

                    # Get the rounded R&D values for this project
                    rd_rounded_proj_topics = rd_rounded_matrix[p_idx, :]
                    for k_idx, topic_name in enumerate(all_topics):
                        # Use the already rounded value directly. Check against small epsilon.
                        if rd_rounded_proj_topics[k_idx] > 1e-7:
                            topic_allocs[topic_name] = rd_rounded_proj_topics[k_idx]

                    # Use the already rounded non-R&D value directly. Check against small epsilon.
                    nonrnd_val = nonrnd_rounded[p_idx]

                    if topic_allocs or nonrnd_val > 1e-7:
                        day_allocations[pname] = {
                            "topics": topic_allocs,
                            "nonRnD": nonrnd_val if nonrnd_val > 1e-7 else 0.0 # Store 0 if effectively zero
                        }
                        day_has_allocation = True # Mark that this day has content

                # Only add the day to the main allocations if it has non-zero rounded allocations
                if day_has_allocation:
                    allocations[emp_name][d_str] = day_allocations


    # Merge pre-assigned locked allocations (handles locked employees)
    for emp_name, daily_allocs in locked_allocs_output.items():
        if emp_name not in allocations:
            allocations[emp_name] = {}
        for d_str, project_allocs in daily_allocs.items():
            if d_str not in allocations[emp_name]:
                allocations[emp_name][d_str] = {}
            # Merge project data, ensuring locked data overwrites potentially empty entries
            for pname, data in project_allocs.items():
                 # Only add if there are topics or non-zero nonRnD
                 if data.get("topics", {}) or data.get("nonRnD", 0.0) > 1e-7:
                     allocations[emp_name][d_str][pname] = data


    # --- [Diagnostics Section: Overall Allocations Check] ---
    header = "\n================= DIAGNOSTIC: OVERALL ALLOCATIONS (Rounded Values) =================="
    print(header)
    diag_lines.append(header)
    overall_alloc_rd = 0.0 # Use float for accumulation
    overall_alloc_nonrnd = 0.0 # Use float for accumulation
    overall_avail_rd = 0.0
    overall_avail_nonrnd = 0.0

    all_emps_combined = locked_employee_list + free_employee_list
    for emp in all_emps_combined:
        emp_name = emp.employee_name
        for d_str in date_list:
            # Accumulate available hours directly from employee objects
            overall_avail_rd += emp.research_hours.get(d_str, 0.0)
            overall_avail_nonrnd += emp.nonRnD_hours.get(d_str, 0.0)
            # Accumulate allocated hours from the final 'allocations' dictionary
            if emp_name in allocations and d_str in allocations[emp_name]:
                for pname, data in allocations[emp_name][d_str].items():
                    overall_alloc_rd += sum(data.get("topics", {}).values())
                    overall_alloc_nonrnd += data.get("nonRnD", 0)

    # --- CHANGE: Round values before printing and checking ---
    rounded_overall_avail_rd = round(overall_avail_rd)
    rounded_overall_alloc_rd = round(overall_alloc_rd)
    rounded_overall_avail_nonrnd = round(overall_avail_nonrnd)
    rounded_overall_alloc_nonrnd = round(overall_alloc_nonrnd)

    msg = f"Overall R&D      : Total available = {rounded_overall_avail_rd:d} hrs, Total allocated = {rounded_overall_alloc_rd:d} hrs"
    print(msg)
    diag_lines.append(msg)
    msg = f"Overall Non‑R&D  : Total available = {rounded_overall_avail_nonrnd:d} hrs, Total allocated = {rounded_overall_alloc_nonrnd:d} hrs"
    print(msg)
    diag_lines.append(msg)

    # --- CHANGE: Check rounded values against tolerance ---
    # Compare rounded integers. Tolerance of 1.0 means they must be exactly equal.
    tolerance = 1.0
    if abs(rounded_overall_alloc_rd - rounded_overall_avail_rd) >= tolerance or abs(rounded_overall_alloc_nonrnd - rounded_overall_avail_nonrnd) >= tolerance:
         warning_msg = f"WARNING: Overall rounded allocated hours deviate from rounded available hours by >= {tolerance:.0f} hr."
         print(warning_msg)
         diag_lines.append(warning_msg)
    else:
         msg = "Overall rounded allocated hours match rounded available hours."
         print(msg)
         diag_lines.append(msg)
    # --- END CHANGE ---
    footer = "==========================================================================================="
    print(footer)
    diag_lines.append(footer)

    # --- Diagnostics: Project Cost Breakdown & Topic Allocations ---
    header = "\n================= DIAGNOSTIC: PROJECT COST DETAILS & TOPIC ALLOCATIONS ================="
    print(header)
    diag_lines.append(header)
    grand_total_cost = 0.0
    grand_target_cost = 0.0
    # Calculate final costs based on the OPTIMIZER'S continuous solution values
    # Also calculate costs based on the ROUNDED allocation values for comparison/reporting
    final_project_costs_solver = {}
    final_project_costs_rounded = {}

    # Calculate costs from solver's continuous values
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        try:
            # Cost from solver's perspective (using continuous X.value, Y.value)
            cost_val = project_cost_exprs[pname].value
            final_project_costs_solver[pname] = float(cost_val) if cost_val is not None and np.isfinite(cost_val) else 0.0
        except Exception as e:
            print(f"Warning: Error evaluating solver cost for {pname}: {e}")
            final_project_costs_solver[pname] = float("nan")

    # Calculate costs from the final rounded 'allocations' dictionary
    # This requires iterating through the allocations and applying salary rates
    for p_idx, proj in enumerate(projects):
         pname = proj.name if proj.name else f"Project_{p_idx}"
         proj_cost_rounded = 0.0
         for emp_name_iter, daily_allocs in allocations.items():
              # Find the corresponding employee object to get salary info
              emp_obj = next((e for e in all_emps_combined if e.employee_name == emp_name_iter), None)
              if not emp_obj: continue # Should not happen

              for d_str, project_data in daily_allocs.items():
                   if pname in project_data:
                        day_info = emp_obj.salary_levels.get(d_str, {})
                        base_salary = float(day_info.get("amount", 0.0))
                        hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0

                        alloc_data = project_data[pname]
                        r_hours = sum(alloc_data.get("topics", {}).values())
                        nr_hours = alloc_data.get("nonRnD", 0.0)
                        proj_cost_rounded += (r_hours + nr_hours) * hourly_rate
         final_project_costs_rounded[pname] = proj_cost_rounded

    # --- CHANGE: Use Rounded Costs and Hours for Display ---
    info_msg = "(Note: Costs below are based on the final rounded allocations, Solver cost in brackets)"
    print(info_msg)
    diag_lines.append(info_msg)

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        # Use rounded cost for primary display, solver cost for comparison
        computed_cost_rounded = final_project_costs_rounded.get(pname, 0.0)
        computed_cost_solver = final_project_costs_solver.get(pname, float('nan'))
        target_cost = target_costs.get(pname, 0.0)

        # --- CHANGE: Round costs for display ---
        rounded_computed_cost_rounded = round(computed_cost_rounded)
        rounded_computed_cost_solver = round(computed_cost_solver) if not np.isnan(computed_cost_solver) else 'N/A'
        rounded_target_cost = round(target_cost)
        # --- END CHANGE ---

        grand_total_cost += computed_cost_rounded # Accumulate rounded cost for grand total
        grand_target_cost += target_cost

        # Keep relative deviation based on the continuous solver cost for consistency with optimization goal
        rel_dev_percent_solver = float('nan')
        if not np.isnan(computed_cost_solver):
             if target_cost > 1e-6:
                 rel_dev_percent_solver = ((computed_cost_solver / target_cost) - 1) * 100
             elif computed_cost_solver > 1e-6:
                 rel_dev_percent_solver = float('inf') # Infinite deviation if target is zero but cost is positive
             else:
                 rel_dev_percent_solver = 0.0 # Zero deviation if both are zero

        msg = f"Project '{pname}':"
        print(msg)
        diag_lines.append(msg)
        # --- CHANGE: Display rounded integer costs ---
        msg = f"  Computed Cost (Rounded): {rounded_computed_cost_rounded:10d} | Target Cost: {rounded_target_cost:10d} [Solver: {rounded_computed_cost_solver}]"
        print(msg)
        diag_lines.append(msg)
        if not np.isnan(rel_dev_percent_solver):
            msg = f"  Relative Cost Deviation (Solver): {rel_dev_percent_solver:+.1f} %" # Keep one decimal for percentage
        else:
            msg = "  Relative Cost Deviation (Solver): N/A"
        print(msg)
        diag_lines.append(msg)

        # Calculate total hours per project from the 'allocations' dictionary
        topic_hours = {}
        total_proj_rd_hours = 0.0
        total_proj_nonrnd_hours = 0.0
        for emp_name_iter in allocations:
            for d_str in date_list:
                if d_str in allocations[emp_name_iter] and pname in allocations[emp_name_iter][d_str]:
                    alloc_data = allocations[emp_name_iter][d_str][pname]
                    current_nonrnd = alloc_data.get("nonRnD", 0.0)
                    total_proj_nonrnd_hours += current_nonrnd
                    for topic, hours in alloc_data.get("topics", {}).items():
                        topic_hours[topic] = topic_hours.get(topic, 0.0) + hours
                        total_proj_rd_hours += hours

        # --- CHANGE: Round hours for display ---
        rounded_total_proj_rd_hours = round(total_proj_rd_hours)
        rounded_total_proj_nonrnd_hours = round(total_proj_nonrnd_hours)

        msg = f"  Total R&D Hours (Rounded):   {rounded_total_proj_rd_hours:6d}"
        print(msg)
        diag_lines.append(msg)
        msg = f"  Total Non-R&D Hours (Rounded): {rounded_total_proj_nonrnd_hours:6d}"
        print(msg)
        diag_lines.append(msg)
        if topic_hours:
            msg = "  Topic Allocations (Rounded):"
            print(msg)
            diag_lines.append(msg)
            sorted_topics = sorted(topic_hours.items(), key=lambda item: item[1], reverse=True)
            for topic, hours in sorted_topics:
                 # --- CHANGE: Round topic hours for display ---
                 rounded_topic_hours = round(hours)
                 # Only display if rounded hours > 0
                 if rounded_topic_hours > 0:
                    topic_msg = f"    {topic:20s}: {rounded_topic_hours:6d} hrs"
                    print(topic_msg)
                    diag_lines.append(topic_msg)
        separator = "-------------------------------------------------------------"
        print(separator)
        diag_lines.append(separator)
    # --- END Cost/Hour Display Changes ---

    # --- CHANGE: Round grand totals for display ---
    rounded_grand_total_cost = round(grand_total_cost) # Based on sum of rounded project costs
    rounded_grand_target_cost = round(grand_target_cost)

    msg = f"\nGrand Total Computed Cost (Rounded): {rounded_grand_total_cost:12d}"
    print(msg)
    diag_lines.append(msg)
    msg = f"Grand Total Target Cost:          {rounded_grand_target_cost:12d}"
    print(msg)
    diag_lines.append(msg)

    # Keep overall relative deviation based on solver's continuous costs
    grand_total_cost_solver = sum(v for v in final_project_costs_solver.values() if not np.isnan(v))
    grand_rel_dev_percent_solver = float('nan')
    if grand_target_cost > 1e-6:
        grand_rel_dev_percent_solver = ((grand_total_cost_solver / grand_target_cost) - 1) * 100
    elif grand_total_cost_solver > 1e-6:
        grand_rel_dev_percent_solver = float('inf')
    else:
        grand_rel_dev_percent_solver = 0.0

    if not np.isnan(grand_rel_dev_percent_solver):
        msg = f"Overall Relative Deviation (Solver Cost):{grand_rel_dev_percent_solver:+.1f} %" # Keep one decimal
    else:
        msg = "Overall Relative Deviation (Solver Cost): N/A"
    print(msg)
    diag_lines.append(msg)
    # --- END CHANGE ---
    footer = "=========================================================================================="
    print(footer)
    diag_lines.append(footer)

    # At the end, join all diagnostic lines and include them in the returned result.
    diagnostics_str = "\n".join(diag_lines)
    return {
        "solver_status": problem.status,
        "final_objective": problem.value if problem.value is not None else float('nan'),
        # Return the costs calculated from the solver's continuous results
        "final_costs": final_project_costs_solver,
        # Return the allocations dictionary (contains 2-decimal rounded values)
        "allocations": allocations,
        "diagnostics": diagnostics_str # Appended diagnostic information with integer formatting
    }