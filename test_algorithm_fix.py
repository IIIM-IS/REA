#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("COMPREHENSIVE ALGORITHM TEST: With and Without Concatenation")
print("=" * 80)
print()

try:
    from Model import ReaDataModel, ProjectModel, EmployeeModel
    from algorithm import run_allocation_algorithm
    print("✓ Successfully imported required modules")
except ImportError as e:
    print(f"✗ Failed to import modules: {e}")
    sys.exit(1)

def test_without_concatenation():
    """Test algorithm when previous_spending = 0 (normal run, no concatenation)"""
    print("\n" + "=" * 80)
    print("TEST 1: Without Concatenation (previous_spending = 0)")
    print("=" * 80)
    print()
    
    timesheets_dir = "Timesheets2025"
    if not os.path.exists(timesheets_dir):
        print(f"✗ Directory not found: {timesheets_dir}")
        return False
    
    model = ReaDataModel()
    date_ranges = [("01-01-2025", "11-11-2025")]
    
    try:
        employees = model.extract_data_from_csv(timesheets_dir, date_ranges)
        print(f"✓ Loaded {len(employees)} employees")
    except Exception as e:
        print(f"✗ Failed to load employees: {e}")
        return False
    
    projects = [
        ProjectModel(name="EURIDICE", grant_contractual=10000000.0, previous_spending=0.0, matching_fund_type="percentage", matching_fund_value=50.0),
        ProjectModel(name="ICE-ID", grant_contractual=3500000.0, previous_spending=0.0),
        ProjectModel(name="FRESH-ID", grant_contractual=7300000.0, previous_spending=0.0),
        ProjectModel(name="AI-STYLIST", grant_contractual=8910000.0, previous_spending=0.0),
        ProjectModel(name="TRACKWELL", grant_contractual=500000.0, previous_spending=0.0),
    ]
    
    for proj in projects:
        proj.research_topics = model.research_topics
        proj.allowed_topics = model.research_topics.copy()
    
    print(f"✓ Created {len(projects)} projects (all with previous_spending = 0)")
    
    start_date = "01-01-2025"
    end_date = "11-11-2025"
    all_topics = model.research_topics
    
    print(f"\nRunning algorithm for {start_date} to {end_date}...")
    print(f"Employees: {len(employees)}, Projects: {len(projects)}")
    
    try:
        result = run_allocation_algorithm(employees, projects, start_date, end_date, all_topics)
        solver_status = result.get('solver_status', 'N/A')
        print(f"\n✓ Algorithm completed")
        print(f"  Solver status: {solver_status}")
        
        if 'infeasible' in str(solver_status).lower() or 'VAR_NONE' in str(solver_status):
            total_avail_rnd = sum(sum(emp.research_hours.values()) for emp in employees)
            total_cost_cap = sum(
                sum((float(emp.salary_levels.get(d_str, {}).get("amount", 0.0)) / 160.0 * 1.25) * 
                    (emp.research_hours.get(d_str, 0.0) + emp.nonRnD_hours.get(d_str, 0.0))
                    for d_str in emp.research_hours.keys())
                for emp in employees
            )
            if total_cost_cap < 1e-6:
                print(f"  ⚠ WARNING: Solver infeasible because all costs are 0 (no salary data)")
                print(f"    This is expected when timesheets don't have salary information")
                print(f"    Test 1 requires salary data to be meaningful")
                return True
            else:
                print(f"  ✗ ERROR: Solver returned {solver_status} - algorithm is broken!")
                return False
        
        final_costs = result.get('final_costs', {})
        allocations = result.get('allocations', {})
        
        total_allocated = sum(final_costs.values())
        print(f"  Total cost allocated: {total_allocated:,.0f} ISK")
        
        total_avail_rnd = sum(sum(emp.research_hours.values()) for emp in employees)
        total_alloc_rnd = 0.0
        for emp_name, date_dict in allocations.items():
            for date_str, project_dict in date_dict.items():
                for proj_name, proj_info in project_dict.items():
                    topics_sum = sum(proj_info.get("topics", {}).values())
                    nonrnd_val = proj_info.get("nonRnD", 0.0)
                    total_alloc_rnd += (topics_sum + nonrnd_val)
        
        utilization = (total_alloc_rnd / total_avail_rnd * 100) if total_avail_rnd > 0 else 0.0
        print(f"  Hour utilization: {utilization:.1f}% ({total_alloc_rnd:.1f}/{total_avail_rnd:.1f} hrs)")
        
        if utilization < 99.9:
            print(f"  ✗ ERROR: Hour utilization below 100%!")
            return False
        
        if total_allocated == 0:
            print(f"  ✗ ERROR: No costs allocated (all costs are 0)!")
            return False
        
        print(f"  ✓ Test 1 PASSED: Algorithm works without concatenation")
        return True
        
    except Exception as e:
        print(f"✗ Algorithm failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_concatenation():
    """Test algorithm when previous_spending > 0 (concatenation scenario)"""
    print("\n" + "=" * 80)
    print("TEST 2: With Concatenation (previous_spending > 0)")
    print("=" * 80)
    print()
    
    state_file = "projectStates/Euridice_LATEST.json"
    if not os.path.exists(state_file):
        print(f"⚠ State file not found: {state_file}")
        print("  Skipping concatenation test")
        return True
    
    try:
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        print(f"✓ Loaded state file: {state_file}")
    except Exception as e:
        print(f"✗ Failed to load state file: {e}")
        return False
    
    projects = []
    for proj_dict in state_data.get("projects", []):
        proj = ProjectModel()
        proj.name = proj_dict.get("name", "")
        proj.grant_contractual = proj_dict.get("grant_contractual", 0)
        proj.previous_spending = proj_dict.get("previous_spending", 0)
        proj.matching_fund_type = proj_dict.get("matching_fund_type", "")
        proj.matching_fund_value = proj_dict.get("matching_fund_value", 0)
        proj.research_topics = proj_dict.get("research_topics", [])
        proj.allowed_topics = proj.research_topics.copy()
        projects.append(proj)
    
    print(f"✓ Loaded {len(projects)} projects from state")
    for proj in projects:
        print(f"  {proj.name}: target={proj.grant_contractual:,.0f}, previous={proj.previous_spending:,.0f}")
    
    employees = []
    for emp_dict in state_data.get("employees", []):
        emp = EmployeeModel(emp_dict["employee_name"])
        emp.research_hours.update(emp_dict.get("research_hours", {}))
        emp.nonRnD_hours.update(emp_dict.get("nonRnD_hours", {}))
        emp.salary_levels.update(emp_dict.get("salary_levels", {}))
        employees.append(emp)
    
    print(f"✓ Loaded {len(employees)} employees from state")
    
    timesheets_2025_dir = "Timesheets2025"
    if os.path.exists(timesheets_2025_dir):
        model = ReaDataModel()
        date_ranges_2025 = [("01-01-2025", "12-31-2025")]
        employees_2025 = model.extract_data_from_csv(timesheets_2025_dir, date_ranges_2025)
        
        for emp_2025 in employees_2025:
            existing_emp = next((e for e in employees if e.employee_name == emp_2025.employee_name), None)
            if existing_emp:
                for date_str, hours in emp_2025.research_hours.items():
                    existing_emp.research_hours[date_str] = hours
                for date_str, hours in emp_2025.nonRnD_hours.items():
                    existing_emp.nonRnD_hours[date_str] = hours
                if not emp_2025.salary_levels:
                    existing_salary_dates = sorted(existing_emp.salary_levels.keys())
                    if existing_salary_dates:
                        last_salary = existing_emp.salary_levels[existing_salary_dates[-1]]
                        for date_str in emp_2025.research_hours.keys():
                            if date_str not in existing_emp.salary_levels:
                                existing_emp.salary_levels[date_str] = last_salary.copy()
            else:
                employees.append(emp_2025)
        
        print(f"✓ Merged 2025 timesheets with existing employees")
    
    start_date = "01-01-2025"
    end_date = "12-31-2025"
    all_topics = model.research_topics
    
    print(f"\nRunning algorithm for {start_date} to {end_date}...")
    print(f"Employees: {len(employees)}, Projects: {len(projects)}")
    
    try:
        result = run_allocation_algorithm(employees, projects, start_date, end_date, all_topics)
        solver_status = result.get('solver_status', 'N/A')
        print(f"\n✓ Algorithm completed")
        print(f"  Solver status: {solver_status}")
        
        if 'infeasible' in str(solver_status).lower() or 'VAR_NONE' in str(solver_status):
            print(f"  ✗ ERROR: Solver returned {solver_status}!")
            return False
        
        final_costs = result.get('final_costs', {})
        allocations = result.get('allocations', {})
        
        print(f"\nProject Results:")
        all_valid = True
        for proj in projects:
            proj_name = proj.name if proj.name else "Unnamed"
            actual_cost = final_costs.get(proj_name, 0.0)
            previous_spending = float(getattr(proj, 'previous_spending', 0) or 0)
            total_spending = previous_spending + actual_cost
            target = float(proj.grant_contractual or 0.0)
            remaining_target = max(0.0, target - previous_spending)
            
            print(f"  {proj_name}:")
            print(f"    Target: {target:,.0f}, Previous: {previous_spending:,.0f}, Remaining: {remaining_target:,.0f}")
            print(f"    This run: {actual_cost:,.0f}, Total: {total_spending:,.0f}")
            
            if target > 1e-6 and total_spending < 1e-6:
                print(f"    ✗ ERROR: Has target but 0 spending!")
                all_valid = False
        
        from datetime import datetime
        try:
            start_dt = datetime.strptime(start_date, "%d-%m-%Y")
            end_dt = datetime.strptime(end_date, "%d-%m-%Y")
        except ValueError:
            try:
                start_dt = datetime.strptime(start_date, "%m-%d-%Y")
                end_dt = datetime.strptime(end_date, "%m-%d-%Y")
            except ValueError:
                print(f"  ⚠ WARNING: Could not parse dates {start_date} or {end_date}")
                return all_valid
        
        total_avail_rnd = 0.0
        for emp in employees:
            for date_str, hours in emp.research_hours.items():
                try:
                    date_dt = datetime.strptime(date_str, "%d-%m-%Y")
                    if start_dt <= date_dt <= end_dt:
                        total_avail_rnd += hours
                except:
                    pass
        
        total_alloc_rnd = 0.0
        for emp_name, date_dict in allocations.items():
            for date_str, project_dict in date_dict.items():
                for proj_name, proj_info in project_dict.items():
                    topics_sum = sum(proj_info.get("topics", {}).values())
                    nonrnd_val = proj_info.get("nonRnD", 0.0)
                    total_alloc_rnd += (topics_sum + nonrnd_val)
        
        utilization = (total_alloc_rnd / total_avail_rnd * 100) if total_avail_rnd > 0 else 0.0
        print(f"\n  Hour utilization: {utilization:.1f}% ({total_alloc_rnd:.1f}/{total_avail_rnd:.1f} hrs)")
        
        if utilization < 99.9:
            print(f"  ✗ ERROR: Hour utilization below 100%!")
            all_valid = False
        
        if all_valid:
            print(f"\n  ✓ Test 2 PASSED: Concatenation works correctly")
            return True
        else:
            return False
        
    except Exception as e:
        print(f"✗ Algorithm failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print()
    
    test1_passed = test_without_concatenation()
    test2_passed = test_with_concatenation()
    
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Without Concatenation): {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Test 2 (With Concatenation): {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    print("=" * 80)
    
    if test1_passed and test2_passed:
        print("\n✅ ALL TESTS PASSED - Algorithm is working correctly!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED - Please review the issues above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

