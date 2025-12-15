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

"""
Worker threads for long-running operations.
Prevents UI freezing by executing heavy computations in background threads.
"""

from PyQt5.QtCore import QThread, pyqtSignal
from typing import Any, Callable, Dict, List, Tuple
from logger import get_logger


class AlgorithmWorker(QThread):
    """
    Worker thread for running the allocation algorithm.
    
    Executes the optimization algorithm in a background thread to prevent
    UI freezing. Emits signals for progress updates and completion.
    """
    
    progress_updated = pyqtSignal(str)
    finished_success = pyqtSignal(dict)
    finished_error = pyqtSignal(str)
    
    def __init__(self, algorithm_func: Callable, employees: List, projects: List,
                 start_date: str, end_date: str, all_topics: List, initial_costs: Dict[str, float] = None):
        """
        Initialize algorithm worker.
        
        Args:
            algorithm_func: Function to call for algorithm execution
            employees: List of employee models
            projects: List of project models
            start_date: Start date string
            end_date: End date string
            all_topics: List of all research topics
            initial_costs: Dictionary of project names to initial costs for concatenation
        """
        super().__init__()
        self.algorithm_func = algorithm_func
        self.employees = employees
        self.projects = projects
        self.start_date = start_date
        self.end_date = end_date
        self.all_topics = all_topics
        self.initial_costs = initial_costs or {}
        self.logger = get_logger()
        self._is_cancelled = False
    
    def run(self):
        """
        Execute the algorithm in background thread.
        """
        try:
            self.progress_updated.emit("Initializing algorithm...")
            
            if self._is_cancelled:
                return
            
            self.progress_updated.emit("Setting up constraints and variables...")
            
            if self._is_cancelled:
                return
            
            self.progress_updated.emit("Solving optimization problem...")
            
            if self._is_cancelled:
                return
            
            result = self.algorithm_func(
                employees_arg=self.employees,
                projects_arg=self.projects,
                start_date=self.start_date,
                end_date=self.end_date,
                all_topics_arg=self.all_topics,
                initial_costs=self.initial_costs
            )
            
            if self._is_cancelled:
                return
            
            self.progress_updated.emit("Processing results...")
            
            if self._is_cancelled:
                return
            
            self.progress_updated.emit("Algorithm completed successfully")
            self.finished_success.emit(result)
            
        except Exception as e:
            error_msg = f"Algorithm execution failed: {str(e)}"
            self.logger.error(error_msg)
            self.finished_error.emit(error_msg)
    
    def cancel(self):
        """
        Cancel the algorithm execution.
        """
        self._is_cancelled = True
        self.progress_updated.emit("Cancelling algorithm...")


class CSVLoaderWorker(QThread):
    """
    Worker thread for loading CSV timesheet files.
    
    Loads and processes CSV files in background to prevent UI freezing
    during file I/O operations.
    """
    
    progress_updated = pyqtSignal(str, int)
    finished_success = pyqtSignal(list)
    finished_error = pyqtSignal(str)
    
    def __init__(self, model, directory: str, date_ranges: List[Tuple[str, str]]):
        """
        Initialize CSV loader worker.
        
        Args:
            model: ReaDataModel instance
            directory: Directory containing CSV files
            date_ranges: List of date range tuples
        """
        super().__init__()
        self.model = model
        self.directory = directory
        self.date_ranges = date_ranges
        self.logger = get_logger()
    
    def run(self):
        """
        Load CSV files in background thread.
        """
        try:
            self.progress_updated.emit("Loading timesheet files...", 0)
            
            employees = self.model.extract_data_from_csv(
                self.directory,
                self.date_ranges
            )
            
            self.progress_updated.emit("Timesheet loading complete", 100)
            self.finished_success.emit(employees)
            
        except Exception as e:
            error_msg = f"Failed to load timesheet files: {str(e)}"
            self.logger.error(error_msg)
            self.finished_error.emit(error_msg)


class StateLoaderWorker(QThread):
    """
    Worker thread for loading saved state from JSON files.
    
    Loads and deserializes state files in background thread.
    """
    
    progress_updated = pyqtSignal(str)
    finished_success = pyqtSignal(dict)
    finished_error = pyqtSignal(str)
    
    def __init__(self, filename: str):
        """
        Initialize state loader worker.
        
        Args:
            filename: Path to state file
        """
        super().__init__()
        self.filename = filename
        self.logger = get_logger()
    
    def run(self):
        """
        Load state file in background thread.
        """
        try:
            import json
            
            self.progress_updated.emit("Loading state file...")
            
            with open(self.filename, 'r') as f:
                state_data = json.load(f)
            
            self.progress_updated.emit("State file loaded successfully")
            self.finished_success.emit(state_data)
            
        except Exception as e:
            error_msg = f"Failed to load state file: {str(e)}"
            self.logger.error(error_msg)
            self.finished_error.emit(error_msg)


class StateSaverWorker(QThread):
    """
    Worker thread for saving state to JSON files.
    
    Serializes and saves state in background thread.
    """
    
    progress_updated = pyqtSignal(str)
    finished_success = pyqtSignal()
    finished_error = pyqtSignal(str)
    
    def __init__(self, filename: str, state_data: Dict[str, Any]):
        """
        Initialize state saver worker.
        
        Args:
            filename: Path to save state file
            state_data: Dictionary containing state data
        """
        super().__init__()
        self.filename = filename
        self.state_data = state_data
        self.logger = get_logger()
    
    def run(self):
        """
        Save state file in background thread.
        """
        try:
            import json
            
            self.progress_updated.emit("Saving state file...")
            
            with open(self.filename, 'w') as f:
                json.dump(self.state_data, f, indent=2)
            
            self.progress_updated.emit("State file saved successfully")
            self.finished_success.emit()
            
        except Exception as e:
            error_msg = f"Failed to save state file: {str(e)}"
            self.logger.error(error_msg)
            self.finished_error.emit(error_msg)

