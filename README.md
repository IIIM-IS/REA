# Research Expenditure Allocation (REA)

A PyQt5-based application for transparent compensation assessment and expenditure allocation. You can:
- Import timesheets (CSV files),
- Define projects and their funding requirements,
- Run an allocation algorithm to distribute hours to meet project cost targets.

## Features
- **User Interface (PyQt5)**: Interactive GUI to select date ranges, read employee CSVs, and manage projects.
- **Algorithm**: Iterative approach (in `algorithm.py`) to optimize hours per topic to match project funding targets.
- **Data Models**: `EmployeeModel` and `ProjectModel` store per-day data, topics, costs, etc.

## Installation

1. Clone the repository:
REA code repository can be cloned via GitHub for Desktop. In the File menu, click "Clone a Repository". Click the URL tab and enter git clone `https://github.com/IIIM-IS/REA`

2. Install dependencies:
`pip install -r requirements.txt`

## Usage
1. Run the main Python entry point
`python main.py`
3. Select a date range, import timesheets, and create projects.
4. Click "Generate Output" to run the allocation algorithm.
5. View the final project costs and optimized topic hours in the console.

## Requirements
Python 3.9 or higher recommended
See requirements.txt for all dependencies and pinned versions.

## License
This project is licensed under the MIT License




   
