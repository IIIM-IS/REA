#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Model import ReaDataModel, ProjectModel, EmployeeModel
from algorithm import run_allocation_algorithm
from Control import Controller

def create_test_directories():
    """Create separate directories for test outputs."""
    test_reports_dir = Path("test_reports")
    test_states_dir = Path("test_projectStates")
    test_reports_dir.mkdir(exist_ok=True)
    test_states_dir.mkdir(exist_ok=True)
    return test_reports_dir, test_states_dir

def load_from_state(state_file="projectStates/Euridice_LATEST.json"):
    """Load employees and projects from a state file."""
    if not os.path.exists(state_file):
        print(f"⚠ State file not found: {state_file}")
        return None, None
    
    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        employees = []
        for emp_dict in state_data.get("employees", []):
            emp = EmployeeModel(emp_dict["employee_name"])
            emp.research_hours.update(emp_dict.get("research_hours", {}))
            emp.nonRnD_hours.update(emp_dict.get("nonRnD_hours", {}))
            emp.meeting_hours.update(emp_dict.get("meeting_hours", {}))
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
            employees.append(emp)
        
        projects = []
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
            proj.color = proj_dict.get("color", "")
            
            allowed_topics = proj.research_topics.copy() if proj.research_topics else []
            proj.allowed_topics = allowed_topics
            
            projects.append(proj)
        
        print(f"✓ Loaded {len(employees)} employees and {len(projects)} projects from {state_file}")
        return employees, projects
    except Exception as e:
        print(f"⚠ Failed to load from {state_file}: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def load_projects_from_state(state_file="projectStates/Euridice_LATEST.json"):
    """Load projects from a state file (deprecated - use load_from_state instead)."""
    _, projects = load_from_state(state_file)
    return projects

def create_default_projects_2024():
    """Create default projects for 2024 if state file is not available."""
    model = ReaDataModel()
    projects = [
        ProjectModel(
            name="EURIDICE",
            grant_contractual=10000000.0,
            funding_start="01-01-2024",
            funding_end="12-31-2024",
            matching_fund_type="percentage",
            matching_fund_value=50.0,
            nonrnd_percentage=0.92
        ),
        ProjectModel(
            name="ICE-ID",
            grant_contractual=3500000.0,
            funding_start="01-01-2024",
            funding_end="12-31-2024",
            matching_fund_type="absolute",
            matching_fund_value=0.0,
            nonrnd_percentage=0.02
        ),
        ProjectModel(
            name="FRESH-ID",
            grant_contractual=7300000.0,
            funding_start="01-01-2024",
            funding_end="12-31-2024",
            matching_fund_type="absolute",
            matching_fund_value=6650000.0,
            nonrnd_percentage=0.02
        ),
        ProjectModel(
            name="AI-STYLIST",
            grant_contractual=8910000.0,
            funding_start="01-01-2024",
            funding_end="12-31-2024",
            matching_fund_type="absolute",
            matching_fund_value=0.0,
            nonrnd_percentage=0.0
        ),
    ]
    
    for proj in projects:
        proj.research_topics = model.research_topics.copy()
        proj.allowed_topics = model.research_topics.copy()
    
    print(f"✓ Created {len(projects)} default projects for 2024")
    return projects

def load_employees_from_csv(timesheets_dir="Timesheets2024", date_ranges=None):
    """Load employees from CSV timesheet files."""
    if date_ranges is None:
        date_ranges = [("01-01-2024", "12-31-2024")]
    
    if not os.path.exists(timesheets_dir):
        print(f"✗ Timesheets directory not found: {timesheets_dir}")
        return None
    
    model = ReaDataModel()
    try:
        employees = model.extract_data_from_csv(timesheets_dir, date_ranges)
        print(f"✓ Loaded {len(employees)} employees from {timesheets_dir}")
        return employees
    except Exception as e:
        print(f"✗ Failed to load employees: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_test_state(employees, projects, test_states_dir, filename="test_2024_state.json"):
    """Save test state to separate directory."""
    state_data = {
        "run_comment": "Test run for 2024",
        "date_ranges": [["01-01-2024", "12-31-2024"]],
        "ui_start_date": "01-01-2024",
        "ui_end_date": "12-31-2024",
        "employees": [],
        "projects": []
    }
    
    for emp in employees:
        emp_dict = {
            "employee_name": emp.employee_name,
            "research_hours": dict(emp.research_hours),
            "nonRnD_hours": dict(emp.nonRnD_hours),
            "meeting_hours": dict(emp.meeting_hours),
            "research_topics": {date: dict(topics) for date, topics in emp.research_topics.items()},
            "salary_levels": {date: dict(sal) for date, sal in emp.salary_levels.items()}
        }
        state_data["employees"].append(emp_dict)
    
    for proj in projects:
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
            "research_topics": proj.research_topics,
            "nonrnd_percentage": proj.nonrnd_percentage,
            "color": proj.color
        }
        state_data["projects"].append(proj_dict)
    
    state_file = test_states_dir / filename
    with open(state_file, 'w') as f:
        json.dump(state_data, f, indent=2)
    
    print(f"✓ Saved test state to {state_file}")
    return str(state_file)

def save_test_report(diagnostics, test_reports_dir, filename=None):
    """Save diagnostics report to separate directory."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"test_diagnostics_{timestamp}.txt"
    
    report_file = test_reports_dir / filename
    with open(report_file, 'w') as f:
        f.write(diagnostics)
    
    print(f"✓ Saved test report to {report_file}")
    return str(report_file)

def run_test_2024():
    """Run the algorithm test for 2024."""
    print("=" * 80)
    print("TEST ALGORITHM FOR 2024")
    print("=" * 80)
    print()
    
    test_reports_dir, test_states_dir = create_test_directories()
    
    print("Step 1: Loading employees and projects from state file...")
    state_file = "projectStates/Euridice_LATEST.json"
    employees, projects = load_from_state(state_file)
    
    if not employees or not projects:
        print("✗ Failed to load from state file. Trying alternative approach...")
        print("\n  Loading employees from CSV...")
        employees = load_employees_from_csv("Timesheets2024", [("01-01-2024", "12-31-2024")])
        if not employees:
            print("✗ Failed to load employees. Exiting.")
            return False
        
        print(f"\n  Loading projects...")
        projects = load_projects_from_state(state_file)
        if not projects:
            print("  Creating default projects for 2024...")
            projects = create_default_projects_2024()
    else:
        print(f"  Using employees and projects from {state_file}")
    
    print(f"\nProjects configured:")
    for proj in projects:
        print(f"  - {proj.name}: {proj.grant_contractual:,.0f} ISK")
    
    print(f"\nStep 3: Running allocation algorithm...")
    print(f"  Period: 01-01-2024 to 12-31-2024")
    print(f"  Employees: {len(employees)}")
    print(f"  Projects: {len(projects)}")
    
    model = ReaDataModel()
    all_topics = model.research_topics
    
    try:
        result = run_allocation_algorithm(
            employees, 
            projects, 
            "01-01-2024", 
            "12-31-2024", 
            all_topics,
            initial_costs=None
        )
        
        solver_status = result.get('solver_status', 'N/A')
        final_costs = result.get('final_costs', {})
        allocations = result.get('allocations', {})
        diagnostics_str = result.get('diagnostics', '')
        
        print(f"\n✓ Algorithm completed")
        print(f"  Solver status: {solver_status}")
        print(f"\n  Project Costs:")
        for proj in projects:
            proj_name = proj.name if proj.name else "Unnamed"
            cost = final_costs.get(proj_name, 0.0)
            base_grant = float(proj.grant_contractual or 0.0)
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            overhead_val = float(proj.operational_overhead or 0.0)
            if overhead_val >= 100000.0:
                overhead_amt = overhead_val
            else:
                overhead_amt = 0.0
            total_target = base_grant + match_abs + overhead_amt
            diff_pct = ((cost / total_target - 1) * 100) if total_target > 0 else 0.0
            print(f"    {proj_name}: {cost:,.0f} ISK (target: {total_target:,.0f}, {diff_pct:+.1f}%)")
        
        print(f"\nStep 4: Generating diagnostics report...")
        diagnostics_text = generate_diagnostics(employees, projects, result, "01-01-2024", "12-31-2024", {})
        
        print(f"\nStep 5: Saving results...")
        save_test_report(diagnostics_text, test_reports_dir)
        save_test_state(employees, projects, test_states_dir)
        
        print(f"\n" + "=" * 80)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nResults saved to:")
        print(f"  - Reports: {test_reports_dir}/")
        print(f"  - States: {test_states_dir}/")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Algorithm failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_test_2024_then_2025():
    """Run the algorithm test for 2024, then concatenate with 2025."""
    print("=" * 80)
    print("TEST ALGORITHM: 2024 THEN 2025 (CONCATENATION)")
    print("=" * 80)
    print()
    
    test_reports_dir, test_states_dir = create_test_directories()
    
    # ========== STEP 1: RUN 2024 ==========
    print("=" * 80)
    print("PHASE 1: Running 2024 allocation")
    print("=" * 80)
    print()
    
    print("Step 1: Loading 2024 employees and projects from state file...")
    state_file_2024 = "projectStates/Euridice_LATEST.json"
    employees_2024, projects_2024 = load_from_state(state_file_2024)
    
    if not employees_2024 or not projects_2024:
        print("✗ Failed to load 2024 data. Exiting.")
        return False
    
    print(f"\nStep 2: Running 2024 allocation algorithm...")
    print(f"  Period: 01-01-2024 to 12-31-2024")
    print(f"  Employees: {len(employees_2024)}")
    print(f"  Projects: {len(projects_2024)}")
    
    model = ReaDataModel()
    all_topics = model.research_topics
    
    try:
        result_2024 = run_allocation_algorithm(
            employees_2024, 
            projects_2024, 
            "01-01-2024", 
            "12-31-2024", 
            all_topics,
            initial_costs=None
        )
        
        solver_status_2024 = result_2024.get('solver_status', 'N/A')
        final_costs_2024 = result_2024.get('final_costs', {})
        
        print(f"\n✓ 2024 Algorithm completed")
        print(f"  Solver status: {solver_status_2024}")
        print(f"\n  2024 Project Costs:")
        for proj in projects_2024:
            proj_name = proj.name if proj.name else "Unnamed"
            cost = final_costs_2024.get(proj_name, 0.0)
            base_grant = float(proj.grant_contractual or 0.0)
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            overhead_val = float(proj.operational_overhead or 0.0)
            if overhead_val >= 100000.0:
                overhead_amt = overhead_val
            else:
                overhead_amt = 0.0
            total_target = base_grant + match_abs + overhead_amt
            diff_pct = ((cost / total_target - 1) * 100) if total_target > 0 else 0.0
            print(f"    {proj_name}: {cost:,.0f} ISK (target: {total_target:,.0f}, {diff_pct:+.1f}%)")
        
        print(f"\nStep 3: Saving 2024 results...")
        save_test_state(employees_2024, projects_2024, test_states_dir, "test_2024_state.json")
        
        # Generate 2024 diagnostics
        diagnostics_2024 = generate_diagnostics(employees_2024, projects_2024, result_2024, "01-01-2024", "12-31-2024", {})
        save_test_report(diagnostics_2024, test_reports_dir, "test_2024_diagnostics.txt")
        
    except Exception as e:
        print(f"\n✗ 2024 Algorithm failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========== STEP 2: RUN 2025 WITH CONCATENATION ==========
    print("\n" + "=" * 80)
    print("PHASE 2: Running 2025 allocation (concatenated with 2024)")
    print("=" * 80)
    print()
    
    print("Step 1: Loading 2025 employees and projects from state file...")
    state_file_2025 = "projectStates/nov_2025.json"
    employees_2025, projects_2025 = load_from_state(state_file_2025)
    
    if not employees_2025 or not projects_2025:
        print("✗ Failed to load 2025 data. Exiting.")
        return False
    
    print(f"\nStep 2: Using 2024 costs as initial costs for 2025...")
    initial_costs_2025 = final_costs_2024.copy()
    print(f"  Initial costs from 2024:")
    for proj_name, cost in initial_costs_2025.items():
        print(f"    {proj_name}: {cost:,.0f} ISK")
    
    print(f"\nStep 3: Running 2025 allocation algorithm...")
    date_ranges_2025 = [("01-01-2025", "11-11-2025")]
    start_date_2025 = "01-01-2025"
    end_date_2025 = "11-11-2025"
    
    print(f"  Period: {start_date_2025} to {end_date_2025}")
    print(f"  Employees: {len(employees_2025)}")
    print(f"  Projects: {len(projects_2025)}")
    
    try:
        result_2025 = run_allocation_algorithm(
            employees_2025, 
            projects_2025, 
            start_date_2025, 
            end_date_2025, 
            all_topics,
            initial_costs=initial_costs_2025
        )
        
        solver_status_2025 = result_2025.get('solver_status', 'N/A')
        final_costs_2025 = result_2025.get('final_costs', {})
        
        print(f"\n✓ 2025 Algorithm completed")
        print(f"  Solver status: {solver_status_2025}")
        print(f"\n  2025 Project Costs (Total including 2024):")
        for proj in projects_2025:
            proj_name = proj.name if proj.name else "Unnamed"
            total_cost = final_costs_2025.get(proj_name, 0.0)
            initial_cost = initial_costs_2025.get(proj_name, 0.0)
            new_cost = total_cost - initial_cost
            base_grant = float(proj.grant_contractual or 0.0)
            match_raw = float(proj.matching_fund_value or 0.0)
            mf_type = (proj.matching_fund_type or "").lower()
            if match_raw > 0.0:
                match_abs = (base_grant * match_raw / 100.0) if mf_type == "percentage" else match_raw
            else:
                match_abs = 0.0
            overhead_val = float(proj.operational_overhead or 0.0)
            if overhead_val >= 100000.0:
                overhead_amt = overhead_val
            else:
                overhead_amt = 0.0
            total_target = base_grant + match_abs + overhead_amt
            diff_pct = ((total_cost / total_target - 1) * 100) if total_target > 0 else 0.0
            print(f"    {proj_name}:")
            print(f"      Total: {total_cost:,.0f} ISK (target: {total_target:,.0f}, {diff_pct:+.1f}%)")
            print(f"      From 2024: {initial_cost:,.0f} ISK")
            print(f"      New in 2025: {new_cost:,.0f} ISK")
        
        print(f"\nStep 4: Saving 2025 results...")
        save_test_state(employees_2025, projects_2025, test_states_dir, "test_2025_state.json")
        
        diagnostics_2025 = generate_diagnostics(employees_2025, projects_2025, result_2025, start_date_2025, end_date_2025, initial_costs_2025)
        save_test_report(diagnostics_2025, test_reports_dir, "test_2025_concatenated_diagnostics.txt")
        
        print(f"\n" + "=" * 80)
        print("CONCATENATION TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nResults saved to:")
        print(f"  - Reports: {test_reports_dir}/")
        print(f"  - States: {test_states_dir}/")
        print(f"\n  Files created:")
        print(f"    - test_2024_diagnostics.txt")
        print(f"    - test_2025_concatenated_diagnostics.txt")
        print(f"    - test_2024_state.json")
        print(f"    - test_2025_state.json")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 2025 Algorithm failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_diagnostics(employees, projects, result, start_date, end_date, initial_costs):
    """Generate diagnostics report from algorithm results."""
    from datetime import datetime
    
    allocations = result.get('allocations', {})
    final_costs = result.get('final_costs', {})
    solver_status = result.get('solver_status', 'N/A')
    diagnostics_str = result.get('diagnostics', '')
    
    report_time = datetime.now().strftime("%Y-%m-%d at %H:%M:%S")
    
    diagnostics = []
    diagnostics.append("# 📊 Research Expenditure Allocation - Diagnostics Report\n")
    diagnostics.append(f"**Generated:** {report_time}  \n")
    diagnostics.append(f"**Reporting Period:** {start_date} to {end_date}  \n")
    diagnostics.append(f"**Employees:** {len(employees)}  \n")
    diagnostics.append(f"**Projects:** {len(projects)}  \n")
    is_concatenating = bool(initial_costs)
    if is_concatenating:
        diagnostics.append(f"**Note:** This run concatenates with previous allocations. Actual costs shown include both previous and new allocations, compared against original targets.  \n")
    diagnostics.append("---\n")
    
    overall_rnd_avail = overall_rnd_alloc = 0.0
    overall_nonrnd_avail = overall_nonrnd_alloc = 0.0
    total_cost_allocated = 0.0
    total_cost_target = 0.0
    project_statuses = []
    
    for employee in employees:
        overall_rnd_avail += sum(employee.research_hours.values())
        overall_nonrnd_avail += sum(employee.nonRnD_hours.values())
    
    for emp_name, date_dict in allocations.items():
        for date_str, project_dict in date_dict.items():
            for proj_name, proj_info in project_dict.items():
                rnd_hours = sum(proj_info.get("topics", {}).values())
                nonrnd_hours = proj_info.get("nonRnD", 0.0)
                overall_rnd_alloc += rnd_hours
                overall_nonrnd_alloc += nonrnd_hours
                
                emp_obj = next((e for e in employees if e.employee_name == emp_name), None)
                if emp_obj:
                    sal_info = emp_obj.salary_levels.get(date_str, {})
                    base_salary = float(sal_info.get("amount", 0.0))
                    hourly_rate = (base_salary / 160.0) * 1.25 if base_salary > 0 else 0.0
                    total_cost_allocated += (rnd_hours + nonrnd_hours) * hourly_rate
    
    for proj in projects:
        proj_name = proj.name if proj.name else "Unnamed"
        actual_cost = final_costs.get(proj_name, 0.0)
        try:
            original_target = float(proj.grant_contractual or 0.0)
        except Exception:
            original_target = 0.0
        previous_cost = float(initial_costs.get(proj_name, 0.0))
        residual_target = max(original_target - previous_cost, 0.0)
        total_cost_target += original_target
        
        diff_original = actual_cost - original_target
        diff_pct_original = (diff_original / original_target * 100) if original_target > 0 else 0.0
        
        status = "✅ On Target" if abs(diff_pct_original) < 5.0 else ("⚠️ Over Budget" if diff_pct_original > 0 else "📉 Under Budget")
        project_statuses.append({
            "name": proj_name,
            "actual": actual_cost,
            "original_target": original_target,
            "residual_target": residual_target,
            "previous_cost": previous_cost,
            "diff": diff_original,
            "diff_pct": diff_pct_original,
            "status": status
        })
    
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
    diagnostics.append(f"- **Solver Status:** `{solver_status}`  \n")
    diagnostics.append("\n---\n")
    
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
    diagnostics.append("## 🔧 Algorithm Diagnostics\n\n")
    diagnostics.append("```\n")
    diagnostics.append(diagnostics_str)
    diagnostics.append("\n```\n")
    
    return "".join(diagnostics)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--concatenate":
        success = run_test_2024_then_2025()
    else:
        success = run_test_2024()
    sys.exit(0 if success else 1)

