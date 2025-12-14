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

"""
Controller for the REA application.
Mediates between Model and View, handling user interactions and coordinating data flow.
"""

import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any

from PyQt5.QtWidgets import QFileDialog, QMessageBox  # pyright: ignore[reportMissingImports]
from algorithm import run_allocation_algorithm
from Model import ReaDataModel, EmployeeModel, ProjectModel
from View import ReaDataView
from config import AppConfig
from validators import DateValidator, NumericValidator
from utils import DateManager
from logger import get_logger
from error_handling import ErrorHandler, handle_exceptions
from worker_threads import AlgorithmWorker, CSVLoaderWorker


class Controller:
    """
    Main controller coordinating the REA application.
    
    Handles user interactions from the View, updates the Model, and coordinates
    long-running operations through worker threads.
    """
    
    def __init__(self, model: ReaDataModel, view: ReaDataView):
        """
        Initialize controller with model and view.
        
        Args:
            model: Data model instance
            view: View instance
        """
        self.model = model
        self.view = view
        self.logger = get_logger()
        
        self.employees = []
        self.projects = []
        self.date_ranges = []
        
        self.setting_start_date = True
        
        self.algorithm_worker = None
        self.csv_loader_worker = None
        self.state_loader_worker = None
        self.state_saver_worker = None
        
        self._initial_costs_used = {}
        self._previous_report_path = None

        # ------------------ Connect signals from the View ------------------ #
        # Calendar & Date range
        self.view.open_calendar_button.clicked.connect(self.toggle_calendar)
        self.view.calendar.clicked.connect(self.set_date)
        self.view.apply_dates_button.clicked.connect(self.add_dates)

        # Timesheets
        self.view.timesheet_button.clicked.connect(self.read_timesheets)

        # Projects
        self.view.add_project_button.clicked.connect(self.create_new_project)

        # Output
        self.view.generate_output_button.clicked.connect(self.generate_output)

        # Save/Load
        self.view.save_state_button.clicked.connect(self.save_state)
        self.view.load_state_button.clicked.connect(self.load_state)

        self.view.project_saved.connect(self.on_project_saved)
        self.view.project_deleted.connect(self.on_project_deleted)

        # Employee Salary Editing
        self.view.employee_salary_range_added.connect(self.on_employee_salary_range_added)
        self.view.employee_salary_interval_edited.connect(self.on_employee_salary_interval_edited)

    @handle_exceptions(show_dialog=True)
    def on_employee_salary_range_added(self, data: Dict[str, Any]):
        """
        Handle addition of salary range for an employee.
        
        Validates input data and applies salary level to employee for specified date range.
        
        Args:
            data: Dictionary containing employee_object, level_label, amount, start_date, end_date
        """
        emp_obj = data["employee_object"]
        level_label = data["level_label"]
        amount_str = data["amount"]
        start_str = data["start_date"]
        end_str = data["end_date"]
        
        if not level_label.strip():
            ErrorHandler.show_warning(
                self.view,
                "Invalid Input",
                "Salary level label cannot be empty"
            )
            return
        
        is_valid, amount_val, error_msg = NumericValidator.validate_salary(amount_str)
        if not is_valid:
            ErrorHandler.show_warning(self.view, "Invalid Salary", error_msg)
            return
        
        validation = DateValidator.validate_date_range(start_str, end_str)
        if not validation:
            ErrorHandler.show_warning(
                self.view,
                "Invalid Date Range",
                validation.error_message
            )
            return
        
        date_list = DateManager.generate_date_list(start_str, end_str)
        for day_str in date_list:
            emp_obj.set_salary_level_for_date(day_str, level_label, amount_val)
        
        self.logger.info(
            f"Applied salary '{level_label}' = {amount_val} for {emp_obj.employee_name} "
            f"from {start_str} to {end_str}"
        )
        
        self.view.create_employee_overview_section(self.employees)

    # -------------------------------------------------------------------------
    # PROJECT CREATION
    # -------------------------------------------------------------------------
    def create_new_project(self, checked=False):
        """
        Create a new project and add it to the UI.
        
        Creates a new ProjectModel instance and registers it with both the
        controller and the view.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        new_proj = ProjectModel()
        self.projects.append(new_proj)
        self.view.projects.append(new_proj)
        self.view.create_project_subsection_from_project(new_proj)
        self.logger.info("Created new project")
    
    def toggle_calendar(self, checked=False):
        """
        Toggle visibility of the calendar widget.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        self.view.calendar.setVisible(not self.view.calendar.isVisible())
    
    def set_date(self, q_date):
        """
        Set start or end date from calendar selection.
        
        Args:
            q_date: QDate object from calendar widget
        """
        selected_date = q_date.toString("MM-dd-yyyy")
        if self.setting_start_date:
            self.view.start_date_input.setText(selected_date)
            self.setting_start_date = False
        else:
            self.view.end_date_input.setText(selected_date)
            self.setting_start_date = True
    
    @handle_exceptions(show_dialog=True)
    def add_dates(self, checked=False):
        """
        Add a date range from UI inputs after validation.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        start_date = self.view.start_date_input.text().strip()
        end_date = self.view.end_date_input.text().strip()
        
        if not start_date or not end_date:
            ErrorHandler.show_warning(
                self.view,
                "Missing Dates",
                "Both start and end dates must be filled"
            )
            return
        
        validation = DateValidator.validate_date_range(start_date, end_date)
        if not validation:
            ErrorHandler.show_warning(
                self.view,
                "Invalid Date Range",
                validation.error_message
            )
            return
        
        self.date_ranges.append((start_date, end_date))
        self.logger.info(f"Added date range: {start_date} to {end_date}")
        ErrorHandler.show_info(
            self.view,
            "Date Range Added",
            f"Date range {start_date} to {end_date} has been added successfully"
        )
    
    @handle_exceptions(show_dialog=True)
    def read_timesheets(self, checked=False):
        """
        Load timesheets from selected directory using worker thread.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        if not self.date_ranges:
            ErrorHandler.show_warning(
                self.view,
                "No Date Range",
                "You must specify at least one date range before loading timesheets"
            )
            return
        
        directory = QFileDialog.getExistingDirectory(self.view, "Select Timesheet Directory")
        if not directory:
            self.logger.info("Directory selection cancelled")
            ErrorHandler.show_warning(
                self.view,
                "No Directory Selected",
                "No directory was selected. Timesheet loading cancelled."
            )
            return
        
        self.view.directory_label.setText(f"Selected Directory: {directory}")
        
        self.csv_loader_worker = CSVLoaderWorker(self.model, directory, self.date_ranges)
        self.csv_loader_worker.progress_updated.connect(self._on_csv_progress)
        self.csv_loader_worker.finished_success.connect(self._on_csv_loaded)
        self.csv_loader_worker.finished_error.connect(self._on_csv_error)
        self.csv_loader_worker.start()
    
    def _on_csv_progress(self, message: str, progress: int):
        """
        Handle progress updates from CSV loader.
        
        Args:
            message: Progress message
            progress: Progress percentage (0-100)
        """
        self.logger.info(f"CSV Loading: {message} ({progress}%)")
    
    def _on_csv_loaded(self, employees: List[EmployeeModel]):
        """
        Handle successful CSV loading.
        
        Args:
            employees: List of loaded employee models
        """
        self.employees = employees
        self.view.create_employee_overview_section(self.employees)
        self.logger.info(f"Loaded {len(employees)} employees from timesheets")
        
        if not employees:
            ErrorHandler.show_warning(
                self.view,
                "No Employees Loaded",
                "No valid employee data was found in the selected directory.\n\n"
                "Please check that:\n"
                "- The directory contains CSV files\n"
                "- The CSV files have the correct format\n"
                "- The date ranges match dates in the timesheets"
            )
        else:
            ErrorHandler.show_info(
                self.view,
                "Timesheets Loaded",
                f"Successfully loaded {len(employees)} employee timesheets"
            )
    
    def _on_csv_error(self, error_message: str):
        """
        Handle CSV loading error.
        
        Args:
            error_message: Error description
        """
        ErrorHandler.show_warning(
            self.view,
            "Timesheet Loading Issue",
            f"Could not load timesheets from the selected directory.\n\n"
            f"Details: {error_message}\n\n"
            f"Please check that:\n"
            f"- The directory exists and is accessible\n"
            f"- The directory contains valid CSV files\n"
            f"- The CSV files have the correct format\n"
            f"- You have read permissions for the directory"
        )
        self.logger.warning(f"CSV loading failed: {error_message}")

    def _parse_previous_report_costs(self, path: str) -> Dict[str, float]:
        """
        Parse previous actual project costs from either a JSON run output or a diagnostics text file.

        Args:
            path: File path to a .json run output or a .txt diagnostics report.

        Returns:
            Dict[str, float]: Mapping {project_name: previous_actual_isk}.
        """
        lower = path.lower()
        if lower.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            candidates: List[Dict[str, float]] = []
            if isinstance(data, dict):
                if isinstance(data.get("final_costs"), dict):
                    candidates.append(data["final_costs"])
                if isinstance(data.get("project_costs"), dict):
                    candidates.append(data["project_costs"])
                if "results" in data and isinstance(data["results"], dict):
                    rc = data["results"]
                    if isinstance(rc.get("final_costs"), dict):
                        candidates.append(rc["final_costs"])
                    if isinstance(rc.get("project_costs"), dict):
                        candidates.append(rc["project_costs"])

            merged: Dict[str, float] = {}
            for cand in candidates:
                for k, v in cand.items():
                    try:
                        merged[k] = float(v)
                    except Exception:
                        continue

            if not merged:
                raise ValueError("No project cost mapping found in JSON. Expected keys like 'final_costs' or 'project_costs'.")
            return merged

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        prev_costs: Dict[str, float] = {}

        table_anchor = "## 💰 Project Cost Analysis"
        if table_anchor in text:
            section = text.split(table_anchor, 1)[1]
            rows = []
            for line in section.splitlines():
                if line.strip().startswith("|"):
                    rows.append(line.strip())
                elif rows:
                    break
            for row in rows:
                parts = [p.strip() for p in row.strip("|").split("|")]
                if len(parts) >= 5 and parts[0].lower() != "project":
                    name = parts[0].strip("* ").strip()
                    actual_str = parts[2]
                    actual_num = re.sub(r"[^\d.]", "", actual_str.replace(",", "").replace("`", ""))
                    if actual_num:
                        try:
                            prev_costs[name] = float(actual_num)
                        except Exception:
                            pass
        
        if prev_costs:
            return prev_costs

        if not prev_costs:
            blocks = re.split(r"^####\s*Project:\s*(.+?)\s*$", text, flags=re.MULTILINE)
            if len(blocks) > 1:
                for i in range(1, len(blocks), 2):
                    name = blocks[i].strip()
                    body = blocks[i + 1] if i + 1 < len(blocks) else ""
                    m = re.search(r"\*\*Computed Cost:\*\*\s*`([\d,\.]+)`\s*ISK", body)
                    if m:
                        try:
                            prev_costs[name] = float(m.group(1).replace(",", ""))
                        except Exception:
                            pass

        if not prev_costs:
            for m in re.finditer(
                r"Project\s+'([^']+)':.*?Computed Cost\s*\(Rounded\)\s*:\s*([0-9,\.]+)",
                text,
                flags=re.DOTALL,
            ):
                name = m.group(1).strip()
                try:
                    prev_costs[name] = float(m.group(2).replace(",", ""))
                except Exception:
                    pass

        if not prev_costs:
            raise ValueError("Could not parse previous costs from diagnostics text file.")
        return prev_costs


    @handle_exceptions(show_dialog=True)
    def generate_output(self, checked=False):
        """
        Run allocation algorithm in background thread and display results.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        if not self.date_ranges:
            ErrorHandler.show_warning(
                self.view,
                "No Date Range",
                "Please specify a date range before generating output"
            )
            return
        
        self.projects = self.view.projects
        
        if not self.projects:
            ErrorHandler.show_warning(
                self.view,
                "No Projects",
                "Please add at least one project before generating output"
            )
            return
        
        if not self.employees:
            ErrorHandler.show_warning(
                self.view,
                "No Employees",
                "Please load timesheet data before generating output"
            )
            return
        
        start_date, end_date = self.date_ranges[-1]
        all_topics = self.model.research_topics
        
        initial_costs = {}
        self._previous_report_path = None
        reply = QMessageBox.question(
            self.view,
            "Concatenate with Previous Run?",
            "Do you want to concatenate costs from a previous report?\n\n"
            "This will add the costs from a previous run to the current calculation, "
            "allowing you to continue from where you left off.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            import os
            reports_dir = AppConfig.REPORTS_DIR
            default_path = os.path.join(os.getcwd(), reports_dir) if os.path.exists(os.path.join(os.getcwd(), reports_dir)) else os.getcwd()
            
            report_file, _ = QFileDialog.getOpenFileName(
                self.view,
                "Select Previous Report to Concatenate",
                default_path,
                "Diagnostics (*.txt);;Run Output (*.json);;All Files (*)"
            )
            
            if report_file:
                initial_costs = self._parse_previous_report_costs(report_file)
                if initial_costs:
                    self._initial_costs_used = dict(initial_costs)
                    self._previous_report_path = report_file
                    cost_summary = "\n".join([f"  - {name}: {cost:,.0f} ISK" for name, cost in initial_costs.items()])
                    ErrorHandler.show_info(
                        self.view,
                        "Previous Costs Loaded",
                        f"Successfully loaded costs from previous report:\n\n{cost_summary}\n\n"
                        f"These costs will be added to the current allocation."
                    )
                    self.logger.info(f"Concatenating with previous report: {report_file}")
                    print("[CONCATENATION] Starting from previous costs:")
                    for proj_name, cost in initial_costs.items():
                        print(f"[CONCATENATION]   {proj_name}: {cost:,.0f} ISK")
                else:
                    self._initial_costs_used = {}
                    self._previous_report_path = None
                    ErrorHandler.show_warning(
                        self.view,
                        "No Costs Found",
                        "The selected report does not contain project costs. "
                        "Starting from zero."
                    )
            else:
                self._previous_report_path = None
        
        self.logger.info(
            f"Starting allocation algorithm: {start_date} to {end_date}, "
            f"{len(self.employees)} employees, {len(self.projects)} projects"
        )
        if initial_costs:
            self.logger.info(f"Concatenating with {len(initial_costs)} previous project costs")
        
        self.algorithm_worker = AlgorithmWorker(
            run_allocation_algorithm,
            self.employees,
            self.projects,
            start_date,
            end_date,
            all_topics,
            initial_costs
        )
        self.algorithm_worker.progress_updated.connect(self._on_algorithm_progress)
        self.algorithm_worker.finished_success.connect(self._on_algorithm_complete)
        self.algorithm_worker.finished_error.connect(self._on_algorithm_error)
        self.algorithm_worker.start()
    
    def _on_algorithm_progress(self, message: str):
        """
        Handle progress updates from algorithm worker.
        
        Args:
            message: Progress message
        """
        self.logger.info(f"Algorithm: {message}")
    
    def _on_algorithm_complete(self, result: Dict[str, Any]):
        """
        Handle successful algorithm completion.
        
        Args:
            result: Dictionary containing algorithm results
        """
        self.logger.info("Algorithm completed successfully")
        self._process_algorithm_results(result)
    
    def _on_algorithm_error(self, error_message: str):
        """
        Handle algorithm execution error.
        
        Args:
            error_message: Error description
        """
        ErrorHandler.show_error(
            self.view,
            "Algorithm Failed",
            error_message
        )
    
    def _process_algorithm_results(self, result: Dict[str, Any]):
        """
        Process and display algorithm results.
        
        Args:
            result: Dictionary containing algorithm results
        """
        self.logger.info(f"Algorithm status: {result.get('solver_status', 'N/A')}")
        self.logger.info(f"Final objective: {result.get('final_objective', 'N/A')}")

        # Project Costs
        print("\n================= PROJECT COSTS (Actual vs. Target) =================")
        final_costs = result['final_costs']
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            try:
                base_grant = float(proj.grant_contractual or 0.0)
                target_min = float(proj.grant_min or 0.0)
            except Exception:
                base_grant = 0.0
                target_min = 0.0
            
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            
            overhead_val = float(proj.operational_overhead or 0.0)
            overhead_pct = overhead_val / 100.0 if overhead_val > 1.0 else max(overhead_val, 0.0)
            overhead_pct = max(0.0, min(overhead_pct, 1.0))
            
            total_target = max((base_grant + match_abs) * (1.0 - overhead_pct), 0.0)

            diff_total = actual_cost - total_target
            diff_pct_total = (diff_total / total_target * 100) if total_target > 0 else 0
            
            diff_min = actual_cost - target_min
            diff_pct_min = (diff_min / target_min * 100) if target_min > 0 else 0

            print(f"Project: {proj_name}")
            print(f"  Actual Cost : {actual_cost:10.2f}")
            print(f"  Total Target : {total_target:10.2f} (optimization target)")
            if target_min > 0 and target_min != total_target:
                print(f"  Minimum Target : {target_min:10.2f} (reference)")
            if actual_cost > total_target:
                print(f"  >>> WARNING: Over Total Budget by {diff_total:10.2f} ({diff_pct_total:6.2f}%)")
            else:
                print("  Total Budget Status: OK")
            if target_min > 0 and target_min != total_target and actual_cost < target_min:
                print(f"  >>> NOTE: Below Minimum Target by {abs(diff_min):10.2f} ({abs(diff_pct_min):6.2f}%)")
            print("-" * 60)
        print("======================================================================\n")

        # Final Allocations
        allocations = result['allocations']
        for emp_name, date_dict in allocations.items():
            for date_str, project_dict in date_dict.items():
                daily_total = 0.0
                for proj_name, proj_info in project_dict.items():
                    nonrnd_val = proj_info.get("nonRnD", 0.0)
                    topics_sum = sum(proj_info.get("topics", {}).values())
                    daily_total += (nonrnd_val + topics_sum)

        # Generate comprehensive diagnostics with metadata, analysis, and formatting
        start_date, end_date = self.date_ranges[-1]
        report_time = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")
        
        diagnostics = []
        
        # ========== REPORT HEADER & METADATA ==========
        diagnostics.append("# 📊 Research Expenditure Allocation - Diagnostics Report\n")
        diagnostics.append(f"**Generated:** {report_time}  \n")
        diagnostics.append(f"**Reporting Period:** {start_date} to {end_date}  \n")
        diagnostics.append(f"**Employees:** {len(self.employees)}  \n")
        diagnostics.append(f"**Projects:** {len(self.projects)}  \n")
        is_concatenating = bool(getattr(self, '_initial_costs_used', {}))
        if is_concatenating:
            diagnostics.append(f"**Note:** This run concatenates with previous allocations. Actual costs shown include both previous and new allocations, compared against original targets.  \n")
        diagnostics.append("---\n")
        
        # ========== EXECUTIVE SUMMARY ==========
        diagnostics.append("## 📈 Executive Summary\n")
        
        # Calculate overall statistics
        overall_rnd_avail = overall_rnd_alloc = 0.0
        overall_nonrnd_avail = overall_nonrnd_alloc = 0.0
        total_cost_allocated = 0.0
        total_cost_target = 0.0
        project_statuses = []
        
        for employee in self.employees:
            overall_rnd_avail += sum(employee.research_hours.values())
            overall_nonrnd_avail += sum(employee.nonRnD_hours.values())

        for emp_name, date_dict in allocations.items():
            for date_str, project_dict in date_dict.items():
                for proj_name, proj_info in project_dict.items():
                    rnd_hours = sum(proj_info.get("topics", {}).values())
                    nonrnd_hours = proj_info.get("nonRnD", 0.0)
                    overall_rnd_alloc += rnd_hours
                    overall_nonrnd_alloc += nonrnd_hours
                    
                    # Find employee for salary calculation
                    emp_obj = next((e for e in self.employees if e.employee_name == emp_name), None)
                    if emp_obj:
                        sal_info = emp_obj.salary_levels.get(date_str, {})
                        base_salary = float(sal_info.get("amount", 0.0))
                        hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
                        total_cost_allocated += (rnd_hours + nonrnd_hours) * hourly_rate
        
        initial_costs_used = getattr(self, '_initial_costs_used', {})
        for proj in self.projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            try:
                base_grant = float(proj.grant_contractual or 0.0)
            except Exception:
                base_grant = 0.0
            
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            
            overhead_val = float(proj.operational_overhead or 0.0)
            overhead_pct = overhead_val / 100.0 if overhead_val > 1.0 else max(overhead_val, 0.0)
            overhead_pct = max(0.0, min(overhead_pct, 1.0))
            
            original_target = max((base_grant + match_abs) * (1.0 - overhead_pct), 0.0)
            previous_cost = float(initial_costs_used.get(proj_name, 0.0))
            residual_target = max(original_target - previous_cost, 0.0)
            total_cost_target += original_target
            
            diff_original = actual_cost - original_target
            diff_pct_original = (diff_original / original_target * 100) if original_target > 0 else 0.0
            diff_residual = actual_cost - previous_cost - residual_target
            diff_pct_residual = (diff_residual / residual_target * 100) if residual_target > 1e-6 else 0.0
            
            status = "✅ On Target" if abs(diff_pct_original) < 5.0 else ("⚠️ Over Budget" if diff_pct_original > 0 else "📉 Under Budget")
            project_statuses.append({
                "name": proj_name,
                "actual": actual_cost,
                "original_target": original_target,
                "residual_target": residual_target,
                "previous_cost": previous_cost,
                "diff": diff_original,
                "diff_pct": diff_pct_original,
                "diff_residual": diff_residual,
                "diff_pct_residual": diff_pct_residual,
                "status": status
            })
        
        # Overall allocation status
        rnd_balanced = abs(overall_rnd_avail - overall_rnd_alloc) < 0.01
        nonrnd_balanced = abs(overall_nonrnd_avail - overall_nonrnd_alloc) < 0.01
        allocation_status = "✅ **Perfect Balance**" if (rnd_balanced and nonrnd_balanced) else "⚠️ **Imbalance Detected**"
        
        diagnostics.append(f"**Allocation Status:** {allocation_status}  \n")
        diagnostics.append(f"- R&D Hours: `{overall_rnd_alloc:.2f}` / `{overall_rnd_avail:.2f}` allocated {'✅' if rnd_balanced else '⚠️'}  \n")
        diagnostics.append(f"- Non-R&D Hours: `{overall_nonrnd_alloc:.2f}` / `{overall_nonrnd_avail:.2f}` allocated {'✅' if nonrnd_balanced else '⚠️'}  \n")
        diagnostics.append(f"- **Total Cost Allocated:** `{total_cost_allocated:,.0f}` ISK  \n")
        diagnostics.append(f"- **Total Target Cost:** `{total_cost_target:,.0f}` ISK  \n")
        cost_deviation_pct = ((total_cost_allocated / total_cost_target - 1) * 100) if total_cost_target > 0 else 0.0
        diagnostics.append(f"- **Overall Cost Deviation:** `{cost_deviation_pct:+.1f}%`  \n")
        diagnostics.append(f"- **Solver Status:** `{result.get('solver_status', 'N/A')}`  \n")
        diagnostics.append("\n---\n")
        
        # ========== PROJECT COST ANALYSIS ==========
        diagnostics.append("## 💰 Project Cost Analysis\n")
        if is_concatenating:
            diagnostics.append("| Project | Original Target | Previous Cost | Residual Target | Actual Cost | Deviation (vs Original) | Status |\n")
            diagnostics.append("|---------|----------------|--------------|----------------|-------------|------------------------|--------|\n")
            for proj_stat in project_statuses:
                status_icon = "✅" if abs(proj_stat["diff_pct"]) < 5.0 else ("⚠️" if proj_stat["diff_pct"] > 0 else "📉")
                diagnostics.append(f"| **{proj_stat['name']}** | `{proj_stat['original_target']:,.0f}` ISK | `{proj_stat['previous_cost']:,.0f}` ISK | `{proj_stat['residual_target']:,.0f}` ISK | `{proj_stat['actual']:,.0f}` ISK | `{proj_stat['diff_pct']:+.1f}%` | {status_icon} {proj_stat['status']} |\n")
        else:
            diagnostics.append("| Project | Target Cost | Actual Cost | Deviation | Status |\n")
            diagnostics.append("|---------|-------------|-------------|-----------|--------|\n")
            for proj_stat in project_statuses:
                status_icon = "✅" if abs(proj_stat["diff_pct"]) < 5.0 else ("⚠️" if proj_stat["diff_pct"] > 0 else "📉")
                diagnostics.append(f"| **{proj_stat['name']}** | `{proj_stat['original_target']:,.0f}` ISK | `{proj_stat['actual']:,.0f}` ISK | `{proj_stat['diff_pct']:+.1f}%` | {status_icon} {proj_stat['status']} |\n")
        
        diagnostics.append("\n---\n")
        
        # ========== PER-EMPLOYEE ALLOCATIONS ==========
        diagnostics.append("## 👥 Per-Employee Allocation Details\n")
        
        employee_issues = []
        for employee in self.employees:
            emp_name = employee.employee_name
            available_rnd = sum(employee.research_hours.values())
            allocated_rnd = 0.0
            available_nonrnd = sum(employee.nonRnD_hours.get(d, 0.0) for d in employee.research_hours)
            allocated_nonrnd = 0.0

            for date_str, available in employee.research_hours.items():
                day_alloc_rnd = 0.0
                day_alloc_nonrnd = 0.0
                if emp_name in allocations and date_str in allocations[emp_name]:
                    for proj_info in allocations[emp_name][date_str].values():
                        day_alloc_rnd += sum(proj_info.get("topics", {}).values())
                        day_alloc_nonrnd += proj_info.get("nonRnD", 0.0)
                allocated_rnd += day_alloc_rnd
                allocated_nonrnd += day_alloc_nonrnd

            rnd_diff = allocated_rnd - available_rnd
            nonrnd_diff = allocated_nonrnd - available_nonrnd
            rnd_balanced = abs(rnd_diff) < 0.01
            nonrnd_balanced = abs(nonrnd_diff) < 0.01
            
            if not rnd_balanced or not nonrnd_balanced:
                employee_issues.append({
                    "name": emp_name,
                    "rnd_diff": rnd_diff,
                    "nonrnd_diff": nonrnd_diff
                })

            diagnostics.append(f"### {emp_name}\n")
            diagnostics.append("| Category | Available | Allocated | Difference | Status |\n")
            diagnostics.append("|----------|-----------|-----------|------------|--------|\n")
            
            rnd_status = "✅ Balanced" if rnd_balanced else f"⚠️ {'Over' if rnd_diff > 0 else 'Under'}-allocated"
            nonrnd_status = "✅ Balanced" if nonrnd_balanced else f"⚠️ {'Over' if nonrnd_diff > 0 else 'Under'}-allocated"
            
            diagnostics.append(f"| **R&D** | `{available_rnd:.2f}` hrs | `{allocated_rnd:.2f}` hrs | `{rnd_diff:+.2f}` hrs | {rnd_status} |\n")
            diagnostics.append(f"| **Non-R&D** | `{available_nonrnd:.2f}` hrs | `{allocated_nonrnd:.2f}` hrs | `{nonrnd_diff:+.2f}` hrs | {nonrnd_status} |\n")
            diagnostics.append("\n")
        
        diagnostics.append("---\n")
        
        # ========== OVERALL STATISTICS ==========
        diagnostics.append("## 📊 Overall Statistics\n")
        diagnostics.append("| Metric | Value |\n")
        diagnostics.append("|--------|-------|\n")
        diagnostics.append(f"| **Total R&D Hours Available** | `{overall_rnd_avail:,.2f}` hrs |\n")
        diagnostics.append(f"| **Total R&D Hours Allocated** | `{overall_rnd_alloc:,.2f}` hrs |\n")
        rnd_util_rate = (overall_rnd_alloc / overall_rnd_avail * 100) if overall_rnd_avail > 0 else 0.0
        nonrnd_util_rate = (overall_nonrnd_alloc / overall_nonrnd_avail * 100) if overall_nonrnd_avail > 0 else 0.0
        total_avail = overall_rnd_avail + overall_nonrnd_avail
        total_alloc = overall_rnd_alloc + overall_nonrnd_alloc
        overall_util_rate = ((total_alloc / total_avail * 100) if total_avail > 0 else 0.0)
        
        diagnostics.append(f"| **R&D Utilization Rate** | `{rnd_util_rate:.1f}%` |\n")
        diagnostics.append(f"| **Total Non-R&D Hours Available** | `{overall_nonrnd_avail:,.2f}` hrs |\n")
        diagnostics.append(f"| **Total Non-R&D Hours Allocated** | `{overall_nonrnd_alloc:,.2f}` hrs |\n")
        diagnostics.append(f"| **Non-R&D Utilization Rate** | `{nonrnd_util_rate:.1f}%` |\n")
        diagnostics.append(f"| **Total Hours Available** | `{total_avail:,.2f}` hrs |\n")
        diagnostics.append(f"| **Total Hours Allocated** | `{total_alloc:,.2f}` hrs |\n")
        diagnostics.append(f"| **Overall Utilization Rate** | `{overall_util_rate:.1f}%` |\n")
        diagnostics.append("\n---\n")
        
        # ========== AUTOMATIC ANALYSIS ==========
        diagnostics.append("## 🤖 Automatic Analysis\n")
        
        # Analyze allocation balance
        analysis_points = []
        if rnd_balanced and nonrnd_balanced:
            analysis_points.append("✅ **Hour Balance:** Perfect - All available hours are allocated with no discrepancies.")
        else:
            rnd_diff_total = overall_rnd_alloc - overall_rnd_avail
            nonrnd_diff_total = overall_nonrnd_alloc - overall_nonrnd_avail
            if abs(rnd_diff_total) > 0.01:
                analysis_points.append(f"⚠️ **R&D Hour Imbalance:** Difference of `{rnd_diff_total:+.2f}` hrs ({'over' if rnd_diff_total > 0 else 'under'}-allocated).")
            if abs(nonrnd_diff_total) > 0.01:
                analysis_points.append(f"⚠️ **Non-R&D Hour Imbalance:** Difference of `{nonrnd_diff_total:+.2f}` hrs ({'over' if nonrnd_diff_total > 0 else 'under'}-allocated).")
        
        # Analyze project budgets
        over_budget_count = sum(1 for p in project_statuses if p["diff_pct"] > 5.0)
        under_budget_count = sum(1 for p in project_statuses if p["diff_pct"] < -5.0)
        on_budget_count = len(project_statuses) - over_budget_count - under_budget_count
        
        if over_budget_count > 0:
            over_projects = [p["name"] for p in project_statuses if p["diff_pct"] > 5.0]
            analysis_points.append(f"⚠️ **Budget Overruns:** {over_budget_count} project(s) significantly over budget: {', '.join(over_projects)}")
        
        if under_budget_count > 0:
            under_projects = [p["name"] for p in project_statuses if p["diff_pct"] < -5.0]
            analysis_points.append(f"📉 **Budget Underruns:** {under_budget_count} project(s) significantly under budget: {', '.join(under_projects)}")
        
        if on_budget_count == len(project_statuses):
            analysis_points.append("✅ **Budget Status:** All projects are within 5% of target budgets.")
        
        # Analyze solver status
        solver_status = result.get('solver_status', 'N/A')
        if 'inaccurate' in str(solver_status).lower():
            analysis_points.append("⚠️ **Solver Accuracy:** Solution marked as 'inaccurate' - results may not be optimal.")
        elif 'optimal' in str(solver_status).lower():
            analysis_points.append("✅ **Solver Status:** Optimal solution found.")
        else:
            analysis_points.append(f"⚠️ **Solver Status:** `{solver_status}` - Review solver output for details.")
        
        # Analyze employee issues
        if employee_issues:
            issue_names = [e["name"] for e in employee_issues]
            analysis_points.append(f"⚠️ **Employee Allocation Issues:** {len(employee_issues)} employee(s) with hour balance discrepancies: {', '.join(issue_names)}")
        else:
            analysis_points.append("✅ **Employee Allocations:** All employees have balanced hour allocations.")
        
        # Analyze capacity vs requirements
        cost_deviation_pct = ((total_cost_allocated / total_cost_target - 1) * 100) if total_cost_target > 0 else 0.0
        is_concatenating = bool(getattr(self, '_initial_costs_used', {}))
        if abs(cost_deviation_pct) > 10.0:
            if is_concatenating:
                analysis_points.append(f"⚠️ **Cost Deviation:** Total cost (including previous allocations) is `{abs(cost_deviation_pct):.1f}%` {'over' if cost_deviation_pct > 0 else 'under'} original target. Review project requirements and capacity.")
            else:
                analysis_points.append(f"⚠️ **Cost Deviation:** Overall cost is `{abs(cost_deviation_pct):.1f}%` {'over' if cost_deviation_pct > 0 else 'under'} target. Review project requirements and capacity.")
        
        for point in analysis_points:
            diagnostics.append(f"- {point}\n")
        
        diagnostics.append("\n---\n")
        
        # ========== ACTIONABLE INSIGHTS ==========
        diagnostics.append("## 💡 Actionable Insights\n")
        
        insights = []
        
        # Capacity insights
        is_concatenating = bool(getattr(self, '_initial_costs_used', {}))
        if total_cost_allocated > total_cost_target * 1.1:
            if is_concatenating:
                insights.append("🔴 **Critical:** Total allocated cost (including previous allocations) exceeds original target by more than 10%. Consider reducing project targets or increasing employee capacity.")
            else:
                insights.append("🔴 **Critical:** Total allocated cost exceeds target by more than 10%. Consider reducing project targets or increasing employee capacity.")
        elif total_cost_allocated < total_cost_target * 0.9:
            if is_concatenating:
                insights.append("🟡 **Warning:** Total allocated cost (including previous allocations) is significantly below original target. You may have unused capacity - consider adding more projects or reducing employee hours.")
            else:
                insights.append("🟡 **Warning:** Total allocated cost is significantly below target. You may have unused capacity - consider adding more projects or reducing employee hours.")
        
        # Project-specific insights
        for proj_stat in project_statuses:
            if proj_stat["diff_pct"] > 20.0:
                if is_concatenating:
                    prev_cost = getattr(self, '_initial_costs_used', {}).get(proj_stat['name'], 0.0)
                    if prev_cost > 0:
                        insights.append(f"🔴 **{proj_stat['name']}:** Total cost (previous + new) exceeds original target by `{proj_stat['diff_pct']:.1f}%`. Previous: {prev_cost:,.0f} ISK, New: {proj_stat['actual'] - prev_cost:,.0f} ISK. Review allocations or increase project budget.")
                    else:
                        insights.append(f"🔴 **{proj_stat['name']}:** Over budget by `{proj_stat['diff_pct']:.1f}%`. Review allocations or increase project budget.")
                else:
                    insights.append(f"🔴 **{proj_stat['name']}:** Over budget by `{proj_stat['diff_pct']:.1f}%`. Review allocations or increase project budget.")
            elif proj_stat["diff_pct"] < -20.0:
                insights.append(f"🟡 **{proj_stat['name']}:** Under budget by `{abs(proj_stat['diff_pct']):.1f}%`. Consider allocating more hours to this project.")
        
        # Solver insights
        if 'inaccurate' in str(solver_status).lower():
            insights.append("🟡 **Solver Quality:** Solution is marked as inaccurate. Consider adjusting solver settings or problem constraints for better results.")
        
        # Employee insights
        if employee_issues:
            insights.append("🟡 **Employee Allocations:** Some employees have hour balance issues. Review individual allocations to ensure accuracy.")
        
        if not insights:
            insights.append("✅ **No Critical Issues:** Current allocation appears balanced and within acceptable parameters.")
        
        for insight in insights:
            diagnostics.append(f"- {insight}\n")
        
        diagnostics.append("\n---\n")
        
        # ========== ALLOCATION ALGORITHM DETAILS ==========
        if "diagnostics" in result:
            diagnostics.append("## 🔧 Allocation Algorithm Diagnostics\n\n")
            algo_diag = result["diagnostics"]
            
            # Convert to markdown format
            algo_diag = algo_diag.replace("================= ", "### ")
            algo_diag = algo_diag.replace(" ==================", "")
            algo_diag = algo_diag.replace("=================", "---")
            algo_diag = algo_diag.replace("✓", "✅")
            algo_diag = algo_diag.replace("⚠️", "⚠️")
            
            # Wrap numbers with units in backticks
            algo_diag = re.sub(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(hrs?|ISK|%)', r'`\1 \2`', algo_diag)
            
            # Convert lines starting with "Project" to headers
            algo_diag = re.sub(r'^Project \'([^\']+)\':', r'#### Project: \1', algo_diag, flags=re.MULTILINE)
            
            # Convert cost lines to better format
            algo_diag = re.sub(r'Computed Cost \(Rounded\):\s+(\d+)\s+\|\s+Target Cost:\s+(\d+)', 
                             r'**Computed Cost:** `\1` ISK | **Target Cost:** `\2` ISK', algo_diag)
            
            diagnostics.append(algo_diag)
        
        diag_text = "\n".join(diagnostics)

        print("\nDiagnostics:")
        print(diag_text)

        self.view.show_diagnostics(diag_text)

        try:
            import os
            reports_dir = AppConfig.REPORTS_DIR
            os.makedirs(reports_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = os.path.join(reports_dir, f"diagnostics_{timestamp}.txt")
            
            with open(filename, "w", encoding="utf-8") as diag_file:
                diag_file.write("Allocation Diagnostics\n")
                diag_file.write("======================\n\n")
                diag_file.write(diag_text)
                
                if self._previous_report_path and os.path.exists(self._previous_report_path):
                    diag_file.write("\n\n")
                    diag_file.write("=" * 80 + "\n")
                    diag_file.write("PREVIOUS REPORT (Concatenated)\n")
                    diag_file.write("=" * 80 + "\n\n")
                    try:
                        with open(self._previous_report_path, "r", encoding="utf-8") as prev_file:
                            prev_content = prev_file.read()
                            diag_file.write(prev_content)
                    except Exception as e:
                        diag_file.write(f"[ERROR] Could not read previous report: {e}\n")
            print(f"[INFO] Diagnostics written to {filename}")
        except Exception as e:
            print(f"[ERROR] Writing diagnostics file: {e}")

        # Detailed Project Cost Breakdown
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
                    sal = (float(emp.salary_levels.get(date_str, {}).get("amount", 0.0)) / 160.0) * 1.25
                    total_direct_cost += (rnd_hours + nonrnd_hours) * sal

            computed_cost = total_direct_cost

            base_grant = float(proj.grant_contractual or 0.0)
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            
            overhead_val = float(proj.operational_overhead or 0.0)
            overhead_pct = overhead_val / 100.0 if overhead_val > 1.0 else max(overhead_val, 0.0)
            overhead_pct = max(0.0, min(overhead_pct, 1.0))
            
            total_target = max((base_grant + match_abs) * (1.0 - overhead_pct), 0.0)
            target_min = float(proj.grant_min or 0.0)

            try:
                rel_dev = ((computed_cost / total_target - 1) * 100) if total_target > 0 else None
            except Exception:
                rel_dev = None

            print(f"Project '{proj_name}':")
            print(f"  Total R&D Hours: {total_rnd_hours:.2f}")
            print(f"  Total Non-R&D Hours: {total_nonrnd_hours:.2f}")
            print(f"  Direct Cost (R&D + Non-R&D): {total_direct_cost:.2f}")
            target_display = f"{total_target:.2f} (total)"
            if target_min > 0 and target_min != total_target:
                target_display += f" / {target_min:.2f} (minimum)"
            print(f"  Computed Total Cost: {computed_cost:.2f} | Target Cost: {target_display}")
            if rel_dev is not None:
                print(f"  Relative Cost Deviation: {rel_dev:.2f} %")
            print("-------------------------------------------------------------")
        print("================================================================\n")

    # -------------------------------------------------------------------------
    # SAVE / LOAD STATE
    # -------------------------------------------------------------------------
    def save_state(self, checked=False):
        """
        Saves the current state, including project colors, to a JSON file.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
        """
        filename, _ = QFileDialog.getSaveFileName(
            self.view, "Save State As", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filename:
            print("[INFO] Save State canceled (no file selected).")
            return

        state_data = {}
        state_data["run_comment"] = self.view.run_comment_input.toPlainText()
        state_data["date_ranges"] = self.date_ranges
        state_data["ui_start_date"] = self.view.start_date_input.text().strip()
        state_data["ui_end_date"] = self.view.end_date_input.text().strip()

        # Employees
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

        # Projects
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
                "nonrnd_percentage": proj.nonrnd_percentage,
                "previous_spending": getattr(proj, "previous_spending", 0.0),
                "color": proj.color
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

    def load_state(self, checked=False):
        """
        Loads a saved state, clears existing project tabs, and recreates them with colors.
        
        Args:
            checked: Ignored (required for PyQt5 signal compatibility)
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
            self.date_ranges = state_data.get("date_ranges", [])
            self.view.start_date_input.setText(state_data.get("ui_start_date", ""))
            self.view.end_date_input.setText(state_data.get("ui_end_date", ""))

            # Employees
            self.employees.clear()
            for emp_dict in state_data.get("employees", []):
                emp = EmployeeModel(emp_dict["employee_name"])
                emp.research_hours.update(emp_dict.get("research_hours", {}))
                emp.meeting_hours.update(emp_dict.get("meeting_hours", {}))
                emp.nonRnD_hours.update(emp_dict.get("nonRnD_hours", {}))
                for date_str, topics_map in emp_dict.get("research_topics", {}).items():
                    for topic, hrs in topics_map.items():
                        emp.research_topics[date_str][topic] = hrs
                salary_levels_data = emp_dict.get("salary_levels", {})
                for date_str, salary_info in salary_levels_data.items():
                    if isinstance(salary_info, dict) and "level" in salary_info and "amount" in salary_info:
                        emp.salary_levels[date_str] = {
                            "level": salary_info["level"],
                            "amount": float(salary_info["amount"])
                        }
                self.employees.append(emp)

            # Projects
            self.projects.clear()
            self.view.projects.clear()
            self.view.clear_project_tabs()  # Clear existing tabs
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
                proj.nonrnd_percentage = proj_dict.get("nonrnd_percentage", 0)
                proj.previous_spending = proj_dict.get("previous_spending", 0.0)
                proj.color = proj_dict.get("color", "")
                self.projects.append(proj)
                self.view.projects.append(proj)
                self.view.create_project_subsection_from_project(proj)

            self.view.create_employee_overview_section(self.employees)
            print(f"[INFO] Loaded {len(self.employees)} employees, {len(self.projects)} projects.")
            print("[INFO] State restoration complete.")

        except Exception as e:
            print(f"[ERROR] Failed to load state from {filename}: {e}")

    def on_project_saved(self, project_obj, data):
        """
        Updates a project's fields when saved.
        """
        try:
            project_obj.grant_min = float(data["grant_min"]) if data["grant_min"] else 0
        except Exception:
            project_obj.grant_min = 0

        try:
            project_obj.grant_max = float(data["grant_max"]) if data["grant_max"] else 0
        except Exception:
            project_obj.grant_max = 0

        try:
            project_obj.grant_contractual = float(data["grant_contractual"]) if data["grant_contractual"] else 0
        except Exception:
            project_obj.grant_contractual = 0

        try:
            project_obj.operational_overhead = data["operational_overhead"]
        except Exception:
            project_obj.operational_overhead = 0

        try:
            project_obj.matching_fund_value = float(data["matching_fund_value"]) if data["matching_fund_value"] else 0
        except Exception:
            project_obj.matching_fund_value = 0

        try:
            project_obj.nonrnd_percentage = data["nonrnd_percentage"] or 0
        except Exception:
            project_obj.nonrnd_percentage = 0

        project_obj.name = data["name"]
        project_obj.funding_agency = data["funding_agency"]
        project_obj.matching_fund_type = data["matching_fund_type"]
        project_obj.funding_start = data["funding_start"]
        project_obj.funding_end = data["funding_end"]
        project_obj.research_topics = data["research_topics"]

        print(f"[INFO] Project '{project_obj.name}' fields have been updated.")

    def on_project_deleted(self, project_obj):
        """
        Removes a project and its corresponding tab from the UI.
        """
        if project_obj in self.projects:
            self.projects.remove(project_obj)
        if project_obj in self.view.projects:
            self.view.projects.remove(project_obj)
        self.view.remove_project_tab(project_obj)
        print(f"[INFO] Project '{project_obj.name}' removed.")

    def on_employee_salary_interval_edited(self, employee, old_start, old_end, new_start, new_end, new_level, new_amount):
        """
        Edits an employee's salary interval and updates the Employees tab.
        """
        employee.remove_salary_interval(old_start, old_end)

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

        current_dt = new_start_dt
        while current_dt <= new_end_dt:
            day_str = current_dt.strftime("%m-%d-%Y")
            employee.set_salary_level_for_date(day_str, new_level, new_amount_val)
            current_dt += timedelta(days=1)

        print(f"[INFO] Edited salary for {employee.employee_name}: Changed interval {old_start}–{old_end} to {new_start}–{new_end} with level '{new_level}' and amount {new_amount_val}.")
        self.view.create_employee_overview_section(self.employees)