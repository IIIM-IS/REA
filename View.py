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
from PyQt5.QtCore import Qt
from Model import ProjectModel
from datetime import datetime, timedelta


class ReaDataView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Research Expenditure Allocation (REA)")
        self.setGeometry(500, 100, 900, 600)

        # A list of all possible research topics (for demonstration).
        # In practice, one might retrieve this from Model.
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

        # Central Widget and Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Tab Widget
        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Main Tab
        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "INIT Tab")

        ## Scrollable Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        # Create a widget to hold the layout
        self.scroll_area_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_widget)
        # Set up the layout for the scroll area widget
        self.main_tab_layout = QVBoxLayout(self.scroll_area_widget)
        self.main_tab.setLayout(QVBoxLayout())  # Set layout for the main tab
        self.main_tab.layout().addWidget(self.scroll_area)  # Add scroll area to the tab layout


        # Calendar Widget
        self.calendar = QCalendarWidget()
        self.calendar.setVisible(False)
        self.main_tab_layout.addWidget(self.calendar)

        # Button to open calendar
        self.open_calendar_button = QPushButton("Open/Close Calendar")
        self.main_tab_layout.addWidget(self.open_calendar_button)

        # Start Date Input
        self.start_label = QLabel("Start Date (YYYY-MM-DD):")
        self.main_tab_layout.addWidget(self.start_label)
        self.start_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.start_date_input)

        # End Date Input
        self.end_label = QLabel("End Date (YYYY-MM-DD):")
        self.main_tab_layout.addWidget(self.end_label)
        self.end_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.end_date_input)


        # Additional Buttons
        self.apply_dates_button = QPushButton("Apply dates")
        self.main_tab_layout.addWidget(self.apply_dates_button)

        self.timesheet_button = QPushButton("TimeSheet Inputs")
        self.main_tab_layout.addWidget(self.timesheet_button)

        # Label to display directory path
        self.directory_label = QLabel("No directory selected.")
        self.main_tab_layout.addWidget(self.directory_label)

        # Add button to toggle visibility
        self.toggle_employee_button = QPushButton("Show/Hide Employee Overview")
        self.main_tab_layout.addWidget(self.toggle_employee_button)

        # Add button to toggle visibility
        self.toggle_project_button = QPushButton("Show/Hide Project Overview")
        self.main_tab_layout.addWidget(self.toggle_project_button)

        # Add "Add New Project" Button
        self.add_project_button = QPushButton("Add a New Project")
        self.main_tab_layout.addWidget(self.add_project_button)

        # Projects Section Layout
        self.projects_section_container = QWidget()
        self.projects_section_layout = QVBoxLayout(self.projects_section_container)
        #self.refresh_add_project_button_position()
        self.main_tab_layout.addWidget(self.projects_section_container)

        # Generate Output via the Algorithm:
        self.generate_output_button = QPushButton("Generate Output")
        self.main_tab_layout.addWidget(self.generate_output_button)

    def create_employee_overview_section(self, employees):
        # Create a container for the entire section
        self.employee_section_container = QWidget()
        self.employee_section_layout = QVBoxLayout(self.employee_section_container)

        for employee in employees:
            # Create a container widget for each employee
            employee_container = QWidget()
            employee_layout = QVBoxLayout(employee_container)
            employee_container.setLayout(employee_layout)

            # Call create_employee_overview_subsection with the specific layout
            self.create_employee_overview_subsection(employee, employee_layout)

            # Add a separator label or visual separator if desired
            separator = QLabel("-------------------------------------------------")
            separator.setAlignment(Qt.AlignCenter)

            #
            self.employee_section_layout.addWidget(employee_container)
            self.employee_section_layout.addWidget(separator)

        # Add the entire section container to the main layout
        self.main_tab_layout.addWidget(self.employee_section_container)
        self.refresh_section_positions()


        def toggle_employee_section():
            if self.employee_section_container.isVisible():
                self.employee_section_container.setVisible(False)
            else:
                self.employee_section_container.setVisible(True)

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

        # Add a section for research topics
        research_topics_label = QLabel("Research Topics")
        layout.addWidget(research_topics_label)

        # Show only the topics (no hours)
        #    We'll collect all topic names from all days in this time period
        all_topics = set()  # to avoid duplicates
        for date_str, daily_topics in employee.research_topics.items():
            all_topics.update(daily_topics.keys())

        # Only display topic names if any exist
        if all_topics:
            research_topics_label = QLabel("Research Topics (without hours):")
            layout.addWidget(research_topics_label)

            for topic in sorted(all_topics):
                topic_label = QLabel(f"- {topic}")
                layout.addWidget(topic_label)

        # Add a container for dynamic salary levels
        salary_levels_container = QVBoxLayout()
        layout.addLayout(salary_levels_container)

        # Initialize salary level count
        salary_level_count = 0  # Counter for salary levels

        def add_salary_level():
            nonlocal salary_level_count
            salary_level_count += 1  # Increment the salary level count
            # Create a horizontal layout for the salary level inputs
            salary_level_layout = QHBoxLayout()

            salary_amount = QLabel(f"Salary {salary_level_count}")
            salary_amount_input = QLineEdit()
            salary_amount_input.setPlaceholderText("Enter the salary amount")
            # salary_amount_input.textChanged.connect(lambda text: setattr(employee, 'salary_level', text))
            salary_level_layout.addWidget(salary_amount)
            salary_level_layout.addWidget(salary_amount_input)

            # Set the entered salary level
            #employee.salary_level = salary_amount_input
            #name_input.textChanged.connect(lambda text: setattr(project, 'name', text))

            # Add start and end date inputs
            salary_start_label = QLabel("Start Date (YYYY-MM-DD):")
            salary_start_input = QLineEdit()
            salary_start_input.setPlaceholderText("Enter start date")

            # NEW: Default to the user-specified start date
            salary_start_input.setText(self.start_date_input.text())

            #salary_amount_input.setText(self.start_date_input.toString("yyyy-MM-dd"))
            salary_level_layout.addWidget(salary_start_label)
            salary_level_layout.addWidget(salary_start_input)

            salary_end_label = QLabel("End Date (YYYY-MM-DD):")
            salary_end_input = QLineEdit()
            salary_end_input.setPlaceholderText("Enter end date")
            #salary_end_input.setText(self.end_date_input.toString("yyyy-MM-dd"))

            # NEW: Default to the user-specified end date
            salary_end_input.setText(self.end_date_input.text())

            salary_level_layout.addWidget(salary_end_label)
            salary_level_layout.addWidget(salary_end_input)

            # Add the completed layout to the container
            salary_levels_container.addLayout(salary_level_layout)

            # Button to apply the salary to each day in the date range
            apply_button = QPushButton("Apply Salary for Range")
            salary_level_layout.addWidget(apply_button)

            # Define how to apply the salary
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

                # Iterate through the date range
                current_date = start_date
                while current_date <= end_date:
                    day_str = current_date.strftime("%Y-%m-%d")
                    # e.g., we label it "Salary Level 1, 2, etc."
                    level_label = f"Salary Level {salary_level_count}"
                    employee.set_salary_level_for_date(day_str, level_label, amount_val)
                    current_date += timedelta(days=1)

                print(f"Applied salary of {amount_val} from {start_text} to {end_text} for {employee.employee_name}.")

            apply_button.clicked.connect(apply_salary_for_range)

        add_salary_level()
        # Add the "Add Salary Level" button
        add_salary_button = QPushButton("Add Salary Level")
        layout.addWidget(add_salary_button)
        add_salary_button.clicked.connect(add_salary_level)



    def create_project_subsection(self):
        # Create a new ProjectModel instance
        project = ProjectModel()
        self.projects.append(project)

        # Create a subsection (container + layout)
        project_subsection = QWidget()
        project_layout = QVBoxLayout(project_subsection)

        # Project Name
        name_label = QLabel("Project Name:")
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter project name")
        name_input.textChanged.connect(lambda text: setattr(project, 'name', text))
        project_layout.addWidget(name_label)
        project_layout.addWidget(name_input)

        # Funding Agency
        funding_label = QLabel("Funding Agency Name:")
        funding_input = QLineEdit()
        funding_input.setPlaceholderText("Enter funding agency name")
        funding_input.textChanged.connect(lambda text: setattr(project, 'funding_agency', text))
        project_layout.addWidget(funding_label)
        project_layout.addWidget(funding_input)

        # Grant Amounts
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

        # Funding Period
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

        # Create a section to show all research topics with checkboxes
        topics_label = QLabel("Select Research Topics:")
        project_layout.addWidget(topics_label)

        # We'll store the checkboxes in a local list or dictionary
        # so we can refer to them when the user clicks "Apply Topics"
        topic_checkboxes = []
        for topic in self.all_research_topics:
            checkbox = QCheckBox(topic)
            project_layout.addWidget(checkbox)
            topic_checkboxes.append(checkbox)

        #   Button to apply the checked topics to the project
        apply_topics_button = QPushButton("Apply Topics")

        def apply_topics():
            # Clear the project's research_topics first if you want a fresh set each time
            # or else you can keep them and only add new ones.
            project.research_topics.clear()

            # Add each checked topic to the project
            for cb in topic_checkboxes:
                if cb.isChecked():
                    project.add_research_topic(cb.text())

            print(f"Project '{project.name}' Topics Updated:", project.research_topics)

        apply_topics_button.clicked.connect(apply_topics)
        project_layout.addWidget(apply_topics_button)

        # Add the subsection to the main projects section layout
        self.projects_section_layout.addWidget(project_subsection)

        # Add a separator label or visual separator if desired
        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)

        #
        self.projects_section_layout.addWidget(separator_project)

        # Refresh the button and sections positions
        self.refresh_section_positions()

    def toggle_project_section(self):
        if self.projects_section_container.isVisible():
            self.projects_section_container.setVisible(False)
        else:
            self.projects_section_container.setVisible(True)


    def refresh_add_project_button_position(self):
        # Remove the button from its current position
        self.projects_section_layout.removeWidget(self.add_project_button)

        # Add the button back at the bottom
        self.projects_section_layout.addWidget(self.add_project_button)

    def refresh_section_positions(self):
        # Remove the projects section and button
        self.main_tab_layout.removeWidget(self.projects_section_container)
        self.main_tab_layout.removeWidget(self.add_project_button)
        self.main_tab_layout.removeWidget(self.toggle_project_button)

        # Add the projects section and button at the end
        self.main_tab_layout.addWidget(self.projects_section_container)
        self.main_tab_layout.addWidget(self.add_project_button)
        self.main_tab_layout.addWidget(self.toggle_project_button)