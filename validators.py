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
Validation utilities for input data.
Provides comprehensive validation for dates, numeric values, and data structures.
"""

import re
from datetime import datetime
from typing import Tuple, Optional
from config import DateConfig, ValidationConfig


class ValidationResult:
    """
    Result of a validation operation.
    
    Encapsulates whether validation succeeded and provides error messages
    for failed validations.
    """
    
    def __init__(self, is_valid: bool, error_message: str = ""):
        self.is_valid = is_valid
        self.error_message = error_message
    
    def __bool__(self):
        return self.is_valid
    
    def __str__(self):
        return self.error_message if not self.is_valid else "Valid"


class DateValidator:
    """
    Validates date strings and date ranges.
    """
    
    @staticmethod
    def validate_date_string(date_str: str) -> ValidationResult:
        """
        Validate a date string matches the expected format.
        
        Args:
            date_str: Date string to validate
            
        Returns:
            ValidationResult indicating success or failure
        """
        if not date_str or not date_str.strip():
            return ValidationResult(False, "Date string is empty")
        
        pattern = r'^\d{2}-\d{2}-\d{4}$'
        if not re.match(pattern, date_str):
            return ValidationResult(
                False, 
                f"Date '{date_str}' must match format {DateConfig.DISPLAY_FORMAT}"
            )
        
        try:
            datetime.strptime(date_str, DateConfig.INTERNAL_FORMAT)
            return ValidationResult(True)
        except ValueError as e:
            return ValidationResult(False, f"Invalid date: {str(e)}")
    
    @staticmethod
    def validate_date_range(start_date: str, end_date: str) -> ValidationResult:
        """
        Validate a date range ensuring start is before end and range is reasonable.
        
        Args:
            start_date: Start date string
            end_date: End date string
            
        Returns:
            ValidationResult indicating success or failure
        """
        start_result = DateValidator.validate_date_string(start_date)
        if not start_result:
            return start_result
        
        end_result = DateValidator.validate_date_string(end_date)
        if not end_result:
            return end_result
        
        try:
            start_dt = datetime.strptime(start_date, DateConfig.INTERNAL_FORMAT)
            end_dt = datetime.strptime(end_date, DateConfig.INTERNAL_FORMAT)
            
            if start_dt > end_dt:
                return ValidationResult(
                    False, 
                    "Start date must be before or equal to end date"
                )
            
            days_diff = (end_dt - start_dt).days
            if days_diff > DateConfig.MAX_DATE_RANGE_DAYS:
                return ValidationResult(
                    False,
                    f"Date range exceeds maximum of {DateConfig.MAX_DATE_RANGE_DAYS} days"
                )
            
            return ValidationResult(True)
        except Exception as e:
            return ValidationResult(False, f"Error validating date range: {str(e)}")


class NumericValidator:
    """
    Validates numeric inputs including salaries, hours, and percentages.
    """
    
    @staticmethod
    def validate_salary(value: str) -> Tuple[bool, Optional[float], str]:
        """
        Validate a salary value.
        
        Args:
            value: Salary value as string
            
        Returns:
            Tuple of (is_valid, parsed_value, error_message)
        """
        if not value or not value.strip():
            return False, None, "Salary cannot be empty"
        
        try:
            salary = float(value.strip())
            
            if salary < ValidationConfig.MIN_SALARY:
                return False, None, f"Salary cannot be negative"
            
            if salary > ValidationConfig.MAX_SALARY:
                return False, None, f"Salary exceeds maximum of {ValidationConfig.MAX_SALARY:,.0f}"
            
            return True, salary, ""
        except ValueError:
            return False, None, f"Salary must be a valid number"
    
    @staticmethod
    def validate_hours(value: str) -> Tuple[bool, Optional[float], str]:
        """
        Validate an hours value.
        
        Args:
            value: Hours value as string
            
        Returns:
            Tuple of (is_valid, parsed_value, error_message)
        """
        if not value or not value.strip():
            return False, None, "Hours cannot be empty"
        
        try:
            hours = float(value.strip())
            
            if hours < ValidationConfig.MIN_HOURS:
                return False, None, "Hours cannot be negative"
            
            if hours > ValidationConfig.MAX_HOURS_PER_DAY:
                return False, None, f"Hours exceed maximum of {ValidationConfig.MAX_HOURS_PER_DAY} per day"
            
            return True, hours, ""
        except ValueError:
            return False, None, "Hours must be a valid number"
    
    @staticmethod
    def validate_percentage(value: str) -> Tuple[bool, Optional[float], str]:
        """
        Validate a percentage value.
        
        Args:
            value: Percentage value as string
            
        Returns:
            Tuple of (is_valid, parsed_value as decimal, error_message)
        """
        if not value or not value.strip():
            return True, 0.0, ""
        
        try:
            value_clean = value.strip().replace('%', '').strip()
            percentage = float(value_clean)
            
            if percentage < ValidationConfig.MIN_PERCENTAGE:
                return False, None, "Percentage cannot be negative"
            
            if percentage > ValidationConfig.MAX_PERCENTAGE:
                return False, None, f"Percentage cannot exceed {ValidationConfig.MAX_PERCENTAGE}%"
            
            return True, percentage / 100.0, ""
        except ValueError:
            return False, None, "Percentage must be a valid number"
    
    @staticmethod
    def validate_currency(value: str) -> Tuple[bool, Optional[float], str]:
        """
        Validate a currency value.
        
        Args:
            value: Currency value as string
            
        Returns:
            Tuple of (is_valid, parsed_value, error_message)
        """
        if not value or not value.strip():
            return True, 0.0, ""
        
        try:
            value_clean = value.strip().replace(',', '').replace(' ', '')
            amount = float(value_clean)
            
            if amount < 0:
                return False, None, "Amount cannot be negative"
            
            return True, amount, ""
        except ValueError:
            return False, None, "Amount must be a valid number"


class DataValidator:
    """
    Validates complex data structures and relationships.
    """
    
    @staticmethod
    def validate_employee_count(count: int) -> ValidationResult:
        """
        Validate the number of employees is within acceptable limits.
        
        Args:
            count: Number of employees
            
        Returns:
            ValidationResult indicating success or failure
        """
        if count < 0:
            return ValidationResult(False, "Employee count cannot be negative")
        
        if count > ValidationConfig.MAX_EMPLOYEES:
            return ValidationResult(
                False,
                f"Employee count exceeds maximum of {ValidationConfig.MAX_EMPLOYEES}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_project_count(count: int) -> ValidationResult:
        """
        Validate the number of projects is within acceptable limits.
        
        Args:
            count: Number of projects
            
        Returns:
            ValidationResult indicating success or failure
        """
        if count < 0:
            return ValidationResult(False, "Project count cannot be negative")
        
        if count > ValidationConfig.MAX_PROJECTS:
            return ValidationResult(
                False,
                f"Project count exceeds maximum of {ValidationConfig.MAX_PROJECTS}"
            )
        
        return ValidationResult(True)
    
    @staticmethod
    def validate_csv_structure(df, required_rows: int = 50) -> ValidationResult:
        """
        Validate that a CSV dataframe has the expected structure.
        
        Args:
            df: Pandas dataframe loaded from CSV
            required_rows: Minimum number of rows required
            
        Returns:
            ValidationResult indicating success or failure
        """
        if df is None or df.empty:
            return ValidationResult(False, "CSV file is empty or invalid")
        
        if df.shape[0] < required_rows:
            return ValidationResult(
                False,
                f"CSV has only {df.shape[0]} rows, expected at least {required_rows}"
            )
        
        if df.shape[1] < 5:
            return ValidationResult(
                False,
                f"CSV has only {df.shape[1]} columns, expected at least 5"
            )
        
        return ValidationResult(True)

