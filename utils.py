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
Utility functions and classes for common operations.
Provides helper functions for date handling, calculations, and data formatting.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from config import DateConfig, SalaryConfig


class DateManager:
    """
    Centralized date handling and conversion utilities.
    """
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.
        
        Args:
            date_str: Date string in internal format
            
        Returns:
            Datetime object or None if parsing fails
        """
        try:
            return datetime.strptime(date_str, DateConfig.INTERNAL_FORMAT)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def format_date(date_obj: datetime) -> str:
        """
        Format a datetime object into internal string format.
        
        Args:
            date_obj: Datetime object to format
            
        Returns:
            Date string in internal format
        """
        return date_obj.strftime(DateConfig.INTERNAL_FORMAT)
    
    @staticmethod
    def generate_date_list(start_date: str, end_date: str) -> List[str]:
        """
        Generate a list of all dates between start and end (inclusive).
        
        Args:
            start_date: Start date string
            end_date: End date string
            
        Returns:
            List of date strings in internal format
        """
        start_dt = datetime.strptime(start_date, DateConfig.INTERNAL_FORMAT)
        end_dt = datetime.strptime(end_date, DateConfig.INTERNAL_FORMAT)
        
        date_list = []
        current = start_dt
        while current <= end_dt:
            date_list.append(current.strftime(DateConfig.INTERNAL_FORMAT))
            current += timedelta(days=1)
        
        return date_list
    
    @staticmethod
    def is_consecutive(date1: str, date2: str) -> bool:
        """
        Check if date2 is exactly one day after date1.
        
        Args:
            date1: First date string
            date2: Second date string
            
        Returns:
            True if dates are consecutive, False otherwise
        """
        d1 = datetime.strptime(date1, DateConfig.INTERNAL_FORMAT)
        d2 = datetime.strptime(date2, DateConfig.INTERNAL_FORMAT)
        return (d2 - d1).days == 1


class SalaryCalculator:
    """
    Centralized salary and cost calculation utilities.
    """
    
    @staticmethod
    def calculate_hourly_rate(monthly_salary: float) -> float:
        """
        Calculate hourly rate from monthly salary.
        
        Args:
            monthly_salary: Monthly salary amount
            
        Returns:
            Hourly rate with overhead applied
        """
        return SalaryConfig.calculate_hourly_rate(monthly_salary)
    
    @staticmethod
    def calculate_cost(hours: float, monthly_salary: float) -> float:
        """
        Calculate cost for given hours at a salary level.
        
        Args:
            hours: Number of hours worked
            monthly_salary: Monthly salary amount
            
        Returns:
            Total cost for the hours
        """
        hourly_rate = SalaryCalculator.calculate_hourly_rate(monthly_salary)
        return hours * hourly_rate
    
    @staticmethod
    def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
        """
        Safely divide two numbers, returning default if denominator is zero.
        
        Args:
            numerator: Number to divide
            denominator: Number to divide by
            default: Value to return if denominator is zero
            
        Returns:
            Result of division or default value
        """
        if abs(denominator) < 1e-9:
            return default
        return numerator / denominator


class ProjectNameResolver:
    """
    Utilities for resolving project names consistently.
    """
    
    @staticmethod
    def get_project_name(project, index: int = 0) -> str:
        """
        Get a consistent project name, using index as fallback.
        
        Args:
            project: Project object
            index: Index to use if project has no name
            
        Returns:
            Project name or generated name
        """
        if hasattr(project, 'name') and project.name:
            return project.name
        return f"Project_{index}"


class DataCompressor:
    """
    Utilities for compressing sparse data to reduce memory usage.
    """
    
    @staticmethod
    def compress_daily_data(data_dict: Dict[str, float], 
                           threshold: float = 1e-9) -> Dict[str, float]:
        """
        Remove entries below threshold to compress sparse data.
        
        Args:
            data_dict: Dictionary of date -> value
            threshold: Minimum value to keep
            
        Returns:
            Compressed dictionary with only significant values
        """
        return {
            date: value 
            for date, value in data_dict.items() 
            if abs(value) > threshold
        }
    
    @staticmethod
    def compress_topics(topics_dict: Dict[str, Dict[str, float]], 
                       threshold: float = 1e-9) -> Dict[str, Dict[str, float]]:
        """
        Remove topic entries below threshold to compress sparse data.
        
        Args:
            topics_dict: Dictionary of date -> topic -> hours
            threshold: Minimum hours to keep
            
        Returns:
            Compressed dictionary with only significant values
        """
        compressed = {}
        for date, topic_hours in topics_dict.items():
            significant_topics = {
                topic: hours 
                for topic, hours in topic_hours.items() 
                if abs(hours) > threshold
            }
            if significant_topics:
                compressed[date] = significant_topics
        return compressed


class ErrorMessageFormatter:
    """
    Utilities for formatting consistent error messages.
    """
    
    @staticmethod
    def format_validation_error(field_name: str, error_message: str) -> str:
        """
        Format a validation error message consistently.
        
        Args:
            field_name: Name of the field that failed validation
            error_message: Detailed error message
            
        Returns:
            Formatted error message
        """
        return f"Validation error in {field_name}: {error_message}"
    
    @staticmethod
    def format_file_error(filename: str, error_message: str) -> str:
        """
        Format a file operation error message consistently.
        
        Args:
            filename: Name of the file
            error_message: Detailed error message
            
        Returns:
            Formatted error message
        """
        return f"Error with file '{filename}': {error_message}"
    
    @staticmethod
    def format_calculation_error(context: str, error_message: str) -> str:
        """
        Format a calculation error message consistently.
        
        Args:
            context: Context where calculation failed
            error_message: Detailed error message
            
        Returns:
            Formatted error message
        """
        return f"Calculation error in {context}: {error_message}"


class StateVersionManager:
    """
    Manages versioning of saved state files for forward compatibility.
    """
    
    CURRENT_VERSION = "1.0"
    
    @staticmethod
    def add_version(state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add version information to state data.
        
        Args:
            state_data: Dictionary containing state data
            
        Returns:
            State data with version information added
        """
        state_data['_version'] = StateVersionManager.CURRENT_VERSION
        return state_data
    
    @staticmethod
    def check_version(state_data: Dict[str, Any]) -> bool:
        """
        Check if state data version is compatible with current version.
        
        Args:
            state_data: Dictionary containing state data
            
        Returns:
            True if version is compatible, False otherwise
        """
        if '_version' not in state_data:
            return True
        
        return state_data['_version'] == StateVersionManager.CURRENT_VERSION
    
    @staticmethod
    def migrate_if_needed(state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate state data to current version if needed.
        
        Args:
            state_data: Dictionary containing state data
            
        Returns:
            Migrated state data
        """
        if '_version' not in state_data:
            state_data['_version'] = StateVersionManager.CURRENT_VERSION
        
        return state_data

