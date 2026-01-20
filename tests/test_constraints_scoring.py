import pytest
from app.models.entities import Task, Resource, Assignment
from app.utils.scoring import score_schedule, soft_penalty
from app.engine.constraint_propagation import ConstraintPropagator


class TestScoring:
    """Unit tests for scoring and soft constraints."""

    def test_no_penalty_in_preferred_window(self):
        """Assignment within preferred window has zero penalty."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"],
            preferred_windows=[(100, 200)]
        )
        assignment = Assignment(
            task_id="task",
            start=120,
            end=150,
            resource_ids=["resource"]
        )
        penalty = soft_penalty(task, assignment)
        assert penalty == 0.0

    def test_penalty_outside_preferred_window(self):
        """Assignment outside preferred window incurs penalty."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"],
            preferred_windows=[(100, 200)]
        )
        assignment = Assignment(
            task_id="task",
            start=300,
            end=330,
            resource_ids=["resource"]
        )
        penalty = soft_penalty(task, assignment)
        assert penalty > 0.0

    def test_no_preferred_windows_zero_penalty(self):
        """Task without preferred windows has zero penalty."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"],
            preferred_windows=None
        )
        assignment = Assignment(
            task_id="task",
            start=500,
            end=530,
            resource_ids=["resource"]
        )
        penalty = soft_penalty(task, assignment)
        assert penalty == 0.0

    def test_schedule_score_sums_penalties(self, complex_scenario):
        """Schedule score is sum of all task penalties."""
        tasks, _ = complex_scenario
        assignments = {
            "interview-1": Assignment("interview-1", 480, 540, ["room-a"]),
            "interview-2": Assignment("interview-2", 600, 630, ["room-a"]),
            "interview-3": Assignment("interview-3", 650, 695, ["room-b"]),
        }
        score = score_schedule(assignments, tasks)
        
        # Should be non-negative
        assert score >= 0.0
        
        # Manual calculation
        expected = (
            soft_penalty(tasks["interview-1"], assignments["interview-1"]) +
            soft_penalty(tasks["interview-2"], assignments["interview-2"]) +
            soft_penalty(tasks["interview-3"], assignments["interview-3"])
        )
        assert score == expected


class TestConstraintPropagation:
    """Unit tests for constraint propagation module."""

    def test_prune_infeasible_violates_time_bounds(self):
        """Propagator removes windows violating time bounds."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"],
            earliest_start=100,
            latest_end=150
        )
        resources = {"resource": Resource(id="resource", capacity=1)}
        propagator = ConstraintPropagator({task.id: task}, resources)
        
        windows = [(0, 50), (100, 120), (200, 300)]
        feasible = propagator.prune_infeasible_values(task.id, windows)
        
        # Only (100, 120) fits within [100, 150]
        assert len(feasible) == 1
        assert (100, 120) in feasible

    def test_prune_violates_availability(self):
        """Propagator removes windows outside resource availability."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"]
        )
        resources = {
            "resource": Resource(
                id="resource",
                capacity=1,
                availability=[(500, 600)]
            )
        }
        propagator = ConstraintPropagator({task.id: task}, resources)
        
        windows = [(400, 450), (500, 530), (600, 700)]
        feasible = propagator.prune_infeasible_values(task.id, windows)
        
        # Only (500, 530) overlaps with [500, 600]
        assert (500, 530) in feasible
        assert (400, 450) not in feasible
        assert (600, 700) not in feasible

    def test_conflict_graph_construction(self, conflicting_tasks, simple_resources):
        """Propagator builds correct conflict graph."""
        propagator = ConstraintPropagator(conflicting_tasks, simple_resources)
        graph = propagator.compute_task_conflicts()
        
        # Both tasks share room-a
        assert "task-2" in graph["task-1"]
        assert "task-1" in graph["task-2"]

    def test_domain_size_estimation(self):
        """Propagator estimates domain sizes reasonably."""
        task = Task(
            id="task",
            duration=30,
            required_resources=["resource"]
        )
        resources = {
            "resource": Resource(
                id="resource",
                capacity=1,
                availability=[(0, 1440)]  # Full day
            )
        }
        propagator = ConstraintPropagator({task.id: task}, resources)
        domain_size = propagator.estimate_domain_size(task.id)
        
        # Should be positive
        assert domain_size > 0
        # Should be roughly (1440 - 30) / 30 slots ≈ 47
        assert 30 < domain_size < 60


class TestConstraintValidation:
    """Test hard constraint enforcement."""

    def test_availability_window_validation(self, simple_resource):
        """Validate assignment respects availability."""
        task = Task(
            id="task",
            duration=60,
            required_resources=["resource-1"]
        )
        resources = {simple_resource.id: simple_resource}
        
        propagator = ConstraintPropagator(
            {task.id: task},
            resources
        )
        
        # Test window within availability
        windows = [(100, 160)]
        result = propagator.prune_infeasible_values(task.id, windows)
        assert len(result) == 1

    def test_time_bound_validation(self):
        """Validate time bound constraints."""
        task = Task(
            id="task",
            duration=60,
            required_resources=["resource"],
            earliest_start=100,
            latest_end=200
        )
        resources = {"resource": Resource(id="resource", capacity=1)}
        propagator = ConstraintPropagator({task.id: task}, resources)
        
        # Window outside bounds
        windows = [(0, 50), (150, 200), (300, 400)]
        result = propagator.prune_infeasible_values(task.id, windows)
        
        # Only (150, 200) is feasible: start >= 100, end <= 200
        assert (150, 200) in result
        assert (0, 50) not in result
        assert (300, 400) not in result
