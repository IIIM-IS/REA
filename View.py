from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QLabel,
    QPushButton, QWidget, QListWidget, QLineEdit, QCalendarWidget, QCheckBox,
    QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTextEdit

class ReaDataView(QMainWindow):
    """
    A simplified view class that displays:
      - Date input controls
      - Employee & Project Overviews
      - Buttons for timesheet reading, generating output, saving/loading state
      - A new interface for adding salary over a specified date range for each employee

    The actual data modifications and saving/loading are handled in the Controller.
    """

    # Existing signals
    employee_salary_range_added = pyqtSignal(dict)
    project_saved = pyqtSignal(object, dict)
    project_deleted = pyqtSignal(object)

    # >>> ADD THIS SIGNAL <<<
    # Emitted when the user edits an existing salary interval.
    # We pass old_start, old_end, plus the new start/end/level/amount.
    employee_salary_interval_edited = pyqtSignal(
        object,  # EmployeeModel
        str,     # old_start_date
        str,     # old_end_date
        str,     # new_start_date
        str,     # new_end_date
        str,     # new_level_label
        str      # new_amount
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Research Expenditure Allocation (REA)")
        self.setGeometry(500, 100, 900, 600)

        # Lists for holding references to model objects
        self.projects = []
        self.employees = []

        # Potential research topics, used when creating project UI
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

        # ---------------- Main Layout / Tabs ---------------- #
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)


        # ---------------- Run Comment ---------------- #
        self.run_comment_label = QLabel("Run Comment:")
        self.main_layout.addWidget(self.run_comment_label)
        self.run_comment_input = QTextEdit()
        self.run_comment_input.setPlaceholderText("Enter run comment here...")
        self.main_layout.addWidget(self.run_comment_input)

        self.tab_widget = QTabWidget()
        self.main_layout.addWidget(self.tab_widget)

        # Main tab
        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "INIT Tab")

        # Scroll area for the main tab
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.main_tab.setLayout(QVBoxLayout())
        self.main_tab.layout().addWidget(self.scroll_area)
        self.main_tab_layout = QVBoxLayout(self.scroll_area_widget)

        # Calendar (initially hidden) + toggle button
        self.calendar = QCalendarWidget()
        self.calendar.setVisible(False)
        self.main_tab_layout.addWidget(self.calendar)

        self.open_calendar_button = QPushButton("Open/Close Calendar")
        self.main_tab_layout.addWidget(self.open_calendar_button)

        # ---------------- Date Inputs ---------------- #
        self.start_label = QLabel("Start Date (MM-DD-YYYY):")
        self.main_tab_layout.addWidget(self.start_label)
        self.start_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.start_date_input)

        self.end_label = QLabel("End Date (MM-DD-YYYY):")
        self.main_tab_layout.addWidget(self.end_label)
        self.end_date_input = QLineEdit()
        self.main_tab_layout.addWidget(self.end_date_input)

        self.apply_dates_button = QPushButton("Apply dates")
        self.main_tab_layout.addWidget(self.apply_dates_button)

        # ---------------- Timesheet reading ---------------- #
        self.timesheet_button = QPushButton("TimeSheet Inputs")
        self.main_tab_layout.addWidget(self.timesheet_button)

        self.directory_label = QLabel("No directory selected.")
        self.main_tab_layout.addWidget(self.directory_label)

        # ---------------- Employee Overview Toggle ---------------- #
        self.toggle_employee_button = QPushButton("Show/Hide Employee Overview")
        self.main_tab_layout.addWidget(self.toggle_employee_button)

        # ---------------- Project Overview + Controls ---------------- #
        self.toggle_project_button = QPushButton("Show/Hide Project Overview")
        self.main_tab_layout.addWidget(self.toggle_project_button)

        self.add_project_button = QPushButton("Add a New Project")
        self.main_tab_layout.addWidget(self.add_project_button)

        self.projects_section_container = QWidget()
        self.projects_section_layout = QVBoxLayout(self.projects_section_container)
        self.main_tab_layout.addWidget(self.projects_section_container)

        self.generate_output_button = QPushButton("Generate Output")
        self.main_tab_layout.addWidget(self.generate_output_button)

        # ---------------- Save/Load State ---------------- #
        self.save_state_button = QPushButton("Save State")
        self.main_tab_layout.addWidget(self.save_state_button)

        self.load_state_button = QPushButton("Load State")
        self.main_tab_layout.addWidget(self.load_state_button)

    # -------------------------------------------------------------------------
    # EMPLOYEE OVERVIEW UI
    # -------------------------------------------------------------------------
    def create_employee_overview_section(self, employees):
        """
        Clears any existing employee UI and re-builds a list of subsections 
        showing name, total hours (read-only), and salary range inputs.
        """
        self.employees = employees

        # Remove old employee UI if it exists
        if hasattr(self, "employee_section_container") and self.employee_section_container:
            self.main_tab_layout.removeWidget(self.employee_section_container)
            self.employee_section_container.deleteLater()

        # Create a fresh container for employees
        self.employee_section_container = QWidget()
        self.employee_section_layout = QVBoxLayout(self.employee_section_container)

        for emp in employees:
            emp_widget = self._build_employee_subsection(emp)
            self.employee_section_layout.addWidget(emp_widget)

            sep = QLabel("-------------------------------------------------")
            sep.setAlignment(Qt.AlignCenter)
            self.employee_section_layout.addWidget(sep)

        self.main_tab_layout.addWidget(self.employee_section_container)

        def toggle_employee_section():
            self.employee_section_container.setVisible(
                not self.employee_section_container.isVisible()
            )

        # Connect the toggle button
        self.toggle_employee_button.clicked.connect(toggle_employee_section)

    def _build_employee_subsection(self, employee):
        """
        Returns a QWidget that displays:
          - Employee name (not editable)
          - Total research/meeting/Non-R&D hours (read-only labels)
          - A list of current salary intervals (with an Edit button)
          - An interface to add a new salary range
        """
        container = QWidget()
        layout = QVBoxLayout(container)

        # -- Employee Name (read-only)
        name_label = QLabel(f"Employee Name: {employee.employee_name}")
        layout.addWidget(name_label)

        # -- Show total research, meeting, non-R&D hours as read-only labels
        total_rh = sum(employee.research_hours.values())
        rh_label = QLabel(f"Total Research Hours: {total_rh:.2f}")
        layout.addWidget(rh_label)

        total_mh = sum(employee.meeting_hours.values())
        mh_label = QLabel(f"Total Meeting Hours: {total_mh:.2f}")
        layout.addWidget(mh_label)

        total_nonrnd = sum(employee.nonRnD_hours.values())
        nonrnd_label = QLabel(f"Total Non-R&D Hours: {total_nonrnd:.2f}")
        layout.addWidget(nonrnd_label)

        # ---------------------------------------------------------------------
        # Display current salary intervals, each with an "Edit" button
        # ---------------------------------------------------------------------
        salary_label = QLabel("Current Salary Levels:")
        layout.addWidget(salary_label)

        for (old_start, old_end, old_level, old_amount) in employee.get_salary_intervals():
            hbox = QHBoxLayout()

            interval_info_label = QLabel(
                f"{old_start} → {old_end}: {old_level} = {old_amount}"
            )
            hbox.addWidget(interval_info_label)

            edit_button = QPushButton("Edit")
            hbox.addWidget(edit_button)

            # Create a hidden sub-form for editing
            edit_widget = QWidget()
            edit_layout = QHBoxLayout(edit_widget)
            edit_widget.setVisible(False)

            # new start date
            new_start_input = QLineEdit()
            new_start_input.setPlaceholderText("New Start Date (MM-DD-YYYY)")
            edit_layout.addWidget(new_start_input)

            # new end date
            new_end_input = QLineEdit()
            new_end_input.setPlaceholderText("New End Date (MM-DD-YYYY)")
            edit_layout.addWidget(new_end_input)

            # new level
            new_level_input = QLineEdit()
            new_level_input.setPlaceholderText("New Level Label")
            edit_layout.addWidget(new_level_input)

            # new amount
            new_amount_input = QLineEdit()
            new_amount_input.setPlaceholderText("New Salary Amount")
            edit_layout.addWidget(new_amount_input)

            # "Save" changes
            save_edit_button = QPushButton("Save")
            edit_layout.addWidget(save_edit_button)

            # "Cancel" - hide the edit widget
            cancel_edit_button = QPushButton("Cancel")
            edit_layout.addWidget(cancel_edit_button)

            layout.addLayout(hbox)
            layout.addWidget(edit_widget)

            def toggle_edit_widget():
                edit_widget.setVisible(not edit_widget.isVisible())

                # If toggling it on, pre-fill with the old values
                if edit_widget.isVisible():
                    new_start_input.setText(old_start)
                    new_end_input.setText(old_end)
                    new_level_input.setText(old_level)
                    new_amount_input.setText(str(old_amount))

            edit_button.clicked.connect(toggle_edit_widget)

            def save_edited_interval():
                new_start_val = new_start_input.text().strip()
                new_end_val = new_end_input.text().strip()
                new_level_val = new_level_input.text().strip()
                new_amount_val = new_amount_input.text().strip()

                # Emit a signal with both the old interval and the new data
                self.employee_salary_interval_edited.emit(
                    employee,
                    old_start,
                    old_end,
                    new_start_val,
                    new_end_val,
                    new_level_val,
                    new_amount_val
                )
                # Hide edit widget after saving
                toggle_edit_widget()

            save_edit_button.clicked.connect(save_edited_interval)

            def cancel_edit():
                toggle_edit_widget()

            cancel_edit_button.clicked.connect(cancel_edit)

        # ---------------------------------------------------------------------
        # Interface to add a NEW salary interval
        # ---------------------------------------------------------------------
        salary_container = QWidget()
        salary_layout = QHBoxLayout(salary_container)
        layout.addWidget(salary_container)

        # Salary level label
        level_label = QLabel("Level Label:")
        salary_layout.addWidget(level_label)
        level_input = QLineEdit()
        salary_layout.addWidget(level_input)

        # Salary amount
        amount_label = QLabel("Salary Amount:")
        salary_layout.addWidget(amount_label)
        amount_input = QLineEdit()
        salary_layout.addWidget(amount_input)

        # Start date
        start_label = QLabel("Start Date (MM-DD-YYYY):")
        salary_layout.addWidget(start_label)
        start_input = QLineEdit()
        salary_layout.addWidget(start_input)

        # End date
        end_label = QLabel("End Date (MM-DD-YYYY):")
        salary_layout.addWidget(end_label)
        end_input = QLineEdit()
        salary_layout.addWidget(end_input)

        # Apply Salary button
        apply_salary_button = QPushButton("Apply Salary")
        salary_layout.addWidget(apply_salary_button)

        def on_apply_salary():
            """
            Gather the salary range info and emit a signal so the Controller
            can update the EmployeeModel by adding a new interval.
            """
            data = {
                "employee_object": employee,
                "level_label": level_input.text().strip(),
                "amount": amount_input.text().strip(),
                "start_date": start_input.text().strip(),
                "end_date": end_input.text().strip()
            }
            self.employee_salary_range_added.emit(data)

            # Optionally clear the fields
            level_input.clear()
            amount_input.clear()
            start_input.clear()
            end_input.clear()

        apply_salary_button.clicked.connect(on_apply_salary)

        return container

    # -------------------------------------------------------------------------
    # PROJECT OVERVIEW UI
    # -------------------------------------------------------------------------
    def create_project_subsection(self):
        """
        Create UI elements for adding a new project. Actual project object
        creation & saving is handled in the Controller.
        """
        project_subsection = self._build_project_subsection()
        self.projects_section_layout.addWidget(project_subsection)

        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)
        self.projects_section_layout.addWidget(separator_project)

    def create_project_subsection_from_project(self, project):
        """
        Create UI elements for a *specific* existing project.
        The Controller should pass in a ProjectModel with pre-filled data.
        """
        project_subsection = self._build_project_subsection(project)
        self.projects_section_layout.addWidget(project_subsection)

        separator_project = QLabel("-------------------------------------------------")
        separator_project.setAlignment(Qt.AlignCenter)
        self.projects_section_layout.addWidget(separator_project)

    def _build_project_subsection(self, project=None):
        """
        Builds and returns a QWidget subsection with fields for project data.
        The controller will connect signals to update the model (not in the view).
        """
        project_subsection = QWidget()
        layout = QVBoxLayout(project_subsection)

        # --- Project name ---
        name_label = QLabel("Project Name:")
        layout.addWidget(name_label)
        name_input = QLineEdit()
        layout.addWidget(name_input)

        # --- Funding agency ---
        funding_label = QLabel("Funding Agency:")
        layout.addWidget(funding_label)
        funding_input = QLineEdit()
        layout.addWidget(funding_input)

        # --- Grant amounts ---
        grant_label = QLabel("Grant Amounts (Min / Max / Contractual):")
        layout.addWidget(grant_label)
        grant_layout = QHBoxLayout()
        min_input = QLineEdit()
        max_input = QLineEdit()
        contractual_input = QLineEdit()

        grant_layout.addWidget(QLabel("Min:"))
        grant_layout.addWidget(min_input)
        grant_layout.addWidget(QLabel("Max:"))
        grant_layout.addWidget(max_input)
        grant_layout.addWidget(QLabel("Contractual:"))
        grant_layout.addWidget(contractual_input)
        layout.addLayout(grant_layout)

        # --- Overhead ---
        overhead_label = QLabel("Overhead Rate (%)")
        layout.addWidget(overhead_label)
        overhead_input = QLineEdit()
        layout.addWidget(overhead_input)

        # --- Matching fund ---
        matching_label = QLabel("Matching Fund:")
        layout.addWidget(matching_label)
        matching_layout = QHBoxLayout()
        matching_type_combo = QComboBox()
        matching_type_combo.addItems(["Percentage", "Absolute"])
        matching_layout.addWidget(QLabel("Type:"))
        matching_layout.addWidget(matching_type_combo)

        matching_value_input = QLineEdit()
        matching_layout.addWidget(QLabel("Value:"))
        matching_layout.addWidget(matching_value_input)
        layout.addLayout(matching_layout)

        # --- Max non-R&D ---
        max_nonrnd_label = QLabel("Max Non-R&D (%)")
        layout.addWidget(max_nonrnd_label)
        max_nonrnd_input = QLineEdit()
        layout.addWidget(max_nonrnd_input)

        # --- Funding period ---
        funding_period_label = QLabel("Funding Period:")
        layout.addWidget(funding_period_label)
        funding_period_layout = QHBoxLayout()
        start_input = QLineEdit()
        end_input = QLineEdit()
        funding_period_layout.addWidget(QLabel("Start Date:"))
        funding_period_layout.addWidget(start_input)
        funding_period_layout.addWidget(QLabel("End Date:"))
        funding_period_layout.addWidget(end_input)
        layout.addLayout(funding_period_layout)

        # --- Research Topics ---
        topics_label = QLabel("Select Research Topics:")
        layout.addWidget(topics_label)
        topic_checkboxes = []
        for t in self.all_research_topics:
            cb = QCheckBox(t)
            layout.addWidget(cb)
            topic_checkboxes.append(cb)

        apply_topics_button = QPushButton("Apply Topics")
        layout.addWidget(apply_topics_button)

        # --- Save & Delete buttons (controller will connect them) ---
        save_project_button = QPushButton("Save Project")
        layout.addWidget(save_project_button)

        delete_project_button = QPushButton("Delete Project")
        layout.addWidget(delete_project_button)

        def on_save_project():
            # Convert overhead % text to float
            oh_text = overhead_input.text().strip()
            oh_float = float(oh_text) / 100.0 if oh_text else 0.0

            # Convert matching type to string
            matching_type = matching_type_combo.currentText().lower()

            # Convert max_nonrnd % text to float
            max_nonrnd_text = max_nonrnd_input.text().strip()
            max_nonrnd_float = float(max_nonrnd_text) / 100.0 if max_nonrnd_text else None

            # Gather topics
            selected_topics = [cb.text() for cb in topic_checkboxes if cb.isChecked()]

            data = {
                "name": name_input.text().strip(),
                "funding_agency": funding_input.text().strip(),
                "grant_min": min_input.text().strip(),
                "grant_max": max_input.text().strip(),
                "grant_contractual": contractual_input.text().strip(),
                "operational_overhead": oh_float,
                "matching_fund_type": matching_type,
                "matching_fund_value": matching_value_input.text().strip(),
                "max_nonrnd_percentage": max_nonrnd_float,
                "funding_start": start_input.text().strip(),
                "funding_end": end_input.text().strip(),
                "research_topics": selected_topics,
            }
            self.project_saved.emit(project, data)

        save_project_button.clicked.connect(on_save_project)

        def on_delete_project():
            self.project_deleted.emit(project)

        delete_project_button.clicked.connect(on_delete_project)

        # If `project` exists, pre-fill fields
        if project:
            name_input.setText(project.name)
            funding_input.setText(project.funding_agency)
            min_input.setText(str(project.grant_min))
            max_input.setText(str(project.grant_max))
            contractual_input.setText(str(project.grant_contractual))
            if project.operational_overhead:
                overhead_input.setText(str(project.operational_overhead * 100))
            matching_type_combo.setCurrentIndex(
                1 if (project.matching_fund_type and project.matching_fund_type.lower() == "absolute") else 0
            )
            matching_value_input.setText(str(project.matching_fund_value))
            if project.max_nonrnd_percentage:
                max_nonrnd_input.setText(str(project.max_nonrnd_percentage * 100))
            start_input.setText(project.funding_start)
            end_input.setText(project.funding_end)
            if project.research_topics:
                for cb in topic_checkboxes:
                    if cb.text() in project.research_topics:
                        cb.setChecked(True)

        return project_subsection

    def toggle_project_section(self):
        visible = self.projects_section_container.isVisible()
        self.projects_section_container.setVisible(not visible)

    def refresh_projects_section(self, projects):
        # Clear old widgets from projects_section_layout
        while self.projects_section_layout.count():
            item = self.projects_section_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Re-create UI for each project
        for p in projects:
            self.create_project_subsection_from_project(p)
