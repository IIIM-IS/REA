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

import numpy as np
from datetime import datetime, timedelta


def run_allocation_algorithm(employees, projects, start_date, end_date, all_topics):
    """
    Runs the iterative adjustment algorithm to determine how many hours per topic per day
    each employee should allocate, so that target project costs are met.

    :param employees: List[EmployeeModel]
    :param projects: List[ProjectModel]
    :param start_date: str, e.g. "2025-01-01"
    :param end_date: str, e.g. "2025-01-10"
    :param all_topics: list of all known topic names (e.g. from ReaDataModel)
    :return: A data structure (e.g., dict) with the optimized hours results
    """

    # Parse the date range
    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
    date_list = []
    current = dt_start
    while current <= dt_end:
        date_list.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    num_days = len(date_list)

    # Gather employees data
    num_employees = len(employees)

    # Build a map of all topics -> index, so we can store them in a matrix
    #    (We also add 1 slot for nonRnD hours at the end.)
    topic_to_index = {topic: i for i, topic in enumerate(all_topics)}
    num_topics = len(all_topics)

    # Build a matrix of daily salaries for each employee
    #    We'll flatten them as [emp0_day0, emp0_day1, ..., emp1_day0, emp1_day1, ...]
    salaries = []
    for emp_i, emp in enumerate(employees):
        for day_str in date_list:
            # If you stored daily salary in employee.salary_levels[day_str], parse it
            # or default to some value
            day_salary_info = emp.salary_levels.get(day_str, {})
            day_salary_amount = day_salary_info.get("amount", 0.0)
            salaries.append(day_salary_amount)

    salaries = np.array(salaries)  # shape: (num_employees * num_days,)

    # Build project -> contractual target map
    target_costs = {}
    # We only consider projects that fall (at least partially) in the date range.
    for proj in projects:
        proj_name = proj.name if proj.name else "Unnamed"
        target_costs[proj_name] = float(proj.grant_contractual)

    # Build project -> topic indices (based on project.research_topics)
    project_topics = {}
    for proj in projects:
        proj_name = proj.name if proj.name else "Unnamed"
        topics_index_list = []
        for t_name in proj.research_topics:
            if t_name in topic_to_index:  # recognized topic
                topics_index_list.append(topic_to_index[t_name])
        project_topics[proj_name] = topics_index_list

    # Build the research_hours matrix [num_employees, num_days]
    #    The user’s daily research hours for each day are in employee.research_hours[day_str].
    research_hours_array = np.zeros((num_employees, num_days), dtype=float)
    for emp_i, emp in enumerate(employees):
        for d_i, d_str in enumerate(date_list):
            research_hours_array[emp_i, d_i] = emp.research_hours[d_str]

    # Initialize the “optimized_hours” structure
    #    shape: (num_employees, num_days, num_topics+1)  # +1 for nonRnD hours
    optimized_hours = np.zeros((num_employees, num_days, num_topics + 1), dtype=float)

    # ------------------------------
    # Helper function to compute project costs
    # ------------------------------
    def compute_project_costs(hours):
        costs = {p_name: 0.0 for p_name in project_topics}
        for p_name, topic_indices in project_topics.items():
            for day_i in range(num_days):
                for emp_i in range(num_employees):
                    # Sum contributions for topics
                    for t_idx in topic_indices:
                        costs[p_name] += hours[emp_i, day_i, t_idx] * salaries[emp_i * num_days + day_i]

                    # Add nonRnD hours
                    costs[p_name] += hours[emp_i, day_i, -1] * salaries[emp_i * num_days + day_i]
        return costs

    # Parameters
    hour_limits = np.array([8] * num_employees * num_days)  # 8-hour daily limit. Is this affecting anything?
    learning_rate = 0.000001
    penalty_factor = 0.001
    max_iterations = 50

    # ------------------------------
    # Iterative adjustment
    # ------------------------------
    for iteration in range(max_iterations):
        project_costs_dict = compute_project_costs(optimized_hours)

        for emp_i in range(num_employees):
            for day_i in range(num_days):
                for p_name, topic_indices in project_topics.items():
                    # Re-check cost each time we handle a project in this day
                    cost_now = project_costs_dict[p_name]
                    target = target_costs[p_name]
                    deficit = max(0, target - cost_now)

                    for t_idx in topic_indices:
                        # Convert t_idx back to a topic name
                        topic_name = all_topics[t_idx]
                        # Check if the employee actually has this topic for this day
                        d_str = date_list[day_i]
                        if topic_name in employees[emp_i].research_topics[d_str]:
                            #### We scale the learning rate inversely with salary
                            #     so high-salary employees adjust more slowly.
                            base_lr = learning_rate
                            emp_salary = salaries[emp_i * num_days + day_i]

                            ### "scaled_lr" is smaller for big salaries
                            scaled_lr = base_lr / (1.0 + (emp_salary / 1500.0))

                            optimized_hours[emp_i, day_i, t_idx] += (scaled_lr * emp_salary * deficit)

                    ####: After adjusting topics for this project, re-compute costs
                    project_costs_dict = compute_project_costs(optimized_hours)

                    # Adjust nonRnD hours
                    total_research = np.sum(optimized_hours[emp_i, day_i, :num_topics])
                    ### Only allocate nonRnD if total_research > 0
                    if total_research > 0:
                        if cost_now > target:
                            diff = cost_now - target
                            new_mgmt = optimized_hours[emp_i, day_i, -1] - penalty_factor * diff * salaries[
                                emp_i * num_days + day_i]
                            optimized_hours[emp_i, day_i, -1] = max(0, new_mgmt)
                        elif cost_now < target:
                            diff = target - cost_now
                            optimized_hours[emp_i, day_i, -1] += learning_rate * diff
                    else:
                        # If there's no research, no nonRnD hours
                        optimized_hours[emp_i, day_i, -1] = 0.0

                # Ensure nonRnD ≤ 25% of total research
                max_mgmt = 0.25 * research_hours_array[emp_i, day_i]
                if optimized_hours[emp_i, day_i, -1] > max_mgmt:
                    optimized_hours[emp_i, day_i, -1] = max_mgmt

                # Adjust to match the user’s total research hours exactly
                if not np.isclose(total_research, research_hours_array[emp_i, day_i]):
                    diff = research_hours_array[emp_i, day_i] - total_research
                    if total_research > 0:
                        # Scale proportionally
                        optimized_hours[emp_i, day_i, :num_topics] += (diff / total_research) * optimized_hours[emp_i,
                                                                                                day_i, :num_topics]
                    else:
                        # Evenly distribute if no research yet
                        optimized_hours[emp_i, day_i, :num_topics] += diff / num_topics

        # Recompute costs after the adjustments
        project_costs_dict = compute_project_costs(optimized_hours)
        # Check if all targets are met
        if all(project_costs_dict[p_name] >= target_costs[p_name] for p_name in project_topics):
            break

    #    Save the results back into the EmployeeModel objects
    #    For each employee/day/topic, store the final optimized hours
    for emp_i, emp in enumerate(employees):
        for d_i, d_str in enumerate(date_list):
            # Overwrite or store in a new structure. Let's store in a new field: emp.optimized_hours[date_str][topic]
            if not hasattr(emp, "optimized_hours"):
                emp.optimized_hours = {}  # { date_str: { topic_name: hours, ..., 'nonRnD': x } }

            if d_str not in emp.optimized_hours:
                emp.optimized_hours[d_str] = {}

            # Fill in the final topic hours
            for t_idx, t_name in enumerate(all_topics):
                emp.optimized_hours[d_str][t_name] = optimized_hours[emp_i, d_i, t_idx]

            # Also store nonRnD hours
            emp.optimized_hours[d_str]['nonRnD'] = optimized_hours[emp_i, d_i, -1]

    # Build a results structure for direct return
    # Example: per-employee, per-day breakdown of each topic + nonRnD
    allocations = {}
    for emp_i, emp in enumerate(employees):
        emp_alloc = {
            "name": emp.employee_name,
            "daily_allocations": {}
        }
        for d_i, d_str in enumerate(date_list):
            day_dict = {}
            for t_idx, t_name in enumerate(all_topics):
                day_dict[t_name] = optimized_hours[emp_i, d_i, t_idx]
            day_dict["nonRnD"] = optimized_hours[emp_i, d_i, -1]

            emp_alloc["daily_allocations"][d_str] = day_dict

        allocations[emp.employee_name] = emp_alloc

    return {
        'iteration': iteration,
        'final_costs': project_costs_dict,
        'allocations': allocations
    }
