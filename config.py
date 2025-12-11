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
Configuration module for REA application.
Contains all configuration constants, default values, and application settings.
"""


class SalaryConfig:
    """
    Configuration for salary calculations.
    
    HOURS_PER_MONTH: Standard working hours per month (160 hours = 4 weeks * 40 hours)
    OVERHEAD_MULTIPLIER: Multiplier applied to base salary for overhead costs (1.25 = 25% overhead)
    """
    HOURS_PER_MONTH = 160.0
    OVERHEAD_MULTIPLIER = 1.25
    
    @classmethod
    def calculate_hourly_rate(cls, monthly_salary):
        """
        Calculate hourly rate from monthly salary including overhead.
        
        Args:
            monthly_salary: Monthly salary amount
            
        Returns:
            Hourly rate with overhead applied
        """
        if monthly_salary <= 0:
            return 0.0
        return (monthly_salary / cls.HOURS_PER_MONTH) * cls.OVERHEAD_MULTIPLIER


class CSVConfig:
    """
    Configuration for CSV timesheet parsing.
    
    Defines the row and column indices for extracting data from employee timesheet CSVs.
    All indices are zero-based.
    """
    EMPLOYEE_NAME_ROW = 1
    EMPLOYEE_NAME_COL = 2
    
    DATE_ROW = 2
    FIRST_DATE_COL = 4
    
    RESEARCH_HOURS_ROW = 11
    MEETING_IIIM_ROW = 14
    MEETING_OTHER_ROW = 15
    NONRND_HOURS_ROW = 42
    
    TOPICS_START_ROW = 19
    
    DATE_FORMAT = '%m/%d/%Y'


class DateConfig:
    """
    Configuration for date handling throughout the application.
    
    INTERNAL_FORMAT: Format used for storing dates as strings (MM-DD-YYYY)
    DISPLAY_FORMAT: Format shown to users in the UI
    """
    INTERNAL_FORMAT = "%m-%d-%Y"
    DISPLAY_FORMAT = "MM-DD-YYYY"
    
    MAX_DATE_RANGE_DAYS = 366 * 5


class AlgorithmConfig:
    MAX_ITERATIONS_ECOS = 20_000
    MAX_ITERATIONS_SCS = 20_000
    MAX_ITERATIONS_CLARABEL = 10_000

    TOLERANCE_ABSOLUTE = 1e-7
    TOLERANCE_RELATIVE = 1e-7
    TOLERANCE_FEASIBILITY = 1e-7
    TOLERANCE_SCS = 5e-4

    BIG_SLACK_PENALTY = 1e5
    LAMBDA_SMOOTH = 1e-3
    LAMBDA_TOPIC = 5e-3
    BETA_COST_DEVIATION = 1e-2
    GAMMA_NONRND_FRACTION = 1e-5
    REGULARIZATION_LAMBDA = 1e-6

    HUBER_M_FACTOR = 0.1

    ROUNDING_DECIMALS = 2
    ZERO_THRESHOLD = 1e-7
    ALLOCATION_TOLERANCE = 1e-2

    ALPHA_OVERSHOOT = 5.0
    ALPHA_UNDERSHOOT = 1.0
    GLOBAL_BUDGET_BAND = 0.03


class UIConfig:
    """
    Configuration for user interface settings.
    """
    WINDOW_WIDTH = 900
    WINDOW_HEIGHT = 600
    WINDOW_START_X = 500
    WINDOW_START_Y = 100
    
    MAX_COLORS = 20
    
    AVAILABLE_COLORS = [
        "#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
        "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
        "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
        "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9"
    ]


class ValidationConfig:
    """
    Configuration for input validation.
    """
    MIN_SALARY = 0
    MAX_SALARY = 10_000_000
    
    MIN_HOURS = 0
    MAX_HOURS_PER_DAY = 24
    
    MIN_PERCENTAGE = 0
    MAX_PERCENTAGE = 100
    
    MAX_EMPLOYEES = 1000
    MAX_PROJECTS = 100


class ResearchTopics:
    """
    Predefined research topics used throughout the application.
    """
    TOPICS = [
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
    
    BRIDGE_TOPIC = "Bridge"


class AppConfig:
    """
    Main application configuration.
    """
    ORGANIZATION_NAME = "IIIM"
    APPLICATION_NAME = "REAApp"
    
    DEBUG_LOG_FILE = "allocation_debug.log"
    REPORTS_DIR = "reports"
    EXPLANATIONS_DIR = "explanations"
    
    STATE_FILE_VERSION = "1.0"


class LockedAllocations:
    """
    Configuration for locked employee allocations.
    
    This dictionary defines employees who are pre-assigned to specific projects
    and should not be reallocated by the optimization algorithm.
    """
    ALLOCATIONS = {
        "Bridget Burger": "EURIDICE"
    }
    
    @classmethod
    def get_locked_project(cls, employee_name):
        """
        Get the project an employee is locked to, if any.
        
        Args:
            employee_name: Name of the employee
            
        Returns:
            Project name if locked, None otherwise
        """
        return cls.ALLOCATIONS.get(employee_name)
    
    @classmethod
    def is_locked(cls, employee_name):
        """
        Check if an employee is locked to a project.
        
        Args:
            employee_name: Name of the employee
            
        Returns:
            True if employee is locked, False otherwise
        """
        return employee_name in cls.ALLOCATIONS

