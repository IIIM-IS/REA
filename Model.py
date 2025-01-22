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


import pandas as pd
import os
from collections import defaultdict

class ReaDataModel:
    def __init__(self):
        self.research_topics = [
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
        self.employees = [] # List to store EmployeeModel objects
        self.projects = []  # List to hold project objects


        self.names = []
        self.employee_names = []
        self.in_range_columns = []
        self.total_research_hours_list = []
        self.total_meeting_hours_list = []
        self.topics_hours = []
        self.non_zero_topics_with_hours = [] # The list will contain disctionaries for research topics and hours of all employees


    def extract_data_from_csv(self, directory, date_ranges):
        # Identify all CSV files
        csv_files = [f for f in os.listdir(directory) if f.endswith('.csv')]

        # We'll store each employee in a list
        employees_list = []

        for file_name in csv_files:
            file_path = os.path.join(directory, file_name)

            # Read the CSV into a DataFrame
            df = pd.read_csv(file_path, header=None)

            # Extract employee name from the CSV
            # Note: extract_names appends to self.names;
            employee_name = self.extract_names(df)[-1]  # last appended name

            # Get columns in range based on the last date range in date_ranges
            in_range_columns = self.extract_in_range_columns(df, date_ranges)

            # Extract daily research/meeting hours
            daily_hours_dict = self.extract_research_meeting_hours(df, in_range_columns)
            # Example structure:
            # {
            #   '2025-01-01': {
            #       'research_hours': 4.0,
            #       'meeting_hours': 2.5
            #   },
            #   '2025-01-02': {
            #       'research_hours': 5.0,
            #       'meeting_hours': 1.0
            #   },
            #   ...
            # }

            # Extract daily topics
            daily_topics_dict = self.extract_research_topics(df, in_range_columns)
            # Example structure:
            # {
            #   '2025-01-01': {
            #       "Data Processing / Data Mgmt": 2.0,
            #       "Reasoning / Planning": 1.5,
            #   },
            #   '2025-01-02': {
            #       "Visualization / UX": 3.0
            #   },
            #   ...
            # }

            # Create an EmployeeModel for this CSV/employee
            employee = EmployeeModel(employee_name)

            # Fill the employee with per-day data
            for date_str, hours_data in daily_hours_dict.items():
                # Example: hours_data might be {"research_hours": 4.0, "meeting_hours": 2.5}
                employee.add_daily_research_hours(date_str, hours_data["research_hours"])
                employee.add_daily_meeting_hours(date_str, hours_data["meeting_hours"])

            # Next, populate daily research topics
            for date_str, topics_map in daily_topics_dict.items():
                for topic, hrs in topics_map.items():
                    employee.add_daily_research_topic_hours(date_str, topic, hrs)

            # Add the populated EmployeeModel to the list
            employees_list.append(employee)

        return employees_list


    def extract_names(self, df):
        # Get the value at C3 (row index 2, column index 2)
        name = df.iloc[1, 2]  # Row 2 and column 2 in zero-based indexing
        self.names.append(name)
        return self.names

    def extract_in_range_columns(self, df, date_ranges):
        # Ensure there is a valid date range
        if not date_ranges:
            print("No date range has been added yet.")
            return

        # Get the last date range added
        start_date, end_date = date_ranges[-1]

        # Convert the start and end dates to datetime
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)

        # Extract the date row (assume dates are in row 3 of the CSV, zero-indexed as row 2)
        try:
            dates = pd.to_datetime(df.iloc[2, 4:], format='%m/%d/%Y', errors='coerce')  # Parse dates
        except Exception as e:
            print(f"Error processing dates in CSV: {str(e)}")
            return

        # Exclude the dateless columns of .csv files
        if dates is not pd.NaT:
            # Find columns where dates fall within the range
            self.in_range_columns = dates[(dates >= start_date) & (dates <= end_date)].index.tolist()
        #print(f"in_range_columns: {self.in_range_columns}")
        return self.in_range_columns

    def extract_research_meeting_hours(self, df, in_range_columns):
        """
        Returns a dictionary mapping each date (str) to a sub-dictionary with
        'research_hours' and 'meeting_hours'.
        Example:
        {
          '2025-01-01': {
             'research_hours': 4.0,
             'meeting_hours': 3.0
          },
          '2025-01-02': {
             'research_hours': 5.0,
             'meeting_hours': 2.5
          },
          ...
        }
        """

        daily_hours = {}

        for col_index in in_range_columns:
            # Identify the date in row 2 (third row in Excel, zero-based index 2)
            date_val = df.iloc[2, col_index]

            # Convert to a standard string format (YYYY-MM-DD); skip if invalid
            try:
                date_parsed = pd.to_datetime(date_val, errors='coerce')
                if pd.isna(date_parsed):
                    # If we cannot parse the date or it's NaN, skip this column
                    continue
                date_str = date_parsed.strftime("%Y-%m-%d")
            except:
                # If there's an error parsing the date, skip this column
                continue

            # Extract research hours from row 11 (zero-based index 11)
            raw_val_research = df.iloc[11, col_index]
            if pd.isna(raw_val_research) or raw_val_research == '':
                raw_val_research = 0.0
            research_hours = float(raw_val_research)

            # Extract IIIM meeting hours from row 14
            raw_val_meeting_iiim = df.iloc[14, col_index]
            if pd.isna(raw_val_meeting_iiim) or raw_val_meeting_iiim == '':
                raw_val_meeting_iiim = 0.0

            # Extract meeting hours with other companies from row 15
            raw_val_meeting_other = df.iloc[15, col_index]
            if pd.isna(raw_val_meeting_other) or raw_val_meeting_other == '':
                raw_val_meeting_other = 0.0

            # Sum meeting hours for both meeting types
            total_meeting_hours = float(raw_val_meeting_iiim) + float(raw_val_meeting_other)

            # Store the results in our dictionary
            daily_hours[date_str] = {
                'research_hours': research_hours,
                'meeting_hours': total_meeting_hours
            }

        return daily_hours

    def extract_research_topics(self, df, in_range_columns):
        """
        Returns a dictionary of dictionaries:
        {
          'YYYY-MM-DD': {
             'Topic A': 2.0,
             'Topic B': 1.5,
             ...
          },
          'YYYY-MM-DD2': {
             ...
          },
          ...
        }
        """
        daily_topics = {}

        for col_idx in in_range_columns:
            # Identify the date in row 2 (zero-based index: 2)
            date_val = df.iloc[2, col_idx]
            try:
                date_parsed = pd.to_datetime(date_val, errors='coerce')
                if pd.isna(date_parsed):
                    continue  # Skip columns that don't parse to a valid date
                date_str = date_parsed.strftime("%Y-%m-%d")
            except:
                continue

            # Prepare an empty sub-dictionary if this date hasn't been seen yet
            if date_str not in daily_topics:
                daily_topics[date_str] = {}

            #    Loop through the rows corresponding to research topics
            #    In the original code, these were rows 19 to 35 (inclusive)
            #    i.e., 17 topics in total.
            for topic_idx, row_idx in enumerate(range(19, 19 + len(self.research_topics))):
                # Ensure we're within the DataFrame’s row bounds
                if row_idx >= df.shape[0]:
                    continue
                # Ensure col_idx is within column bounds
                if col_idx >= df.shape[1]:
                    continue

                # Extract hours for the topic in the given column
                hours_val = df.iloc[row_idx, col_idx]
                if pd.isna(hours_val) or hours_val == '':
                    hours_val = 0.0

                try:
                    hours_val = float(hours_val)
                except (ValueError, TypeError):
                    hours_val = 0.0

                # If hours are > 0, store them in our daily topics dict
                if hours_val > 0:
                    topic_name = self.research_topics[topic_idx]
                    if topic_name not in daily_topics[date_str]:
                        daily_topics[date_str][topic_name] = 0.0
                    daily_topics[date_str][topic_name] += hours_val

        return daily_topics


