from PyQt5.QtWidgets import (  # pyright: ignore[reportMissingImports]
    QMainWindow, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QLabel,
    QPushButton, QWidget, QLineEdit, QCalendarWidget, QCheckBox,
    QComboBox
)

from PyQt5.QtCore import Qt, pyqtSignal  # pyright: ignore[reportMissingImports]
from PyQt5.QtWidgets import QTextEdit  # pyright: ignore[reportMissingImports]

class ReaDataView(QMainWindow):
    """
    A simplified view class that displays:
      - Date input controls
      - Employee & Project Overviews (now in separate tabs)
      - Buttons for timesheet reading, generating output, saving/loading state
      - A new interface for adding salary over a specified date range for each employee

    The actual data modifications and saving/loading are handled in the Controller.
    """

    # Existing signals
    employee_salary_range_added = pyqtSignal(dict)
    project_saved = pyqtSignal(object, dict)
    project_deleted = pyqtSignal(object)

    # Emitted when the user edits an existing salary interval.
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
        self.setMinimumSize(700, 500)

        # Lists for holding references to model objects
        # Assuming ProjectModel objects will be stored here eventually by Controller
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

        # Available colors for project tabs
        self.available_colors = ["#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
                                 "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
                                 "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
                                 "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"] # Using hex for more choice
        # Dictionary to store assigned colors to projects (Project Object -> Color String)
        self.project_colors = {}

        # Dictionary to map projects to their tab widgets
        self.project_widgets = {}

        # ---------------- Main Layout / Tabs ---------------- #
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # ---------------- Run Comment ---------------- #
        run_comment_container = QWidget()
        run_comment_container_layout = QVBoxLayout(run_comment_container)
        run_comment_container_layout.setContentsMargins(0, 0, 0, 0)
        
        run_comment_header = QHBoxLayout()
        self.run_comment_label = QLabel("Run Comment:")
        run_comment_header.addWidget(self.run_comment_label)
        self.run_comment_toggle_button = QPushButton("▼")
        self.run_comment_toggle_button.setFixedSize(25, 25)
        self.run_comment_toggle_button.setToolTip("Collapse or expand the run comment field. Use this to save screen space when the comment field is not needed.")
        self.run_comment_toggle_button.setEnabled(True)
        self.run_comment_toggle_button.clicked.connect(self._toggle_run_comment)
        run_comment_header.addWidget(self.run_comment_toggle_button)
        run_comment_header.addStretch()
        run_comment_container_layout.addLayout(run_comment_header)
        
        self.run_comment_input = QTextEdit()
        self.run_comment_input.setPlaceholderText("Enter run comment here...")
        self.run_comment_input.setMinimumHeight(60)
        self.run_comment_input.setMaximumHeight(200)
        self.run_comment_visible = True
        run_comment_container_layout.addWidget(self.run_comment_input)
        
        self.main_layout.addWidget(run_comment_container)

        self.tab_widget = QTabWidget()
        # Enable document mode for a cleaner look, especially with colored tabs
        # self.tab_widget.setDocumentMode(True) # Optional: uncomment for a different look
        self.main_layout.addWidget(self.tab_widget)

        # Main tab (INIT Tab)
        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "INIT Tab")
        self.main_tab_layout_container = QVBoxLayout(self.main_tab) # Layout for the tab itself

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_area_widget)
        self.main_tab_layout_container.addWidget(self.scroll_area)
        self.main_tab_layout = QVBoxLayout(self.scroll_area_widget)
        self.main_tab_layout.setAlignment(Qt.AlignCenter)

        # Calendar (initially hidden) + toggle button
        self.calendar = QCalendarWidget()
        self.calendar.setVisible(False)
        self.main_tab_layout.addWidget(self.calendar)

        calendar_container = QWidget()
        calendar_layout = QHBoxLayout(calendar_container)
        calendar_layout.setAlignment(Qt.AlignCenter)
        calendar_layout.setContentsMargins(0, 0, 0, 0)
        self.open_calendar_button = QPushButton("Open/Close Calendar")
        self.open_calendar_button.setToolTip("Toggle the calendar widget to visually select dates. The calendar can help you pick start and end dates for your analysis period. Click to show or hide the calendar.")
        self.open_calendar_button.setEnabled(True)
        calendar_layout.addWidget(self.open_calendar_button)
        self.main_tab_layout.addWidget(calendar_container)

        # ---------------- Date Inputs ---------------- #
        start_container = QWidget()
        start_layout = QVBoxLayout(start_container)
        start_layout.setAlignment(Qt.AlignCenter)
        start_layout.setContentsMargins(0, 0, 0, 0)
        self.start_label = QLabel("Start Date (MM-DD-YYYY):")
        self.start_label.setAlignment(Qt.AlignCenter)
        start_layout.addWidget(self.start_label)
        self.start_date_input = QLineEdit()
        start_layout.addWidget(self.start_date_input)
        self.main_tab_layout.addWidget(start_container)

        end_container = QWidget()
        end_layout = QVBoxLayout(end_container)
        end_layout.setAlignment(Qt.AlignCenter)
        end_layout.setContentsMargins(0, 0, 0, 0)
        self.end_label = QLabel("End Date (MM-DD-YYYY):")
        self.end_label.setAlignment(Qt.AlignCenter)
        end_layout.addWidget(self.end_label)
        self.end_date_input = QLineEdit()
        end_layout.addWidget(self.end_date_input)
        self.main_tab_layout.addWidget(end_container)

        apply_dates_container = QWidget()
        apply_dates_layout = QHBoxLayout(apply_dates_container)
        apply_dates_layout.setAlignment(Qt.AlignCenter)
        apply_dates_layout.setContentsMargins(0, 0, 0, 0)
        self.apply_dates_button = QPushButton("Apply dates")
        self.apply_dates_button.setToolTip("Add the date range (start and end dates) to your analysis. You can add multiple date ranges. The dates must be in MM-DD-YYYY format. The algorithm will process all date ranges you add.")
        self.apply_dates_button.setEnabled(True)
        apply_dates_layout.addWidget(self.apply_dates_button)
        self.main_tab_layout.addWidget(apply_dates_container)

        # ---------------- Timesheet reading ---------------- #
        timesheet_container = QWidget()
        timesheet_layout = QHBoxLayout(timesheet_container)
        timesheet_layout.setAlignment(Qt.AlignCenter)
        timesheet_layout.setContentsMargins(0, 0, 0, 0)
        self.timesheet_button = QPushButton("TimeSheet Inputs")
        self.timesheet_button.setToolTip("Load employee timesheet CSV files from a directory. The program will extract employee work hours and research topic allocations for the specified date ranges. Make sure you have added at least one date range first. The CSV files should follow the standard timesheet format.")
        self.timesheet_button.setEnabled(True)
        timesheet_layout.addWidget(self.timesheet_button)
        self.main_tab_layout.addWidget(timesheet_container)

        self.directory_label = QLabel("No directory selected.")
        self.directory_label.setAlignment(Qt.AlignCenter)
        self.main_tab_layout.addWidget(self.directory_label)

        # ---------------- Project Controls ---------------- #
        add_project_container = QWidget()
        add_project_layout = QHBoxLayout(add_project_container)
        add_project_layout.setAlignment(Qt.AlignCenter)
        add_project_layout.setContentsMargins(0, 0, 0, 0)
        self.add_project_button = QPushButton("Add a New Project")
        self.add_project_button.setToolTip("Create a new project with cost targets, overhead, matching requirements, and research topic allocations. Each project will appear as a separate tab where you can configure its settings.")
        self.add_project_button.setEnabled(True)
        add_project_layout.addWidget(self.add_project_button)
        self.main_tab_layout.addWidget(add_project_container)

        # ---------------- Output and Save/Load ---------------- #
        generate_container = QWidget()
        generate_layout = QHBoxLayout(generate_container)
        generate_layout.setAlignment(Qt.AlignCenter)
        generate_layout.setContentsMargins(0, 0, 0, 0)
        self.generate_output_button = QPushButton("Generate Output")
        self.generate_output_button.setToolTip("Run the allocation algorithm to distribute employee hours across projects. This will optimize the allocation based on cost targets, constraints, and preferences. Results will be displayed in the Diagnostics tab. Make sure you have loaded timesheets and created at least one project.")
        self.generate_output_button.setEnabled(True)
        generate_layout.addWidget(self.generate_output_button)
        self.main_tab_layout.addWidget(generate_container)

        save_state_container = QWidget()
        save_state_layout = QHBoxLayout(save_state_container)
        save_state_layout.setAlignment(Qt.AlignCenter)
        save_state_layout.setContentsMargins(0, 0, 0, 0)
        self.save_state_button = QPushButton("Save State")
        self.save_state_button.setToolTip("Save the current project state (employees, projects, date ranges, salaries) to a JSON file. This allows you to resume work later or create backups. All project configurations and employee data will be preserved.")
        self.save_state_button.setEnabled(True)
        save_state_layout.addWidget(self.save_state_button)
        self.main_tab_layout.addWidget(save_state_container)

        load_state_container = QWidget()
        load_state_layout = QHBoxLayout(load_state_container)
        load_state_layout.setAlignment(Qt.AlignCenter)
        load_state_layout.setContentsMargins(0, 0, 0, 0)
        self.load_state_button = QPushButton("Load State")
        self.load_state_button.setToolTip("Load a previously saved project state from a JSON file. This will restore all employees, projects, date ranges, and salary information. Current data will be replaced with the loaded state.")
        self.load_state_button.setEnabled(True)
        load_state_layout.addWidget(self.load_state_button)
        self.main_tab_layout.addWidget(load_state_container)

        # ---------------- Employees Tab ---------------- #
        self.employees_tab = QWidget()
        self.tab_widget.addTab(self.employees_tab, "Employees")
        self.employees_tab_layout_container = QVBoxLayout(self.employees_tab) # Layout for the tab itself

        self.employees_scroll_area = QScrollArea()
        self.employees_scroll_area.setWidgetResizable(True)
        self.employees_scroll_area_widget = QWidget()
        self.employees_scroll_area.setWidget(self.employees_scroll_area_widget)
        self.employees_tab_layout_container.addWidget(self.employees_scroll_area) # Add scroll area
        self.employees_layout = QVBoxLayout(self.employees_scroll_area_widget) # Layout for content

        # ---------------- Diagnostics Tab ---------------- #
        self.diagnostics_tab = QWidget()
        self.tab_widget.addTab(self.diagnostics_tab, "Diagnostics")
        self.diagnostics_layout = QVBoxLayout(self.diagnostics_tab)
        self.diagnostics_output = QTextEdit()
        self.diagnostics_output.setReadOnly(True)
        self.diagnostics_layout.addWidget(self.diagnostics_output)

    # --- [ DIAGNOSTICS UI - Markdown Rendering ] ---
    def _format_diagnostics_to_html(self, diag_text: str) -> str:
        """
        Converts the raw diagnostics text into a nicely formatted HTML report using Markdown.
        The text is parsed as Markdown and rendered with enhanced styling for better readability.
        """
        try:
            import markdown
            
            # Configure markdown with extensions for better formatting
            md = markdown.Markdown(extensions=[
                'codehilite',
                'tables',
                'fenced_code',
                'nl2br',  # Convert newlines to <br>
                'sane_lists',  # Better list handling
            ])
            
            # Convert markdown to HTML
            html_content = md.convert(diag_text)
        except ImportError:
            # Fallback if markdown library is not available
            import html
            html_content = f"<pre>{html.escape(diag_text)}</pre>"
            html_content += "<p><em>Note: Install 'markdown' package for better formatting</em></p>"
        except Exception as e:
            # Fallback on any error
            import html
            html_content = f"<pre>{html.escape(diag_text)}</pre>"
            html_content += f"<p><em>Error rendering markdown: {str(e)}</em></p>"

        full_html = f"""
        <html>
        <head>
            <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
                background-color: #f5f7fa;
                color: #2c3e50;
                margin: 0;
                padding: 0;
                line-height: 1.7;
            }}
            .diag-container {{
                max-width: 1400px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 40px 50px;
                border-radius: 12px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                min-height: 100vh;
            }}
            h1 {{
                text-align: left;
                color: #1a5f9e;
                border-bottom: 4px solid #1a5f9e;
                padding-bottom: 20px;
                margin: 0 0 25px 0;
                font-size: 32px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
            h2 {{
                color: #2c3e50;
                border-bottom: 2px solid #e8ecf0;
                padding-bottom: 10px;
                margin-top: 40px;
                margin-bottom: 20px;
                font-size: 24px;
                font-weight: 600;
                padding-top: 10px;
            }}
            h3 {{
                color: #34495e;
                margin-top: 30px;
                margin-bottom: 15px;
                font-size: 20px;
                font-weight: 600;
            }}
            h4 {{
                color: #555;
                margin-top: 25px;
                margin-bottom: 12px;
                font-size: 18px;
                font-weight: 600;
            }}
            p {{
                margin: 12px 0;
                color: #444;
                line-height: 1.8;
            }}
            pre {{
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-left: 4px solid #1a5f9e;
                border-radius: 6px;
                padding: 16px;
                overflow-x: auto;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.6;
                color: #2c3e50;
                margin: 15px 0;
            }}
            code {{
                background-color: #f1f3f5;
                padding: 3px 8px;
                border-radius: 4px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 13px;
                color: #d63384;
                font-weight: 500;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
                color: #2c3e50;
                font-weight: normal;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
                background-color: #fff;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                border-radius: 8px;
                overflow: hidden;
            }}
            th {{
                background: linear-gradient(135deg, #1a5f9e 0%, #0d4a7a 100%);
                color: #fff;
                padding: 14px 16px;
                text-align: left;
                font-weight: 600;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: none;
            }}
            td {{
                padding: 12px 16px;
                border-bottom: 1px solid #e9ecef;
                color: #495057;
                font-size: 14px;
            }}
            tr:last-child td {{
                border-bottom: none;
            }}
            tr:nth-child(even) {{
                background-color: #f8f9fa;
            }}
            tr:hover {{
                background-color: #e7f3ff;
                transition: background-color 0.2s;
            }}
            ul, ol {{
                margin: 15px 0;
                padding-left: 35px;
            }}
            li {{
                margin: 8px 0;
                color: #495057;
                line-height: 1.7;
            }}
            li strong {{
                color: #2c3e50;
            }}
            blockquote {{
                border-left: 5px solid #1a5f9e;
                margin: 20px 0;
                padding: 15px 25px;
                background: linear-gradient(to right, #f0f7ff 0%, #ffffff 100%);
                color: #555;
                border-radius: 0 6px 6px 0;
                font-style: italic;
            }}
            hr {{
                border: none;
                border-top: 3px solid #e0e6ed;
                margin: 35px 0;
                height: 0;
            }}
            strong {{
                color: #2c3e50;
                font-weight: 600;
            }}
            em {{
                color: #6c757d;
                font-style: italic;
            }}
            /* Enhanced styling for status indicators */
            .success, .success code {{
                color: #28a745;
                font-weight: 600;
            }}
            .warning, .warning code {{
                color: #ffc107;
                font-weight: 600;
            }}
            .error, .error code {{
                color: #dc3545;
                font-weight: 600;
            }}
            /* Better spacing for sections */
            h2 + p, h3 + p {{
                margin-top: 10px;
            }}
            /* Code block improvements */
            code {{
                word-break: break-word;
            }}
            /* Table improvements */
            table th:first-child,
            table td:first-child {{
                padding-left: 20px;
            }}
            table th:last-child,
            table td:last-child {{
                padding-right: 20px;
            }}
            /* Status column styling */
            td:last-child {{
                font-weight: 500;
            }}
            /* Project name styling in tables */
            td strong {{
                color: #1a5f9e;
                font-size: 15px;
            }}
            /* List item styling for analysis sections - enhanced visibility */
            ul li {{
                padding: 10px 15px;
                margin: 8px 0;
                border-radius: 6px;
                transition: background-color 0.2s;
            }}
            ul li:hover {{
                background-color: #f8f9fa;
            }}
            </style>
        </head>
        <body>
            <div class="diag-container">
                {html_content}
            </div>
        </body>
        </html>
        """
        return full_html

    def show_diagnostics(self, diag_text: str):
        """
        Displays the formatted diagnostics report in the Diagnostics tab.
        """
        formatted_html = self._format_diagnostics_to_html(diag_text)
        self.diagnostics_output.setHtml(formatted_html)
        self.tab_widget.setCurrentWidget(self.diagnostics_tab)

    # --- [ EMPLOYEE OVERVIEW UI - unchanged ] ---
    def create_employee_overview_section(self, employees):
        """
        Clears any existing employee UI and re-builds a list of subsections
        showing name, total hours (read-only), and salary range inputs in the Employees tab.
        """
        self.employees = employees # Keep track of employee models

        # Clear existing widgets in employees_layout
        while self.employees_layout.count():
            child = self.employees_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # If you add layouts directly, handle them too (optional)
                # You might need a recursive clear function for complex layouts
                pass # Simple case assumes only widgets are added directly

        if not employees:
            no_emp_label = QLabel("No employee data loaded or available.")
            no_emp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.employees_layout.addWidget(no_emp_label)
            return

        for emp in employees:
            emp_widget = self._build_employee_subsection(emp)
            self.employees_layout.addWidget(emp_widget)

            # Add a visual separator between employees
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet("background-color: #cccccc;")
            self.employees_layout.addWidget(sep)

        self.employees_layout.addStretch(1) # Push content to the top

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
        layout.setSpacing(8) # Add some spacing

        # -- Employee Name (read-only)
        name_label = QLabel(f"<b>{employee.employee_name}</b>") # Make name bold
        layout.addWidget(name_label)

        # -- Show total research, meeting, non-R&D hours as read-only labels
        hours_layout = QHBoxLayout()
        total_rh = sum(employee.research_hours.values())
        rh_label = QLabel(f"Research: {total_rh:.2f}h")
        hours_layout.addWidget(rh_label)

        total_mh = sum(employee.meeting_hours.values())
        mh_label = QLabel(f"Meeting: {total_mh:.2f}h")
        hours_layout.addWidget(mh_label)

        total_nonrnd = sum(employee.nonRnD_hours.values())
        nonrnd_label = QLabel(f"Non-R&D: {total_nonrnd:.2f}h")
        hours_layout.addWidget(nonrnd_label)
        layout.addLayout(hours_layout)

        # --- Display current salary intervals ---
        salary_label = QLabel("Current Salary Levels:")
        layout.addWidget(salary_label)

        intervals = employee.get_salary_intervals()
        if not intervals:
            no_salary_label = QLabel("<i>No salary intervals defined.</i>")
            layout.addWidget(no_salary_label)
        else:
            for (old_start, old_end, old_level, old_amount) in intervals:
                hbox = QHBoxLayout()

                interval_info_label = QLabel(
                    f"[{old_start} → {old_end}] <b>{old_level}</b>: ISK{old_amount:,.2f}" # Format amount
                )
                interval_info_label.setToolTip(f"Salary: {old_level} (ISK{old_amount}) from {old_start} to {old_end}")
                hbox.addWidget(interval_info_label, 1) # Give label more space

                edit_button = QPushButton("Edit")
                edit_button.setFixedWidth(60) # Make edit button smaller
                edit_button.setToolTip("Edit this salary interval. You can modify the start date, end date, level label, and amount. Click to reveal the edit form.")
                edit_button.setEnabled(True)
                hbox.addWidget(edit_button)

                # --- Hidden sub-form for editing ---
                edit_widget = QWidget()
                edit_layout = QHBoxLayout(edit_widget)
                edit_widget.setVisible(False)

                new_start_input = QLineEdit(old_start)
                new_start_input.setPlaceholderText("New Start (MM-DD-YYYY)")
                edit_layout.addWidget(new_start_input)

                new_end_input = QLineEdit(old_end)
                new_end_input.setPlaceholderText("New End (MM-DD-YYYY)")
                edit_layout.addWidget(new_end_input)

                new_level_input = QLineEdit(old_level)
                new_level_input.setPlaceholderText("New Level")
                edit_layout.addWidget(new_level_input)

                new_amount_input = QLineEdit(str(old_amount))
                new_amount_input.setPlaceholderText("New Amount")
                edit_layout.addWidget(new_amount_input)

                save_edit_button = QPushButton("Save")
                save_edit_button.setToolTip("Save the changes to this salary interval. The updated values will replace the existing interval. Make sure all fields are filled correctly before saving.")
                save_edit_button.setEnabled(True)
                edit_layout.addWidget(save_edit_button)

                cancel_edit_button = QPushButton("Cancel")
                cancel_edit_button.setToolTip("Cancel editing and discard any changes made to this salary interval. The original values will be preserved.")
                cancel_edit_button.setEnabled(True)
                edit_layout.addWidget(cancel_edit_button)

                layout.addLayout(hbox)
                layout.addWidget(edit_widget)

                # Use lambda to capture the current state for each button
                edit_button.clicked.connect(
                    lambda checked=False, ew=edit_widget,
                           ns=new_start_input, ne=new_end_input, nl=new_level_input, na=new_amount_input,
                           os=old_start, oe=old_end, ol=old_level, oa=old_amount:
                    self._toggle_edit_salary_widget(ew, ns, ne, nl, na, os, oe, ol, oa)
                )

                save_edit_button.clicked.connect(
                    lambda checked=False, emp=employee,
                           os=old_start, oe=old_end,
                           ns=new_start_input, ne=new_end_input, nl=new_level_input, na=new_amount_input,
                           ew=edit_widget:
                    self._save_edited_salary_interval(emp, os, oe, ns, ne, nl, na, ew)
                )

                cancel_edit_button.clicked.connect(lambda checked=False, ew=edit_widget: ew.setVisible(False))


        # --- Interface to add a NEW salary interval ---
        add_salary_label = QLabel("Add New Salary Level:")
        layout.addWidget(add_salary_label)

        salary_container = QWidget()
        salary_layout = QHBoxLayout(salary_container)
        salary_layout.setContentsMargins(0, 0, 0, 0) # Remove extra margins
        layout.addWidget(salary_container)

        level_input = QLineEdit()
        level_input.setPlaceholderText("Level Label")
        salary_layout.addWidget(level_input)

        amount_input = QLineEdit()
        amount_input.setPlaceholderText("Amount")
        salary_layout.addWidget(amount_input)

        start_input = QLineEdit()
        start_input.setPlaceholderText("Start (MM-DD-YYYY)")
        salary_layout.addWidget(start_input)

        end_input = QLineEdit()
        end_input.setPlaceholderText("End (MM-DD-YYYY)")
        salary_layout.addWidget(end_input)

        apply_salary_layout = QHBoxLayout()
        apply_salary_button = QPushButton("Add")
        apply_salary_button.setFixedWidth(60) # Make add button smaller
        apply_salary_button.setToolTip("Add a new salary interval for this employee. Specify the salary level label, amount (in ISK), start date, and end date. Multiple intervals can be defined for different time periods to reflect salary changes.")
        apply_salary_button.setEnabled(True)
        apply_salary_layout.addWidget(apply_salary_button)
        apply_salary_layout.addStretch()
        salary_layout.addLayout(apply_salary_layout)

        # Use lambda to capture widgets for clearing
        apply_salary_button.clicked.connect(
            lambda checked=False, emp=employee, lvl=level_input, amt=amount_input, st=start_input, en=end_input:
            self._on_apply_salary(emp, lvl, amt, st, en)
        )

        return container

    def _toggle_run_comment(self):
        """Toggle visibility of run comment field."""
        if self.run_comment_visible:
            self.run_comment_input.setVisible(False)
            self.run_comment_toggle_button.setText("▶")
            self.run_comment_visible = False
        else:
            self.run_comment_input.setVisible(True)
            self.run_comment_toggle_button.setText("▼")
            self.run_comment_visible = True


    # Helper methods for employee salary editing
    def _toggle_edit_salary_widget(self, edit_widget, ns_input, ne_input, nl_input, na_input, os, oe, ol, oa):
        """ Toggles visibility and resets fields of the edit salary widget. """
        is_visible = not edit_widget.isVisible()
        edit_widget.setVisible(is_visible)
        if is_visible:
            ns_input.setText(os)
            ne_input.setText(oe)
            nl_input.setText(ol)
            na_input.setText(str(oa)) # Amount might be float/Decimal

    def _save_edited_salary_interval(self, employee, old_start, old_end, new_start_input, new_end_input, new_level_input, new_amount_input, edit_widget):
        """ Emits signal to save edited salary interval and hides the edit widget. """
        new_start_val = new_start_input.text().strip()
        new_end_val = new_end_input.text().strip()
        new_level_val = new_level_input.text().strip()
        new_amount_val = new_amount_input.text().strip()

        self.employee_salary_interval_edited.emit(
            employee,
            old_start, old_end, # Old identifiers
            new_start_val, new_end_val, new_level_val, new_amount_val # New data
        )
        edit_widget.setVisible(False) # Hide after saving

    def _on_apply_salary(self, employee, level_input, amount_input, start_input, end_input):
        """ Gathers data and emits signal to add a new salary range. """
        data = {
            "employee_object": employee,
            "level_label": level_input.text().strip(),
            "amount": amount_input.text().strip(),
            "start_date": start_input.text().strip(),
            "end_date": end_input.text().strip()
        }
        # Basic validation could be added here before emitting
        if data["level_label"] and data["amount"] and data["start_date"] and data["end_date"]:
            self.employee_salary_range_added.emit(data)
            # Clear inputs after successful emission
            level_input.clear()
            amount_input.clear()
            start_input.clear()
            end_input.clear()
        else:
            # Optionally show an error message if fields are missing
            print("Please fill all salary fields.") # Replace with a proper message box


    # -------------------------------------------------------------------------
    # PROJECT OVERVIEW UI
    # -------------------------------------------------------------------------

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # NEW METHOD: Assigns a color to a project if it doesn't have one
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _assign_project_color(self, project):
        """Assigns an available color to the project if it doesn't have one."""
        if project not in self.project_colors or not self.project_colors[project]:
            current_used_colors = set(self.project_colors.values())
            color_assigned = False
            for color in self.available_colors:
                if color not in current_used_colors:
                    self.project_colors[project] = color
                    # Assuming the project object can store its color
                    # If not, self.project_colors is the single source of truth
                    if hasattr(project, 'color'):
                         project.color = color
                    color_assigned = True
                    break
            if not color_assigned:
                # Fallback if all defined colors are used
                self.project_colors[project] = "#808080" # Default Gray
                if hasattr(project, 'color'):
                    project.color = "#808080"

        # Ensure the project object has the color attribute if it exists
        elif hasattr(project, 'color') and project not in self.project_colors:
             # If loaded project has color but it's not in our dict, add it
             self.project_colors[project] = project.color

        elif hasattr(project, 'color') and project in self.project_colors:
             # Ensure consistency if project had a color loaded
             project.color = self.project_colors[project]

    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # MODIFIED METHOD: Updates the stylesheet for all tabs
    # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def update_tab_stylesheet(self):
        """
        Generate and apply a stylesheet to color each project tab button based on its assigned color.
        Fixed tabs (INIT, Employees, Diagnostics) remain unaffected.
        """
        stylesheet = """
            QTabBar::tab {
                /* Default tab style - can customize font, padding etc. */
                padding: 6px 10px;
                border: 1px solid #C4C4C3;
                border-bottom: none; /* Tab connects to the pane */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px; /* Spacing between tabs */
            }
            QTabBar::tab:selected {
                /* Style for the selected tab */
                background: white; /* Or slightly different background */
                border-color: #9B9B9B;
                font-weight: bold;
            }
            QTabBar::tab:!selected {
                /* Style for non-selected tabs */
                background: #E0E0E0; /* Default background for non-selected */
                margin-top: 2px; /* Makes non-selected tabs look slightly lower */
                color: #444444;
            }
            QTabWidget::pane { /* The area where the tab widget's contents are shown */
                border: 1px solid #9B9B9B;
                top: -1px; /* Overlap with bottom border of tabs */
                background: white;
            }
        """
        color_stylesheet_parts = []

        # Iterate through *all* tabs to apply styles based on index
        for index in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(index)
            found_project = None

            # Check if this widget corresponds to a known project widget
            for project, proj_widget in self.project_widgets.items():
                if proj_widget == widget:
                    found_project = project
                    break

            if found_project and found_project in self.project_colors:
                color = self.project_colors[found_project]
                # Determine text color based on background brightness (simple heuristic)
                try:
                    # Calculate luminance (approximation)
                    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = "white" if luminance < 0.5 else "black"
                except Exception:
                    text_color = "black"

                # Style for non-selected colored tabs
                color_stylesheet_parts.append(
                    f'QTabBar::tab:!selected:nth-child({index + 1}) {{ '
                    f'background-color: {color}; '
                    f'color: {text_color}; '
                    f'border-color: {color}; ' # Match border color
                    f'}}\n'
                )
                # Style for selected colored tabs (often good to keep it distinct, e.g., white or lighter)
                color_stylesheet_parts.append(
                    f'QTabBar::tab:selected:nth-child({index + 1}) {{ '
                    f'background-color: white; ' # Selected tab usually stands out with white bg
                    f'color: {color}; ' # Use project color for text when selected
                    f'border: 1px solid {color}; ' # Border uses project color
                    f'border-bottom-color: white;' # Bottom border blends with pane
                    f'font-weight: bold;'
                    f'}}\n'
                )

        # Combine base stylesheet with specific color rules
        full_stylesheet = stylesheet + "\n" + "".join(color_stylesheet_parts)
        self.tab_widget.setStyleSheet(full_stylesheet)


    def create_project_subsection_from_project(self, project):
        """
        Create UI elements for a specific existing project as a new tab.
        The Controller passes a ProjectModel with pre-filled data.
        Assigns a color if needed and updates tab styles.
        """
        # --- Assign color BEFORE creating the tab ---
        self._assign_project_color(project)

        project_subsection = self._build_project_subsection(project)
        tab_name = project.name if project and project.name else "New Project"
        self.tab_widget.addTab(project_subsection, tab_name)
        self.project_widgets[project] = project_subsection

        # --- Update stylesheet AFTER adding the tab ---
        self.update_tab_stylesheet()

    # --- _build_project_subsection remains largely the same ---
    # (Make sure it uses the project object passed to it)
    def _build_project_subsection(self, project=None):
        """
        Builds and returns a QWidget subsection with fields for project data.
        The controller will connect signals to update the model.
        """
        project_subsection = QWidget()
        layout = QVBoxLayout(project_subsection)
        layout.setSpacing(8)

        # --- Project name ---
        name_h_layout = QHBoxLayout()
        name_label = QLabel("Project Name:")
        name_h_layout.addWidget(name_label)
        name_input = QLineEdit()
        if project:
            name_input.setText(project.name)
        name_h_layout.addWidget(name_input)
        layout.addLayout(name_h_layout)

        # --- Funding agency ---
        funding_h_layout = QHBoxLayout()
        funding_label = QLabel("Funding Agency:")
        funding_h_layout.addWidget(funding_label)
        funding_input = QLineEdit()
        if project:
            funding_input.setText(project.funding_agency)
        funding_h_layout.addWidget(funding_input)
        layout.addLayout(funding_h_layout)

        # --- Grant amounts ---
        grant_label = QLabel("Grant Amounts:")
        layout.addWidget(grant_label)
        grant_layout = QHBoxLayout()
        min_input = QLineEdit()
        min_input.setPlaceholderText("Minimum")
        min_input.setToolTip("Minimum grant amount required for this project (in ISK). This is a reference value displayed in diagnostics but NOT used in the optimization algorithm. It helps track if allocations meet minimum funding requirements. The algorithm optimizes based on the Contractual amount instead.")
        min_input.setEnabled(True)
        if project:
            min_input.setText(str(project.grant_min or ''))
        max_input = QLineEdit()
        max_input.setPlaceholderText("Maximum")
        max_input.setToolTip("Maximum grant amount allowed for this project (in ISK). This is a reference value displayed in diagnostics but NOT used in the optimization algorithm. It helps track if allocations exceed maximum funding limits. The algorithm optimizes based on the Contractual amount instead.")
        max_input.setEnabled(True)
        if project:
            max_input.setText(str(project.grant_max or ''))
        contractual_input = QLineEdit()
        contractual_input.setPlaceholderText("Contractual")
        contractual_input.setToolTip("Contractual grant amount (in ISK). If no period or lifetime target is provided, this value becomes the period target used by the solver for cost matching and penalties.")
        contractual_input.setEnabled(True)
        if project:
            contractual_input.setText(str(project.grant_contractual or ''))

        min_label = QLabel("Min:")
        min_label.setToolTip("Minimum grant amount required for this project (in ISK). This is a reference value displayed in diagnostics but NOT used in the optimization algorithm. It helps track if allocations meet minimum funding requirements. The algorithm optimizes based on the Contractual amount instead.")
        grant_layout.addWidget(min_label)
        grant_layout.addWidget(min_input)
        
        max_label = QLabel("Max:")
        max_label.setToolTip("Maximum grant amount allowed for this project (in ISK). This is a reference value displayed in diagnostics but NOT used in the optimization algorithm. It helps track if allocations exceed maximum funding limits. The algorithm optimizes based on the Contractual amount instead.")
        grant_layout.addWidget(max_label)
        grant_layout.addWidget(max_input)
        
        contractual_label = QLabel("Contractual:")
        contractual_label.setToolTip("Contractual grant amount (in ISK). If no period or lifetime target is provided, this value becomes the period target used by the solver for cost matching and penalties.")
        grant_layout.addWidget(contractual_label)
        grant_layout.addWidget(contractual_input)
        layout.addLayout(grant_layout)

        # --- Row for Overhead, Matching, Non-R&D ---
        rates_layout = QHBoxLayout()

        # --- Overhead ---
        overhead_label = QLabel("Overhead (%):")
        overhead_label.setToolTip("Operational overhead. In the solver, values ≥ 100000 are treated as a fixed ISK overhead. Values > 1 are treated as a percentage (v%) of direct costs. Values between 0 and 1 are treated as zero overhead.")
        rates_layout.addWidget(overhead_label)
        overhead_input = QLineEdit()
        overhead_input.setFixedWidth(80)
        overhead_input.setToolTip("Enter overhead. The solver interprets >1 as percent (v%), and ≥100000 as fixed ISK. Values between 0 and 1 are ignored. Current UI stores this as a fraction, so enter whole percentages (e.g., 25 for 25%).")
        overhead_input.setEnabled(True)
        if project and project.operational_overhead is not None:
            overhead_input.setText(str(project.operational_overhead * 100))
        rates_layout.addWidget(overhead_input)
        rates_layout.addSpacing(20)

        # --- Matching fund ---
        matching_label = QLabel("Matching Fund:")
        matching_label.setToolTip("Matching fund requirement added on top of the contractual value. The solver computes matching from the contractual amount (not lifetime/period) and penalizes allocations that fall short of Contractual + Matching.")
        rates_layout.addWidget(matching_label)
        matching_type_combo = QComboBox()
        matching_type_combo.addItems(["Percentage", "Absolute"])
        matching_type_combo.setToolTip("Choose how to apply matching on the contractual amount: Percentage (e.g., 20% of contractual) or Absolute (fixed ISK).")
        matching_type_combo.setEnabled(True)
        if project and project.matching_fund_type:
            index = 0 if project.matching_fund_type.lower() == "percentage" else 1
            matching_type_combo.setCurrentIndex(index)
        rates_layout.addWidget(matching_type_combo)

        matching_value_input = QLineEdit()
        matching_value_input.setPlaceholderText("Value")
        matching_value_input.setFixedWidth(100)
        matching_value_input.setToolTip("Matching value applied to the contractual amount. Percentage: enter whole percent (e.g., 20). Absolute: enter ISK (e.g., 100000). Solver target = Contractual + Matching.")
        matching_value_input.setEnabled(True)
        if project:
            matching_value_input.setText(str(project.matching_fund_value or ''))
        rates_layout.addWidget(matching_value_input)
        rates_layout.addSpacing(20)

        # --- Max non-R&D ---
        nonrnd_label = QLabel("Min Non-R&D (%):")
        nonrnd_label.setToolTip("Minimum percentage (0-100) of total hours that must be non-R&D. The solver uses the fractional form (value/100) as a soft constraint.")
        rates_layout.addWidget(nonrnd_label)
        nonrnd_input = QLineEdit()
        nonrnd_input.setFixedWidth(80)
        nonrnd_input.setToolTip("Enter 0-100. The solver uses value/100 as the minimum non-R&D share; deviations are penalized.")
        nonrnd_input.setEnabled(True)
        if project and project.nonrnd_percentage is not None:
            nonrnd_input.setText(str(project.nonrnd_percentage * 100))
        rates_layout.addWidget(nonrnd_input)
        rates_layout.addStretch(1) # Push elements left

        layout.addLayout(rates_layout)


        # --- Funding period ---
        funding_period_label = QLabel("Funding Period (MM-DD-YYYY):")
        funding_period_label.setToolTip("The start and end dates of the funding period for this project. This is used for reference and reporting purposes. The actual allocation period is determined by the date ranges you add in the INIT tab.")
        layout.addWidget(funding_period_label)
        funding_period_layout = QHBoxLayout()
        start_input = QLineEdit()
        start_input.setPlaceholderText("Start Date")
        start_input.setToolTip("Funding period start date in MM-DD-YYYY format. This is for reference and reporting only - the actual allocation uses date ranges from the INIT tab.")
        if project:
            start_input.setText(project.funding_start)
        end_input = QLineEdit()
        end_input.setPlaceholderText("End Date")
        end_input.setToolTip("Funding period end date in MM-DD-YYYY format. This is for reference and reporting only - the actual allocation uses date ranges from the INIT tab.")
        if project:
            end_input.setText(project.funding_end)
        start_funding_label = QLabel("Start:")
        start_funding_label.setToolTip("Funding period start date in MM-DD-YYYY format. This is for reference and reporting only - the actual allocation uses date ranges from the INIT tab.")
        funding_period_layout.addWidget(start_funding_label)
        funding_period_layout.addWidget(start_input)
        end_funding_label = QLabel("End:")
        end_funding_label.setToolTip("Funding period end date in MM-DD-YYYY format. This is for reference and reporting only - the actual allocation uses date ranges from the INIT tab.")
        funding_period_layout.addWidget(end_funding_label)
        funding_period_layout.addWidget(end_input)
        layout.addLayout(funding_period_layout)

        # --- Research Topics ---
        topics_label = QLabel("Select Research Topics:")
        topics_label.setToolTip("Select which research topics are allowed for this project. The algorithm will only allocate R&D hours to these topics. If a topic is not selected, the algorithm will heavily penalize (but still allow) allocations to that topic if necessary for feasibility. The 'Bridge' topic is automatically allowed for all projects.")
        layout.addWidget(topics_label)

        # Use a scroll area for topics if the list is long
        topics_scroll = QScrollArea()
        topics_scroll.setWidgetResizable(True)
        topics_widget = QWidget()
        topics_layout = QVBoxLayout(topics_widget)
        topics_layout.setSpacing(4)
        topic_checkboxes = []
        project_topics = set(project.research_topics) if project and project.research_topics else set()
        for t in self.all_research_topics:
            cb = QCheckBox(t)
            if t in project_topics:
                cb.setChecked(True)
            topics_layout.addWidget(cb)
            topic_checkboxes.append(cb)
        topics_scroll.setWidget(topics_widget)
        topics_scroll.setMinimumHeight(150) # Limit height
        layout.addWidget(topics_scroll)

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        save_project_button = QPushButton("Save Project")
        save_project_button.setToolTip("Save this project with all its settings (name, cost targets, overhead, matching requirements, funding period, and selected research topics). The project will appear as a separate tab. You must save before the project can be used in allocation calculations.")
        save_project_button.setEnabled(True)
        button_layout.addWidget(save_project_button)

        delete_project_button = QPushButton("Delete Project")
        delete_project_button.setStyleSheet("color: red;") # Make delete more prominent
        delete_project_button.setToolTip("Permanently delete this project. This action cannot be undone. The project must be saved first before it can be deleted. All project settings and allocations will be removed.")
        delete_project_button.setEnabled(True)
        button_layout.addWidget(delete_project_button)
        button_layout.addStretch(1) # Push buttons left
        layout.addLayout(button_layout)

        layout.addStretch(1) # Push everything up

        # --- Connect Signals ---
        def on_save_project():
            # Basic input conversion and validation can happen here or in Controller
            oh_text = overhead_input.text().strip().replace('%', '')
            oh_float = float(oh_text) / 100.0 if oh_text else 0.0

            matching_type = matching_type_combo.currentText().lower()
            match_val_text = matching_value_input.text().strip()
            match_val = float(match_val_text) if match_val_text else 0.0 # Adapt type as needed

            nonrnd_text = nonrnd_input.text().strip().replace('%', '')
            nonrnd_float = float(nonrnd_text) / 100.0 if nonrnd_text else None

            selected_topics = [cb.text() for cb in topic_checkboxes if cb.isChecked()]

            data = {
                "name": name_input.text().strip(),
                "funding_agency": funding_input.text().strip(),
                "grant_min": min_input.text().strip(), # Keep as string, controller validates/converts
                "grant_max": max_input.text().strip(),
                "grant_contractual": contractual_input.text().strip(),
                "operational_overhead": oh_float,
                "matching_fund_type": matching_type,
                "matching_fund_value": match_val, # Pass converted value
                "nonrnd_percentage": nonrnd_float,
                "funding_start": start_input.text().strip(),
                "funding_end": end_input.text().strip(),
                "research_topics": selected_topics,
            }

            # --- Update tab text if name changed ---
            current_tab_index = self.tab_widget.indexOf(project_subsection)
            if current_tab_index != -1 and self.tab_widget.tabText(current_tab_index) != data["name"]:
                 self.tab_widget.setTabText(current_tab_index, data["name"])
                 # Note: Renaming might affect style if not reapplied, but update_tab_stylesheet handles index changes.

            # --- Emit signal ---
            # Pass the *original* project object reference if editing, or None/placeholder if new
            self.project_saved.emit(project, data)


        save_project_button.clicked.connect(on_save_project)

        def on_delete_project():
             # Pass the actual project object to be deleted
             self.project_deleted.emit(project)

        # Disable delete button if it's a *new* unsaved project (project is None)
        if not project:
            delete_project_button.setEnabled(False)
            delete_project_button.setToolTip("Save the project first to enable deletion.")
        else:
             delete_project_button.clicked.connect(on_delete_project)


        return project_subsection

    def clear_project_tabs(self):
        """Remove all project tabs, keeping INIT, Employees, and Diagnostics."""
        while self.tab_widget.count() > 3:
            self.tab_widget.removeTab(3)
        self.project_widgets.clear()

    def remove_project_tab(self, project):
        """Remove the tab associated with a specific project."""
        if project in self.project_widgets:
            widget = self.project_widgets[project]
            index = self.tab_widget.indexOf(widget)
            if index != -1:
                self.tab_widget.removeTab(index)
            del self.project_widgets[project]
            self.update_tab_stylesheet()