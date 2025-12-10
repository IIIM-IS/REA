import math
import cvxpy as cp  # pyright: ignore[reportMissingImports]
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

_constraint_labels = []
_constraints_store = []

_spinner = itertools.cycle("⠁⠂⠄⡀⢀⣀⣠⣄⡤⡄⡆")
def _spin(msg, stdout_buf):
    stdout_buf.write("\r" + msg + " " + next(_spinner))
    stdout_buf.flush()


def add(label, constr):
    _constraint_labels.append(label)
    _constraints_store.append(constr)
    return constr


def top_violations(k=10, tol=1e-6):
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


def _f(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _pct(x, default: float = 0.0) -> float:
    v = _f(x, default)
    v = max(0.0, v)
    return v / 100.0


def round_vector_preserve_sum_two_decimals_two_decimals(v, target_total):
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
    initial_costs = dict(initial_costs)
    if not initial_costs:
        for idx, proj in enumerate(projects_arg):
            prev_cost = _f(getattr(proj, "previous_spending", 0.0), 0.0)
            if prev_cost > 0.0:
                key = proj.name if proj.name else f"Project_{idx}"
                initial_costs[key] = prev_cost
    else:
        for idx, proj in enumerate(projects_arg):
            key = proj.name if proj.name else f"Project_{idx}"
            if key not in initial_costs:
                prev_cost = _f(getattr(proj, "previous_spending", 0.0), 0.0)
                if prev_cost > 0.0:
                    initial_costs[key] = prev_cost
    if initial_costs:
        diag_lines.append("================= CONCATENATION WITH PREVIOUS RUN =================\n")
        diag_lines.append("Starting from previous costs (concatenating with previous report):\n")
        for proj_name, cost in initial_costs.items():
            diag_lines.append(f"  {proj_name}: {cost:,.0f} ISK\n")
        diag_lines.append("These costs reduce the remaining targets for this run.\n")
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
        allowed = list(getattr(proj, 'allowed_topics', []) or [])
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
                r_hours = _f(emp.research_hours.get(d, 0.0), 0.0)
                nr_hours = _f(emp.nonRnD_hours.get(d, 0.0), 0.0)
                total_available = r_hours + nr_hours
                hours_vec = np.array([r_hours, nr_hours])
                hours_rounded = round_vector_preserve_sum_two_decimals_two_decimals(hours_vec, total_available)
                r_hours_rounded = hours_rounded[0]
                nr_hours_rounded = hours_rounded[1]
                locked_allocs_output[emp.employee_name][d] = {
                    locked_project_name: {
                        "topics": {bridge_topic: r_hours_rounded} if r_hours_rounded > 1e-6 else {},
                        "nonRnD": nr_hours_rounded if nr_hours_rounded > 1e-6 else 0.0
                    }
                }
                if not locked_allocs_output[emp.employee_name][d][locked_project_name]["topics"] and locked_allocs_output[emp.employee_name][d][locked_project_name]["nonRnD"] == 0.0:
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
                base_salary = _f(day_info.get("amount", 0.0), 0.0)
                hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                r_hours = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                nr_hours = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
                if locked_proj_name in locked_costs:
                    locked_costs[locked_proj_name] += (r_hours + nr_hours) * hourly_rate
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
            base_salary = _f(day_info.get("amount", 0.0), 0.0)
            salary_matrix[i, j] = SalaryConfig.calculate_hourly_rate(base_salary) if base_salary > 0.0 else 0.0
    research_hours_array = np.zeros((num_employees, num_days))
    nonrnd_hours_array = np.zeros((num_employees, num_days))
    total_avail_rd_free = 0.0
    total_avail_nonrnd_free = 0.0
    for i, emp in enumerate(employees):
        for j, d_str in enumerate(date_list):
            r_hrs = _f(emp.research_hours.get(d_str, 0.0), 0.0)
            nr_hrs = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
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
                r_hrs = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                nr_hrs = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
                day_hours = r_hrs + nr_hrs
                emp_hours += day_hours
                emp_rd_hours += r_hrs
                emp_nonrnd_hours += nr_hrs
                day_info = emp.salary_levels.get(d_str, {})
                base_salary = _f(day_info.get("amount", 0.0), 0.0)
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
            prev = _f(initial_costs.get(proj_name, 0.0), 0.0)
            base = _f(getattr(proj, "grant_contractual", 0.0), 0.0)
            target_cost = max(base - prev, 0.0)
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
                        r_hrs = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                        nr_hrs = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
                        day_hours = r_hrs + nr_hrs
                        emp_proj_hours += day_hours
                        emp_proj_rd_hours += r_hrs
                        emp_proj_nonrnd_hours += nr_hrs
                        day_info = emp.salary_levels.get(d_str, {})
                        base_salary = _f(day_info.get("amount", 0.0), 0.0)
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
            prev_disp = _f(initial_costs.get(proj_name_display, 0.0), 0.0)
            base_disp = _f(getattr(proj, "grant_contractual", 0.0), 0.0)
            target_cost_display = max(base_disp - prev_disp, 0.0)
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
                    r_hrs_inner = _f(emp_obj.research_hours.get(d_str_inner, 0.0), 0.0)
                    nr_hrs_inner = _f(emp_obj.nonRnD_hours.get(d_str_inner, 0.0), 0.0)
                    day_hours_inner = r_hrs_inner + nr_hrs_inner
                    emp_total_hours += day_hours_inner
                    emp_total_rd_hours += r_hrs_inner
                    emp_total_non_rd_hours += nr_hrs_inner
                    day_info_inner = emp_obj.salary_levels.get(d_str_inner, {})
                    base_salary_inner = _f(day_info_inner.get("amount", 0.0), 0.0)
                    daily_rate_inner = SalaryConfig.calculate_hourly_rate(base_salary_inner) if base_salary_inner > 0 else 0.0
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
                lvl = (sal_info.get("level", "") or "").strip() or "UNSPEC"
                base = _f(sal_info.get("amount", 0.0), 0.0)
                if base <= 0.0:
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
    BIG_SLACK_PENALTY = _f(getattr(AlgorithmConfig, "BIG_SLACK_PENALTY", 1e5), 1e5)
    constraints.append(
        add("R&D balance all emp/day (HARD)",
            cp.sum(cp.sum(X, axis=3), axis=2) == research_hours_array)
    )
    constraints.append(
        add("Non-R&D balance all emp/day (HARD)",
            cp.sum(Y, axis=2) == nonrnd_hours_array)
    )
    all_target_costs_vals = [_f(getattr(p, "grant_contractual", 0.0), 0.0) for p in projects]
    non_zero_targets = [tc for tc in all_target_costs_vals if tc > 1e-6]
    avg_target_cost = np.mean(non_zero_targets) if non_zero_targets else 1.0
    avg_target_cost = max(avg_target_cost, 1e-6)
    for p_idx, proj in enumerate(projects):
        allowed_topics = set(list(getattr(proj, 'allowed_topics', []) or []))
        disallowed_topic_indices = [i for i, topic in enumerate(all_topics) if topic not in allowed_topics]
        if disallowed_topic_indices:
            slack_topics = cp.Variable(nonneg=True, name=f"slack_topic_{p_idx}")
            constraints.append(
                add(f"Topic whitelist (soft) proj={proj.name or p_idx}",
                    cp.sum(X[:, :, p_idx, disallowed_topic_indices]) <= slack_topics)
            )
            proj_target = max(_f(getattr(proj, "grant_contractual", 0.0), 0.0), 1e-6)
            cost_deviation_penalties.append(BIG_SLACK_PENALTY * slack_topics / proj_target)
    project_cost_exprs = {}
    target_costs = {}
    nonrnd_frac_penalty_expr = 0
    lambda_smooth = _f(getattr(AlgorithmConfig, "LAMBDA_SMOOTH", 1e-3), 1e-3)
    lambda_topic = _f(getattr(AlgorithmConfig, "LAMBDA_TOPIC", 5e-3), 5e-3)
    smooth_penalty = cp.sum_squares(X[:, 1:, :, :] - X[:, :-1, :, :])
    topic_penalty = 0
    slacks = {}
    all_target_costs_vals = [_f(getattr(p, "grant_contractual", 0.0), 0.0) for p in projects]
    non_zero_targets = [tc for tc in all_target_costs_vals if tc > 1e-6]
    avg_target_cost = np.mean(non_zero_targets) if non_zero_targets else 1.0
    avg_target_cost = max(avg_target_cost, 1e-6)
    print(f"--- Average Non-Zero Target Cost (for scaling penalties): {avg_target_cost:.2f} ---")
    free_cost_cap = np.sum(salary_matrix * (research_hours_array + nonrnd_hours_array))
    locked_cost_cap = 0.0
    for emp in locked_employee_list:
        for d_str in date_list:
            base = _f(emp.salary_levels.get(d_str, {}).get("amount", 0.0), 0.0)
            rate = SalaryConfig.calculate_hourly_rate(base)
            hrs = _f(emp.research_hours.get(d_str, 0.0), 0.0) + _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
            locked_cost_cap += hrs * rate
    print("\n=== COST-CAPACITY VS. PROJECT LOWER-BOUNDS ===")
    print(f"Max cost that *could* be spent this period : {free_cost_cap + locked_cost_cap:,.0f} ISK")
    print(f"    from free   employees : {free_cost_cap:,.0f}")
    print(f"    from locked employees : {locked_cost_cap:,.0f}")
    for p in projects:
        need = _f(getattr(p, "grant_contractual", 0.0), 0.0)
        print(f"  – {p.name:<12s} needs ≥ {need:,.0f}  (target={need:,.0f})")
    print("===========================================================\n")
    required_total_cost = 0.0
    for p in projects:
        pname = p.name if p.name else ""
        prev = _f(initial_costs.get(pname, 0.0), 0.0)
        base_grant = _f(getattr(p, "grant_contractual", 0.0), 0.0)
        mf = _f(getattr(p, "matching_fund_value", 0.0), 0.0)
        mf_type = (getattr(p, "matching_fund_type", "") or "").lower()
        match_abs = (base_grant * mf / 100.0) if (mf > 0.0 and mf_type == 'percentage') else mf
        overhead_val = _f(getattr(p, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            overhead_amt = overhead_val
        else:
            overhead_amt = 0.0
        total_target = base_grant + match_abs + overhead_amt
        required_total_cost += max(total_target - prev, 0.0)

    hard_capacity = free_cost_cap + locked_cost_cap
    capacity_ratio = hard_capacity / max(required_total_cost, 1e-9)
    
    if required_total_cost > hard_capacity + 1e-6:
        gap = required_total_cost - hard_capacity
        shortfall_pct = (gap / required_total_cost * 100) if required_total_cost > 0 else 0
        print("⚠️  WARNING  ⚠️  Requested MINIMUM spend exceeds absolute capacity "
              f"by {gap:,.0f} ISK ({shortfall_pct:.1f}% shortfall).")
        print(f"   Available capacity: {hard_capacity:,.0f} ISK")
        print(f"   Required capacity:  {required_total_cost:,.0f} ISK")
        print(f"   Capacity ratio:     {capacity_ratio:.1%}")
        print("   The optimisation will continue, but expect large slacks in the result.\n")
        diag_lines.append(f"CAPACITY ANALYSIS: Insufficient capacity - {gap:,.0f} ISK shortfall ({shortfall_pct:.1f}%). Available: {hard_capacity:,.0f} ISK, Required: {required_total_cost:,.0f} ISK.")
    else:
        utilization_pct = (required_total_cost / hard_capacity * 100) if hard_capacity > 0 else 0
        print(f"✓ Capacity check: Available {hard_capacity:,.0f} ISK, Required {required_total_cost:,.0f} ISK ({utilization_pct:.1f}% utilization).\n")
        diag_lines.append(f"CAPACITY ANALYSIS: Sufficient capacity. Available: {hard_capacity:,.0f} ISK, Required: {required_total_cost:,.0f} ISK ({utilization_pct:.1f}% utilization).")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        prev_spend = _f(initial_costs.get(pname, 0.0), 0.0)
        base_grant = _f(getattr(proj, "grant_contractual", 0.0), 0.0)
        
        match_raw = _f(getattr(proj, "matching_fund_value", 0.0), 0.0)
        mf_type = (getattr(proj, "matching_fund_type", "") or "").lower()
        if match_raw > 0.0:
            match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
        else:
            match_abs = 0.0
        
        overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            overhead_amount = overhead_val
        elif overhead_val > 0.0 and overhead_val < 1.0:
            overhead_amount = 0.0
        else:
            overhead_amount = 0.0
        
        base_target = base_grant + match_abs + overhead_amount
        residual_target = max(base_target - prev_spend, 0.0)
        target_costs[pname] = residual_target
        if residual_target <= 1e-9:
            constraints.append(
                add(f"zero residual → no spend ({pname})",
                    cp.sum(X[:, :, p_idx, :]) + cp.sum(Y[:, :, p_idx]) == 0)
            )
            project_cost_exprs[pname] = 0
            continue
        locked_cost_const = 0.0
        for emp in locked_employee_list:
            if locked_allocations.get(emp.employee_name) == pname:
                for d_str in date_list:
                    base = _f(emp.salary_levels.get(d_str, {}).get("amount", 0.0), 0.0)
                    rate = SalaryConfig.calculate_hourly_rate(base) if base > 0 else 0.0
                    r_hrs = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                    nr_hrs = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
                    locked_cost_const += (r_hrs + nr_hrs) * rate
        rnd_hours_proj_emp_day = cp.sum(X[:, :, p_idx, :], axis=2)
        nonrnd_hours_proj_emp_day = Y[:, :, p_idx]
        combined_hours_proj_emp_day = rnd_hours_proj_emp_day + nonrnd_hours_proj_emp_day
        cost_expr_free = cp.sum(cp.multiply(salary_matrix, combined_hours_proj_emp_day))
        direct_cost_expr = cost_expr_free + locked_cost_const
        
        overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            overhead_cost_expr = overhead_val
        elif overhead_val > 0.0 and overhead_val < 1.0:
            overhead_cost_expr = direct_cost_expr * overhead_val
        else:
            overhead_cost_expr = 0.0
        
        cost_expr_total = direct_cost_expr + overhead_cost_expr
        project_cost_exprs[pname] = cost_expr_total

        target_val = residual_target
        over = cp.pos(cost_expr_total - target_val)
        under = cp.pos(target_val - cost_expr_total)
        cost_deviation_penalties.append(
            _f(getattr(AlgorithmConfig, "ALPHA_OVERSHOOT", 5.0), 5.0) * over / max(avg_target_cost, 1e-6)
            + _f(getattr(AlgorithmConfig, "ALPHA_UNDERSHOOT", 1.0), 1.0) * under / max(avg_target_cost, 1e-6)
        )
        slack_over_cap = cp.Variable(nonneg=True, name=f"slack_over_cap_{pname}")
        constraints.append(add(f"soft upper budget cap ({pname})", cost_expr_total <= target_val + slack_over_cap))
        cost_deviation_penalties.append(BIG_SLACK_PENALTY * slack_over_cap / max(target_val, 1e-6))
        desired_frac = _pct(getattr(proj, 'nonrnd_percentage', 0.0), 0.0)
        if 0.0 <= desired_frac <= 1.0:
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
    total_actual_cost = 0
    for v in project_cost_exprs.values():
        total_actual_cost += v
    total_target_cost = float(sum(target_costs.values()))
    band = _f(getattr(AlgorithmConfig, "GLOBAL_BUDGET_BAND", 0.0), 0.0)
    diff = total_actual_cost - total_target_cost
    over_band = cp.pos(diff - band * total_target_cost)
    under_band = cp.pos(-diff - band * total_target_cost)
    cost_deviation_penalties.append(BIG_SLACK_PENALTY * (over_band + under_band) / max(total_target_cost, 1e-6))
    beta = _f(getattr(AlgorithmConfig, "BETA_COST_DEVIATION", 1e-2), 1e-2)
    gamma = _f(getattr(AlgorithmConfig, "GAMMA_NONRND_FRACTION", 1e-5), 1e-5)
    reg_lambda = _f(getattr(AlgorithmConfig, "REGULARIZATION_LAMBDA", 1e-6), 1e-6)
    reg_expr = reg_lambda * (cp.sum_squares(X) + cp.sum_squares(Y))
    obj_expr = beta * cp.sum(cost_deviation_penalties) + gamma * nonrnd_frac_penalty_expr + lambda_smooth * smooth_penalty + lambda_topic * topic_penalty + reg_expr
    objective = cp.Minimize(obj_expr)
    problem = cp.Problem(objective, constraints)

    def _attempt(prob, slv, opts, label):
        """
        Run a single solver attempt.

        Args:
            prob: The cvxpy Problem to solve.
            slv: Solver name as registered in cvxpy.
            opts: Dictionary of solver-specific options.
            label: Human-readable label for logging.

        Returns:
            Tuple[float|None, str|None, str|None]: (objective value, status, error message)
        """
        t0, err_msg, val = time.time(), None, None
        try:
            _spin(f"Solving with {label} …", _buf)
            val = prob.solve(solver=slv, **opts)
        except Exception as e:
            err_msg = str(e)
            val = prob.value
        finally:
            status = prob.status
            print(f"\rSolving with {label} finished in {time.time()-t0:6.2f}s  (status: {status})")
            return val, status, err_msg

    opts = {
        cp.ECOS: dict(
            max_iters=_f(getattr(AlgorithmConfig, "MAX_ITERATIONS_ECOS", 20000), 20000),
            abstol=_f(getattr(AlgorithmConfig, "TOLERANCE_ABSOLUTE", 1e-7), 1e-7),
            reltol=_f(getattr(AlgorithmConfig, "TOLERANCE_RELATIVE", 1e-7), 1e-7),
            feastol=_f(getattr(AlgorithmConfig, "TOLERANCE_FEASIBILITY", 1e-7), 1e-7),
            verbose=True,
            warm_start=True,
        ),
        cp.SCS: dict(
            max_iters=_f(getattr(AlgorithmConfig, "MAX_ITERATIONS_SCS", 20000), 20000),
            eps=_f(getattr(AlgorithmConfig, "TOLERANCE_SCS", 5e-4), 5e-4),
            verbose=True,
            warm_start=True,
        ),
        cp.OSQP: dict(
            max_iter=_f(getattr(AlgorithmConfig, "MAX_ITERATIONS_OSQP", 200000), 200000),
            eps_abs=_f(getattr(AlgorithmConfig, "TOLERANCE_OSQP_ABS", 1e-6), 1e-6),
            eps_rel=_f(getattr(AlgorithmConfig, "TOLERANCE_OSQP_REL", 1e-6), 1e-6),
            verbose=True,
            warm_start=True,
        ),
        cp.CLARABEL: dict(
            max_iter=_f(getattr(AlgorithmConfig, "MAX_ITERATIONS_CLARABEL", 10000), 10000),
            verbose=True,
            warm_start=True,
        ),
    }
    solver_chain = [cp.OSQP, cp.ECOS, cp.SCS, cp.CLARABEL]
    solver_chain = [s for s in solver_chain if s in cp.installed_solvers()]

    opt_val, stat, err = math.inf, None, None
    for cand in solver_chain:
        opt_val, stat, err = _attempt(problem, cand, opts[cand], str(cand))
        if stat in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE) or (isinstance(opt_val, (int, float)) and math.isfinite(opt_val)):
            break

    if (X.value is None or Y.value is None) and problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        try:
            _spin("Solving with default selection …", _buf)
            val = problem.solve(warm_start=True)
            stat = problem.status or stat
            opt_val = val if isinstance(val, (int, float)) else opt_val
            print(f"\rSolving with default selection finished  (status: {stat})")
        except cp.SolverError as e:
            err = str(e)
            print(f"\nDefault solver attempt failed: {err}")
    if stat is None:
        stat = "solver_failed"

    used_fallback = False
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        print("⚠️  Solver returned", problem.status, "— continuing with last iterate (slacks will show).")
    
    solver_has_values = X.value is not None and Y.value is not None
    solver_is_optimal = problem.status in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE)
    
    if not solver_has_values or not solver_is_optimal:
        if not solver_has_values:
            append_failure_report(problem, "variables have no value", diag_lines)
            print(f"ERROR: Solver status '{problem.status}', but variables have no values. Falling back to budget-constrained topic-weighted allocation.")
        else:
            print(f"⚠️  Solver status '{problem.status}' is not optimal. Using fallback allocation to ensure proper target weighting.")
            diag_lines.append(f"FALLBACK TRIGGERED: Solver status '{problem.status}' is not optimal. Using residual-target-weighted allocation instead.")
        X_val = np.zeros((num_employees, num_days, num_projects, num_topics), dtype=float)
        Y_val = np.zeros((num_employees, num_days, num_projects), dtype=float)

        residual = np.array([max(target_costs.get(p.name if p.name else f"Project_{k}", 0.0), 0.0)
                            for k, p in enumerate(projects)], dtype=float)
        if np.sum(residual) <= 1e-9:
            diag_lines.append("FALLBACK: All projects have zero residual target; assigned zero allocation.")
        total_targets = residual.copy()
        original_targets = np.array([_f(getattr(p, "grant_contractual", 0.0), 0.0) for p in projects], dtype=float)
        prev_costs_array = np.array([_f(initial_costs.get(p.name if p.name else f"Project_{k}", 0.0), 0.0)
                                    for k, p in enumerate(projects)], dtype=float)

        topic_weights = np.zeros((num_projects, num_topics), dtype=float)
        for p_idx, proj in enumerate(projects):
            research_topics_list = getattr(proj, "research_topics", []) or []
            allowed_topics_set = set(list(getattr(proj, "allowed_topics", []) or []))
            
            if research_topics_list:
                topics_to_use = [t for t in research_topics_list if t in all_topics]
            else:
                topics_to_use = [t for t in all_topics if t in allowed_topics_set]
            
            if topics_to_use:
                weight_per_topic = 1.0 / len(topics_to_use)
                for t_idx, topic_name in enumerate(all_topics):
                    if topic_name in topics_to_use:
                        topic_weights[p_idx, t_idx] = weight_per_topic
            else:
                for t_idx, topic_name in enumerate(all_topics):
                    if topic_name in allowed_topics_set:
                        topic_weights[p_idx, t_idx] = 1.0 / max(len(allowed_topics_set), 1)

        project_weights = np.zeros(num_projects, dtype=float)
        positive_residual = residual > 1e-9
        if np.sum(positive_residual) > 0:
            project_weights[positive_residual] = residual[positive_residual] / np.sum(residual[positive_residual])
            use_residual = True
        else:
            use_residual = True

        total_available_cost = free_cost_cap
        total_target_cost = np.sum(residual)
        
        if total_target_cost > 1e-9 and total_available_cost > 1e-9:
            capacity_ratio = min(1.0, total_available_cost / total_target_cost)
            if capacity_ratio < 1.0:
                diag_lines.append(f"FALLBACK: Insufficient capacity ({total_available_cost:,.0f} available vs {total_target_cost:,.0f} required). Allocations will be capped to budget limits.")
            else:
                diag_lines.append(f"FALLBACK: Sufficient capacity ({total_available_cost:,.0f} available vs {total_target_cost:,.0f} required).")

        for i in range(num_employees):
            for j in range(num_days):
                r_hours = float(research_hours_array[i, j])
                n_hours = float(nonrnd_hours_array[i, j])
                
                if r_hours > 1e-12 and np.sum(project_weights) > 1e-12:
                    for p_idx in range(num_projects):
                        if project_weights[p_idx] > 1e-12:
                            proj_r_share = project_weights[p_idx] * r_hours
                            for t_idx in range(num_topics):
                                if topic_weights[p_idx, t_idx] > 1e-12:
                                    X_val[i, j, p_idx, t_idx] = proj_r_share * topic_weights[p_idx, t_idx]
                
                if n_hours > 1e-12 and np.sum(project_weights) > 1e-12:
                    for p_idx in range(num_projects):
                        if project_weights[p_idx] > 1e-12:
                            Y_val[i, j, p_idx] = project_weights[p_idx] * n_hours

        if np.sum(project_weights) > 1e-12:
            current_costs = np.zeros(num_projects, dtype=float)
            for p_idx in range(num_projects):
                for i in range(num_employees):
                    for j in range(num_days):
                        r_hours = np.sum(X_val[i, j, p_idx, :])
                        n_hours = Y_val[i, j, p_idx]
                        hourly_rate = salary_matrix[i, j]
                        current_costs[p_idx] += (r_hours + n_hours) * hourly_rate
            
            max_costs = np.zeros(num_projects, dtype=float)
            for p_idx, proj in enumerate(projects):
                pname = proj.name if proj.name else f"Project_{p_idx}"
                total_target = total_targets[p_idx]
                prev_cost = prev_costs_array[p_idx]
                max_total_cost = prev_cost + total_target
                max_costs[p_idx] = max_total_cost
                if max_costs[p_idx] < 1e-9:
                    max_costs[p_idx] = float('inf')
            
            for p_idx in range(num_projects):
                overhead_val = _f(getattr(projects[p_idx], "operational_overhead", 0.0), 0.0)
                direct_cost = current_costs[p_idx]
                prev_cost = prev_costs_array[p_idx]
                
                if overhead_val >= 100000.0:
                    overhead_cost = overhead_val
                elif overhead_val > 0.0 and overhead_val < 1.0:
                    overhead_cost = direct_cost * overhead_val
                else:
                    overhead_cost = 0.0
                
                total_cost_with_overhead = direct_cost + overhead_cost
                cumulative_cost = prev_cost + total_cost_with_overhead
                max_total = max_costs[p_idx]
                
                if cumulative_cost > max_total + 1e-6 and max_total < float('inf'):
                    max_new_allocation = max_total - prev_cost
                    if max_new_allocation < 0:
                        max_new_allocation = 0
                    scale_factor = max_new_allocation / max(total_cost_with_overhead, 1e-9)
                    if scale_factor < 1.0:
                        X_val[:, :, p_idx, :] *= scale_factor
                        Y_val[:, :, p_idx] *= scale_factor
                        diag_lines.append(f"FALLBACK: Capped project '{projects[p_idx].name if projects[p_idx].name else p_idx}' to hard limit {max_total:,.0f} ISK total (scaled by {scale_factor:.3f}).")
            
            min_allocation_pct = 0.01
            for p_idx in range(num_projects):
                if total_targets[p_idx] > 1e-9:
                    min_allocation = total_targets[p_idx] * min_allocation_pct
                    direct_cost = current_costs[p_idx]
                    if direct_cost < min_allocation - 1e-6:
                        scale_factor = min_allocation / max(direct_cost, 1e-9)
                        X_val[:, :, p_idx, :] *= scale_factor
                        Y_val[:, :, p_idx] *= scale_factor
                        diag_lines.append(f"FALLBACK: Ensured minimum allocation for '{projects[p_idx].name if projects[p_idx].name else p_idx}' ({min_allocation:,.0f} ISK minimum, {min_allocation_pct*100:.1f}% of target).")
            
            if use_residual:
                diag_lines.append("FALLBACK: Used residual-target-weighted allocation with budget constraints and topic-based distribution.")
            else:
                diag_lines.append("FALLBACK: Used original-target-weighted allocation with budget constraints and topic-based distribution.")

        class DummyProblem:
            status = "fallback_feasible"
            value = float("nan")
        problem = DummyProblem()
        used_fallback = True

    if not used_fallback:
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
    zero_residual_projects = {name for name, val in target_costs.items() if val <= 1e-9}
    if zero_residual_projects:
        for proj_idx, proj in enumerate(projects):
            pname = proj.name if proj.name else f"Project_{proj_idx}"
            if pname in zero_residual_projects:
                X_val[:, :, proj_idx, :] = 0.0
                Y_val[:, :, proj_idx] = 0.0
    if zero_residual_projects:
        for emp_name, daily_allocs in list(allocations.items()):
            for d_str, project_allocs in list(daily_allocs.items()):
                for pname in list(project_allocs.keys()):
                    if pname in zero_residual_projects:
                        del project_allocs[pname]
                if not project_allocs:
                    del daily_allocs[d_str]
            if not daily_allocs:
                del allocations[emp_name]
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
                base = _f(day_pay.get("amount", 0.0), 0.0)
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
                print(f"    @{rate:,.2f} ISK/hr → {data['tot']:.2f} h  (R&D {data['rd']:.2f} h, Non-R&D {data['nrd']:.2f} h)")
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
            overall_avail_rd += _f(emp.research_hours.get(d_str, 0.0), 0.0)
            overall_avail_nonrnd += _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
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
    residual_total = sum(target_costs.values())
    if zero_residual_projects and used_fallback and residual_total <= 1e-9:
        rd_diff_exact = 0.0
        nonrnd_diff_exact = 0.0
        rd_diff_rounded = 0
        nonrnd_diff_rounded = 0
        max_emp_day_rd_violation = 0.0
        max_emp_day_nonrnd_violation = 0.0
    skip_balance_checks = zero_residual_projects and used_fallback and residual_total <= 1e-9
    if not skip_balance_checks:
        for emp in employees_orig:
            for d_str in date_list:
                avail_rd = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                avail_nonrnd = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
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
    strict_tolerance = _f(getattr(AlgorithmConfig, "ALLOCATION_TOLERANCE", 1e-2), 1e-2)
    if skip_balance_checks:
        diag_lines.append("Hour balance checks skipped because residual targets are zero after concatenation.")
    elif (rd_diff_exact > strict_tolerance or nonrnd_diff_exact > strict_tolerance or
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
        locked_direct_cost = 0.0
        for emp in locked_employee_list:
            if locked_allocations.get(emp.employee_name) == pname:
                for d_str in date_list:
                    day_info = emp.salary_levels.get(d_str, {})
                    base_salary = _f(day_info.get("amount", 0.0), 0.0)
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                    r_hours = _f(emp.research_hours.get(d_str, 0.0), 0.0)
                    nr_hours = _f(emp.nonRnD_hours.get(d_str, 0.0), 0.0)
                    locked_direct_cost += (r_hours + nr_hours) * hourly_rate
        
        overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            locked_overhead = overhead_val
        elif overhead_val > 0.0 and overhead_val < 1.0:
            locked_overhead = locked_direct_cost * overhead_val
        else:
            locked_overhead = 0.0
        
        final_project_costs_solver[pname] += locked_direct_cost + locked_overhead
    if num_employees > 0:
        for p_idx, proj in enumerate(projects):
            pname = proj.name if proj.name else f"Project_{p_idx}"
            normalized_cost_free = 0.0
            for i, emp in enumerate(employees):
                for j, d_str in enumerate(date_list):
                    day_info = emp.salary_levels.get(d_str, {})
                    base_salary = _f(day_info.get("amount", 0.0), 0.0)
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                    rnd_hours = np.sum(X_val[i, j, p_idx, :])
                    nonrnd_hours = Y_val[i, j, p_idx]
                    normalized_cost_free += (rnd_hours + nonrnd_hours) * hourly_rate
            
            overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
            if overhead_val >= 100000.0:
                overhead_cost = overhead_val
            elif overhead_val > 0.0 and overhead_val < 1.0:
                overhead_cost = normalized_cost_free * overhead_val
            else:
                overhead_cost = 0.0
            
            final_project_costs_solver[pname] += normalized_cost_free + overhead_cost
            if pname in initial_costs:
                total_after = final_project_costs_solver[pname]
                previous = initial_costs[pname]
                new_cost = total_after - previous
                diag_lines.append(f"[CONCATENATION] Project '{pname}': Previous={previous:,.0f} + New (Locked+Free)={new_cost:,.0f} = Total={total_after:,.0f} ISK\n")
                print(f"[CONCATENATION] Project '{pname}': Previous={previous:,.0f} + New (Locked+Free)={new_cost:,.0f} = Total={total_after:,.0f} ISK")
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        proj_cost_rounded = initial_costs.get(pname, 0.0)
        direct_cost = 0.0
        for emp_name_iter, daily_allocs in allocations.items():
            emp_obj = next((e for e in employees_orig if e.employee_name == emp_name_iter), None)
            if not emp_obj:
                continue
            for d_str, project_data in daily_allocs.items():
                if pname in project_data:
                    day_info = emp_obj.salary_levels.get(d_str, {})
                    base_salary = _f(day_info.get("amount", 0.0), 0.0)
                    hourly_rate = SalaryConfig.calculate_hourly_rate(base_salary)
                    alloc_data = project_data[pname]
                    r_hours = sum(alloc_data.get("topics", {}).values())
                    nr_hours = alloc_data.get("nonRnD", 0.0)
                    direct_cost += (r_hours + nr_hours) * hourly_rate
        
        overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            overhead_cost = overhead_val
        elif overhead_val > 0.0 and overhead_val < 1.0:
            overhead_cost = direct_cost * overhead_val
        else:
            overhead_cost = 0.0
        
        proj_cost_rounded += direct_cost + overhead_cost
        final_project_costs_rounded[pname] = proj_cost_rounded
    info_msg = "(Note: Rounded costs are from final rounded allocations. Solver costs are from normalized continuous solution, calculated after normalization to match actual allocations.)"
    diag_lines.append(info_msg)
    for p_idx, proj in enumerate(projects):
        pname = proj.name if proj.name else f"Project_{p_idx}"
        computed_cost_rounded = final_project_costs_rounded.get(pname, 0.0)
        computed_cost_solver = final_project_costs_solver.get(pname, float('nan'))
        target_cost_val = target_costs.get(pname, 0.0)
        base_grant = _f(getattr(proj, "grant_contractual", 0.0), 0.0)
        previous_cost = _f(initial_costs.get(pname, 0.0), 0.0)
        
        match_raw = _f(getattr(proj, "matching_fund_value", 0.0), 0.0)
        mf_type = (getattr(proj, "matching_fund_type", "") or "").lower()
        if match_raw > 0.0:
            match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
        else:
            match_abs = 0.0
        overhead_val = _f(getattr(proj, "operational_overhead", 0.0), 0.0)
        if overhead_val >= 100000.0:
            overhead_amt = overhead_val
        else:
            overhead_amt = 0.0
        total_target = base_grant + match_abs + overhead_amt
        
        rounded_computed_cost_rounded = round(computed_cost_rounded)
        rounded_computed_cost_solver_display = round(computed_cost_solver) if not np.isnan(computed_cost_solver) else 'N/A'
        rounded_target_cost = round(target_cost_val)
        rounded_total_target = round(total_target)
        rounded_base_grant = round(base_grant)
        rounded_previous_cost = round(previous_cost)
        grand_total_cost_rounded_final += computed_cost_rounded
        grand_target_cost += total_target
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
        if previous_cost > 1e-6:
            msg = f"  Grant: {rounded_base_grant:10d} ISK | Matching: {round(match_abs):10d} ISK | Overhead: {round(overhead_amt):10d} ISK | Total Target: {rounded_total_target:10d} ISK"
            diag_lines.append(msg)
            msg = f"  Previous Cost: {rounded_previous_cost:10d} ISK | Residual Target: {rounded_target_cost:10d} ISK"
            diag_lines.append(msg)
            msg = f"  Computed Cost (Rounded): {rounded_computed_cost_rounded:10d} ISK | [Solver: {rounded_computed_cost_solver_display}]"
            diag_lines.append(msg)
        else:
            msg = f"  Grant: {rounded_base_grant:10d} ISK | Matching: {round(match_abs):10d} ISK | Overhead: {round(overhead_amt):10d} ISK | Total Target: {rounded_total_target:10d} ISK"
            diag_lines.append(msg)
            msg = f"  Computed Cost (Rounded): {rounded_computed_cost_rounded:10d} ISK | [Solver: {rounded_computed_cost_solver_display}]"
            diag_lines.append(msg)
        if not np.isnan(rel_dev_percent_solver):
            if target_cost_val > 1e-6:
                msg = f"  Relative Cost Deviation vs Residual Target (Solver): {rel_dev_percent_solver:+.1f} %"
            else:
                msg = f"  Relative Cost Deviation vs Total Target (Solver): {((computed_cost_solver / total_target) - 1) * 100:+.1f} %" if total_target > 1e-6 else "  Relative Cost Deviation (Solver): N/A"
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
    grand_total_original_target = sum(_f(getattr(p, "grant_contractual", 0.0), 0.0) for p in projects)
    grand_total_previous_cost = sum(_f(initial_costs.get(p.name if p.name else f"Project_{k}", 0.0), 0.0) for k, p in enumerate(projects))
    grand_total_residual_target = sum(target_costs.values())
    
    rounded_grand_total_cost_final = round(grand_total_cost_rounded_final)
    rounded_grand_original_target = round(grand_total_original_target)
    rounded_grand_residual_target = round(grand_total_residual_target)
    rounded_grand_previous_cost = round(grand_total_previous_cost)
    
    msg = f"\nGrand Total Computed Cost (Rounded Allocations): {rounded_grand_total_cost_final:12d}"
    diag_lines.append(msg)
    if grand_total_previous_cost > 1e-6:
        msg = f"Grand Total Original Target Cost:                  {rounded_grand_original_target:12d}"
        diag_lines.append(msg)
        msg = f"Grand Total Previous Cost:                         {rounded_grand_previous_cost:12d}"
        diag_lines.append(msg)
        msg = f"Grand Total Residual Target Cost:                 {rounded_grand_residual_target:12d}"
        diag_lines.append(msg)
    else:
        msg = f"Grand Total Target Cost:                         {rounded_grand_original_target:12d}"
        diag_lines.append(msg)
    grand_total_cost_solver_sum = sum(v for v in final_project_costs_solver.values() if not np.isnan(v))
    grand_rel_dev_percent_solver = float('nan')
    if grand_total_original_target > 1e-6:
        grand_rel_dev_percent_solver = ((grand_total_cost_solver_sum / grand_total_original_target) - 1) * 100
    elif grand_total_cost_solver_sum > 1e-6:
        grand_rel_dev_percent_solver = float('inf')
    else:
        grand_rel_dev_percent_solver = 0.0
    if not np.isnan(grand_rel_dev_percent_solver):
        msg = f"Overall Relative Deviation (Sum of Solver Costs vs Sum of Original Target Costs):{grand_rel_dev_percent_solver:+.1f} %"
    else:
        msg = "Overall Relative Deviation (Sum of Solver Costs vs Sum of Original Target Costs): N/A"
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
