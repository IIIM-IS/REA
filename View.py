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

from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QLabel, QPushButton,
    QWidget, QListWidget, QLineEdit, QFileDialog, QCalendarWidget, QCheckBox
)
from PyQt5.QtCore import Qt, QSettings
from Model import ProjectModel
from datetime import datetime, timedelta

class ReaDataView(QMainWindow):
    def __init__(self):
        super().__init__()
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

        self.projects = []

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
        self.main_tab_layout = QVBoxLayout(self.scroll_area_widget)
        self.main_tab.setLayout(QVBoxLayout())
        self.main_tab.layout().addWidget(self.scroll_area)

        self.calendar = QCalendarWidget()
        self.calendar.setVisible(False)
        self.main_tab_layout.addWidget(self.calendar)

        self.open_calendar_button = QPushButton("Open/Close Calendar")
        self.main_tab_layout.addWidget(self.open_calendar_button)

        self.start_label = QLabel("Start Date (YYYY-MM-DD):")
        self.main_tab_layout.addWidget(self.start_label)
        self.start_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.start_date_input)

        self.end_label = QLabel("End Date (YYYY-MM-DD):")
        self.main_tab_layout.addWidget(self.end_label)
        self.end_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.end_date_input)

        self.apply_dates_button = QPushButton("Apply dates")
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
        self.main_tab_layout.addWidget(self.add_project_button)

        self.projects_section_container = QWidget()
        self.projects_section_layout = QVBoxLayout(self.projects_section_container)
        self.main_tab_layout.addWidget(self.projects_section_container)

        self.generate_output_button = QPushButton("Generate Output")
        self.main_tab_layout.addWidget(self.generate_output_button)

        # --- New buttons for explicit Save/Load ---
        self.save_state_button = QPushButton("Save State")
        self.main_tab_layout.addWidget(self.save_state_button)

        self.load_state_button = QPushButton("Load State")
        self.main_tab_layout.addWidget(self.load_state_button)

    def closeEvent(self, event):
        settings = QSettings("IIIM", "REAApp")
        settings.setValue("start_date", self.start_date_input.text())
        settings.setValue("end_date", self.end_date_input.text())
        settings.sync()  # Force an immediate write to disk.
        event.accept()

    def create_employee_overview_section(self, employees):
        self.employee_section_container = QWidget()
        self.employee_section_layout = QVBoxLayout(self.employee_section_container)
        for employee in employees:
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
            if self.employee_section_container.isVisible():
                self.employee_section_container.setVisible(False)
            else:
                self.employee_section_container.setVisible(True)

        self.toggle_employee_button.clicked.connect(toggle_employee_section)

    def create_employee_overview_subsection(self, employee, layout):
        from datetime import datetime, timedelta
        # --- Basic Employee Information ---
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

        # --- Research Topics Section ---
        research_topics_label = QLabel("Research Topics")
        layout.addWidget(research_topics_label)

        all_topics = set()
        for date_str, daily_topics in employee.research_topics.items():
            all_topics.update(daily_topics.keys())

        if all_topics:
            research_topics_label = QLabel("Research Topics (without hours):")
            layout.addWidget(research_topics_label)
            for topic in sorted(all_topics):
                topic_label = QLabel(f"- {topic}")
                layout.addWidget(topic_label)

        # --- Salary Levels Section with Add/Remove Functionality ---
        # Create a container widget for salary level rows so they can be individually removed.
        salary_levels_container_widget = QWidget()
        salary_levels_container = QVBoxLayout(salary_levels_container_widget)
        layout.addWidget(salary_levels_container_widget)

        salary_level_count = 0
        def add_salary_level():
            nonlocal salary_level_count
            salary_level_count += 1
            current_level_label = f"Salary Level {salary_level_count}"
            # Wrap each salary level row in its own widget.
            salary_level_widget = QWidget()
            salary_level_layout = QHBoxLayout(salary_level_widget)

            # Salary Level Label
            salary_label = QLabel(current_level_label)
            salary_level_layout.addWidget(salary_label)

            # Salary Amount Input
            salary_amount_input = QLineEdit()
            salary_amount_input.setPlaceholderText("Enter the salary amount")
            salary_level_layout.addWidget(salary_amount_input)

            # Start Date Input
            salary_start_label = QLabel("Start Date (YYYY-MM-DD):")
            salary_level_layout.addWidget(salary_start_label)
            salary_start_input = QLineEdit()
            salary_start_input.setPlaceholderText("Enter start date")
            salary_start_input.setText(self.start_date_input.text())
            salary_level_layout.addWidget(salary_start_input)

            # End Date Input
            salary_end_label = QLabel("End Date (YYYY-MM-DD):")
            salary_level_layout.addWidget(salary_end_label)
            salary_end_input = QLineEdit()
            salary_end_input.setPlaceholderText("Enter end date")
            salary_end_input.setText(self.end_date_input.text())
            salary_level_layout.addWidget(salary_end_input)

            # Apply Button
            apply_button = QPushButton("Apply Salary for Range")
            salary_level_layout.addWidget(apply_button)

            # Remove Button
            remove_button = QPushButton("Remove Salary Level")
            salary_level_layout.addWidget(remove_button)

            # Add this salary level widget to the container.
            salary_levels_container.addWidget(salary_level_widget)

            def apply_salary_for_range():
                start_text = salary_start_input.text().strip()
                end_text = salary_end_input.text().strip()
                amount_text = salary_amount_input.text().strip()
                if not start_text or not end_text or not amount_text:
                    print("Please fill in salary, start date, and end date.")
                    return
                try:
                    start_date = datetime.strptime(start_text, "%Y-%m-%d")
                    end_date = datetime.strptime(end_text, "%Y-%m-%d")
                    amount_val = float(amount_text)
                except Exception as e:
                    print("Error parsing salary info:", e)
                    return
                current_date = start_date
                while current_date <= end_date:
                    day_str = current_date.strftime("%Y-%m-%d")
                    employee.set_salary_level_for_date(day_str, current_level_label, amount_val)
                    current_date += timedelta(days=1)
                print(f"Applied salary of {amount_val} from {start_text} to {end_text} for {employee.employee_name} under {current_level_label}.")
            apply_button.clicked.connect(apply_salary_for_range)

            def remove_salary_level():
                start_text = salary_start_input.text().strip()
                end_text = salary_end_input.text().strip()
                if not start_text or not end_text:
                    print("Cannot remove salary level: missing start or end date.")
                    return
                try:
                    start_date = datetime.strptime(start_text, "%Y-%m-%d")
                    end_date = datetime.strptime(end_text, "%Y-%m-%d")
                except Exception as e:
                    print("Error parsing salary dates for removal:", e)
                    return
                current_date = start_date
                while current_date <= end_date:
                    day_str = current_date.strftime("%Y-%m-%d")
                    if day_str in employee.salary_levels and employee.salary_levels[day_str].get("level") == current_level_label:
                        del employee.salary_levels[day_str]
                    current_date += timedelta(days=1)
                salary_levels_container.removeWidget(salary_level_widget)
                salary_level_widget.deleteLater()
                print(f"Removed {current_level_label} for {employee.employee_name}.")
            remove_button.clicked.connect(remove_salary_level)

        add_salary_level()
        add_salary_button = QPushButton("Add Salary Level")
        layout.addWidget(add_salary_button)
        add_salary_button.clicked.connect(add_salary_level)

    def create_project_subsection(self):
        project = ProjectModel()
        self.projects.append(project)
        project_subsection = QWidget()
        project_layout = QVBoxLayout(project_subsection)
        name_label = QLabel("Project Name:")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter project name")
        name_input.textChanged.connect(lambda text: setattr(project, 'name', text))
        project_layout.addWidget(name_label)
        project_layout.addWidget(name_input)
        funding_label = QLabel("Funding Agency Name:")
        funding_input = QLineEdit()
        funding_input.setPlaceholderText("Enter funding agency name")
        funding_input.textChanged.connect(lambda text: setattr(project, 'funding_agency', text))
        project_layout.addWidget(funding_label)
        project_layout.addWidget(funding_input)
        grant_label = QLabel("Grant Amounts:")
        grant_layout = QHBoxLayout()
        min_label = QLabel("Min:")
        min_input = QLineEdit()
        min_input.setPlaceholderText("Enter min grant")
        min_input.textChanged.connect(lambda text: setattr(project, 'grant_min', text))
        max_label = QLabel("Max:")
        max_input = QLineEdit()
        max_input.setPlaceholderText("Enter max grant")
        max_input.textChanged.connect(lambda text: setattr(project, 'grant_max', text))
        contractual_label = QLabel("Contractual:")
        contractual_input = QLineEdit()
        contractual_input.setPlaceholderText("Enter contractual grant")
        contractual_input.textChanged.connect(lambda text: setattr(project, 'grant_contractual', text))
        grant_layout.addWidget(min_label)
        grant_layout.addWidget(min_input)
        grant_layout.addWidget(max_label)
        grant_layout.addWidget(max_input)
        grant_layout.addWidget(contractual_label)
        grant_layout.addWidget(contractual_input)
        project_layout.addLayout(grant_layout)
        funding_period_label = QLabel("Funding Period:")
        funding_period_layout = QHBoxLayout()
        start_label = QLabel("Start Date:")
        start_input = QLineEdit()
        start_input.setPlaceholderText("Enter start date")
        start_input.textChanged.connect(lambda text: setattr(project, 'funding_start', text))
        end_label = QLabel("End Date:")
        end_input = QLineEdit()
        end_input.setPlaceholderText("Enter end date")
        end_input.textChanged.connect(lambda text: setattr(project, 'funding_end', text))
        funding_period_layout.addWidget(start_label)
        funding_period_layout.addWidget(start_input)
        funding_period_layout.addWidget(end_label)
        funding_period_layout.addWidget(end_input)
        project_layout.addLayout(funding_period_layout)
        topics_label = QLabel("Select Research Topics:")
        project_layout.addWidget(topics_label)
        topic_checkboxes = []
        for topic in self.all_research_topics:
            checkbox = QCheckBox(topic)
            project_layout.addWidget(checkbox)
            topic_checkboxes.append(checkbox)
        apply_topics_button = QPushButton("Apply Topics")
        def apply_topics():
            project.research_topics.clear()
            for cb in topic_checkboxes:
                if cb.isChecked():
                    project.add_research_topic(cb.text())
            print(f"Project '{project.name}' Topics Updated:", project.research_topics)
        apply_topics_button.clicked.connect(apply_topics)
        project_layout.addWidget(apply_topics_button)
        self.projects_section_layout.addWidget(project_subsection)
        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)
        self.projects_section_layout.addWidget(separator_project)
        self.refresh_section_positions()

    def create_project_subsection_from_project(self, project):
        project_subsection = QWidget()
        project_layout = QVBoxLayout(project_subsection)
        name_label = QLabel("Project Name:")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter project name")
        name_input.setText(project.name)
        name_input.textChanged.connect(lambda text: setattr(project, 'name', text))
        project_layout.addWidget(name_label)
        project_layout.addWidget(name_input)
        funding_label = QLabel("Funding Agency Name:")
        funding_input = QLineEdit()
        funding_input.setPlaceholderText("Enter funding agency name")
        funding_input.setText(project.funding_agency)
        funding_input.textChanged.connect(lambda text: setattr(project, 'funding_agency', text))
        project_layout.addWidget(funding_label)
        project_layout.addWidget(funding_input)
        grant_label = QLabel("Grant Amounts:")
        grant_layout = QHBoxLayout()
        min_label = QLabel("Min:")
        min_input = QLineEdit()
        min_input.setPlaceholderText("Enter min grant")
        min_input.setText(str(project.grant_min))
        min_input.textChanged.connect(lambda text: setattr(project, 'grant_min', text))
        max_label = QLabel("Max:")
        max_input = QLineEdit()
        max_input.setPlaceholderText("Enter max grant")
        max_input.setText(str(project.grant_max))
        max_input.textChanged.connect(lambda text: setattr(project, 'grant_max', text))
        contractual_label = QLabel("Contractual:")
        contractual_input = QLineEdit()
        contractual_input.setPlaceholderText("Enter contractual grant")
        contractual_input.setText(str(project.grant_contractual))
        contractual_input.textChanged.connect(lambda text: setattr(project, 'grant_contractual', text))
        grant_layout.addWidget(min_label)
        grant_layout.addWidget(min_input)
        grant_layout.addWidget(max_label)
        grant_layout.addWidget(max_input)
        grant_layout.addWidget(contractual_label)
        grant_layout.addWidget(contractual_input)
        project_layout.addLayout(grant_layout)
        funding_period_label = QLabel("Funding Period:")
        funding_period_layout = QHBoxLayout()
        start_label = QLabel("Start Date:")
        start_input = QLineEdit()
        start_input.setPlaceholderText("Enter start date")
        start_input.setText(project.funding_start)
        start_input.textChanged.connect(lambda text: setattr(project, 'funding_start', text))
        end_label = QLabel("End Date:")
        end_input = QLineEdit()
        end_input.setPlaceholderText("Enter end date")
        end_input.setText(project.funding_end)
        end_input.textChanged.connect(lambda text: setattr(project, 'funding_end', text))
        funding_period_layout.addWidget(start_label)
        funding_period_layout.addWidget(start_input)
        funding_period_layout.addWidget(end_label)
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
        apply_topics_button.clicked.connect(apply_topics)
        project_layout.addWidget(apply_topics_button)
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
