import math
import cvxpy as cp
import numpy as np
import itertools
import sys
import io
import time

from datetime import datetime, timedelta

from config import SalaryConfig, AlgorithmConfig, LockedAllocations, ResearchTopics

"""
ECOS (Interior-Point Method)
ECOS reformulates the problem as a “homogeneous self-dual” cone program and then uses a primal–dual interior-point method to solve it. It keeps both the original (primal) and the dual variables strictly inside the feasible region and takes Newton-style steps—adjusting step lengths in a predictor–corrector fashion—to satisfy the optimality (KKT) conditions. This typically converges in a few dozen iterations with high accuracy for medium-sized problems.

SCS (Operator Splitting / ADMM)
Instead of Newton steps, SCS applies a first-order operator-splitting algorithm (a variant of ADMM) to the same self-dual embedding. It breaks the problem into two simple sub-steps—projecting onto the cone constraints, then taking a linear least-squares update—and alternates between them. Because each iteration is just matrix–vector multiplies and simple projections, SCS can handle very large problems using modest memory, but it often takes hundreds to thousands of iterations to reach moderate accuracy.
"""

# ================= DEBUG HELPERS =========================================
_constraint_labels = []          # parallel lists
_constraints_store = []

_spinner = itertools.cycle("⠁⠂⠄⡀⢀⣀⣠⣄⡤⡄⡆")
def _spin(msg, stdout_buf):
    stdout_buf.write("\r" + msg + " " + next(_spinner))
    stdout_buf.flush()


def add(label, constr):
    """register a labelled constraint and return the same object"""
    _constraint_labels.append(label)
    _constraints_store.append(constr)
    return constr


def top_violations(k=10, tol=1e-6):
    """largest absolute gaps among all constraints"""
    bad = []
    for lab, c in zip(_constraint_labels, _constraints_store):
        try:
            gap = float(np.max(np.abs(c.violation())))
            if gap > tol:
                bad.append((lab, gap))
        except Exception:
            pass
    return sorted(bad, key=lambda t: t[1], reverse=True)[:k]


def append_failure_report(problem, msg, diag):
    diag += ["", "========== FAILURE REPORT ==========",
             f"Status  : {problem.status}",
             f"Message : {msg.strip()}"]
    for lab, gap in top_violations():
        diag.append(f"{lab:40s}  gap = {gap:.3e}")
    diag.append("====================================")
# =========================================================================


def round_vector_preserve_sum_two_decimals_two_decimals(v, target_total):
    """
    Rounds a 1D numpy array `v` to two decimals such that the sum is equal to `target_total`
    (which is also given to two decimals), using a largest-remainder method.
    Uses deterministic tie-breaking based on index order for reproducibility.
    """
    target_total = round(target_total, 2)
    scale = 100
    v_scaled = v * scale
    target_scaled = int(round(target_total * scale))

    floor_vals = np.floor(v_scaled)
    int_vals = floor_vals.astype(int)
    remainder = v_scaled - floor_vals
    remainder = np.maximum(remainder, 0)

    current_total = int(np.sum(int_vals))
    remainder_needed = target_scaled - current_total

    if remainder_needed > 0:
        tie_breaker = np.arange(len(remainder), dtype=float) * 1e-12
        sorted_indices = np.lexsort((tie_breaker, -remainder))
        num_indices_to_increment = min(remainder_needed, len(sorted_indices))
        for i in range(num_indices_to_increment):
            int_vals[sorted_indices[i]] += 1
    elif remainder_needed < 0:
        tie_breaker = np.arange(len(remainder), dtype=float) * 1e-12
        sorted_indices = np.lexsort((-tie_breaker, remainder))
        num_indices_to_decrement = min(abs(remainder_needed), len(sorted_indices))
        decremented_count = 0
        idx_pointer = 0
        while decremented_count < num_indices_to_decrement and idx_pointer < len(sorted_indices):
            idx = sorted_indices[idx_pointer]
            if int_vals[idx] > 0:
                int_vals[idx] -= 1
                decremented_count += 1
            idx_pointer += 1

    result = int_vals / scale

    computed_sum = np.sum(result)
    diff = target_total - computed_sum

    if abs(diff) > 1e-9:
        if remainder_needed >= 0:
            idx_max = np.argmax(result)
            result[idx_max] += diff
        else:
            non_zero_indices = np.where(np.abs(result) > 1e-9)[0]
            if len(non_zero_indices) > 0:
                idx_adjust = non_zero_indices[np.argmax(np.abs(result[non_zero_indices]))]
            else:
                idx_adjust = 0
            result[idx_adjust] += diff

    return np.round(result, 2)


