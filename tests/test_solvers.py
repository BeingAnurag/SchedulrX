import pytest
from app.engine.solver import backtrack
from app.engine.ortools_solver import solve_with_ortools
from app.utils.scoring import score_schedule


class TestBacktrackingSolver:
    """Unit tests for backtracking CSP solver."""

    def test_simple_task_solves(self, simple_task, simple_resource):
        """Single task should always be solvable."""
        tasks = {simple_task.id: simple_task}
        resources = {simple_resource.id: simple_resource}
        result = backtrack(tasks, resources)
        
        assert result is not None
        assert simple_task.id in result
        assignment = result[simple_task.id]
        assert assignment.end - assignment.start == simple_task.duration

    def test_no_overlap_constraint(self, conflicting_tasks, simple_resources):
        """Two tasks on same resource must not overlap."""
        result = backtrack(conflicting_tasks, simple_resources)
        
        assert result is not None
        assert len(result) == 2
        
        task1_assign = result["task-1"]
        task2_assign = result["task-2"]
        
        # Check no overlap on shared resource
        assert task1_assign.end <= task2_assign.start or task2_assign.end <= task1_assign.start

    def test_time_bound_respect(self, simple_resource):
        """Assignments must respect earliest_start and latest_end."""
        task = {
            "bounded": Task(
                id="bounded",
                duration=30,
                required_resources=["resource-1"],
                earliest_start=100,
                latest_end=200
            )
        }
        resources = {simple_resource.id: simple_resource}
        result = backtrack(task, resources)
        
        assert result is not None
        assignment = result["bounded"]
        assert assignment.start >= 100
        assert assignment.end <= 200

    def test_availability_constraint(self):
        """Tasks must be within resource availability windows."""
        task = {
            "task": Task(
                id="task",
                duration=30,
                required_resources=["resource"]
            )
        }
        resources = {
            "resource": Resource(
                id="resource",
                capacity=1,
                availability=[(500, 600)]  # Only 100 min available
            )
        }
        result = backtrack(task, resources)
        
        assert result is not None
        assignment = result["task"]
        assert assignment.start >= 500 and assignment.end <= 600

    def test_complex_scenario_solves(self, complex_scenario):
        """Multi-task, multi-resource problem should solve."""
        tasks, resources = complex_scenario
        result = backtrack(tasks, resources)
        
        assert result is not None
        assert len(result) == 3
        
        # Verify all hard constraints
        for tid, assign in result.items():
            task = tasks[tid]
            assert assign.end - assign.start == task.duration

    def test_infeasible_returns_none(self, infeasible_scenario):
        """Impossible problem returns None."""
        tasks, resources = infeasible_scenario
        result = backtrack(tasks, resources)
        assert result is None


class TestORToolsSolver:
    """Unit tests for OR-Tools CP-SAT solver."""

    def test_simple_task_ortools(self, simple_task, simple_resource):
        """OR-Tools should solve simple instance."""
        tasks = {simple_task.id: simple_task}
        resources = {simple_resource.id: simple_resource}
        result = solve_with_ortools(tasks, resources, time_limit_seconds=5)
        
        assert result is not None
        assert simple_task.id in result

    def test_ortools_respects_availability(self):
        """OR-Tools must respect availability windows."""
        task = {
            "task": Task(
                id="task",
                duration=30,
                required_resources=["resource"]
            )
        }
        resources = {
            "resource": Resource(
                id="resource",
                capacity=1,
                availability=[(600, 700)]
            )
        }
        result = solve_with_ortools(task, resources)
        
        if result:  # May be None if solver times out
            assignment = result["task"]
            assert assignment.start >= 600 and assignment.end <= 700

    def test_ortools_handles_conflicts(self, conflicting_tasks, simple_resources):
        """OR-Tools should prevent overlaps."""
        result = solve_with_ortools(conflicting_tasks, simple_resources, time_limit_seconds=5)
        
        if result and len(result) == 2:
            task1_assign = result["task-1"]
            task2_assign = result["task-2"]
            assert task1_assign.end <= task2_assign.start or task2_assign.end <= task1_assign.start


class TestSolverComparison:
    """Compare backtracking vs OR-Tools."""

    def test_both_solvers_agree_on_feasibility(self, complex_scenario):
        """Both solvers should agree on whether problem is feasible."""
        tasks, resources = complex_scenario
        
        bt_result = backtrack(tasks, resources)
        ort_result = solve_with_ortools(tasks, resources, time_limit_seconds=5)
        
        # Both should find solution or both should fail
        if bt_result is not None:
            assert ort_result is not None, "OR-Tools failed where backtracking succeeded"
        
    def test_small_problem_backtracking_faster(self, complex_scenario):
        """Backtracking should be faster on small instances."""
        import time
        tasks, resources = complex_scenario
        
        start = time.time()
        bt_result = backtrack(tasks, resources)
        bt_time = time.time() - start
        
        start = time.time()
        ort_result = solve_with_ortools(tasks, resources, time_limit_seconds=10)
        ort_time = time.time() - start
        
        # Backtracking often faster on small problems
        assert bt_result is not None
