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

from PyQt5.QtWidgets import QApplication,  QFileDialog, QMainWindow, QVBoxLayout, QCalendarWidget, QLineEdit, QLabel, QPushButton, QWidget, QListWidget, QTabWidget, QScrollArea, QFrame, QSpacerItem, QSizePolicy
from algorithm import run_allocation_algorithm
from Model import ReaDataModel
from View import ReaDataView


class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

        # List to store date ranges
        self.date_ranges = []
        # State to track whether setting start or end date
        self.setting_start_date = True

        # Connect the apply dates button
        self.view.apply_dates_button.clicked.connect(self.add_dates)
        # Connect the TimeSheet Inputs button
        self.view.timesheet_button.clicked.connect(self.read_timesheets)
        # Connect the Open Calendar button
        self.view.open_calendar_button.clicked.connect(self.toggle_calendar)
        # Connect calendar clicks to set dates
        self.view.calendar.clicked.connect(self.set_date)
        # Connect project overview
        self.view.add_project_button.clicked.connect(self.view.create_project_subsection)

        self.view.toggle_project_button.clicked.connect(view.toggle_project_section)

        self.view.generate_output_button.clicked.connect(self.generate_output)

        # We'll store employees and projects after reading them
        self.employees = []
        self.projects = []

    def toggle_calendar(self):
        # Toggle calendar visibility
        self.view.calendar.setVisible(not self.view.calendar.isVisible())

    def set_date(self, q_date):
        selected_date = q_date.toString("yyyy-MM-dd")
        if self.setting_start_date:
            self.view.start_date_input.setText(selected_date)
            self.setting_start_date = False  # Switch to end date
        else:
            self.view.end_date_input.setText(selected_date)
            self.setting_start_date = True  # Reset to start date

    def add_dates(self):
        # Get inputs values
        start_date = self.view.start_date_input.text().strip()
        end_date = self.view.end_date_input.text().strip()
        self.date_ranges.append((start_date, end_date))
        print(f"Date ranges: {self.date_ranges}")


    def generate_output(self):
        # Ensure we have at least one date range (or use last one)
        if not self.date_ranges:
            print("No date range specified.")
            return

        # For simplicity, we take the last date range
        start_date, end_date = self.date_ranges[-1]

        # Get the projects from the view
        self.projects = self.view.projects

        # Run the algorithm
        # self.employees set by read_timesheets / create_project_subsection etc.
        all_topics = self.model.research_topics  # or however you retrieve the global topic list

        result = run_allocation_algorithm(
            employees=self.employees,
            projects=self.projects,
            start_date=start_date,
            end_date=end_date,
            all_topics=all_topics
        )

        # Print some top-level info
        print("Algorithm finished.")
        print(f"Iterations used: {result['iteration']}")

        # 1) Show final project costs + target (contractual) side by side
        print("\nProject Costs (Actual vs. Target):")
        final_costs = result['final_costs']  # dict of {project_name: final_cost}
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
                print(f"    WARNING: Project '{proj_name}' actual cost ({actual_cost:.2f}) exceeds target ({target_cost_float:.2f}).")

        # 2) Print the final allocations per employee per day
        print("\nOptimized Hours Allocation:")
        allocations = result['allocations']
        for emp_name, emp_data in allocations.items():
            print(f"Employee: {emp_name}")
            daily_allocations = emp_data["daily_allocations"]
            for date_str, day_data in daily_allocations.items():
                # day_data is a dict of topic->hours plus 'nonRnD'
                nonRnD_hours = day_data.get('nonRnD', 0.0)
                # Sum hours for all topics (all keys except 'nonRnD')
                topics_sum = sum(hours for topic, hours in day_data.items() if topic != "nonRnD")
                total_allocated_day = nonRnD_hours + topics_sum
                topics_str = ", ".join(f"{t}={val:.2f}" for t, val in day_data.items() if t != "nonRnD" and val > 0)
                print(f"  Date {date_str}: {topics_str}, nonRnD={nonRnD_hours:.2f}, Total Allocated={total_allocated_day:.2f}")

        # 3) Diagnostics: compare algorithm allocations with timesheet availability.
        diagnostics = []
        total_available_all = 0.0
        total_allocated_all = 0.0

        diagnostics.append("Per-Employee Allocation Diagnostics:")
        for employee in self.employees:
            emp_name = employee.employee_name
            available_total = sum(employee.research_hours.values())
            total_available_all += available_total

            # Sum allocated hours for this employee from the algorithm result
            allocated_total = 0.0
            if emp_name in allocations:
                for date_str, day_data in allocations[emp_name]["daily_allocations"].items():
                    allocated_day = day_data.get("nonRnD", 0.0) + sum(
                        hours for topic, hours in day_data.items() if topic != "nonRnD"
                    )
                    allocated_total += allocated_day
            total_allocated_all += allocated_total

            diagnostics.append(f" - {emp_name}: Available hours (work hours) = {available_total:.2f}, Allocated hours = {allocated_total:.2f}")
            if allocated_total > available_total:
                diagnostics.append(f"    WARNING: {emp_name} was allocated more hours ({allocated_total:.2f}) than available ({available_total:.2f}).")

            # Also check per day
            for date, available in employee.research_hours.items():
                allocated_day = 0.0
                if emp_name in allocations and date in allocations[emp_name]["daily_allocations"]:
                    day_alloc = allocations[emp_name]["daily_allocations"][date]
                    allocated_day = day_alloc.get("nonRnD", 0.0) + sum(
                        hours for topic, hours in day_alloc.items() if topic != "nonRnD"
                    )
                if allocated_day > available:
                    diagnostics.append(f"    WARNING: {emp_name} on {date} has {allocated_day:.2f} allocated hours, but only {available:.2f} available.")

        diagnostics.append(f"\nOverall: Total available hours = {total_available_all:.2f}, Total allocated hours = {total_allocated_all:.2f}")
        if total_allocated_all > total_available_all:
            diagnostics.append("WARNING: Overall allocated hours exceed the total available hours!")

        # 4) (Optional) Additional project diagnostics can be added here.

        # Print diagnostics to console
        diagnostics_text = "\n".join(diagnostics)
        print("\nDiagnostics:")
        print(diagnostics_text)

        # Write diagnostics to an output file for further inspection
        try:
            with open("output_diagnostics.txt", "w") as diag_file:
                diag_file.write("Allocation Diagnostics\n")
                diag_file.write("======================\n\n")
                diag_file.write(diagnostics_text)
            print("\nDiagnostics written to output_diagnostics.txt")
        except Exception as e:
            print("Error writing diagnostics file:", e)

    def read_timesheets(self):
        """ Read timesheets from Google Drive or allow manual directory selection """

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

            for emp in self.employees:
                print(f"Employee: {emp.employee_name}")
                for date_str in sorted(emp.research_hours.keys()):
                    daily_summary = emp.get_daily_summary(date_str)
                    print(f"  Date: {date_str}, Summary: {daily_summary}")

        except FileNotFoundError:
            print(f"Error: No CSV files found in the selected directory: {directory}.")
        except Exception as e:
            print(f"Unexpected error while processing timesheets: {e}")