class EmployeeModel:
    def __init__(self, name):
        self.employee_name = name

        # Day-specific data for activities
        self.research_hours = defaultdict(float)  # { "2025-01-01": 5.0, "2025-01-02": 4.0 }
        self.meeting_hours = defaultdict(float)  # { "2025-01-01": 2.0, "2025-01-02": 3.0 }
        self.management_hours = defaultdict(float)  # { "2025-01-01": 1.0 }

        # Research topics with hours per day
        self.research_topics = defaultdict(lambda: defaultdict(float))
        # Example: { "2025-01-01": {"Topic A": 3.0, "Topic B": 2.0} }

        # Salary levels with validity for each day
        self.salary_levels = defaultdict(dict)
        # Example: { "2025-01-01": {"level": "Senior", "amount": 120.0} }

    def add_daily_research_hours(self, date, hours):
        """Add research hours for a specific day."""
        self.research_hours[date] += hours

    def add_daily_meeting_hours(self, date, hours):
        """Add meeting hours for a specific day."""
        self.meeting_hours[date] += hours

    def add_daily_management_hours(self, date, hours):
        """Add management hours for a specific day."""
        self.management_hours[date] += hours

    def add_daily_research_topic_hours(self, date, topic, hours):
        """Add hours for a specific research topic on a specific day."""
        self.research_topics[date][topic] += hours

    def set_salary_level_for_date(self, date, level, amount):
        """Set the salary level and amount for a specific day."""
        self.salary_levels[date] = {"level": level, "amount": amount}

    def get_daily_summary(self, date):
        """Retrieve a summary of activities for a specific day."""
        return {
            "research_hours": self.research_hours[date],
            "meeting_hours": self.meeting_hours[date],
            "management_hours": self.management_hours[date],
            "research_topics": dict(self.research_topics[date]),
            "salary_level": self.salary_levels.get(date, {}),
        }

    def __repr__(self):
        """For debugging, show an overview of the employee."""
        return (f"EmployeeModel(name={self.employee_name}, "
                f"research_hours={dict(self.research_hours)}, "
                f"meeting_hours={dict(self.meeting_hours)}, "
                f"management_hours={dict(self.management_hours)}, "
                f"research_topics={dict(self.research_topics)}, "
                f"salary_levels={dict(self.salary_levels)})")