def run_allocation_algorithm(employees_arg, projects_arg, start_date, end_date, all_topics_arg, initial_costs=None):
    _buf = io.StringIO()
    _old_stdout = sys.stdout
    sys.stdout = _buf

    diag_lines = []
    locked_allocations = LockedAllocations.ALLOCATIONS.copy()

    if initial_costs is None:
        initial_costs = {}

    if initial_costs:
        diag_lines.append("================= CONCATENATION WITH PREVIOUS RUN =================\n")
        diag_lines.append("Starting from previous costs (concatenating with previous report):\n")
        for proj_name, cost in initial_costs.items():
            diag_lines.append(f"  {proj_name}: {cost:,.0f} ISK\n")
        diag_lines.append("These costs will be added to the current allocation.\n")
        diag_lines.append("================================================================\n\n")
        print("[CONCATENATION] Starting allocation with previous costs:")
        for proj_name, cost in initial_costs.items():
            print(f"[CONCATENATION]   {proj_name}: {cost:,.0f} ISK")

    global _constraint_labels, _constraints_store
    _constraint_labels.clear()
    _constraints_store.clear()

    employees_orig = employees_arg[:]
    projects = projects_arg[:]
    all_topics = all_topics_arg[:]

    bridge_topic = ResearchTopics.BRIDGE_TOPIC
    if bridge_topic not in all_topics:
        all_topics.append(bridge_topic)

    for proj in projects:
        allowed = getattr(proj, 'allowed_topics', [])
        if bridge_topic not in allowed:
            allowed.append(bridge_topic)
        proj.allowed_topics = allowed

    dt_start = datetime.strptime(start_date, "%m-%d-%Y")
    dt_end = datetime.strptime(end_date, "%m-%d-%Y")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%m-%d-%Y"))
        current += timedelta(days=1)

    locked_employee_list = []
    free_employee_list = []
    locked_allocs_output = {}
    for emp in employees_orig:
        if emp.employee_name in locked_allocations:
            locked_employee_list.append(emp)
            locked_project_name = locked_allocations[emp.employee_name]
            locked_allocs_output[emp.employee_name] = {}
            for d in date_list:
                r_hours = emp.research_hours.get(d, 0.0)
                nr_hours = emp.nonRnD_hours.get(d, 0.0)
                locked_allocs_output[emp.employee_name][d] = {
                    locked_project_name: {
                        "topics": {bridge_topic: r_hours} if r_hours > 1e-6 else {},
                        "nonRnD": nr_hours if nr_hours > 1e-6 else 0.0
                    }
                }
                if not locked_allocs_output[emp.employee_name][d][locked_project_name]["topics"] and \
                   locked_allocs_output[emp.employee_name][d][locked_project_name]["nonRnD"] == 0.0:
                    del locked_allocs_output[emp.employee_name][d][locked_project_name]
        else:
            free_employee_list.append(emp)

    employees = free_employee_list
    num_days = len(date_list)
    num_employees = len(employees)
    num_projects = len(projects)
    num_topics = len(all_topics)

    if num_employees == 0 and not locked_employee_list:
        print("Warning: No employees (free or locked) to allocate. Returning empty.")
        return {
            "solver_status": "no_employees_to_allocate",
            "final_objective": 0.0,
            "final_costs": {proj.name if proj.name else f"Project_{i}": 0.0 for i, proj in enumerate(projects)},
            "allocations": {}
        }

    if num_employees == 0 and locked_employee_list:
        print("Warning: No free employees to allocate. Returning only locked allocations.")
        locked_costs = {proj.name if proj.name else f"Project_{i}": 0.0 for i, proj in enumerate(projects)}
        for emp in locked_employee_list:
            locked_proj_name = locked_allocations[emp.employee_name]
            for d_str in date_list:
                day_info = emp.salary_levels.get(d_str, {})
                base_salary = float(day_info.get("amount", 0.0))
                hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                r_hours = emp.research_hours.get(d_str, 0.0)
                nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                if locked_proj_name in locked_costs:
                    locked_costs[locked_proj_name] += (r_hours + nr_hours) * hourly_rate
                else:
                    print(f"Warning: Locked project '{locked_proj_name}' not in project list for cost calculation.")

        return {
            "solver_status": "no_free_employees",
            "final_objective": 0.0,
            "final_costs": locked_costs,
            "allocations": locked_allocs_output
        }


    salary_matrix = np.zeros((num_employees, num_days))
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            day_info = emp.salary_levels.get(d_str, {})
            base_salary = float(day_info.get("amount", 0.0))
            if base_salary > 0:
                salary_matrix[i, j] = SalaryConfig.calculate_hourly_rate(base_salary)
            else:
                salary_matrix[i, j] = 0.0

    research_hours_array = np.zeros((num_employees, num_days))
    nonrnd_hours_array = np.zeros((num_employees, num_days))
    total_avail_rd_free = 0.0
    total_avail_nonrnd_free = 0.0
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            r_hrs = emp.research_hours.get(d_str, 0.0)
            nr_hrs = emp.nonRnD_hours.get(d_str, 0.0)
            research_hours_array[i, j] = r_hrs
            nonrnd_hours_array[i, j] = nr_hrs
            total_avail_rd_free += r_hrs
            total_avail_nonrnd_free += nr_hrs

    print("\n================= DEBUG INFO: HOURS & SALARY (Free Employees) =================")
    grand_total_hours_free = 0.0
    grand_potential_cost_free = 0.0
    if num_employees > 0:
        for i, emp in enumerate(employees):
            emp_name = emp.employee_name
            emp_hours = float(np.sum(research_hours_array[i, :]) + np.sum(nonrnd_hours_array[i, :]))
            daily_costs = salary_matrix[i, :] * (research_hours_array[i, :] + nonrnd_hours_array[i, :])
            emp_cost = float(np.sum(daily_costs))
            grand_total_hours_free += emp_hours
            grand_potential_cost_free += emp_cost
            print(f"Employee '{emp_name}': total hours = {round(emp_hours):d},  total cost = {round(emp_cost):d}")
        print(f"\nALL FREE EMPLOYEES COMBINED: total R&D hours = {round(total_avail_rd_free):d}")
        print(f"ALL FREE EMPLOYEES COMBINED: total NonR&D hours = {round(total_avail_nonrnd_free):d}")
        print(f"ALL FREE EMPLOYEES COMBINED: total hours = {round(grand_total_hours_free):d}")
        print(f"ALL FREE EMPLOYEES COMBINED:  total cost = {round(grand_potential_cost_free):d}")
    else:
        print("No free employees for this breakdown.")
    print("===============================================================================\n")

    print("\n================= DEBUG INFO: HOURS & SALARY (Locked Employees) =================")
    grand_total_hours_locked = 0.0
    grand_potential_cost_locked = 0.0
    total_avail_rd_locked = 0.0
    total_avail_nonrnd_locked = 0.0
    if locked_employee_list:
        for emp in locked_employee_list:
            emp_name = emp.employee_name
            emp_hours = 0.0
            emp_cost = 0.0
            emp_rd_hours = 0.0
            emp_nonrnd_hours = 0.0
            for d_str in date_list:
                r_hrs = emp.research_hours.get(d_str, 0.0)
                nr_hrs = emp.nonRnD_hours.get(d_str, 0.0)
                day_hours = r_hrs + nr_hrs
                emp_hours += day_hours
                emp_rd_hours += r_hrs
                emp_nonrnd_hours += nr_hrs
                day_info = emp.salary_levels.get(d_str, {})
                base_salary = float(day_info.get("amount", 0.0))
                daily_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                emp_cost += daily_rate * day_hours
            grand_total_hours_locked += emp_hours
            grand_potential_cost_locked += emp_cost
            total_avail_rd_locked += emp_rd_hours
            total_avail_nonrnd_locked += emp_nonrnd_hours
            print(f"Employee '{emp_name}': total hours = {round(emp_hours):d},  total cost = {round(emp_cost):d}")
        print(f"\nALL LOCKED EMPLOYEES COMBINED: total R&D hours = {round(total_avail_rd_locked):d}")
        print(f"ALL LOCKED EMPLOYEES COMBINED: total NonR&D hours = {round(total_avail_nonrnd_locked):d}")
        print(f"ALL LOCKED EMPLOYEES COMBINED: total hours = {round(grand_total_hours_locked):d},  total cost = {round(grand_potential_cost_locked):d}")
    else:
        print("No locked employees for this breakdown.")
    print("===============================================================================\n")

    print("\n================= DEBUG INFO: HOURS & SALARY (ALL Employees) =================")
    combined_total_hours = grand_total_hours_free + grand_total_hours_locked
    combined_total_cost = grand_potential_cost_free + grand_potential_cost_locked
    combined_total_rd_hours = total_avail_rd_free + total_avail_rd_locked
    combined_total_nonrnd_hours = total_avail_nonrnd_free + total_avail_nonrnd_locked
    print(f"ALL EMPLOYEES COMBINED: total R&D hours = {round(combined_total_rd_hours):d}")
    print(f"ALL EMPLOYEES COMBINED: total NonR&D hours = {round(combined_total_nonrnd_hours):d}")
    print(f"ALL EMPLOYEES COMBINED: total hours = {round(combined_total_hours):d}")
    print(f"ALL EMPLOYEES COMBINED:  total cost = {round(combined_total_cost):d}")
    print("===============================================================================\n")

    print("\n================= DEBUG INFO: PROJECT TARGETS & LOCKED CONTRIBUTIONS =================")
    if not projects:
        print("No projects defined.")
    else:
        for proj in projects:
            proj_name = proj.name if proj.name else "Unnamed Project"
            target_cost = float(proj.grant_contractual or 0.0)
            print(f"Project '{proj_name}': Target Cost = {round(target_cost):d}")

            current_proj_locked_hours = 0.0
            current_proj_locked_cost = 0.0
            current_proj_locked_rd_hours = 0.0
            current_proj_locked_nonrnd_hours = 0.0
            found_locked_for_proj = False

            for emp in locked_employee_list:
                if locked_allocations.get(emp.employee_name) == proj_name:
                    found_locked_for_proj = True
                    emp_proj_hours = 0.0
                    emp_proj_cost = 0.0
                    emp_proj_rd_hours = 0.0
                    emp_proj_nonrnd_hours = 0.0
                    for d_str in date_list:
                        r_hrs = emp.research_hours.get(d_str, 0.0)
                        nr_hrs = emp.nonRnD_hours.get(d_str, 0.0)
                        day_hours = r_hrs + nr_hrs
                        emp_proj_hours += day_hours
                        emp_proj_rd_hours += r_hrs
                        emp_proj_nonrnd_hours += nr_hrs

                        day_info = emp.salary_levels.get(d_str, {})
                        base_salary = float(day_info.get("amount", 0.0))
                        daily_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                        emp_proj_cost += daily_rate * day_hours

                    print(f"  Locked Employee '{emp.employee_name}': total hours = {round(emp_proj_hours):d} (R&D: {round(emp_proj_rd_hours):d}, NonR&D: {round(emp_proj_nonrnd_hours):d}),  cost = {round(emp_proj_cost):d}")
                    current_proj_locked_hours += emp_proj_hours
                    current_proj_locked_cost += emp_proj_cost
                    current_proj_locked_rd_hours += emp_proj_rd_hours
                    current_proj_locked_nonrnd_hours += emp_proj_nonrnd_hours

            if found_locked_for_proj:
                print(f"  Project '{proj_name}' LOCKED TOTALS: hours = {round(current_proj_locked_hours):d} (R&D: {round(current_proj_locked_rd_hours):d}, NonR&D: {round(current_proj_locked_nonrnd_hours):d}), cost = {round(current_proj_locked_cost):d}")
            else:
                print(f"  No employees directly locked to Project '{proj_name}'.")
            print("  ----------------------------------------------------------")
    print("====================================================================================\n")

    print("\n================= DEBUG INFO: HOURS & COSTS PER PROJECT (Employee Availability) =================")
    if not projects:
        print("No projects defined.")
    else:
        for proj in projects:
            proj_name_display = proj.name if proj.name else "Unnamed Project"
            target_cost_display = float(proj.grant_contractual or 0.0)
            print(f"Project '{proj_name_display}': Target Cost = {round(target_cost_display):d}")
            print("  Employee Contributions (based on their total available hours):")

            project_total_hours_from_all_emps = 0.0
            project_total_cost_from_all_emps = 0.0
            project_total_rd_hours_from_all_emps = 0.0
            project_total_non_rd_hours_from_all_emps = 0.0

            for emp_idx, emp_obj in enumerate(employees_orig):
                emp_total_hours = 0.0
                emp_total_cost = 0.0
                emp_total_rd_hours = 0.0
                emp_total_non_rd_hours = 0.0

                is_locked_to_this_project = emp_obj.employee_name in locked_allocations and locked_allocations[emp_obj.employee_name] == proj_name_display
                is_locked_elsewhere = emp_obj.employee_name in locked_allocations and locked_allocations[emp_obj.employee_name] != proj_name_display
                locked_status_info = ""
                if is_locked_to_this_project:
                    locked_status_info = " (Locked to this project)"
                elif is_locked_elsewhere:
                    locked_status_info = f" (Locked to {locked_allocations[emp_obj.employee_name]})"

                for d_str_inner in date_list:
                    r_hrs_inner = emp_obj.research_hours.get(d_str_inner, 0.0)
                    nr_hrs_inner = emp_obj.nonRnD_hours.get(d_str_inner, 0.0)
                    day_hours_inner = r_hrs_inner + nr_hrs_inner

                    emp_total_hours += day_hours_inner
                    emp_total_rd_hours += r_hrs_inner
                    emp_total_non_rd_hours += nr_hrs_inner

                    day_info_inner = emp_obj.salary_levels.get(d_str_inner, {})
                    base_salary_inner = float(day_info_inner.get("amount", 0.0))
                    daily_rate_inner = (base_salary_inner / 160.0) * 1.25 if base_salary_inner > 0 else 0.0
                    emp_total_cost += daily_rate_inner * day_hours_inner

                print(f"    - {emp_obj.employee_name}{locked_status_info}: Total Avail. Hours = {round(emp_total_hours):d} (R&D: {round(emp_total_rd_hours):d}, NonR&D: {round(emp_total_non_rd_hours):d}), Cost of these hours = {round(emp_total_cost):d}")

                project_total_hours_from_all_emps += emp_total_hours
                project_total_cost_from_all_emps += emp_total_cost
                project_total_rd_hours_from_all_emps += emp_total_rd_hours
                project_total_non_rd_hours_from_all_emps += emp_total_non_rd_hours

            print(f"  Overall  Pool for '{proj_name_display}' (sum of all employees' total avail. hours):")
            print(f"    Total Hours = {round(project_total_hours_from_all_emps):d} (R&D: {round(project_total_rd_hours_from_all_emps):d}, NonR&D: {round(project_total_non_rd_hours_from_all_emps):d})")
            print(f"    Associated Cost = {round(project_total_cost_from_all_emps):d}")
            print("  -----------------------------------------------------------------------------------")
    print("==============================================================================================\n")

    print("\n================= DEBUG INFO: PER PROJECT, PER SALARY BRACKET (Summary) =================")
    for proj_obj in projects:
        pname = proj_obj.name if proj_obj.name else f"Project_{projects.index(proj_obj)}"
        print(f"Project: {pname}")

        bracket_to_emps = {}

        for emp in employees_orig:
            unique_pairs = set()
            for d_str in date_list:
                sal_info = emp.salary_levels.get(d_str, {})
                lvl = sal_info.get("level", "").strip() or "UNSPEC"
                base = sal_info.get("amount", 0.0)
                if base <= 0:
                    continue
                hr_rate = round(SalaryConfig.calculate_hourly_rate(base), 2)
                unique_pairs.add((lvl, hr_rate))

            for lvl, hr in unique_pairs:
                bracket_to_emps.setdefault((lvl, hr), set()).add(emp.employee_name)

        if not bracket_to_emps:
            print("  No salary data.")
        else:
            for (lvl, hr) in sorted(bracket_to_emps, key=lambda t: t[1]):
                emp_list = ", ".join(sorted(bracket_to_emps[(lvl, hr)]))
                print(f"  {lvl} ({hr:,.0f} ISK/hr): {emp_list}")

        print("---------------------------------------------------------------------------")
    print("========================================================================================\n")

    X = cp.Variable((num_employees, num_days, num_projects, num_topics), nonneg=True)
    Y = cp.Variable((num_employees, num_days, num_projects), nonneg=True)

    constraints = []

    cost_deviation_penalties = []
    BIG_SLACK_PENALTY = AlgorithmConfig.BIG_SLACK_PENALTY

    constraints.append(
        add("R&D balance all emp/day (HARD)",
            cp.sum(cp.sum(X, axis=3), axis=2) == research_hours_array)
    )
    constraints.append(
        add("Non-R&D balance all emp/day (HARD)",
            cp.sum(Y, axis=2) == nonrnd_hours_array)
    )


    all_target_costs_vals = [float(p.grant_contractual or 0.0) for p in projects]
    non_zero_targets = [tc for tc in all_target_costs_vals if tc > 1e-6]
    avg_target_cost = np.mean(non_zero_targets) if non_zero_targets else 1.0
    avg_target_cost = max(avg_target_cost, 1e-6)

    for p_idx, proj in enumerate(projects):
        allowed_topics = set(getattr(proj, 'allowed_topics', []))
        disallowed_topic_indices = [i for i, topic in enumerate(all_topics) if topic not in allowed_topics]
        if disallowed_topic_indices:
            slack_topics = cp.Variable(nonneg=True,
                                       name=f"slack_topic_{p_idx}")
            constraints.append(
                add(f"Topic whitelist (soft) proj={proj.name or p_idx}",
                    cp.sum(X[:, :, p_idx, disallowed_topic_indices])
                    <= slack_topics)
            )
            proj_target = float(proj.grant_contractual or 0.0)
            proj_target = max(proj_target, 1e-6)
            cost_deviation_penalties.append(
                BIG_SLACK_PENALTY * slack_topics / proj_target
            )

    project_cost_exprs = {}
    target_costs = {}
    nonrnd_frac_penalty_expr = 0

    lambda_smooth = AlgorithmConfig.LAMBDA_SMOOTH
    lambda_topic = AlgorithmConfig.LAMBDA_TOPIC
    smooth_penalty = cp.sum_squares(X[:, 1:, :, :] - X[:, :-1, :, :])
    topic_penalty = 0
    slacks = {}

    all_target_costs_vals = [float(p.grant_contractual or 0.0) for p in projects]
    non_zero_targets = [tc for tc in all_target_costs_vals if tc > 1e-6]
    avg_target_cost = np.mean(non_zero_targets) if non_zero_targets else 1.0
    avg_target_cost = max(avg_target_cost, 1e-6)
    print(f"--- Average Non-Zero Target Cost (for scaling penalties): {avg_target_cost:.2f} ---")

    free_cost_cap = np.sum(
        salary_matrix * (research_hours_array + nonrnd_hours_array)
    )
    locked_cost_cap = 0.0
    for emp in locked_employee_list:
        for d_str in date_list:
            base = float(emp.salary_levels.get(d_str, {}).get("amount", 0.0))
            rate = SalaryConfig.calculate_hourly_rate(base)
            hrs = emp.research_hours.get(d_str, 0.0) + \
                  emp.nonRnD_hours.get(d_str, 0.0)
            locked_cost_cap += hrs * rate

    print("\n=== COST-CAPACITY VS. PROJECT LOWER-BOUNDS ===")
    print(f"Max cost that *could* be spent this period : "
          f"{free_cost_cap + locked_cost_cap:,.0f} ISK")
    print(f"    from free   employees : {free_cost_cap:,.0f}")
    print(f"    from locked employees : {locked_cost_cap:,.0f}")

    for p in projects:
        need = float(p.grant_contractual or 0.0)
        print(f"  – {p.name:<12s} needs ≥ {need:,.0f}  (target={need:,.0f})")
    print("===========================================================\n")

    required_total_cost = 0.0
    for p in projects:
        tgt = float(p.grant_contractual or 0.0)
        mf = float(p.matching_fund_value or 0.0)
        if mf and p.matching_fund_type.lower() == 'percentage':
            required_total_cost += tgt * (1 + mf / 100.0)
        else:
            required_total_cost += tgt + mf

    hard_capacity = free_cost_cap + locked_cost_cap
    if required_total_cost > hard_capacity + 1e-6:
        gap = required_total_cost - hard_capacity
        print("⚠️  WARNING  ⚠️  Requested MINIMUM spend exceeds absolute capacity "
              f"by {gap:,.0f} ISK. The optimisation will continue, "
              "but expect large slacks in the result.\n")

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        target_costs[pname] = float(proj.grant_contractual or 0.0)

        locked_cost_const = 0.0
        for emp in locked_employee_list:
            if locked_allocations.get(emp.employee_name) == pname:
                for d_str in date_list:
                    base = float(emp.salary_levels
                                 .get(d_str, {})
                                 .get("amount", 0.0))
                    rate = (base / 160.0) * 1.25 if base > 0 else 0.0
                    r_hrs = emp.research_hours.get(d_str, 0.0)
                    nr_hrs = emp.nonRnD_hours.get(d_str, 0.0)
                    locked_cost_const += (r_hrs + nr_hrs) * rate

        rnd_hours_proj_emp_day = cp.sum(X[:, :, p_idx, :], axis=2)
        nonrnd_hours_proj_emp_day = Y[:, :, p_idx]
        combined_hours_proj_emp_day = rnd_hours_proj_emp_day + nonrnd_hours_proj_emp_day
        cost_expr_free = cp.sum(cp.multiply(salary_matrix, combined_hours_proj_emp_day))

        cost_expr_total = cost_expr_free + locked_cost_const
        project_cost_exprs[pname] = cost_expr_total

        match_raw = float(proj.matching_fund_value or 0.0)
        if match_raw > 0:
            if proj.matching_fund_type.lower() == "percentage":
                match_amount = match_raw / 100.0 * target_costs[pname]
            else:
                match_amount = match_raw

            required_total = target_costs[pname] + match_amount

            slack_under_spend = cp.Variable(nonneg=True)
            slacks[pname] = slack_under_spend
            constraints.append(
                add(f"match-fund soft ≥  ({pname})",
                    cost_expr_total + slack_under_spend >= required_total)
            )
            proj_target = target_costs[pname]
            proj_target = max(proj_target, 1e-6)
            cost_deviation_penalties.append(
                BIG_SLACK_PENALTY * slack_under_spend / proj_target
            )

        target_val = target_costs[pname]
        huber_M_cost = int(round(avg_target_cost * 0.1))
        huber_M_cost = max(1, huber_M_cost)
        cost_deviation_penalties.append(cp.huber(cost_expr_total - target_val, M=huber_M_cost) / avg_target_cost)

        desired_frac = getattr(proj, 'nonrnd_percentage', 0) / 100.0
        if 0 <= desired_frac <= 1:
            rnd_hours_proj_total = cp.sum(X[:, :, p_idx, :])
            nonrnd_hours_proj_total = cp.sum(Y[:, :, p_idx])
            linear_target_deviation = (1.0 - desired_frac) * nonrnd_hours_proj_total - desired_frac * rnd_hours_proj_total
            nonrnd_frac_penalty_expr += cp.square(linear_target_deviation)

        if hasattr(proj, 'rnd_topic_ratios') and proj.rnd_topic_ratios:
            target_vector = np.array([proj.rnd_topic_ratios.get(topic, 0) for topic in all_topics])
            sum_target_vector = np.sum(target_vector)
            if sum_target_vector > 1e-6:
                target_vector = target_vector / sum_target_vector
                allocated_rd_topics = X[:, :, p_idx, :]
                total_rd_alloc_per_emp_day = cp.sum(allocated_rd_topics, axis=2, keepdims=True)
                target_alloc = total_rd_alloc_per_emp_day @ target_vector.reshape((1, -1))
                topic_penalty += cp.sum_squares(allocated_rd_topics - target_alloc)

    beta = 1e-2
    gamma = 1e-5
    reg_lambda = 1e-6

    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))

    obj_expr = beta * cp.sum(cost_deviation_penalties) \
               + gamma * nonrnd_frac_penalty_expr \
               + lambda_smooth * smooth_penalty \
               + lambda_topic * topic_penalty \
               + reg_expr
    objective = cp.Minimize(obj_expr)

    problem = cp.Problem(objective, constraints)

    def _attempt(prob, slv, opts, label):
        """Run <solver>; always return (val, status, err_msg)."""
        t0, err_msg, val = time.time(), None, None
        try:
            _spin(f"Solving with {label} …", _buf)
            val = prob.solve(solver=slv, **opts)
        except cp.SolverError as e:
            err_msg = str(e)
            val = prob.value
        finally:
            status = prob.status
            print(f"\rSolving with {label} finished in "
                  f"{time.time()-t0:6.2f}s  (status: {status})")
            return val, status, err_msg

    opts = {
        cp.ECOS: dict(max_iters=20_000, abstol=1e-7,
                      reltol=1e-7, feastol=1e-7, verbose=True),
        cp.SCS: dict(max_iters=20_000, eps=5e-4, verbose=True),
        cp.CLARABEL: dict(max_iter=10_000, verbose=True),
    }

    solver_chain = [cp.ECOS, cp.SCS, cp.CLARABEL]
    solver_chain = [s for s in solver_chain if s in cp.installed_solvers()]

    opt_val, stat, err = math.inf, None, None
    for cand in solver_chain:
        opt_val, stat, err = _attempt(problem, cand, opts[cand], str(cand))
        if stat in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) \
                or (isinstance(opt_val, (int, float)) and math.isfinite(opt_val)):
            break

    if stat is None:
        stat = "solver_failed"

    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        print("⚠️  Solver returned", problem.status,
              "— continuing with last iterate (slacks will show).")

    if X.value is None or Y.value is None:
        append_failure_report(problem, "variables have no value", diag_lines)
        print(f"ERROR: Solver status '{problem.status}', but variables have no values.")
        locked_costs_err = {proj.name if proj.name else f"Project_{i}": 0.0 for i, p_obj in enumerate(projects)}
        for emp in locked_employee_list:
            locked_proj_name = locked_allocations[emp.employee_name]
            for d_str in date_list:
                day_info = emp.salary_levels.get(d_str, {})
                base_salary = float(day_info.get("amount", 0.0))
                hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                r_hours = emp.research_hours.get(d_str, 0.0)
                nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                if locked_proj_name in locked_costs_err:
                    locked_costs_err[locked_proj_name] += (r_hours + nr_hours) * hourly_rate
        final_costs_err_payload = {p.name if p.name else f"Project_{i}": locked_costs_err.get(p.name if p.name else f"Project_{i}", 0.0) for i, p in enumerate(projects)}

        allocs_err = {}
        allocs_err.update(locked_allocs_output)
        status_str = str(problem.status) if problem.status else "solver_failed"

        sys.stdout = _old_stdout
        with open("allocation_debug.log", "w") as f:
            f.write(_buf.getvalue())

        return {
            "solver_status": status_str + "_VAR_NONE",
            "final_objective": problem.value if problem.value is not None else float('nan'),
            "final_costs": final_costs_err_payload,
            "allocations": allocs_err,
            "diagnostics": "\n".join(diag_lines) +
                           "\nSolver variables are None; diagnostics might be incomplete."
        }

    X_val = np.nan_to_num(X.value)
    Y_val = np.nan_to_num(Y.value)
    X_val = np.maximum(X_val, 0)
    Y_val = np.maximum(Y_val, 0)

    print("\n--- Enforcing Exact Hour Balance Constraints ---")

    for i in range(num_employees):
        for j in range(num_days):
            target_rd = research_hours_array[i, j]
            allocated_rd = np.sum(X_val[i, j, :, :])

            if target_rd > 1e-6:
                if allocated_rd > 1e-6:
                    scale_factor = target_rd / allocated_rd
                    X_val[i, j, :, :] = X_val[i, j, :, :] * scale_factor
                else:
                    if num_projects > 0 and num_topics > 0:
                        X_val[i, j, :, :] = target_rd / (num_projects * num_topics)
            else:
                X_val[i, j, :, :] = 0.0

            target_nonrnd = nonrnd_hours_array[i, j]
            allocated_nonrnd = np.sum(Y_val[i, j, :])

            if target_nonrnd > 1e-6:
                if allocated_nonrnd > 1e-6:
                    scale_factor = target_nonrnd / allocated_nonrnd
                    Y_val[i, j, :] = Y_val[i, j, :] * scale_factor
                else:
                    if num_projects > 0:
                        Y_val[i, j, :] = target_nonrnd / num_projects
            else:
                Y_val[i, j, :] = 0.0

    print("--- Continuous Solution Constraint Verification (Free Employees) ---")
    cont_alloc_rd_sum = np.sum(X_val)
    cont_alloc_nonrnd_sum = np.sum(Y_val)
    print(f"Total Available R&D (Free Emps):   {total_avail_rd_free:.4f}")
    print(f"Total Allocated R&D (After Normalization):  {cont_alloc_rd_sum:.4f}")
    print(f"Total Available NonR&D (Free Emps):{total_avail_nonrnd_free:.4f}")
    print(f"Total Allocated NonR&D (After Normalization):{cont_alloc_nonrnd_sum:.4f}")
    rd_diff = abs(cont_alloc_rd_sum - total_avail_rd_free)
    nonrnd_diff = abs(cont_alloc_nonrnd_sum - total_avail_nonrnd_free)

    max_rd_violation = 0.0
    max_nonrnd_violation = 0.0
    for i in range(num_employees):
        for j in range(num_days):
            allocated_rd_emp_day = np.sum(X_val[i, j, :, :])
            target_rd_emp_day = research_hours_array[i, j]
            rd_violation = abs(allocated_rd_emp_day - target_rd_emp_day)
            max_rd_violation = max(max_rd_violation, rd_violation)

            allocated_nonrnd_emp_day = np.sum(Y_val[i, j, :])
            target_nonrnd_emp_day = nonrnd_hours_array[i, j]
            nonrnd_violation = abs(allocated_nonrnd_emp_day - target_nonrnd_emp_day)
            max_nonrnd_violation = max(max_nonrnd_violation, nonrnd_violation)

    print(f"Maximum per-employee/day R&D violation: {max_rd_violation:.2e}")
    print(f"Maximum per-employee/day NonR&D violation: {max_nonrnd_violation:.2e}")

    if rd_diff > 1e-6 or nonrnd_diff > 1e-6 or max_rd_violation > 1e-6 or max_nonrnd_violation > 1e-6:
        print("WARNING: Unexpected numerical precision issues after normalization!")
        print(f"  Total R&D diff: {rd_diff:.2e}, Total NonR&D diff: {nonrnd_diff:.2e}")
        print(f"  Max per-emp/day violations: R&D={max_rd_violation:.2e}, NonR&D={max_nonrnd_violation:.2e}")
        print("  (This may indicate a bug - normalization should always work mathematically)")
        diag_lines.append("WARNING: Numerical precision issues after normalization (unexpected)")
    else:
        print("✓ Hour balance constraints exactly satisfied (within numerical precision)")
    print("-----------------------------------------------------------\n")

    allocations = {}

    for i, emp in enumerate(employees):
        emp_name = emp.employee_name
        allocations[emp_name] = {}
        for j, d_str in enumerate(date_list):
            target_rd_today = research_hours_array[i, j]
            target_nonrnd_today = nonrnd_hours_array[i, j]

            if target_rd_today > 1e-6 or target_nonrnd_today > 1e-6:
                day_allocations = {}
                nonrnd_vector = Y_val[i, j, :]
                nonrnd_rounded = round_vector_preserve_sum_two_decimals_two_decimals(nonrnd_vector, target_nonrnd_today)

                rd_vector_flat = X_val[i, j, :, :].flatten()
                rd_rounded_flat = round_vector_preserve_sum_two_decimals_two_decimals(rd_vector_flat, target_rd_today)
                rd_rounded_matrix = rd_rounded_flat.reshape((num_projects, num_topics))

                day_has_allocation = False
                for p_idx, proj in enumerate(projects):
                    pname = proj.name if proj.name else f"Project_{p_idx}"
                    topic_allocs = {}
                    rd_rounded_proj_topics = rd_rounded_matrix[p_idx, :]
                    for k_idx, topic_name in enumerate(all_topics):
                        if rd_rounded_proj_topics[k_idx] > 1e-7:
                            topic_allocs[topic_name] = rd_rounded_proj_topics[k_idx]

                    nonrnd_val = nonrnd_rounded[p_idx]
                    if topic_allocs or nonrnd_val > 1e-7:
                        day_allocations[pname] = {
                            "topics": topic_allocs,
                            "nonRnD": nonrnd_val if nonrnd_val > 1e-7 else 0.0
                        }
                        day_has_allocation = True

                if day_has_allocation:
                    allocations[emp_name][d_str] = day_allocations

    for emp_name, daily_allocs in locked_allocs_output.items():
        if emp_name not in allocations:
            allocations[emp_name] = {}
        for d_str, project_allocs in daily_allocs.items():
            if d_str not in allocations[emp_name]:
                allocations[emp_name][d_str] = {}
            for pname, data in project_allocs.items():
                if data.get("topics", {}) or data.get("nonRnD", 0.0) > 1e-7:
                    allocations[emp_name][d_str][pname] = data

    print("\n================= DEBUG INFO: PER PROJECT, PER EMPLOYEE, PER SALARY BRACKET (ALLOCATED HOURS) =================")
    for proj_obj in projects:
        pname = proj_obj.name or f"Project_{projects.index(proj_obj)}"
        print(f"Project: {pname}")

        for emp in employees_orig:
            emp_name = emp.employee_name
            days_here = [
                d for d in date_list
                if emp_name in allocations
                and d in allocations[emp_name]
                and pname in allocations[emp_name][d]
            ]
            if not days_here:
                continue

            bracket_totals = {}

            for d in days_here:
                day_pay = emp.salary_levels.get(d, {})
                base = float(day_pay.get("amount", 0.0))
                rate = round(SalaryConfig.calculate_hourly_rate(base), 2) if base > 0 else 0.0

                alloc = allocations[emp_name][d][pname]
                rd_h = sum(alloc["topics"].values())
                nrd_h = alloc["nonRnD"]
                all_h = rd_h + nrd_h

                if rate not in bracket_totals:
                    bracket_totals[rate] = {"tot": 0.0, "rd": 0.0, "nrd": 0.0}

                bracket_totals[rate]["tot"] += all_h
                bracket_totals[rate]["rd"] += rd_h
                bracket_totals[rate]["nrd"] += nrd_h

            print(f"  Employee: {emp_name}")
            for rate, data in sorted(bracket_totals.items()):
                print(f"    @{rate:,.2f} ISK/hr → "
                      f"{data['tot']:.2f} h  (R&D {data['rd']:.2f} h, "
                      f"Non-R&D {data['nrd']:.2f} h)")
    print("----------------------------------------------------------------")
    print("================================================================\n")

    header = "\n================= DIAGNOSTIC: OVERALL ALLOCATIONS (Rounded Values) =================="
    diag_lines.append(header)
    overall_alloc_rd = 0.0
    overall_alloc_nonrnd = 0.0
    overall_avail_rd = 0.0
    overall_avail_nonrnd = 0.0

    for emp in employees_orig:
        for d_str in date_list:
            overall_avail_rd += emp.research_hours.get(d_str, 0.0)
            overall_avail_nonrnd += emp.nonRnD_hours.get(d_str, 0.0)

            if emp.employee_name in allocations and d_str in allocations[emp.employee_name]:
                for pname, data in allocations[emp.employee_name][d_str].items():
                    overall_alloc_rd += sum(data.get("topics", {}).values())
                    overall_alloc_nonrnd += data.get("nonRnD", 0)

    rounded_overall_avail_rd = round(overall_avail_rd)
    rounded_overall_alloc_rd = round(overall_alloc_rd)
    rounded_overall_avail_nonrnd = round(overall_avail_nonrnd)
    rounded_overall_alloc_nonrnd = round(overall_alloc_nonrnd)

    msg = f"Overall R&D      : Total available = {rounded_overall_avail_rd:d} hrs, Total allocated = {rounded_overall_alloc_rd:d} hrs"
    diag_lines.append(msg)
    msg = f"Overall Non-R&D  : Total available = {rounded_overall_avail_nonrnd:d} hrs, Total allocated = {rounded_overall_alloc_nonrnd:d} hrs"
    diag_lines.append(msg)

    rd_diff_exact = abs(overall_alloc_rd - overall_avail_rd)
    nonrnd_diff_exact = abs(overall_alloc_nonrnd - overall_avail_nonrnd)
    rd_diff_rounded = abs(rounded_overall_alloc_rd - rounded_overall_avail_rd)
    nonrnd_diff_rounded = abs(rounded_overall_alloc_nonrnd - rounded_overall_avail_nonrnd)

    max_emp_day_rd_violation = 0.0
    max_emp_day_nonrnd_violation = 0.0
    for emp in employees_orig:
        for d_str in date_list:
            avail_rd = emp.research_hours.get(d_str, 0.0)
            avail_nonrnd = emp.nonRnD_hours.get(d_str, 0.0)

            alloc_rd = 0.0
            alloc_nonrnd = 0.0
            if emp.employee_name in allocations and d_str in allocations[emp.employee_name]:
                for pname, data in allocations[emp.employee_name][d_str].items():
                    alloc_rd += sum(data.get("topics", {}).values())
                    alloc_nonrnd += data.get("nonRnD", 0.0)

            rd_viol = abs(alloc_rd - avail_rd)
            nonrnd_viol = abs(alloc_nonrnd - avail_nonrnd)
            max_emp_day_rd_violation = max(max_emp_day_rd_violation, rd_viol)
            max_emp_day_nonrnd_violation = max(max_emp_day_nonrnd_violation, nonrnd_viol)

    strict_tolerance = 0.01
    if (rd_diff_exact > strict_tolerance or nonrnd_diff_exact > strict_tolerance or
            max_emp_day_rd_violation > strict_tolerance or max_emp_day_nonrnd_violation > strict_tolerance):
        error_msg = "CRITICAL ERROR: Hour balance constraints violated after normalization and rounding!"
        error_msg += "\n  This should not happen - normalization ensures exact balance mathematically."
        error_msg += f"\n  Total R&D difference: {rd_diff_exact:.4f} hrs (exact), {rd_diff_rounded:d} hrs (rounded)"
        error_msg += f"\n  Total NonR&D difference: {nonrnd_diff_exact:.4f} hrs (exact), {nonrnd_diff_rounded:d} hrs (rounded)"
        error_msg += f"\n  Max per-employee/day R&D violation: {max_emp_day_rd_violation:.4f} hrs"
        error_msg += f"\n  Max per-employee/day NonR&D violation: {max_emp_day_nonrnd_violation:.4f} hrs"
        error_msg += "\n  This likely indicates a bug in the rounding function."
        diag_lines.append(error_msg)
        print(f"\n{error_msg}")
        raise ValueError("Hour balance constraints violated - this indicates a bug in normalization/rounding!")
    else:
        msg = "✓ Hour balance constraints exactly satisfied"
        msg += f"\n  R&D: {rd_diff_exact:.4f} hrs difference (within {strict_tolerance:.2f} hr rounding tolerance)"
        msg += f"\n  NonR&D: {nonrnd_diff_exact:.4f} hrs difference (within {strict_tolerance:.2f} hr rounding tolerance)"
        msg += f"\n  Max per-employee/day violations: R&D={max_emp_day_rd_violation:.4f}, NonR&D={max_emp_day_nonrnd_violation:.4f}"
        diag_lines.append(msg)
    footer = "==========================================================================================="
    diag_lines.append(footer)
    for line in diag_lines[diag_lines.index(header):]:
        print(line)

    header = "\n================= DIAGNOSTIC: PROJECT COST DETAILS & TOPIC ALLOCATIONS ================="
    diag_lines.append(header)
    grand_total_cost_rounded_final = 0.0
    grand_target_cost = 0.0

    final_project_costs_solver = {}
    final_project_costs_rounded = {}

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        final_project_costs_solver[pname] = initial_costs.get(pname, 0.0)
        if pname in initial_costs:
            diag_lines.append(f"[CONCATENATION] Project '{pname}' starting from previous cost: {initial_costs[pname]:,.0f} ISK\n")
            print(f"[CONCATENATION] Project '{pname}' starting from previous cost: {initial_costs[pname]:,.0f} ISK")
        for emp in locked_employee_list:
            if locked_allocations.get(emp.employee_name) == pname:
                for d_str in date_list:
                    day_info = emp.salary_levels.get(d_str, {})
                    base_salary = float(day_info.get("amount", 0.0))
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                    r_hours = emp.research_hours.get(d_str, 0.0)
                    nr_hours = emp.nonRnD_hours.get(d_str, 0.0)
                    final_project_costs_solver[pname] += (r_hours + nr_hours) * hourly_rate

    if num_employees > 0:
        for p_idx, proj in enumerate(projects):
            pname = proj.name if proj.name else f"Project_{p_idx}"
            normalized_cost_free = 0.0
            for i, emp in enumerate(employees):
                emp_name = emp.employee_name
                for j, d_str in enumerate(date_list):
                    day_info = emp.salary_levels.get(d_str, {})
                    base_salary = float(day_info.get("amount", 0.0))
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)

                    rnd_hours = np.sum(X_val[i, j, p_idx, :])
                    nonrnd_hours = Y_val[i, j, p_idx]
                    normalized_cost_free += (rnd_hours + nonrnd_hours) * hourly_rate

            final_project_costs_solver[pname] += normalized_cost_free

            if pname in initial_costs:
                total_after = final_project_costs_solver[pname]
                previous = initial_costs[pname]
                new_cost = total_after - previous
                diag_lines.append(f"[CONCATENATION] Project '{pname}': Previous={previous:,.0f} + New (Locked+Free)={new_cost:,.0f} = Total={total_after:,.0f} ISK\n")
                print(f"[CONCATENATION] Project '{pname}': Previous={previous:,.0f} + New (Locked+Free)={new_cost:,.0f} = Total={total_after:,.0f} ISK")

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        proj_cost_rounded = initial_costs.get(pname, 0.0)
        for emp_name_iter, daily_allocs in allocations.items():
            emp_obj = next((e for e in employees_orig if e.employee_name == emp_name_iter), None)
            if not emp_obj:
                continue

            for d_str, project_data in daily_allocs.items():
                if pname in project_data:
                    day_info = emp_obj.salary_levels.get(d_str, {})
                    base_salary = float(day_info.get("amount", 0.0))
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)

                    alloc_data = project_data[pname]
                    r_hours = sum(alloc_data.get("topics", {}).values())
                    nr_hours = alloc_data.get("nonRnD", 0.0)
                    proj_cost_rounded += (r_hours + nr_hours) * hourly_rate
        final_project_costs_rounded[pname] = proj_cost_rounded

    info_msg = "(Note: Rounded costs are from final rounded allocations. Solver costs are from normalized continuous solution, calculated after normalization to match actual allocations.)"
    diag_lines.append(info_msg)

    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        computed_cost_rounded = final_project_costs_rounded.get(pname, 0.0)
        computed_cost_solver = final_project_costs_solver.get(pname, float('nan'))
        target_cost_val = target_costs.get(pname, 0.0)

        rounded_computed_cost_rounded = round(computed_cost_rounded)
        rounded_computed_cost_solver_display = round(computed_cost_solver) if not np.isnan(computed_cost_solver) else 'N/A'
        rounded_target_cost = round(target_cost_val)

        grand_total_cost_rounded_final += computed_cost_rounded
        grand_target_cost += target_cost_val

        rel_dev_percent_solver = float('nan')
        if not np.isnan(computed_cost_solver):
            if target_cost_val > 1e-6:
                rel_dev_percent_solver = ((computed_cost_solver / target_cost_val) - 1) * 100
            elif computed_cost_solver > 1e-6:
                rel_dev_percent_solver = float('inf')
            else:
                rel_dev_percent_solver = 0.0

        msg = f"Project '{pname}':"
        diag_lines.append(msg)
        msg = f"  Computed Cost (Rounded): {rounded_computed_cost_rounded:10d} | Target Cost: {rounded_target_cost:10d} [Solver: {rounded_computed_cost_solver_display}]"
        diag_lines.append(msg)
        if not np.isnan(rel_dev_percent_solver):
            msg = f"  Relative Cost Deviation (Solver): {rel_dev_percent_solver:+.1f} %"
        else:
            msg = "  Relative Cost Deviation (Solver): N/A"
        diag_lines.append(msg)

        topic_hours = {}
        total_proj_rd_hours = 0.0
        total_proj_nonrnd_hours = 0.0
        for emp_name_iter in allocations:
            for d_str in date_list:
                if d_str in allocations[emp_name_iter] and pname in allocations[emp_name_iter][d_str]:
                    alloc_data = allocations[emp_name_iter][d_str][pname]
                    current_nonrnd = alloc_data.get("nonRnD", 0.0)
                    total_proj_nonrnd_hours += current_nonrnd
                    for topic, hours_val in alloc_data.get("topics", {}).items():
                        topic_hours[topic] = topic_hours.get(topic, 0.0) + hours_val
                        total_proj_rd_hours += hours_val

        rounded_total_proj_rd_hours = round(total_proj_rd_hours)
        rounded_total_proj_nonrnd_hours = round(total_proj_nonrnd_hours)

        msg = f"  Total R&D Hours (Rounded):   {rounded_total_proj_rd_hours:6d}"
        diag_lines.append(msg)
        msg = f"  Total Non-R&D Hours (Rounded): {rounded_total_proj_nonrnd_hours:6d}"
        diag_lines.append(msg)
        if topic_hours:
            msg = "  Topic Allocations (Rounded):"
            diag_lines.append(msg)
            sorted_topics = sorted(topic_hours.items(), key=lambda item: item[1], reverse=True)
            for topic, hours_val in sorted_topics:
                rounded_topic_hours = round(hours_val)
                if rounded_topic_hours > 0:
                    topic_msg = f"    {topic:20s}: {rounded_topic_hours:6d} hrs"
                    diag_lines.append(topic_msg)
        separator = "-------------------------------------------------------------"
        diag_lines.append(separator)

    rounded_grand_total_cost_final = round(grand_total_cost_rounded_final)
    rounded_grand_target_cost = round(grand_target_cost)

    msg = f"\nGrand Total Computed Cost (Rounded Allocations): {rounded_grand_total_cost_final:12d}"
    diag_lines.append(msg)
    msg = f"Grand Total Target Cost:                         {rounded_grand_target_cost:12d}"
    diag_lines.append(msg)

    grand_total_cost_solver_sum = sum(v for v in final_project_costs_solver.values() if not np.isnan(v))
    grand_rel_dev_percent_solver = float('nan')
    if grand_target_cost > 1e-6:
        grand_rel_dev_percent_solver = ((grand_total_cost_solver_sum / grand_target_cost) - 1) * 100
    elif grand_total_cost_solver_sum > 1e-6:
        grand_rel_dev_percent_solver = float('inf')
    else:
        grand_rel_dev_percent_solver = 0.0

    if not np.isnan(grand_rel_dev_percent_solver):
        msg = f"Overall Relative Deviation (Sum of Solver Costs vs Sum of Target Costs):{grand_rel_dev_percent_solver:+.1f} %"
    else:
        msg = "Overall Relative Deviation (Sum of Solver Costs vs Sum of Target Costs): N/A"
    diag_lines.append(msg)
    footer = "=========================================================================================="
    diag_lines.append(footer)
    for line in diag_lines[diag_lines.index(header):]:
        print(line)

    diagnostics_str = "\n".join(diag_lines)

    if slacks:
        print("\n=== MATCH-FUND SLACKS (ISK) ===")
        for pname, sl in slacks.items():
            val = sl.value if sl.value is not None else float('nan')
            print(f"  {pname:<15s}: {val:,.2f} ISK")
    else:
        print("\n(No matching-fund rules defined.)")

    sys.stdout = _old_stdout
    with open("allocation_debug.log", "w") as f:
        f.write(_buf.getvalue())

    return {
        "solver_status": problem.status,
        "final_objective": problem.value if problem.value is not None else float('nan'),
        "final_costs": final_project_costs_solver,
        "allocations": allocations,
        "diagnostics": diagnostics_str
    }
