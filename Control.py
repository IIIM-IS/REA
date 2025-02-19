# -----------------------------------------------------------------------------
# Authors: Arash Sheikhlar and Kristinn Thorisson
# Project: Research Expenditure Allocation (REA)
# -----------------------------------------------------------------------------
# Copyright (c) 2025, Arash Sheikhlar and Kristinn Thorisson.
# All rights reserved.
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

import json
from datetime import datetime, timedelta

from PyQt5.QtWidgets import QFileDialog
from algorithm import run_allocation_algorithm
from Model import ReaDataModel, EmployeeModel, ProjectModel
from View import ReaDataView

class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

        # Lists for holding app data
        self.employees = []
        self.projects = []
        self.date_ranges = []

        # Flag to track whether we are setting start or end date via the calendar
        self.setting_start_date = True

        # ------------------ Connect signals from the View ------------------ #
        # Calendar & Date range
        self.view.open_calendar_button.clicked.connect(self.toggle_calendar)
        self.view.calendar.clicked.connect(self.set_date)
        self.view.apply_dates_button.clicked.connect(self.add_dates)

        # Timesheets
        self.view.timesheet_button.clicked.connect(self.read_timesheets)

        # Projects
        self.view.add_project_button.clicked.connect(self.create_new_project)
        self.view.toggle_project_button.clicked.connect(self.view.toggle_project_section)

        # Output
        self.view.generate_output_button.clicked.connect(self.generate_output)

        # Save/Load
        self.view.save_state_button.clicked.connect(self.save_state)
        self.view.load_state_button.clicked.connect(self.load_state)

        self.view.project_saved.connect(self.on_project_saved)
        self.view.project_deleted.connect(self.on_project_deleted)

        # Employee Salary Editing
        # The view should emit a new signal (e.g., employee_salary_range_added) 
        # when the user inputs a salary level, start date, end date, etc.
        self.view.employee_salary_range_added.connect(self.on_employee_salary_range_added)

        self.view.employee_salary_interval_edited.connect(self.on_employee_salary_interval_edited)


    # -------------------------------------------------------------------------
    # SALARY RANGE ADDITION
    # -------------------------------------------------------------------------
    def on_employee_salary_range_added(self, data):
        """
        Handler for the View's 'employee_salary_range_added' signal.

        The 'data' dict might look like:
            {
                "employee_object": <EmployeeModel>,
                "level_label": "Level 1",
                "amount": 120.0,
                "start_date": "01-01-2025",
                "end_date": "01-31-2025"
            }
        We iterate from start_date to end_date, setting the employee's salary level.
        """
        emp_obj = data["employee_object"]
        level_label = data["level_label"]
        amount_str = data["amount"]
        start_str = data["start_date"]
        end_str = data["end_date"]

        # Validate the fields
        if not level_label.strip():
            print("[WARN] Salary level label cannot be empty.")
            return

        try:
            amount_val = float(amount_str)
        except ValueError:
            print(f"[WARN] Invalid salary amount '{amount_str}'. Must be numeric.")
            return

        if not start_str or not end_str:
            print("[WARN] Start date and end date must be filled for salary range.")
            return

        # Parse the dates and apply
        try:
            start_dt = datetime.strptime(start_str, "%m-%d-%Y")
            end_dt = datetime.strptime(end_str, "%m-%d-%Y")
        except ValueError as ve:
            print(f"[WARN] Could not parse salary date range: {ve}")
            return

        if start_dt > end_dt:
            print("[WARN] Start date is after end date. Invalid range.")
            return

        # For each day in [start_dt, end_dt], set the salary
        current_dt = start_dt
        while current_dt <= end_dt:
            day_str = current_dt.strftime("%m-%d-%Y")
            emp_obj.set_salary_level_for_date(day_str, level_label, amount_val)
            current_dt += timedelta(days=1)

        print(f"[INFO] Applied salary '{level_label}' = {amount_val} for {emp_obj.employee_name} "
              f"from {start_str} to {end_str}.")

        # Optionally re-draw the employee UI if needed
        self.view.create_employee_overview_section(self.employees)


    # -------------------------------------------------------------------------
    # PROJECT CREATION
    # -------------------------------------------------------------------------
    def create_new_project(self):
        """
        Create a new ProjectModel, add it to our internal list,
        and tell the view to build UI for it.
        """
        new_proj = ProjectModel()
        self.projects.append(new_proj)
        self.view.projects.append(new_proj)
        # Make sure the projects section is visible
        self.view.projects_section_container.setVisible(True)
        
        # Now build & show the subsection
        self.view.create_project_subsection_from_project(new_proj)

    # -------------------------------------------------------------------------
    # DATE RANGES & CALENDAR
    # -------------------------------------------------------------------------
    def toggle_calendar(self):
        self.view.calendar.setVisible(not self.view.calendar.isVisible())

    def set_date(self, q_date):
        """
        Called when the user clicks a date in the QCalendarWidget.
        We either set start_date_input or end_date_input depending on the toggle.
        """
        selected_date = q_date.toString("MM-dd-yyyy")
        if self.setting_start_date:
            self.view.start_date_input.setText(selected_date)
            self.setting_start_date = False
        else:
            self.view.end_date_input.setText(selected_date)
            self.setting_start_date = True

    def add_dates(self):
        """
        Grab the start_date_input and end_date_input from the View
        and append the resulting (start, end) to self.date_ranges.
        """
        start_date = self.view.start_date_input.text().strip()
        end_date = self.view.end_date_input.text().strip()
        if not start_date or not end_date:
            print("Both start and end date fields must be filled before adding a date range.")
            return

        self.date_ranges.append((start_date, end_date))
        print(f"[DEBUG] Added date range: {start_date} to {end_date}")
        print(f"[DEBUG] All date ranges: {self.date_ranges}")

    # -------------------------------------------------------------------------
    # TIMESHEET READING
    # -------------------------------------------------------------------------
    def read_timesheets(self):
        """
        Asks the user to pick a directory and then calls the model to parse CSV files
        within that directory for each date range. 
        """
        if not self.date_ranges:
            print("Error: You must specify at least one date range before loading timesheets.")
            return

        directory = QFileDialog.getExistingDirectory(self.view, "Select Directory")
        if not directory:
            print("No directory selected. Skipping timesheet processing.")
            return

        self.view.directory_label.setText(f"Selected Directory: {directory}")

        try:
            self.employees = self.model.extract_data_from_csv(directory, self.date_ranges)
            self.view.create_employee_overview_section(self.employees)

            # Debug info
            for emp in self.employees:
                print(f"[DEBUG] Employee: {emp.employee_name}")
                for date_str in sorted(emp.research_hours.keys()):
                    daily_summary = emp.get_daily_summary(date_str)
                    print(f"    {date_str} => {daily_summary}")

        except FileNotFoundError:
            print(f"Error: No CSV files found in {directory}.")
        except Exception as e:
            print(f"Unexpected error while processing timesheets: {e}")


    # -------------------------------------------------------------------------
    # GENERATING OUTPUT (Allocation Algorithm)
    # -------------------------------------------------------------------------
    def generate_output(self):
        """
        Runs the allocation algorithm using the employees, projects,
        and the last date range in self.date_ranges.
        Then prints a summary + diagnostics.
        """
        if not self.date_ranges:
            print("No date range specified.")
            return

        # Sync local list with whatever is in the View
        self.projects = self.view.projects

        if not self.projects:
            print("No projects have been defined. Please add at least one project before generating output.")
            return

        # We'll use the last date range
        start_date, end_date = self.date_ranges[-1]
        all_topics = self.model.research_topics

        print(f"[DEBUG] Running algorithm from {start_date} to {end_date} "
              f"with {len(self.employees)} employees and {len(self.projects)} projects.")

        # Run the allocation algorithm
        result = run_allocation_algorithm(
            employees=self.employees,
            projects=self.projects,
            start_date=start_date,
            end_date=end_date,
            all_topics=all_topics
        )

        print("Algorithm finished.")
        print(f"Iterations used (if any): {result.get('iteration','N/A')}")

        # 1) Project Costs
        print("\nProject Costs (Actual vs. Target):")
        final_costs = result['final_costs']
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            try:
                target_cost_float = float(proj.grant_contractual)
            except Exception:
                target_cost_float = 0.0
            print(f"  Project '{proj_name}': Actual={actual_cost:.2f}, Target={target_cost_float:.2f}")
            if actual_cost > target_cost_float:
                print(f"    WARNING: '{proj_name}' actual cost "
                      f"({actual_cost:.2f}) exceeds target ({target_cost_float:.2f}).\n"
                      f" (difference={actual_cost - target_cost_float:.2f}).\n"
                      f" (difference in percentage={((actual_cost - target_cost_float) / target_cost_float) * 100:.2f}%)"
                    )

        # 2) Print final allocations
        # print("\nOptimized Hours Allocation:")
        # allocations = result['allocations']
        # for emp_name, date_dict in allocations.items():
        #     print(f"Employee: {emp_name}")
        #     for date_str, project_dict in date_dict.items():
        #         daily_total = 0.0
        #         for proj_name, proj_info in project_dict.items():
        #             nonrnd_val = proj_info.get("nonRnD", 0.0)
        #             topics_sum = sum(proj_info.get("topics", {}).values())
        #             daily_total += (nonrnd_val + topics_sum)
                # print(f"  Date {date_str}: allocated {daily_total:.2f} hours total")

        # 3) Diagnostics
        diagnostics = []
        total_available_all = 0.0
        total_allocated_all = 0.0

        diagnostics.append("Per-Employee Allocation Diagnostics:")
        for employee in self.employees:
            emp_name = employee.employee_name
            available_total = sum(employee.research_hours.values())
            total_available_all += available_total

            allocated_total = 0.0
            if emp_name in allocations:
                for proj_dict in allocations[emp_name].values():
                    for proj_info in proj_dict.values():
                        allocated_total += proj_info.get("nonRnD", 0.0)
                        allocated_total += sum(proj_info.get("topics", {}).values())
            total_allocated_all += allocated_total

            diagnostics.append(f" - {emp_name}: Available={available_total:.2f}, Allocated={allocated_total:.2f}")
            if int(round(allocated_total)) > int(round(available_total)):
                diagnostics.append(f"    WARNING: Over-allocation for {emp_name}.")

            # Check day-by-day
            for date_str, available in employee.research_hours.items():
                allocated_day = 0.0
                if emp_name in allocations and date_str in allocations[emp_name]:
                    for proj_info in allocations[emp_name][date_str].values():
                        allocated_day += proj_info.get("nonRnD", 0.0)
                        allocated_day += sum(proj_info.get("topics", {}).values())
                if int(round(allocated_day)) != int(round(available)):
                    diagnostics.append(f"    WARNING: {emp_name} on {date_str}: "
                                       f"allocated={allocated_day:.2f}, available={available:.2f}")

        diagnostics.append(f"\nOverall: Total available={total_available_all:.2f}, allocated={total_allocated_all:.2f}")
        if int(round(total_allocated_all)) > int(round(total_available_all)):
            diagnostics.append("WARNING: Overall allocated hours exceed total available hours!")

        diag_text = "\n".join(diagnostics)
        print("\nDiagnostics:")
        print(diag_text)

        try:
            with open("output_diagnostics.txt", "w") as diag_file:
                diag_file.write("Allocation Diagnostics\n")
                diag_file.write("======================\n\n")
                diag_file.write(diag_text)
            print("[INFO] Diagnostics written to output_diagnostics.txt")
        except Exception as e:
            print("[ERROR] Writing diagnostics file:", e)

        # 4) Detailed Project Cost Breakdown
        print("\nDetailed Project Cost Breakdown:")
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            total_rnd_hours = 0.0
            total_nonrnd_hours = 0.0
            total_direct_cost = 0.0

            for emp in self.employees:
                emp_name = emp.employee_name
                for date_str in emp.research_hours:
                    proj_alloc = allocations.get(emp_name, {}).get(date_str, {}).get(proj_name, {})
                    rnd_hours = sum(proj_alloc.get("topics", {}).values())
                    nonrnd_hours = proj_alloc.get("nonRnD", 0.0)
                    total_rnd_hours += rnd_hours
                    total_nonrnd_hours += nonrnd_hours
                    sal = float(emp.salary_levels.get(date_str, {}).get("amount", 0.0))
                    total_direct_cost += (rnd_hours + nonrnd_hours) * sal

            overhead_cost = 0.0
            if proj.operational_overhead is not None:
                overhead_cost = proj.operational_overhead * total_direct_cost

            computed_cost = total_direct_cost + overhead_cost

            matching_threshold = None
            if proj.matching_fund_type.lower() == "percentage":
                m_frac = proj.matching_fund_value / 100.0
                if m_frac < 1.0:
                    matching_threshold = float(proj.grant_contractual) / (1.0 - m_frac)
            elif proj.matching_fund_type.lower() == "absolute":
                matching_threshold = float(proj.grant_contractual) + proj.matching_fund_value

            try:
                rel_dev = (computed_cost / float(proj.grant_contractual) - 1) if float(proj.grant_contractual) > 0 else None
            except:
                rel_dev = None

            print(f"Project '{proj_name}':")
            print(f"  Total R&D Hours: {total_rnd_hours:.2f}")
            print(f"  Total Non-R&D Hours: {total_nonrnd_hours:.2f}")
            print(f"  Direct Cost (R&D + Non-R&D): {total_direct_cost:.2f}")
            print(f"  Overhead Cost (Rate {proj.operational_overhead:.2f}): {overhead_cost:.2f}")
            print(f"  Computed Total Cost: {computed_cost:.2f} | Target Cost: {proj.grant_contractual}")
            if matching_threshold is not None:
                print(f"  Matching Fund Threshold: {matching_threshold:.2f}")
            if rel_dev is not None:
                print(f"  Relative Cost Deviation: {rel_dev:.2f}")
            print("-------------------------------------------------------------")
        print("================================================================\n")


    # -------------------------------------------------------------------------
    # SAVE / LOAD STATE
    # -------------------------------------------------------------------------
    def save_state(self):
        """
        Saves the current state (date ranges, UI fields, employees, projects) to a JSON file.
        """
        filename, _ = QFileDialog.getSaveFileName(
            self.view, "Save State As", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            print("[INFO] Save State canceled (no file selected).")
            return

        state_data = {}
        state_data["run_comment"] = self.view.run_comment_input.toPlainText()
        # 1) Date ranges & UI fields
        state_data["date_ranges"] = self.date_ranges
        state_data["ui_start_date"] = self.view.start_date_input.text().strip()
        state_data["ui_end_date"] = self.view.end_date_input.text().strip()

        # 2) Employees
        employees_list = []
        for emp in self.employees:
            emp_dict = {
                "employee_name": emp.employee_name,
                "research_hours": dict(emp.research_hours),
                "meeting_hours": dict(emp.meeting_hours),
                "nonRnD_hours": dict(emp.nonRnD_hours),
                "salary_levels": dict(emp.salary_levels),
                "research_topics": {
                    d: dict(tmap) for d, tmap in emp.research_topics.items()
                },
            }
            employees_list.append(emp_dict)
        state_data["employees"] = employees_list

        # 3) Projects
        projects_list = []
        for proj in self.view.projects:
            proj_dict = {
                "name": proj.name,
                "funding_agency": proj.funding_agency,
                "grant_min": proj.grant_min,
                "grant_max": proj.grant_max,
                "grant_contractual": proj.grant_contractual,
                "funding_start": proj.funding_start,
                "funding_end": proj.funding_end,
                "currency": proj.currency,
                "exchange_rate": proj.exchange_rate,
                "report_type": proj.report_type,
                "matching_fund_type": proj.matching_fund_type,
                "matching_fund_value": proj.matching_fund_value,
                "operational_overhead": proj.operational_overhead,
                "travel_cost": proj.travel_cost,
                "equipment_cost": proj.equipment_cost,
                "other_cost": proj.other_cost,
                "research_topics": proj.research_topics[:],
                "max_nonrnd_percentage": proj.max_nonrnd_percentage,
            }
            projects_list.append(proj_dict)
        state_data["projects"] = projects_list

        print(f"[DEBUG] Saving {len(self.projects)} project(s).")

        try:
            with open(filename, "w") as f:
                json.dump(state_data, f, indent=2)
            print(f"[INFO] State saved to {filename}")
        except Exception as e:
            print(f"[ERROR] Failed to save state to {filename}: {e}")

    def load_state(self):
        """
        Loads a previously saved JSON state, updates self.employees & self.projects,
        and re-creates the view elements accordingly.
        """
        filename, _ = QFileDialog.getOpenFileName(
            self.view, "Load State", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            print("[INFO] Load State canceled (no file selected).")
            return

        try:
            with open(filename, "r") as f:
                state_data = json.load(f)
            print(f"[INFO] State loaded from {filename}")

            self.view.run_comment_input.setPlainText(state_data.get("run_comment", ""))

            # 1) Date Ranges + UI Fields
            self.date_ranges = state_data.get("date_ranges", [])
            self.view.start_date_input.setText(state_data.get("ui_start_date", ""))
            self.view.end_date_input.setText(state_data.get("ui_end_date", ""))

            # 2) Employees
            self.employees.clear()
            for emp_dict in state_data.get("employees", []):
                emp = EmployeeModel(emp_dict["employee_name"])
                emp.research_hours.update(emp_dict.get("research_hours", {}))
                emp.meeting_hours.update(emp_dict.get("meeting_hours", {}))
                emp.nonRnD_hours.update(emp_dict.get("nonRnD_hours", {}))
                for date_str, topics_map in emp_dict.get("research_topics", {}).items():
                    for topic, hrs in topics_map.items():
                        emp.research_topics[date_str][topic] = hrs
                emp.salary_levels.update(emp_dict.get("salary_levels", {}))
                self.employees.append(emp)

            # 3) Projects
            self.projects.clear()
            self.view.projects.clear()
            for proj_dict in state_data.get("projects", []):
                proj = ProjectModel()
                proj.name = proj_dict.get("name", "")
                proj.funding_agency = proj_dict.get("funding_agency", "")
                proj.grant_min = proj_dict.get("grant_min", 0)
                proj.grant_max = proj_dict.get("grant_max", 0)
                proj.grant_contractual = proj_dict.get("grant_contractual", 0)
                proj.funding_start = proj_dict.get("funding_start", "")
                proj.funding_end = proj_dict.get("funding_end", "")
                proj.currency = proj_dict.get("currency", "")
                proj.exchange_rate = proj_dict.get("exchange_rate", 0)
                proj.report_type = proj_dict.get("report_type", "")
                proj.matching_fund_type = proj_dict.get("matching_fund_type", "")
                proj.matching_fund_value = proj_dict.get("matching_fund_value", 0)
                proj.operational_overhead = proj_dict.get("operational_overhead", 0)
                proj.travel_cost = proj_dict.get("travel_cost", 0)
                proj.equipment_cost = proj_dict.get("equipment_cost", 0)
                proj.other_cost = proj_dict.get("other_cost", 0)
                proj.research_topics = proj_dict.get("research_topics", [])
                proj.max_nonrnd_percentage = proj_dict.get("max_nonrnd_percentage", 0)
                self.projects.append(proj)
                self.view.projects.append(proj)

            # Rebuild the UI with the newly loaded employees and projects
            self.view.create_employee_overview_section(self.employees)
            for proj in self.projects:
                self.view.create_project_subsection_from_project(proj)

            print(f"[INFO] Loaded {len(self.employees)} employees, {len(self.projects)} projects.")
            print("[INFO] State restoration complete.")

        except Exception as e:
            print(f"[ERROR] Failed to load state from {filename}: {e}")


    def on_project_saved(self, project_obj, data):
        """
        Updates an existing project's fields when 'Save Project' is clicked.
        """
        # Convert all numeric text fields to appropriate types
        try:
            project_obj.grant_min = float(data["grant_min"]) if data["grant_min"] else 0
        except:
            project_obj.grant_min = 0

        try:
            project_obj.grant_max = float(data["grant_max"]) if data["grant_max"] else 0
        except:
            project_obj.grant_max = 0

        try:
            project_obj.grant_contractual = float(data["grant_contractual"]) if data["grant_contractual"] else 0
        except:
            project_obj.grant_contractual = 0

        try:
            project_obj.operational_overhead = data["operational_overhead"]
        except:
            project_obj.operational_overhead = 0

        try:
            project_obj.matching_fund_value = float(data["matching_fund_value"]) if data["matching_fund_value"] else 0
        except:
            project_obj.matching_fund_value = 0

        try:
            project_obj.max_nonrnd_percentage = data["max_nonrnd_percentage"] or 0
        except:
            project_obj.max_nonrnd_percentage = 0

        # Non-numeric fields
        project_obj.name = data["name"]
        project_obj.funding_agency = data["funding_agency"]
        project_obj.matching_fund_type = data["matching_fund_type"]
        project_obj.funding_start = data["funding_start"]
        project_obj.funding_end = data["funding_end"]
        project_obj.research_topics = data["research_topics"]

        print(f"[INFO] Project '{project_obj.name}' fields have been updated.")

    def on_project_deleted(self, project_obj):
        """
        Removes the project from our lists and redraws the project UI.
        """
        if project_obj in self.projects:
            self.projects.remove(project_obj)
        if project_obj in self.view.projects:
            self.view.projects.remove(project_obj)
        # Now refresh the project section in the view
        self.view.refresh_projects_section(self.projects)
        print(f"[INFO] Project '{project_obj.name}' removed.")

    def on_employee_salary_interval_edited(self, employee, old_start, old_end, new_start, new_end, new_level, new_amount):
        """
        Handler for editing an existing salary interval.
        It removes salary entries from old_start to old_end and then sets new salary entries
        from new_start to new_end with the provided new_level and new_amount.
        """
        # Remove the old salary interval
        employee.remove_salary_interval(old_start, old_end)
        
        # Validate and parse the new salary amount and dates
        try:
            new_amount_val = float(new_amount)
        except ValueError:
            print(f"[WARN] Invalid new salary amount '{new_amount}'. Must be numeric.")
            return

        try:
            new_start_dt = datetime.strptime(new_start, "%m-%d-%Y")
            new_end_dt = datetime.strptime(new_end, "%m-%d-%Y")
        except ValueError as ve:
            print(f"[WARN] Could not parse new salary date range: {ve}")
            return

        if new_start_dt > new_end_dt:
            print("[WARN] New start date is after new end date. Invalid range.")
            return

        # For each day in [new_start_dt, new_end_dt], set the new salary
        current_dt = new_start_dt
        while current_dt <= new_end_dt:
            day_str = current_dt.strftime("%m-%d-%Y")
            employee.set_salary_level_for_date(day_str, new_level, new_amount_val)
            current_dt += timedelta(days=1)

        print(f"[INFO] Edited salary for {employee.employee_name}: Changed interval {old_start}–{old_end} to {new_start}–{new_end} with level '{new_level}' and amount {new_amount_val}.")
        # Refresh the UI to reflect changes
        self.view.create_employee_overview_section(self.employees)