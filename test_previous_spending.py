import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Model import EmployeeModel, ProjectModel  # noqa: E402
from algorithm import run_allocation_algorithm  # noqa: E402


def test_previous_spending_caps_residual_target():
    """Ensure previous spending is carried into residual targets and costs."""
    emp = EmployeeModel("Alice")
    date_str = "01-01-2025"
    emp.add_daily_research_hours(date_str, 8.0)
    emp.add_daily_nonRnD_hours(date_str, 0.0)
    emp.salary_levels[date_str] = {"level": "L1", "amount": 160000.0}

    project = ProjectModel(
        name="Test",
        grant_contractual=1000.0,
        previous_spending=1000.0,
    )
    project.research_topics = ["Topic"]
    project.allowed_topics = ["Topic"]

    result = run_allocation_algorithm(
        [emp],
        [project],
        date_str,
        date_str,
        ["Topic"],
    )
    final_costs = result["final_costs"]
    allocations = result["allocations"]

    total_allocated_hours = 0.0
    for _, date_dict in allocations.items():
        for _, proj_dict in date_dict.items():
            for _, proj_info in proj_dict.items():
                total_allocated_hours += sum(proj_info.get("topics", {}).values())
                total_allocated_hours += proj_info.get("nonRnD", 0.0)

    assert final_costs["Test"] == pytest.approx(1000.0)
    assert total_allocated_hours == pytest.approx(0.0)

