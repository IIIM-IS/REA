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

import json
from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QLabel, QPushButton,
    QWidget, QListWidget, QLineEdit, QFileDialog, QCalendarWidget, QCheckBox, QComboBox
)
from PyQt5.QtCore import Qt, QSettings
from Model import ProjectModel
from datetime import datetime, timedelta

class ReaDataView(QMainWindow):
    def __init__(self):
        super().__init__()
        # --- Initialize QSettings with a specified INI file ---
        # Ensure that the folder "projectStates" exists.
        self.settings = QSettings("projectStates/config.ini", QSettings.IniFormat)
        
        self.setWindowTitle("Research Expenditure Allocation (REA)")
        self.setGeometry(500, 100, 900, 600)

        self.all_research_topics = [
            "General Info. System / Methodology",
            "Networks / Distributed Systems",
            "System / Architecture Integration",
            "Cogn. Architecture / Hybrid Archi",
            "Data Processing / Data Mgmt",
            "Spatial / Temporal Pattrn. Classification",
            "Training Env. / Artificial Pedagogy",
            "Visualization / UX",
            "Multi-Agent Systems",
            "Sense-Act Cycle / Embedded Systems",
            "Reasoning / Planning",
            "Natural Communic. / Autom. Explanation",
            "Cumulative Learning / Transfer Learn.",
            "Resource Control / Attention",
            "Self-Progr. / Seed-Progr. / Cogn. Growth",
            "Hardware / Robot Hardware",
            "Modeling / Simulation",
        ]

        # Auto-increment counter for projects.
        self.project_counter = int(self.settings.value("project_counter", 0))
        self.projects = []  # Projects will be loaded from state.
        self.employees = []  # This list is set when employee sheets are loaded.

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "INIT Tab")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.main_tab.setLayout(QVBoxLayout())
        self.main_tab.layout().addWidget(self.scroll_area)
        self.main_tab_layout = QVBoxLayout(self.scroll_area_widget)

        self.calendar = QCalendarWidget()
        self.calendar.setVisible(False)
        self.main_tab_layout.addWidget(self.calendar)

        self.open_calendar_button = QPushButton("Open/Close Calendar")
        self.main_tab_layout.addWidget(self.open_calendar_button)

        self.start_label = QLabel("Start Date (MM-DD-YYYY):")
        self.main_tab_layout.addWidget(self.start_label)
        self.start_date_input = QLineEdit()
        self.start_date_input.setObjectName("start_date_input")
        self.start_date_input.textChanged.connect(
            lambda text: self.settings.setValue("start_date_input", text)
        )
        self.main_tab_layout.addWidget(self.start_date_input)

        self.end_label = QLabel("End Date (MM-DD-YYYY):")
        self.main_tab_layout.addWidget(self.end_label)
        self.end_date_input = QLineEdit()
        self.end_date_input.setObjectName("end_date_input")
        self.end_date_input.textChanged.connect(
            lambda text: self.settings.setValue("end_date_input", text)
        )
        self.main_tab_layout.addWidget(self.end_date_input)

        self.apply_dates_button = QPushButton("Apply dates")
        self.apply_dates_button.clicked.connect(self.apply_run_dates)
        self.main_tab_layout.addWidget(self.apply_dates_button)

        self.timesheet_button = QPushButton("TimeSheet Inputs")
        self.main_tab_layout.addWidget(self.timesheet_button)

        self.directory_label = QLabel("No directory selected.")
        self.main_tab_layout.addWidget(self.directory_label)

        self.toggle_employee_button = QPushButton("Show/Hide Employee Overview")
        self.main_tab_layout.addWidget(self.toggle_employee_button)

        self.toggle_project_button = QPushButton("Show/Hide Project Overview")
        self.main_tab_layout.addWidget(self.toggle_project_button)

        self.add_project_button = QPushButton("Add a New Project")
        self.add_project_button.clicked.connect(self.create_project_subsection)
        self.main_tab_layout.addWidget(self.add_project_button)

        self.projects_section_container = QWidget()
        self.projects_section_layout = QVBoxLayout(self.projects_section_container)
        self.main_tab_layout.addWidget(self.projects_section_container)

        self.generate_output_button = QPushButton("Generate Output")
        self.main_tab_layout.addWidget(self.generate_output_button)

        # --- New buttons for explicit Save/Load (if needed) ---
        self.save_state_button = QPushButton("Save State")
        self.main_tab_layout.addWidget(self.save_state_button)

        self.load_state_button = QPushButton("Load State")
        self.main_tab_layout.addWidget(self.load_state_button)

        # --- Load saved projects and main UI fields after building UI ---
        self.load_projects()   # This clears current projects and loads the saved ones.
        self.load_auto_state()

    def load_auto_state(self):
        """Load saved main UI fields from QSettings."""
        start_date = self.settings.value("start_date_input", "")
        end_date = self.settings.value("end_date_input", "")
        self.start_date_input.setText(str(start_date))
        self.end_date_input.setText(str(end_date))

    def apply_run_dates(self):
        """Validate and apply run dates; reject incomplete or multiple entries."""
        start = self.start_date_input.text().strip()
        end = self.end_date_input.text().strip()
        if not start or not end:
            print("Incomplete run dates. Please fill both start and end date.")
            return
        try:
            datetime.strptime(start, "%m-%d-%Y")
            datetime.strptime(end, "%m-%d-%Y")
        except Exception as e:
            print("Invalid date format:", e)
            return
        if self.settings.value("run_dates_applied", False, type=bool):
            print("Run dates already applied. Cannot add multiple date ranges.")
            return
        self.settings.setValue("run_dates_applied", True)
        print("Run dates applied:", start, end)

    def auto_save_projects(self):
        """Serialize the current projects list and save to QSettings."""
        projects_data = []
        for project in self.projects:
            projects_data.append({
                "id": project.id,
                "name": project.name,
                "funding_agency": project.funding_agency,
                "grant_min": project.grant_min,
                "grant_max": project.grant_max,
                "grant_contractual": project.grant_contractual,
                "operational_overhead": project.operational_overhead,
                "matching_fund_type": project.matching_fund_type,
                "matching_fund_value": project.matching_fund_value,
                "max_nonrnd_percentage": project.max_nonrnd_percentage,
                "funding_start": project.funding_start,
                "funding_end": project.funding_end,
                "research_topics": project.research_topics,
            })
        self.settings.setValue("projects_data", projects_data)
        self.settings.setValue("project_counter", self.project_counter)

    def load_projects(self):
        # Clear the UI container first
        self.clear_project_ui()
        
        # Also clear the in-memory projects list
        self.projects.clear()
        
        # Now load from QSettings (or your state file)
        projects_data = self.settings.value("projects_data", [])
        if projects_data:
            for proj_dict in projects_data:
                project = ProjectModel()
                project.id = proj_dict.get("id", None)
                if project.id is None:
                    self.project_counter += 1
                    project.id = self.project_counter
                project.name = proj_dict.get("name", "")
                # … set the rest of the project fields …
                topics = proj_dict.get("research_topics", [])
                project.research_topics = topics if isinstance(topics, list) else list(topics)
        
                # Add to the in-memory list and create its UI subsection
                self.projects.append(project)
                self.create_project_subsection_from_project(project)
        
            self.project_counter = max((p.id for p in self.projects), default=0)
        else:
            self.project_counter = 0

    def is_project_name_unique(self, name, current_project):
        """Return True if no other project (other than current_project) has the same name."""
        for proj in self.projects:
            if proj is not current_project and proj.name == name:
                return False
        return True

    def update_project_name(self, text, project, key, name_input):
        if not text.strip():
            print("Project name cannot be empty!")
            name_input.blockSignals(True)
            name_input.setText(project.name)
            name_input.blockSignals(False)
            return
        if self.is_project_name_unique(text, project):
            self.settings.setValue(key, text)
            setattr(project, 'name', text)
            self.auto_save_projects()
        else:
            print("Project name already exists! Please choose a unique name.")
            name_input.blockSignals(True)
            name_input.setText(project.name)
            name_input.blockSignals(False)

    def handle_overhead_change(self, text, key, project):
        """Update both QSettings and the project's overhead value (stored as a decimal)."""
        self.settings.setValue(key, text)
        try:
            project.operational_overhead = int(text) / 100 if text else 0
        except ValueError:
            project.operational_overhead = 0
        self.auto_save_projects()

    def handle_nonrnd_change(self, text, key, project):
        """Update both QSettings and the project's max non-R&D percentage (stored as a decimal)."""
        self.settings.setValue(key, text)
        try:
            project.max_nonrnd_percentage = int(text) / 100 if text else 0
        except ValueError:
            project.max_nonrnd_percentage = 0
        self.auto_save_projects()

    def closeEvent(self, event):
        self.settings.setValue("start_date_input", self.start_date_input.text())
        self.settings.setValue("end_date_input", self.end_date_input.text())
        self.settings.sync()
        event.accept()

    # --- New methods for saving/loading employee salary data ---
    def load_employee_salary_data(self, employees):
        """Load saved salary levels and periods for each employee from QSettings.
           Keys are based on employee.employee_name.
        """
        for employee in employees:
            key = f"employee_{employee.employee_name}_salary_data"
            
            saved = self.settings.value(key, "{}")  # default to an empty JSON string
            if isinstance(saved, str):
                try:
                    saved = json.loads(saved)
                except Exception as e:
                    print(f"[ERROR] Could not parse salary data for {employee.employee_name}: {e}")
                    saved = {"salary_levels": {}, "salary_periods": []}

            if "salary_levels" not in saved:
                saved["salary_levels"] = {}
            if "salary_periods" not in saved:
                saved["salary_periods"] = []

            employee.salary_levels = saved["salary_levels"]
            employee.salary_periods = saved["salary_periods"]

            if isinstance(saved, dict):
                employee.salary_levels = saved.get("salary_levels", {})
                employee.salary_periods = saved.get("salary_periods", [])
            else:
                employee.salary_levels = {}
                employee.salary_periods = []

    def auto_save_employees(self, employees):
        """Save each employee’s salary levels and periods to QSettings keyed by employee name."""
        for employee in employees:
            key = f"employee_{employee.employee_name}_salary_data"
            data = {
                "salary_levels": employee.salary_levels,
                "salary_periods": employee.salary_periods,
            }
            # Save as a JSON string
            self.settings.setValue(key, json.dumps(data))

    def create_employee_overview_section(self, employees):
        self.employees = employees
        self.load_employee_salary_data(employees)
        
        self.employee_section_container = QWidget()
        self.employee_section_layout = QVBoxLayout(self.employee_section_container)
        for employee in employees:
            if not hasattr(employee, 'salary_levels'):
                employee.salary_levels = {}
            if not hasattr(employee, 'salary_periods'):
                employee.salary_periods = []
            employee_container = QWidget()
            employee_layout = QVBoxLayout(employee_container)
            employee_container.setLayout(employee_layout)
            self.create_employee_overview_subsection(employee, employee_layout)
            separator = QLabel("-------------------------------------------------")
            separator.setAlignment(Qt.AlignCenter)
            self.employee_section_layout.addWidget(employee_container)
            self.employee_section_layout.addWidget(separator)
        self.main_tab_layout.addWidget(self.employee_section_container)
        self.refresh_section_positions()
    
        def toggle_employee_section():
            self.employee_section_container.setVisible(not self.employee_section_container.isVisible())
        self.toggle_employee_button.clicked.connect(toggle_employee_section)

    def create_employee_overview_subsection(self, employee, layout):
        name_label = QLabel("Name")
        name_field = QLineEdit()
        name_field.setText(employee.employee_name)
        layout.addWidget(name_label)
        layout.addWidget(name_field)

        rh_label = QLabel("Total research hours")
        rh_field = QLineEdit()
        rh_field.setText(str(sum(employee.research_hours.values())))
        layout.addWidget(rh_label)
        layout.addWidget(rh_field)

        mh_label = QLabel("Total meeting hours")
        mh_field = QLineEdit()
        mh_field.setText(str(sum(employee.meeting_hours.values())))
        layout.addWidget(mh_label)
        layout.addWidget(mh_field)

        nonrnd_label = QLabel("Total Non-R&D hours")
        nonrnd_field = QLineEdit(str(sum(employee.nonRnD_hours.values())))
        layout.addWidget(nonrnd_label)
        layout.addWidget(nonrnd_field)

        research_topics_label = QLabel("Research Topics")
        layout.addWidget(research_topics_label)
        all_topics = set()
        for date_str, daily_topics in employee.research_topics.items():
            all_topics.update(daily_topics.keys())
        if all_topics:
            for topic in sorted(all_topics):
                topic_label = QLabel(f"- {topic}")
                layout.addWidget(topic_label)

        salary_levels_container_widget = QWidget()
        salary_levels_container = QVBoxLayout(salary_levels_container_widget)
        layout.addWidget(salary_levels_container_widget)
        
        salary_level_counter = [0]
        for period in employee.salary_periods:
            try:
                num = int(period["level"].split()[-1])
                if num > salary_level_counter[0]:
                    salary_level_counter[0] = num
            except:
                pass

        def create_salary_level_widget(level_label=None, amount="", start_date="", end_date=""):
            nonlocal salary_level_counter
            if level_label is None:
                salary_level_counter[0] += 1
                level_label = f"Salary Level {salary_level_counter[0]}"
            widget = QWidget()
            widget_layout = QHBoxLayout(widget)
            label_widget = QLabel(level_label)
            widget_layout.addWidget(label_widget)
            amount_input = QLineEdit()
            amount_input.setPlaceholderText("Enter the salary amount")
            amount_input.setText(str(amount))
            widget_layout.addWidget(amount_input)
            start_lbl = QLabel("Start Date (MM-DD-YYYY):")
            widget_layout.addWidget(start_lbl)
            start_input = QLineEdit()
            start_input.setPlaceholderText("Enter start date")
            start_input.setText(start_date if start_date else self.start_date_input.text())
            widget_layout.addWidget(start_input)
            end_lbl = QLabel("End Date (MM-DD-YYYY):")
            widget_layout.addWidget(end_lbl)
            end_input = QLineEdit()
            end_input.setPlaceholderText("Enter end date")
            end_input.setText(end_date if end_date else self.end_date_input.text())
            widget_layout.addWidget(end_input)
            apply_btn = QPushButton("Apply Salary for Range")
            widget_layout.addWidget(apply_btn)
            remove_btn = QPushButton("Remove Salary Level")
            widget_layout.addWidget(remove_btn)
            salary_levels_container.addWidget(widget)
            
            def apply_salary():
                st = start_input.text().strip()
                en = end_input.text().strip()
                amt = amount_input.text().strip()
                if not st or not en or not amt:
                    print("Please fill in salary, start date, and end date.")
                    return
                try:
                    st_dt = datetime.strptime(st, "%m-%d-%Y")
                    en_dt = datetime.strptime(en, "%m-%d-%Y")
                    amt_val = float(amt)
                except Exception as e:
                    print("Error parsing salary info:", e)
                    return
                current = st_dt
                while current <= en_dt:
                    day_str = current.strftime("%m-%d-%Y")
                    employee.set_salary_level_for_date(day_str, level_label, amt_val)
                    current += timedelta(days=1)
                found = False
                for period in employee.salary_periods:
                    if period.get("level") == level_label:
                        period["amount"] = amt_val
                        period["start_date"] = st
                        period["end_date"] = en
                        found = True
                        break
                if not found:
                    employee.salary_periods.append({
                        "level": level_label,
                        "amount": amt_val,
                        "start_date": st,
                        "end_date": en,
                    })
                print(f"Applied salary of {amt_val} from {st} to {en} for {employee.employee_name} under {level_label}.")
                self.auto_save_employees(self.employees)
            apply_btn.clicked.connect(apply_salary)
    
            def remove_salary():
                st = start_input.text().strip()
                en = end_input.text().strip()
                if not st or not en:
                    print("Cannot remove salary level: missing start or end date.")
                    return
                try:
                    st_dt = datetime.strptime(st, "%m-%d-%Y")
                    en_dt = datetime.strptime(en, "%m-%d-%Y")
                except Exception as e:
                    print("Error parsing salary dates for removal:", e)
                    return
                current = st_dt
                while current <= en_dt:
                    day_str = current.strftime("%m-%d-%Y")
                    if day_str in employee.salary_levels and employee.salary_levels[day_str].get("level") == level_label:
                        del employee.salary_levels[day_str]
                    current += timedelta(days=1)
                for period in employee.salary_periods:
                    if period.get("level") == level_label and period.get("start_date") == st and period.get("end_date") == en:
                        employee.salary_periods.remove(period)
                        break
                salary_levels_container.removeWidget(widget)
                widget.deleteLater()
                print(f"Removed {level_label} for {employee.employee_name}.")
                self.auto_save_employees(self.employees)
            remove_btn.clicked.connect(remove_salary)
            
            return widget
    
        for period in employee.salary_periods:
            create_salary_level_widget(period["level"], period["amount"], period["start_date"], period["end_date"])
        
        add_salary_button = QPushButton("Add Salary Level")
        add_salary_button.clicked.connect(lambda: create_salary_level_widget())
        layout.addWidget(add_salary_button)
    
    def _build_project_subsection(self, project):
        project_subsection = QWidget()
        project_layout = QVBoxLayout(project_subsection)
    
        name_label = QLabel("Project Name:")
        project_layout.addWidget(name_label)
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter project name")
        if not (project.name and project.name.strip()):
            project.name = f"Project_{project.id}"
        name_key = f"project_name_{project.id}"
        name_input.setObjectName(name_key)
        saved_name = self.settings.value(name_key, project.name)
        name_input.setText(str(saved_name))
        name_input.editingFinished.connect(
            lambda key=name_key, proj=project, inp=name_input: self.update_project_name(inp.text(), proj, key, inp)
        )
        project_layout.addWidget(name_input)
    
        funding_label = QLabel("Funding Agency Name:")
        project_layout.addWidget(funding_label)
        funding_input = QLineEdit()
        funding_input.setPlaceholderText("Enter funding agency name")
        funding_key = f"project_funding_{project.id}"
        funding_input.setObjectName(funding_key)
        saved_funding = self.settings.value(funding_key, project.funding_agency)
        funding_input.setText(str(saved_funding))
        funding_input.textChanged.connect(lambda text, key=funding_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        funding_input.textChanged.connect(lambda text: (setattr(project, 'funding_agency', text), self.auto_save_projects()))
        project_layout.addWidget(funding_input)
    
        grant_label = QLabel("Grant Amounts:")
        project_layout.addWidget(grant_label)
        grant_layout = QHBoxLayout()
        min_label = QLabel("Min:")
        grant_layout.addWidget(min_label)
        min_input = QLineEdit()
        min_input.setPlaceholderText("Enter min grant")
        min_key = f"project_grant_min_{project.id}"
        min_input.setObjectName(min_key)
        saved_min = self.settings.value(min_key, str(project.grant_min))
        min_input.setText(str(saved_min))
        min_input.textChanged.connect(lambda text, key=min_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        min_input.textChanged.connect(lambda text: (setattr(project, 'grant_min', text), self.auto_save_projects()))
        grant_layout.addWidget(min_input)
        max_label = QLabel("Max:")
        grant_layout.addWidget(max_label)
        max_input = QLineEdit()
        max_input.setPlaceholderText("Enter max grant")
        max_key = f"project_grant_max_{project.id}"
        max_input.setObjectName(max_key)
        saved_max = self.settings.value(max_key, str(project.grant_max))
        max_input.setText(str(saved_max))
        max_input.textChanged.connect(lambda text, key=max_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        max_input.textChanged.connect(lambda text: (setattr(project, 'grant_max', text), self.auto_save_projects()))
        grant_layout.addWidget(max_input)
        contractual_label = QLabel("Contractual:")
        grant_layout.addWidget(contractual_label)
        contractual_input = QLineEdit()
        contractual_input.setPlaceholderText("Enter contractual grant")
        contractual_key = f"project_grant_contractual_{project.id}"
        contractual_input.setObjectName(contractual_key)
        saved_contractual = self.settings.value(contractual_key, str(project.grant_contractual))
        contractual_input.setText(str(saved_contractual))
        contractual_input.textChanged.connect(lambda text, key=contractual_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        contractual_input.textChanged.connect(lambda text: (setattr(project, 'grant_contractual', text), self.auto_save_projects()))
        grant_layout.addWidget(contractual_input)
        project_layout.addLayout(grant_layout)
    
        overhead_label = QLabel("Overhead Rate (%)")
        project_layout.addWidget(overhead_label)
        overhead_input = QLineEdit()
        overhead_input.setPlaceholderText("Enter overhead as percentage (e.g., 20 for 20%)")
        overhead_key = f"project_overhead_{project.id}"
        overhead_input.setObjectName(overhead_key)
        saved_overhead = self.settings.value(overhead_key, None)
        if saved_overhead is None or saved_overhead == "":
            saved_overhead = project.operational_overhead * 100
        else:
            try:
                oh_val = float(saved_overhead)
                if oh_val < 1:
                    saved_overhead = oh_val * 100
            except:
                saved_overhead = project.operational_overhead * 100
        overhead_input.setText(str(saved_overhead))
        overhead_input.textChanged.connect(lambda text, key=overhead_key: self.handle_overhead_change(text, key, project))
        project_layout.addWidget(overhead_input)
    
        matching_label = QLabel("Matching Fund")
        project_layout.addWidget(matching_label)
        matching_layout = QHBoxLayout()
        matching_type_label = QLabel("Type:")
        matching_layout.addWidget(matching_type_label)
        matching_type_combo = QComboBox()
        matching_type_combo.addItems(["Percentage", "Absolute"])
        matching_type_key = f"project_matching_type_{project.id}"
        matching_type_combo.setObjectName(matching_type_key)
        saved_matching_type = self.settings.value(matching_type_key, project.matching_fund_type)
        if saved_matching_type and saved_matching_type.lower() == "absolute":
            matching_type_combo.setCurrentIndex(1)
        else:
            matching_type_combo.setCurrentIndex(0)
        matching_type_combo.currentTextChanged.connect(lambda text, key=matching_type_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        matching_type_combo.currentTextChanged.connect(lambda text: (setattr(project, 'matching_fund_type', text), self.auto_save_projects()))
        matching_layout.addWidget(matching_type_label)
        matching_layout.addWidget(matching_type_combo)
        matching_value_label = QLabel("Value:")
        matching_layout.addWidget(matching_value_label)
        matching_value_input = QLineEdit()
        matching_value_input.setPlaceholderText("e.g. 50 for 50% if type=Percentage")
        matching_value_key = f"project_matching_value_{project.id}"
        matching_value_input.setObjectName(matching_value_key)
        saved_matching_value = self.settings.value(matching_value_key, str(project.matching_fund_value))
        matching_value_input.setText(str(saved_matching_value))
        matching_value_input.textChanged.connect(lambda text, key=matching_value_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        matching_value_input.textChanged.connect(lambda v: (setattr(project, 'matching_fund_value', float(v) if v else 0.0), self.auto_save_projects()))
        matching_layout.addWidget(matching_value_label)
        matching_layout.addWidget(matching_value_input)
        project_layout.addLayout(matching_layout)
    
        max_nonrnd_label = QLabel("Max Non-R&D (%)")
        project_layout.addWidget(max_nonrnd_label)
        max_nonrnd_input = QLineEdit()
        max_nonrnd_input.setPlaceholderText("Enter max non-R&D percentage (e.g., 10 for 10%)")
        max_nonrnd_key = f"project_max_nonrnd_{project.id}"
        max_nonrnd_input.setObjectName(max_nonrnd_key)
        saved_max_nonrnd = self.settings.value(max_nonrnd_key, None)
        if saved_max_nonrnd is None or saved_max_nonrnd == "":
            saved_max_nonrnd = project.max_nonrnd_percentage * 100
        else:
            try:
                mnr_val = float(saved_max_nonrnd)
                if mnr_val < 1:
                    saved_max_nonrnd = mnr_val * 100
            except:
                saved_max_nonrnd = project.max_nonrnd_percentage * 100
        max_nonrnd_input.setText(str(saved_max_nonrnd))
        max_nonrnd_input.textChanged.connect(lambda text, key=max_nonrnd_key: self.handle_nonrnd_change(text, key, project))
        project_layout.addWidget(max_nonrnd_input)
    
        funding_period_label = QLabel("Funding Period:")
        project_layout.addWidget(funding_period_label)
        funding_period_layout = QHBoxLayout()
        start_label = QLabel("Start Date:")
        funding_period_layout.addWidget(start_label)
        start_input = QLineEdit()
        start_input.setPlaceholderText("Enter start date")
        start_key = f"project_funding_start_{project.id}"
        start_input.setObjectName(start_key)
        saved_start = self.settings.value(start_key, project.funding_start)
        start_input.setText(str(saved_start))
        start_input.textChanged.connect(lambda text, key=start_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        start_input.textChanged.connect(lambda text: (setattr(project, 'funding_start', text), self.auto_save_projects()))
        funding_period_layout.addWidget(start_input)
        end_label = QLabel("End Date:")
        funding_period_layout.addWidget(end_label)
        end_input = QLineEdit()
        end_input.setPlaceholderText("Enter end date")
        end_key = f"project_funding_end_{project.id}"
        end_input.setObjectName(end_key)
        saved_end = self.settings.value(end_key, project.funding_end)
        end_input.setText(str(saved_end))
        end_input.textChanged.connect(lambda text, key=end_key: (self.settings.setValue(key, text), self.auto_save_projects()))
        end_input.textChanged.connect(lambda text: (setattr(project, 'funding_end', text), self.auto_save_projects()))
        funding_period_layout.addWidget(end_input)
        project_layout.addLayout(funding_period_layout)
    
        topics_label = QLabel("Select Research Topics:")
        project_layout.addWidget(topics_label)
        topic_checkboxes = []
        for topic in self.all_research_topics:
            checkbox = QCheckBox(topic)
            if topic in project.research_topics:
                checkbox.setChecked(True)
            project_layout.addWidget(checkbox)
            topic_checkboxes.append(checkbox)
        apply_topics_button = QPushButton("Apply Topics")
        def apply_topics():
            project.research_topics.clear()
            for cb in topic_checkboxes:
                if cb.isChecked():
                    project.add_research_topic(cb.text())
            print(f"Project '{project.name}' Topics Updated:", project.research_topics)
            self.auto_save_projects()
        apply_topics_button.clicked.connect(apply_topics)
        project_layout.addWidget(apply_topics_button)
    
        save_project_button = QPushButton("Save Project")
        def save_project():
            print("\n[INFO] Finalizing project data:")
            print(f"Name: {project.name}")
            print(f"Funding Agency: {project.funding_agency}")
            print(f"Grant (Min / Max / Contractual): {project.grant_min}, {project.grant_max}, {project.grant_contractual}")
            print(f"Funding Period: {project.funding_start} to {project.funding_end}")
            print(f"Research Topics: {project.research_topics}")
            print("Project is stored in self.projects list.")
            self.auto_save_projects()
        save_project_button.clicked.connect(save_project)
        project_layout.addWidget(save_project_button)
    
        # --- Delete Project Button ---
        delete_project_button = QPushButton("Delete Project")
        delete_project_button.clicked.connect(
            lambda: self.delete_project(project, project_subsection)
        )
        project_layout.addWidget(delete_project_button)
    
        return project_subsection
    
    def delete_project(self, project, widget):
        """Delete the given project and remove its widget."""
        if project in self.projects:
            self.projects.remove(project)
        widget.setParent(None)
        widget.deleteLater()
        self.auto_save_projects()
        print(f"[INFO] Project '{project.name}' has been deleted.")
    
    def create_project_subsection(self):
        project = ProjectModel()
        self.project_counter += 1
        if not (project.name and project.name.strip()):
            project.name = f"Project_{project.id}"
        self.projects.append(project)
        project_subsection = self._build_project_subsection(project)
        self.projects_section_layout.addWidget(project_subsection)
        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)
        self.projects_section_layout.addWidget(separator_project)
        self.refresh_section_positions()
        self.auto_save_projects()
    
    def create_project_subsection_from_project(self, project):
        project_subsection = self._build_project_subsection(project)
        self.projects_section_layout.addWidget(project_subsection)
        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)
        self.projects_section_layout.addWidget(separator_project)
        self.refresh_section_positions()
    
    def toggle_project_section(self):
        if self.projects_section_container.isVisible():
            self.projects_section_container.setVisible(False)
        else:
            self.projects_section_container.setVisible(True)
    
    def refresh_add_project_button_position(self):
        self.projects_section_layout.removeWidget(self.add_project_button)
        self.projects_section_layout.addWidget(self.add_project_button)
    
    def refresh_section_positions(self):
        self.main_tab_layout.removeWidget(self.projects_section_container)
        self.main_tab_layout.removeWidget(self.add_project_button)
        self.main_tab_layout.removeWidget(self.toggle_project_button)
        self.main_tab_layout.removeWidget(self.generate_output_button)
        self.main_tab_layout.addWidget(self.projects_section_container)
        self.main_tab_layout.addWidget(self.add_project_button)
        self.main_tab_layout.addWidget(self.toggle_project_button)
        self.main_tab_layout.addWidget(self.generate_output_button)

    def clear_project_ui(self):
        # Remove and delete all widgets in the projects_section_layout
        while self.projects_section_layout.count():
            item = self.projects_section_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()