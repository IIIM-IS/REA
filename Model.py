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
Data models for REA application.
Contains model classes for employees, projects, and the main data model.
"""

import pandas as pd  # pyright: ignore[reportMissingImports]
import os
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

from config import ResearchTopics, CSVConfig, DateConfig
from validators import DataValidator
from utils import DateManager, DataCompressor
from logger import get_logger
from error_handling import FileOperationError


class ReaDataModel:
    """
    Main data model for the REA application.
    
    Manages research topics, employees, and projects. Provides methods for
    loading timesheet data from CSV files and validating data structures.
    """
    
    def __init__(self):
        self.research_topics = ResearchTopics.TOPICS.copy()
        self.employees = []
        self.projects = []
        self.logger = get_logger()

    def extract_data_from_csv(self, directory: str, date_ranges: List[Tuple[str, str]]) -> List['EmployeeModel']:
        """
        Extract employee data from CSV timesheet files in a directory.
        
        Processes all CSV files in the given directory, extracting employee names,
        work hours, and research topic allocations for the specified date ranges.
        Multiple CSV files for the same employee are merged.
        
        Args:
            directory: Path to directory containing CSV files
            date_ranges: List of (start_date, end_date) tuples defining ranges to extract
            
        Returns:
            List of EmployeeModel objects with populated data
            
        Raises:
            FileOperationError: If directory cannot be accessed or CSV files are invalid
        """
        if not os.path.exists(directory):
            raise FileOperationError(f"Directory does not exist: {directory}")
        
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]
        
        if not csv_files:
            self.logger.warning(f"No CSV files found in {directory}")
            return []
        
        employees_dict = {}
        
        for file_name in csv_files:
            try:
                file_path = os.path.join(directory, file_name)
                df = pd.read_csv(file_path, header=None)
                
                validation = DataValidator.validate_csv_structure(df)
                if not validation:
                    self.logger.warning(f"Skipping {file_name}: {validation.error_message}")
                    continue
                
                employee_name = self._extract_employee_name(df)
                in_range_columns = self._extract_in_range_columns(df, date_ranges)
                
                if not in_range_columns:
                    self.logger.warning(f"No date columns in range for {file_name}")
                    continue
                
                daily_hours_dict = self._extract_hours_data(df, in_range_columns)
                daily_topics_dict = self._extract_research_topics(df, in_range_columns)
                
                if employee_name in employees_dict:
                    employee = employees_dict[employee_name]
                else:
                    employee = EmployeeModel(employee_name)
                    employees_dict[employee_name] = employee
                
                self._populate_employee_data(employee, daily_hours_dict, daily_topics_dict)
                
                self.logger.info(f"Processed timesheet for {employee_name} from {file_name}")
                
            except Exception as e:
                self.logger.error(f"Error processing {file_name}: {str(e)}")
                continue
        
        self.logger.info(f"Loaded {len(employees_dict)} employees from {len(csv_files)} CSV files")
        return list(employees_dict.values())
    
    def _extract_employee_name(self, df: pd.DataFrame) -> str:
        """
        Extract employee name from CSV dataframe.
        
        Args:
            df: Pandas dataframe loaded from CSV
            
        Returns:
            Employee name string
        """
        name = df.iloc[CSVConfig.EMPLOYEE_NAME_ROW, CSVConfig.EMPLOYEE_NAME_COL]
        return str(name).strip()

    def _extract_in_range_columns(self, df: pd.DataFrame, date_ranges: List[Tuple[str, str]]) -> List[int]:
        """
        Find column indices containing dates within the specified ranges.
        
        Args:
            df: Pandas dataframe from CSV
            date_ranges: List of (start_date, end_date) tuples
            
        Returns:
            List of column indices containing dates in range
        """
        if not date_ranges:
            self.logger.warning("No date ranges provided")
            return []
        
        start_date_str, end_date_str = date_ranges[-1]
        start_date = DateManager.parse_date(start_date_str)
        end_date = DateManager.parse_date(end_date_str)
        
        if not start_date or not end_date:
            self.logger.error("Failed to parse date range")
            return []
        
        try:
            dates = pd.to_datetime(
                df.iloc[CSVConfig.DATE_ROW, CSVConfig.FIRST_DATE_COL:], 
                format=CSVConfig.DATE_FORMAT, 
                errors='coerce'
            )
            
            in_range_mask = (dates >= start_date) & (dates <= end_date)
            in_range_columns = dates[in_range_mask].index.tolist()
            
            return in_range_columns
            
        except Exception as e:
            self.logger.error(f"Error extracting date columns: {str(e)}")
            return []

    def _extract_hours_data(self, df: pd.DataFrame, in_range_columns: List[int]) -> Dict[str, Dict[str, float]]:
        """
        Extract research, meeting, and non-R&D hours for each date.
        
        Args:
            df: Pandas dataframe from CSV
            in_range_columns: List of column indices to process
            
        Returns:
            Dictionary mapping date strings to hours data:
            {
                '01-01-2025': {
                    'research_hours': 4.0,
                    'meeting_hours': 3.0,
                    'nonRnD_hours': 1.0
                },
                ...
            }
        """
        daily_hours = {}
        
        for col_index in in_range_columns:
            date_str = self._parse_date_from_column(df, col_index)
            if not date_str:
                continue
            
            research_hours = self._extract_cell_value(df, CSVConfig.RESEARCH_HOURS_ROW, col_index)
            meeting_iiim = self._extract_cell_value(df, CSVConfig.MEETING_IIIM_ROW, col_index)
            meeting_other = self._extract_cell_value(df, CSVConfig.MEETING_OTHER_ROW, col_index)
            nonrnd_hours = self._extract_cell_value(df, CSVConfig.NONRND_HOURS_ROW, col_index)
            
            total_meeting_hours = meeting_iiim + meeting_other
            
            daily_hours[date_str] = {
                'research_hours': research_hours,
                'meeting_hours': total_meeting_hours,
                'nonRnD_hours': nonrnd_hours
            }
        
        return daily_hours
    
    def _parse_date_from_column(self, df: pd.DataFrame, col_index: int) -> Optional[str]:
        """
        Parse date from a specific column in the dataframe.
        
        Args:
            df: Pandas dataframe from CSV
            col_index: Column index to extract date from
            
        Returns:
            Date string in internal format or None if parsing fails
        """
        try:
            date_val = df.iloc[CSVConfig.DATE_ROW, col_index]
            date_parsed = pd.to_datetime(date_val, errors='coerce')
            
            if pd.isna(date_parsed):
                return None
            
            return date_parsed.strftime(DateConfig.INTERNAL_FORMAT)
        except Exception:
            return None
    
    def _extract_cell_value(self, df: pd.DataFrame, row: int, col: int) -> float:
        """
        Extract and convert a cell value to float, returning 0.0 for invalid values.
        
        Args:
            df: Pandas dataframe
            row: Row index
            col: Column index
            
        Returns:
            Float value or 0.0 if invalid
        """
        try:
            value = df.iloc[row, col]
            if pd.isna(value) or value == '':
                return 0.0
            return float(value)
        except (ValueError, TypeError, IndexError):
            return 0.0

    def _extract_research_topics(self, df: pd.DataFrame, in_range_columns: List[int]) -> Dict[str, Dict[str, float]]:
        """
        Extract research topic hours for each date.
        
        Args:
            df: Pandas dataframe from CSV
            in_range_columns: List of column indices to process
            
        Returns:
            Dictionary mapping date strings to topic hours:
            {
                '01-01-2025': {
                    'Topic A': 2.0,
                    'Topic B': 1.5,
                    ...
                },
                ...
            }
        """
        daily_topics = {}
        
        for col_idx in in_range_columns:
            date_str = self._parse_date_from_column(df, col_idx)
            if not date_str:
                continue
            
            if date_str not in daily_topics:
                daily_topics[date_str] = {}
            
            for topic_idx, topic_name in enumerate(self.research_topics):
                row_idx = CSVConfig.TOPICS_START_ROW + topic_idx
                
                if row_idx >= df.shape[0] or col_idx >= df.shape[1]:
                    continue
                
                hours_val = self._extract_cell_value(df, row_idx, col_idx)
                
                if hours_val > 0:
                    if topic_name not in daily_topics[date_str]:
                        daily_topics[date_str][topic_name] = 0.0
                    daily_topics[date_str][topic_name] += hours_val
        
        return daily_topics
    
    def _populate_employee_data(self, employee: 'EmployeeModel', 
                                daily_hours_dict: Dict[str, Dict[str, float]],
                                daily_topics_dict: Dict[str, Dict[str, float]]):
        """
        Populate an employee model with extracted data.
        
        Args:
            employee: EmployeeModel to populate
            daily_hours_dict: Dictionary of date -> hours data
            daily_topics_dict: Dictionary of date -> topic hours
        """
        for date_str, hours_data in daily_hours_dict.items():
            employee.add_daily_research_hours(date_str, hours_data["research_hours"])
            employee.add_daily_meeting_hours(date_str, hours_data["meeting_hours"])
            employee.add_daily_nonRnD_hours(date_str, hours_data["nonRnD_hours"])
        
        for date_str, topics_map in daily_topics_dict.items():
            for topic, hrs in topics_map.items():
                employee.add_daily_research_topic_hours(date_str, topic, hrs)


class EmployeeModel:
    """
    Model representing an employee with their work hours and salary information.
    
    Stores day-specific data for research hours, meeting hours, non-R&D hours,
    research topic allocations, and salary levels. Uses sparse storage to minimize
    memory usage for large date ranges.
    """
    
    def __init__(self, name: str):
        """
        Initialize an employee model.
        
        Args:
            name: Employee name
        """
        self.employee_name = name
        
        self.research_hours = defaultdict(float)
        self.meeting_hours = defaultdict(float)
        self.nonRnD_hours = defaultdict(float)
        self.research_topics = defaultdict(lambda: defaultdict(float))
        self.salary_levels = defaultdict(dict)
    
    def add_daily_research_hours(self, date: str, hours: float):
        """
        Add research hours for a specific day.
        
        Args:
            date: Date string in internal format
            hours: Hours to add
        """
        self.research_hours[date] += hours
    
    def add_daily_meeting_hours(self, date: str, hours: float):
        """
        Add meeting hours for a specific day.
        
        Args:
            date: Date string in internal format
            hours: Hours to add
        """
        self.meeting_hours[date] += hours
    
    def add_daily_nonRnD_hours(self, date: str, hours: float):
        """
        Add non-R&D hours for a specific day.
        
        Args:
            date: Date string in internal format
            hours: Hours to add
        """
        self.nonRnD_hours[date] += hours
    
    def add_daily_research_topic_hours(self, date: str, topic: str, hours: float):
        """
        Add hours for a specific research topic on a specific day.
        
        Args:
            date: Date string in internal format
            topic: Research topic name
            hours: Hours to add
        """
        self.research_topics[date][topic] += hours
    
    def set_salary_level_for_date(self, date: str, level: str, amount: float):
        """
        Set the salary level and amount for a specific day.
        
        Args:
            date: Date string in internal format
            level: Salary level label
            amount: Salary amount
        """
        self.salary_levels[date] = {"level": level, "amount": amount}
    
    def get_daily_summary(self, date: str) -> Dict[str, Any]:
        """
        Retrieve a summary of activities for a specific day.
        
        Args:
            date: Date string in internal format
            
        Returns:
            Dictionary containing all data for the specified day
        """
        return {
            "research_hours": self.research_hours[date],
            "meeting_hours": self.meeting_hours[date],
            "nonRnD_hours": self.nonRnD_hours[date],
            "research_topics": dict(self.research_topics[date]),
            "salary_level": self.salary_levels.get(date, {}),
        }
    
    def compress_sparse_data(self):
        """
        Compress sparse data by removing zero values to reduce memory usage.
        
        Useful when saving state or working with large date ranges where most
        days have zero hours.
        """
        self.research_hours = DataCompressor.compress_daily_data(dict(self.research_hours))
        self.meeting_hours = DataCompressor.compress_daily_data(dict(self.meeting_hours))
        self.nonRnD_hours = DataCompressor.compress_daily_data(dict(self.nonRnD_hours))
        self.research_topics = DataCompressor.compress_topics(dict(self.research_topics))
    
    def __repr__(self):
        return f"EmployeeModel(name={self.employee_name})"


    def get_salary_intervals(self) -> List[Tuple[str, str, str, float]]:
        """
        Get salary intervals by merging consecutive days with same level and amount.
        
        Returns:
            List of tuples (start_date, end_date, level, amount) where each tuple
            represents a continuous period with the same salary configuration.
            Example:
              [
                ("01-01-2025", "01-31-2025", "Senior", 120.0),
                ("02-01-2025", "02-15-2025", "Junior", 90.0)
              ]
        """
        date_parse_results = [(d, DateManager.parse_date(d)) for d in self.salary_levels.keys()]
        date_parse_results.sort(key=lambda x: x[1] if x[1] is not None else datetime.min)
        sorted_dates = [d for d, _ in date_parse_results]
        
        if not sorted_dates:
            return []
        
        intervals = []
        current_start = sorted_dates[0]
        current_info = self.salary_levels[current_start]
        current_level = current_info.get("level")
        current_amount = current_info.get("amount")
        previous_day = current_start
        
        for i in range(1, len(sorted_dates)):
            d_str = sorted_dates[i]
            day_info = self.salary_levels[d_str]
            day_level = day_info.get("level")
            day_amount = day_info.get("amount")
            
            if (not DateManager.is_consecutive(previous_day, d_str) or
                day_level != current_level or
                day_amount != current_amount):
                
                intervals.append((current_start, previous_day, current_level, current_amount))
                current_start = d_str
                current_level = day_level
                current_amount = day_amount
            
            previous_day = d_str
        
        intervals.append((current_start, previous_day, current_level, current_amount))
        return intervals
    
    def remove_salary_interval(self, start_date: str, end_date: str):
        """
        Remove salary levels for all dates in the specified range (inclusive).
        
        Args:
            start_date: Start date string in internal format
            end_date: End date string in internal format
        """
        date_list = DateManager.generate_date_list(start_date, end_date)
        for day_str in date_list:
            if day_str in self.salary_levels:
                del self.salary_levels[day_str]

class ProjectModel:
    """
    Model representing a research project with funding and cost information.
    
    Stores project details including funding targets, overhead rates, matching funds,
    research topics, and visualization properties.
    """
    
    def __init__(self, name: str = "", funding_agency: str = "", 
                 grant_min: float = 0, grant_max: float = 0, grant_contractual: float = 0,
                 funding_start: str = "", funding_end: str = "", 
                 currency: str = "Euros", exchange_rate: float = 0,
                 report_type: str = "Annual", 
                 matching_fund_type: str = "Percentage", matching_fund_value: float = 0,
                 operational_overhead: float = 0, 
                 travel_cost: float = 0, equipment_cost: float = 0, other_cost: float = 0, 
                 nonrnd_percentage: float = 0, previous_spending: float = 0.0):
        """
        Initialize a project model.
        
        Args:
            name: Project name
            funding_agency: Name of funding agency
            grant_min: Minimum grant amount
            grant_max: Maximum grant amount
            grant_contractual: Contractual grant amount (target)
            funding_start: Start date of funding period
            funding_end: End date of funding period
            currency: Currency type
            exchange_rate: Exchange rate if applicable
            report_type: Type of reporting (Annual, Quarterly, etc.)
            matching_fund_type: Type of matching fund (Percentage or Absolute)
            matching_fund_value: Value of matching fund
            operational_overhead: Operational overhead rate (as decimal, e.g., 0.25 for 25%)
            travel_cost: Travel costs
            equipment_cost: Equipment costs
            other_cost: Other costs
            nonrnd_percentage: Minimum non-R&D percentage (as decimal)
            previous_spending: Amount already spent in earlier periods
        """
        self.id = None
        self.name = name
        self.funding_agency = funding_agency
        self.grant_min = grant_min
        self.grant_max = grant_max
        self.grant_contractual = grant_contractual
        self.funding_start = funding_start
        self.funding_end = funding_end
        self.currency = currency
        self.exchange_rate = exchange_rate
        self.report_type = report_type
        self.matching_fund_type = matching_fund_type
        self.matching_fund_value = matching_fund_value
        self.operational_overhead = operational_overhead
        self.travel_cost = travel_cost
        self.equipment_cost = equipment_cost
        self.other_cost = other_cost
        self.nonrnd_percentage = nonrnd_percentage
        self.previous_spending = previous_spending
        self.color = None
        self.research_topics = []
        self.allowed_topics = []
    
    def add_research_topic(self, topic_name: str):
        """
        Add a research topic to the project's list.
        
        Args:
            topic_name: Name of research topic to add
        """
        if topic_name not in self.research_topics:
            self.research_topics.append(topic_name)
            self.allowed_topics.append(topic_name)
    
    def remove_research_topic(self, topic_name: str):
        """
        Remove a research topic from the project's list.
        
        Args:
            topic_name: Name of research topic to remove
        """
        if topic_name in self.research_topics:
            self.research_topics.remove(topic_name)
        if topic_name in self.allowed_topics:
            self.allowed_topics.remove(topic_name)
    
    def set_research_topics(self, topics: List[str]):
        """
        Set the list of research topics for this project.
        
        Args:
            topics: List of research topic names
        """
        self.research_topics = topics.copy()
        self.allowed_topics = topics.copy()
    
    def __repr__(self):
        return f"ProjectModel(name={self.name}, agency={self.funding_agency})"