class ProjectModel:
    def __init__(self, name="", funding_agency="", grant_min=0, grant_max=0, grant_contractual=0,
                 funding_start="", funding_end="", currency="Euros", exchange_rate=0,
                 report_type="Annual", matching_fund_type="Percentage", matching_fund_value=0,
                 operational_overhead=0, travel_cost=0, equipment_cost=0, other_cost=0):
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

        # A list of research topics. Initially empty.
        self.research_topics = []

    def add_research_topic(self, topic_name):
        """Add a research topic to the project's list."""
        if topic_name not in self.research_topics:
            self.research_topics.append(topic_name)

    def remove_research_topic(self, topic_name):
        """Remove a research topic from the project's list."""
        if topic_name in self.research_topics:
            self.research_topics.remove(topic_name)

    def __repr__(self):
        return (f"ProjectModel(name={self.name}, funding_agency={self.funding_agency}, "
                f"grant_min={self.grant_min}, grant_max={self.grant_max}, "
                f"grant_contractual={self.grant_contractual}, funding_start={self.funding_start}, "
                f"funding_end={self.funding_end}, currency={self.currency}, "
                f"exchange_rate={self.exchange_rate}, report_type={self.report_type}, "
                f"matching_fund_type={self.matching_fund_type}, matching_fund_value={self.matching_fund_value}, "
                f"operational_overhead={self.operational_overhead}, travel_cost={self.travel_cost}, "
                f"equipment_cost={self.equipment_cost}, other_cost={self.other_cost}, "
                f"research_topics={self.research_topics})")