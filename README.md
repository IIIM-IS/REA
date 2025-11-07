# Research Expenditure Allocation (REA)

A PyQt5-based application for transparent compensation assessment and expenditure allocation. The application optimizes the distribution of employee hours across research projects to meet funding targets while respecting constraints and preferences.

## Overview

REA uses a convex optimization algorithm to allocate employee work hours (R&D and Non-R&D) across multiple research projects. The system ensures that:
- All available hours are fully allocated (no unused capacity)
- Project cost targets are met as closely as possible
- Employee salary levels and hourly rates are properly accounted for
- Research topic restrictions and preferences are respected
- Hour balance constraints are strictly enforced

## Architecture

The application follows a **Model-View-Controller (MVC)** architecture:

### Core Components

- **`Model.py`**: Data models and business logic
  - `ReaDataModel`: Main data model managing employees, projects, and research topics
  - `EmployeeModel`: Stores employee data including daily hours, salary levels, and research topics
  - `ProjectModel`: Stores project configuration including funding targets, overhead rates, and topic restrictions

- **`View.py`**: User interface (PyQt5)
  - `ReaDataView`: Main window with tabbed interface
  - Tabs: INIT (date ranges, timesheet loading, project management), Employees (salary configuration), Diagnostics (results display), and individual project tabs

- **`Control.py`**: Application controller
  - `Controller`: Mediates between Model and View, handles user interactions, coordinates data flow, and manages algorithm execution

- **`algorithm.py`**: Optimization engine
  - Uses CVXPY for convex optimization
  - Implements hour balance constraints, cost target matching, topic restrictions, and allocation smoothing
  - Includes normalization step to ensure exact hour balance
  - Supports multiple solvers (ECOS, SCS, CLARABEL)

### Supporting Modules

- **`config.py`**: Centralized configuration constants
  - Date formats, CSV structure, salary calculation parameters, research topics
  - Application metadata and directory paths

- **`validators.py`**: Input validation
  - Date validation (MM-DD-YYYY format)
  - Numeric validation (salaries, percentages)
  - CSV structure validation

- **`utils.py`**: Utility functions
  - Date management (parsing, consecutive checks, list generation)
  - Salary calculations
  - Data compression for sparse storage
  - State file versioning

- **`logger.py`**: Logging configuration
  - Structured logging to console and file (`allocation_debug.log`)

- **`error_handling.py`**: Error management
  - Custom exception classes
  - User-friendly error dialogs
  - Exception handling decorators

- **`worker_threads.py`**: Background task execution
  - `AlgorithmWorker`: Runs allocation algorithm asynchronously
  - `CSVLoaderWorker`: Loads timesheet data in background
  - `StateLoaderWorker`: Loads saved state files
  - `StateSaverWorker`: Saves application state

## Features

### Data Management
- **Timesheet Import**: Load employee timesheet data from CSV files
  - Supports multiple CSV files per employee (merged automatically)
  - Extracts R&D hours, Non-R&D hours, meeting hours, and research topic allocations
  - Validates date ranges and data structure

- **Project Configuration**: Create and manage research projects
  - Set funding targets (minimum, maximum, contractual)
  - Configure operational overhead rates
  - Define matching fund requirements
  - Specify research topic restrictions (whitelist)
  - Set minimum Non-R&D percentage requirements

- **Employee Management**: Configure employee salary levels
  - Set salary levels over date ranges
  - Edit existing salary intervals
  - View total hours per employee (R&D, Non-R&D, meetings)

### State Persistence
- **Save/Load State**: Preserve work sessions
  - Save complete application state (employees, projects, date ranges, UI settings)
  - Load previous sessions to continue work
  - State files stored in `projectStates/` directory

### Allocation Algorithm
- **Optimization**: Convex optimization using CVXPY
  - Minimizes cost deviation from targets
  - Enforces hour balance constraints (exact allocation of all available hours)
  - Respects research topic restrictions
  - Promotes smooth allocation patterns
  - Handles locked employee allocations (pre-assigned to specific projects)

- **Multiple Solvers**: Automatic fallback between solvers
  - ECOS (primary)
  - SCS (fallback)
  - CLARABEL (fallback)

- **Normalization**: Post-processing step ensures exact hour balance
  - Scales allocations to match available hours exactly
  - Prevents any hour balance violations
  - Maintains proportional distribution

### Results & Diagnostics
- **Diagnostics Tab**: Comprehensive markdown-formatted report
  - Executive summary with allocation status
  - Project cost analysis with target vs. actual comparisons
  - Per-employee allocation details
  - Overall statistics and utilization rates
  - Automatic analysis of results
  - Actionable insights and recommendations
  - Detailed algorithm diagnostics

