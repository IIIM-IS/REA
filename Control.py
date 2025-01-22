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

        # Iterate over each project object so we can retrieve target cost + final cost
        for proj in self.projects:
            # Use the project's name to find the final cost in final_costs
            proj_name = proj.name if proj.name else "Unnamed"

            # final_cost for this project from the algorithm
            actual_cost = final_costs.get(proj_name, 0.0)

            # target cost (contractual amount) stored in the project
            target_cost = proj.grant_contractual

            target_cost_float = float(target_cost)
            print(f"  Project '{proj_name}': Actual={actual_cost:.2f}, Target={target_cost_float:.2f}")

        # Print the final allocations
        print("\nOptimized Hours Allocation:")
        allocations = result['allocations']
        for emp_name, emp_data in allocations.items():
            print(f"Employee: {emp_name}")
            daily_allocations = emp_data["daily_allocations"]
            for date_str, day_data in daily_allocations.items():
                # day_data is a dict of topic->hours plus 'management'
                # Separate management from topics
                management_hours = day_data['management']
                # Filter non-zero topics
                non_zero_topics = {
                    topic: hours
                    for topic, hours in day_data.items()
                    if topic != "management" and hours > 0.0
                }
                # Build a string for the non-zero topics
                topics_str = ", ".join(f"{t}={val:.2f}" for t, val in non_zero_topics.items())

                # Print line
                # You can hide management if it's zero as well,
                # but here we show it no matter what.
                print(f"  Date {date_str}: {topics_str}, Management={management_hours:.2f}")


    def read_timesheets(self):
        # Prompt user for a directory selection
        directory = QFileDialog.getExistingDirectory(self.view, "Select Directory")

        # Display the selected directory in the UI
        self.view.directory_label.setText(f"Selected Directory: {directory}")

        # Retrieve employees from the model
        self.employees = self.model.extract_data_from_csv(directory, self.date_ranges)
        self.view.create_employee_overview_section(self.employees)

        # Debug/print daily data to the console (optional)
        for emp in self.employees:
            print(f"Employee: {emp.employee_name}")
            # Sort dates so they are printed in chronological order
            for date_str in sorted(emp.research_hours.keys()):
                daily_summary = emp.get_daily_summary(date_str)
                print(f"  Date: {date_str}, Summary: {daily_summary}")



