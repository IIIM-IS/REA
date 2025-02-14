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
import os
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QVBoxLayout, QCalendarWidget,
    QLineEdit, QLabel, QPushButton, QWidget, QListWidget, QTabWidget,
    QScrollArea, QFrame, QSpacerItem, QSizePolicy
)
from algorithm import run_allocation_algorithm
from Model import ReaDataModel, EmployeeModel, ProjectModel
from View import ReaDataView


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

        # List to store date ranges
        self.date_ranges = []
        # Flag to track whether setting start or end date
        self.setting_start_date = True

        # Connect UI buttons
        self.view.apply_dates_button.clicked.connect(self.add_dates)
        self.view.timesheet_button.clicked.connect(self.read_timesheets)
        self.view.open_calendar_button.clicked.connect(self.toggle_calendar)
        self.view.calendar.clicked.connect(self.set_date)
        self.view.add_project_button.clicked.connect(self.view.create_project_subsection)
        self.view.toggle_project_button.clicked.connect(self.view.toggle_project_section)
        self.view.generate_output_button.clicked.connect(self.generate_output)

        # Connect Save/Load buttons
        self.view.save_state_button.clicked.connect(self.save_state)
        self.view.load_state_button.clicked.connect(self.load_state)

        # We'll store employees and projects after reading them
        self.employees = []
        self.projects = []

    # -------------------------------------------------------------------------
    # Date Ranges & Calendar
    # -------------------------------------------------------------------------
    def toggle_calendar(self):
        self.view.calendar.setVisible(not self.view.calendar.isVisible())

    def set_date(self, q_date):
        selected_date = q_date.toString("MM-dd-yyyy")
        if self.setting_start_date:
            self.view.start_date_input.setText(selected_date)
            self.setting_start_date = False
        else:
            self.view.end_date_input.setText(selected_date)
            self.setting_start_date = True

    def add_dates(self):
        start_date = self.view.start_date_input.text().strip()
        end_date = self.view.end_date_input.text().strip()
        self.date_ranges.append((start_date, end_date))
        print(f"[DEBUG] Added date range: {start_date} to {end_date}")
        print(f"[DEBUG] All date ranges: {self.date_ranges}")

    # -------------------------------------------------------------------------
    # Reading Timesheets
    # -------------------------------------------------------------------------
    def read_timesheets(self):
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
    # Generating Output (Run the Algorithm)
    # -------------------------------------------------------------------------
    def generate_output(self):
        # Must have date range(s)
        if not self.date_ranges:
            print("No date range specified.")
            return

        # First copy projects from the view to self.projects
        self.projects = self.view.projects
        print(f"[DEBUG] generate_output() sees {len(self.projects)} project(s) in self.view.projects.")

        # Check if there are any projects defined
        if not self.projects:
            print("No projects have been defined. Please add at least one project before generating output.")
            return

        # We'll use the last date range
        start_date, end_date = self.date_ranges[-1]
        all_topics = self.model.research_topics

        # Debug print
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

        # 1) Project Costs (Basic)
        print("\nProject Costs (Actual vs. Target):")
        final_costs = result['final_costs']
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            target_cost = proj.grant_contractual
            try:
                target_cost_float = float(target_cost)
            except Exception:
                target_cost_float = 0.0
            print(f"  Project '{proj_name}': Actual={actual_cost:.2f}, Target={target_cost_float:.2f}")
            if actual_cost > target_cost_float:
                print(f"    WARNING: '{proj_name}' actual cost ({actual_cost:.2f}) exceeds target ({target_cost_float:.2f}).")

        # 2) Print final allocations
        print("\nOptimized Hours Allocation:")
        allocations = result['allocations']
        for emp_name, date_dict in allocations.items():
            print(f"Employee: {emp_name}")
            for date_str, project_dict in date_dict.items():
                daily_total = 0.0
                for proj_name, proj_info in project_dict.items():
                    nonrnd_val = proj_info.get("nonRnD", 0.0)
                    topics_sum = sum(proj_info.get("topics", {}).values())
                    daily_total += (nonrnd_val + topics_sum)
                print(f"  Date {date_str}: allocated {daily_total:.2f} hours total")

        # 3) Diagnostics (Existing)
        diagnostics = []
        total_available_all = 0.0
        total_allocated_all = 0.0

        diagnostics.append("Per-Employee Allocation Diagnostics:")
        for employee in self.employees:
            emp_name = employee.employee_name
            available_total = sum(employee.research_hours.values())
            total_available_all += available_total

            # Sum all allocated hours for this employee across all days
            allocated_total = 0.0
            if emp_name in allocations:
                for date_str, proj_dict in allocations[emp_name].items():
                    for proj_info in proj_dict.values():
                        allocated_total += proj_info.get("nonRnD", 0.0)
                        allocated_total += sum(proj_info.get("topics", {}).values())
            total_allocated_all += allocated_total

            alloc_int = int(round(allocated_total))
            avail_int = int(round(available_total))
            diagnostics.append(f" - {emp_name}: Available={available_total:.2f}, Allocated={allocated_total:.2f}")
            if alloc_int > avail_int:
                diagnostics.append(f"    WARNING: Over-allocation for {emp_name} ({alloc_int} > {avail_int}).")
            for date_str, available in employee.research_hours.items():
                allocated_day = 0.0
                if emp_name in allocations and date_str in allocations[emp_name]:
                    for proj_info in allocations[emp_name][date_str].values():
                        allocated_day += proj_info.get("nonRnD", 0.0)
                        allocated_day += sum(proj_info.get("topics", {}).values())
                alloc_day_int = int(round(allocated_day))
                avail_day_int = int(round(available))
                if alloc_day_int != avail_day_int:
                    diagnostics.append(f"    WARNING: {emp_name} on {date_str}: allocated={alloc_day_int}, available={avail_day_int}")
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
        # For each project, compute:
        # - Total R&D hours and direct R&D cost
        # - Total non-R&D hours and direct non-R&D cost
        # - Overhead cost (using project overhead rate)
        # - Computed total cost (direct cost + overhead)
        # - Matching fund threshold and relative deviation
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            total_rnd_hours = 0.0
            total_nonrnd_hours = 0.0
            total_direct_cost = 0.0
            # Loop over each employee and each date (based on employee research_hours)
            for emp in self.employees:
                emp_name = emp.employee_name
                for date_str, available in emp.research_hours.items():
                    if emp_name in allocations and date_str in allocations[emp_name]:
                        proj_alloc = allocations[emp_name][date_str].get(proj_name, {})
                        rnd_hours = sum(proj_alloc.get("topics", {}).values())
                        nonrnd_hours = proj_alloc.get("nonRnD", 0.0)
                        total_rnd_hours += rnd_hours
                        total_nonrnd_hours += nonrnd_hours
                        sal = float(emp.salary_levels.get(date_str, {}).get("amount", 0.0))
                        total_direct_cost += (rnd_hours + nonrnd_hours) * sal
            overhead_cost = proj.operational_overhead * total_direct_cost if proj.operational_overhead is not None else 0.0
            computed_cost = total_direct_cost + overhead_cost
            matching_threshold = None
            if proj.matching_fund_type.lower() == "percentage":
                m_frac = proj.matching_fund_value / 100.0
                if m_frac < 1.0:
                    matching_threshold = float(proj.grant_contractual) / (1.0 - m_frac)
            elif proj.matching_fund_type.lower() == "absolute":
                matching_threshold = float(proj.grant_contractual) + proj.matching_fund_value
            rel_dev = (computed_cost / float(proj.grant_contractual) - 1) if float(proj.grant_contractual) > 0 else None
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
    # Save / Load State
    # -------------------------------------------------------------------------
    def save_state(self):
        filename, _ = QFileDialog.getSaveFileName(
            self.view, "Save State As", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            print("[INFO] Save State canceled (no file selected).")
            return

        state_data = {}

        # 1) Date Ranges & UI Fields
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
                "research_topics": { d: dict(tmap) for d, tmap in emp.research_topics.items() },
            }
            employees_list.append(emp_dict)
        state_data["employees"] = employees_list

        # 3) Projects
        all_projects = self.view.projects
        projects_list = []
        for proj in all_projects:
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
            }
            projects_list.append(proj_dict)
        state_data["projects"] = projects_list

        print(f"[DEBUG] Saving {len(all_projects)} project(s).")

        try:
            with open(filename, "w") as f:
                json.dump(state_data, f, indent=2)
            print(f"[INFO] State saved to {filename}")
        except Exception as e:
            print(f"[ERROR] Failed to save state to {filename}: {e}")

    def load_state(self):
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
            self.view.projects.clear()  # also clear the view's list
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

                self.projects.append(proj)
                self.view.projects.append(proj)

            self.view.create_employee_overview_section(self.employees)

            for p in self.projects:
                self.view.create_project_subsection_from_project(p)

            print(f"[INFO] Loaded {len(self.employees)} employees, {len(self.projects)} projects.")
            print("[INFO] State restoration complete.")

        except Exception as e:
            print(f"[ERROR] Failed to load state from {filename}: {e}")