- **Report Files**: Timestamped diagnostic reports
  - Saved to `reports/` directory
  - Format: `diagnostics_YYYY-MM-DD_HH-MM-SS.txt`
  - Each run creates a new file (no overwrites)
  - Full history preserved for comparison

- **Console Output**: Detailed algorithm execution information
  - Solver status and performance
  - Cost calculations
  - Hour allocations per project and employee
  - Constraint verification

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/IIIM-IS/REA
   cd REA
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Required packages:
   - PyQt5 (GUI framework)
   - pandas (CSV processing)
   - numpy (numerical operations)
   - cvxpy (optimization)
   - markdown (diagnostics rendering)

## Usage

1. **Launch the application:**
   ```bash
   python main.py
   ```

2. **Set date range:**
   - Enter start and end dates in MM-DD-YYYY format
   - Click "Apply dates"

3. **Load timesheet data:**
   - Click "TimeSheet Inputs"
   - Select directory containing CSV timesheet files
   - Employee data is automatically extracted and validated

4. **Configure employees:**
   - Go to "Employees" tab
   - Set salary levels for each employee over date ranges
   - View total hours per employee

5. **Create projects:**
   - Click "Add a New Project"
   - Configure project details:
     - Name and funding agency
     - Grant amounts (min, max, contractual)
     - Operational overhead rate
     - Matching fund requirements
     - Minimum Non-R&D percentage
     - Funding period dates
     - Research topic restrictions (checkboxes)
   - Click "Save Project"

6. **Run allocation algorithm:**
   - Click "Generate Output"
   - Algorithm runs in background (progress shown in console)
   - Results appear in "Diagnostics" tab automatically

7. **Review results:**
   - View formatted diagnostics in Diagnostics tab
   - Check console for detailed output
   - Review timestamped report file in `reports/` directory

8. **Save your work:**
   - Click "Save State" to preserve current session
   - Click "Load State" to restore a previous session

## Directory Structure

```
REA/
├── main.py                 # Application entry point
├── Model.py                # Data models
├── View.py                 # User interface
├── Control.py              # Application controller
├── algorithm.py            # Optimization algorithm
├── config.py               # Configuration constants
├── validators.py           # Input validation
├── utils.py                # Utility functions
├── logger.py               # Logging setup
├── error_handling.py       # Error management
├── worker_threads.py       # Background workers
├── requirements.txt        # Python dependencies
├── projectStates/          # Saved state files
├── reports/                # Timestamped diagnostic reports
├── explanations/           # Documentation files
│   ├── ALGORITHM_IMPLEMENTATION.md  # Technical guide to the algorithm
│   ├── INTERPRETING_RESULTS.md     # How to understand algorithm outputs
│   └── DEBUG_OUTPUT_GUIDE.md       # Debug log explanation
└── Timesheets2024/         # Timesheet CSV files
```

## Configuration

Key configuration is centralized in `config.py`:

- **Date Format**: MM-DD-YYYY (configurable in `DateConfig`)
- **Salary Calculation**: 160 hours/month, 1.25 overhead multiplier
- **Research Topics**: 17 predefined research topics
- **Directories**: `reports/` for diagnostics, `projectStates/` for saved states

## Algorithm Details

The allocation algorithm solves a convex optimization problem with:

**Variables:**
- `X[i,j,p,t]`: R&D hours for employee `i`, day `j`, project `p`, topic `t`
- `Y[i,j,p]`: Non-R&D hours for employee `i`, day `j`, project `p`

**Constraints:**
- Hour balance: Sum of allocations equals available hours (hard constraint)
- Topic restrictions: Only whitelisted topics allowed per project
- Non-negative: All allocations must be non-negative
- Locked allocations: Pre-assigned employees to specific projects

**Objective:**
- Minimize cost deviation from targets (Huber loss)
- Minimize allocation roughness (smoothness)
- Minimize slack variables (matching fund requirements)

**Post-Processing:**
- Normalization: Scale allocations to exactly match available hours
- Rounding: Round to 2 decimal places while preserving sums
- Verification: Check that all constraints are satisfied

For detailed algorithm documentation, see `explanations/ALGORITHM_IMPLEMENTATION.md`.

## Requirements

- **Python**: 3.9 or higher
- **Dependencies**: See `requirements.txt` for complete list
- **Operating System**: Cross-platform (Windows, Linux, macOS)
- **Display**: GUI environment required (X11 on Linux)

## Output Files

- **`reports/diagnostics_*.txt`**: Timestamped diagnostic reports (one per run)
- **`allocation_debug.log`**: Application log file
- **`projectStates/*.json`**: Saved application states

## License

This project is licensed under the MIT License.

## Authors

Arash Sheikhlar and Kristinn Thorisson

---

For detailed explanations of the algorithm, results interpretation, and debug output, see the documentation in the `explanations/` directory.
