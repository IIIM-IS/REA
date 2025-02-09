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

from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QSettings
from datetime import datetime, timedelta
from algorithm import run_allocation_algorithm
from Model import ReaDataModel, EmployeeModel, ProjectModel

class Controller:
    def __init__(self, model, view):
        self.model = model
        self.view = view

        # Create a QSettings instance for auto-saving user inputs.
        self.settings = QSettings("IIIM", "REAApp")
        self.load_settings()

        # List to store date ranges
        self.date_ranges = []
        self.setting_start_date = True

        # Connect signals for date inputs so they are auto-saved.
        self.view.start_date_input.editingFinished.connect(
            lambda: self.settings.setValue("start_date", self.view.start_date_input.text())
        )
        self.view.end_date_input.editingFinished.connect(
            lambda: self.settings.setValue("end_date", self.view.end_date_input.text())
        )

        # Connect buttons from the view.
        self.view.apply_dates_button.clicked.connect(self.add_dates)
        self.view.timesheet_button.clicked.connect(self.read_timesheets)
        self.view.open_calendar_button.clicked.connect(self.toggle_calendar)
        self.view.calendar.clicked.connect(self.set_date)
        self.view.add_project_button.clicked.connect(self.view.create_project_subsection)
        self.view.toggle_project_button.clicked.connect(self.view.toggle_project_section)
        self.view.generate_output_button.clicked.connect(self.generate_output)
        self.view.save_state_button.clicked.connect(self.save_state)
        self.view.load_state_button.clicked.connect(self.load_state)

        self.employees = []
        self.projects = []

    def load_settings(self):
        start_date = self.settings.value("start_date", "")
        end_date = self.settings.value("end_date", "")
        print("Loaded start_date:", start_date)
        print("Loaded end_date:", end_date) 
        self.view.start_date_input.setText(start_date)
        self.view.end_date_input.setText(end_date)

    def toggle_calendar(self):
        self.view.calendar.setVisible(not self.view.calendar.isVisible())

    def set_date(self, q_date):
        selected_date = q_date.toString("yyyy-MM-dd")
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
        print(f"Date ranges: {self.date_ranges}")

    def generate_output(self):
        if not self.date_ranges:
            print("No date range specified.")
            return
        start_date, end_date = self.date_ranges[-1]
        self.projects = self.view.projects
        all_topics = self.model.research_topics
        result = run_allocation_algorithm(
            employees=self.employees,
            projects=self.projects,
            start_date=start_date,
            end_date=end_date,
            all_topics=all_topics
        )
        print("Algorithm finished.")
        print(f"Iterations used: {result['iteration']}")
        print("\nProject Costs (Actual vs. Target):")
        final_costs = result['final_costs']
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            target_cost = proj.grant_contractual
            print(f"  Project '{proj_name}': Actual={actual_cost:.2f}, Target={float(target_cost):.2f}")
        print("\nOptimized Hours Allocation:")
        allocations = result['allocations']
        for emp_name, emp_data in allocations.items():
            print(f"Employee: {emp_name}")
            daily_allocations = emp_data["daily_allocations"]
            for date_str, day_data in daily_allocations.items():
                nonRnD_hours = day_data['nonRnD']
                non_zero_topics = {topic: hours for topic, hours in day_data.items() if topic != "nonRnD" and hours > 0.0}
                topics_str = ", ".join(f"{t}={val:.2f}" for t, val in non_zero_topics.items())
                print(f"  Date {date_str}: {topics_str}, nonRnD={nonRnD_hours:.2f}")

    def read_timesheets(self):
        directory = QFileDialog.getExistingDirectory(self.view, "Select Directory")
        self.view.directory_label.setText(f"Selected Directory: {directory}")
        self.employees = self.model.extract_data_from_csv(directory, self.date_ranges)
        self.view.create_employee_overview_section(self.employees)
        for emp in self.employees:
            print(f"Employee: {emp.employee_name}")
            for date_str in sorted(emp.research_hours.keys()):
                daily_summary = emp.get_daily_summary(date_str)
                print(f"  Date: {date_str}, Summary: {daily_summary}")

    # --- Explicit Save/Load Methods ---
    def gather_state(self):
        state = {}
        state["date_ranges"] = self.date_ranges
        state["start_date"] = self.view.start_date_input.text()
        state["end_date"] = self.view.end_date_input.text()
        state["projects"] = [self.project_to_dict(proj) for proj in self.view.projects]
        state["employees"] = [self.employee_to_dict(emp) for emp in self.employees]
        return state

    def project_to_dict(self, proj):
        return {
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
            "research_topics": proj.research_topics,
        }

    def employee_to_dict(self, emp):
        return {
            "employee_name": emp.employee_name,
            "research_hours": dict(emp.research_hours),
            "meeting_hours": dict(emp.meeting_hours),
            "nonRnD_hours": dict(emp.nonRnD_hours),
            "research_topics": {k: dict(v) for k, v in emp.research_topics.items()},
            "salary_levels": dict(emp.salary_levels),
        }

    def save_state(self):
        import json
        state = self.gather_state()
        filename, _ = QFileDialog.getSaveFileName(self.view, "Save State", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, "w") as f:
                    json.dump(state, f, indent=2)
                print("State saved to", filename)
            except Exception as e:
                print("Error saving state:", e)

    def load_state(self):
        import json
        filename, _ = QFileDialog.getOpenFileName(self.view, "Load State", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, "r") as f:
                    state = json.load(f)
                self.apply_state(state)
                print("State loaded from", filename)
            except Exception as e:
                print("Error loading state:", e)

    def apply_state(self, state):
        self.date_ranges = state.get("date_ranges", [])
        self.view.start_date_input.setText(state.get("start_date", ""))
        self.view.end_date_input.setText(state.get("end_date", ""))
        projects_data = state.get("projects", [])
        self.view.projects.clear()
        self.view.projects = []
        for proj_dict in projects_data:
            proj = self.dict_to_project(proj_dict)
            self.view.projects.append(proj)
            self.view.create_project_subsection_from_project(proj)
        employees_data = state.get("employees", [])
        self.employees.clear()
        for emp_dict in employees_data:
            emp = self.dict_to_employee(emp_dict)
            self.employees.append(emp)

    def dict_to_project(self, d):
        proj = ProjectModel(
            name=d.get("name", ""),
            funding_agency=d.get("funding_agency", ""),
            grant_min=d.get("grant_min", 0),
            grant_max=d.get("grant_max", 0),
            grant_contractual=d.get("grant_contractual", 0),
            funding_start=d.get("funding_start", ""),
            funding_end=d.get("funding_end", ""),
            currency=d.get("currency", "Euros"),
            exchange_rate=d.get("exchange_rate", 0),
            report_type=d.get("report_type", "Annual"),
            matching_fund_type=d.get("matching_fund_type", "Percentage"),
            matching_fund_value=d.get("matching_fund_value", 0),
            operational_overhead=d.get("operational_overhead", 0),
            travel_cost=d.get("travel_cost", 0),
            equipment_cost=d.get("equipment_cost", 0),
            other_cost=d.get("other_cost", 0)
        )
        proj.research_topics = d.get("research_topics", [])
        return proj

    def dict_to_employee(self, d):
        emp = EmployeeModel(d.get("employee_name", ""))
        emp.research_hours = d.get("research_hours", {})
        emp.meeting_hours = d.get("meeting_hours", {})
        emp.nonRnD_hours = d.get("nonRnD_hours", {})
        emp.research_topics = {k: v for k, v in d.get("research_topics", {}).items()}
        emp.salary_levels = d.get("salary_levels", {})
        return emp
