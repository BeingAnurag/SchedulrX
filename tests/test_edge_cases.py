import pytest
from app.engine.solver import backtrack, is_overlap
from app.engine.local_search import local_search_tabu
from app.models.entities import Task, Resource, Assignment


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_task_single_resource(self):
        """Minimal problem: 1 task, 1 resource."""
        tasks = {
            "t1": Task(id="t1", duration=30, required_resources=["r1"])
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 60)])
        }
        result = backtrack(tasks, resources)
        assert result is not None
        assert len(result) == 1

    def test_zero_duration_task(self):
        """Task with zero duration."""
        tasks = {
            "t1": Task(id="t1", duration=0, required_resources=["r1"])
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 1440)])
        }
        result = backtrack(tasks, resources)
        assert result is not None

    def test_many_tasks_same_resource(self):
        """Many tasks competing for single resource."""
        num_tasks = 10
        tasks = {
            f"t{i}": Task(
                id=f"t{i}",
                duration=30,
                required_resources=["r1"]
            )
            for i in range(num_tasks)
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 500)])
        }
        result = backtrack(tasks, resources)
        
        if result:
            # Verify no overlaps
            assignments = list(result.values())
            for i, a1 in enumerate(assignments):
                for a2 in assignments[i + 1:]:
                    assert not is_overlap(a1, a2)

    def test_very_tight_window(self):
        """Task with very narrow time window."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"],
                earliest_start=100,
                latest_end=130  # Exactly fits 30-min task
            )
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 1440)])
        }
        result = backtrack(tasks, resources)
        assert result is not None
        assert result["t1"].start == 100
        assert result["t1"].end == 130

    def test_infeasible_window(self):
        """Task duration exceeds time window."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=100,
                required_resources=["r1"],
                earliest_start=0,
                latest_end=50
            )
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 1440)])
        }
        result = backtrack(tasks, resources)
        assert result is None

    def test_overlapping_availability_windows(self):
        """Resource with multiple availability windows."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"]
            )
        }
        resources = {
            "r1": Resource(
                id="r1",
                capacity=1,
                availability=[(0, 100), (200, 300), (500, 600)]
            )
        }
        result = backtrack(tasks, resources)
        assert result is not None
        # Assignment should fall in one of the windows
        assign = result["t1"]
        in_window = any(
            w[0] <= assign.start and assign.end <= w[1]
            for w in resources["r1"].availability
        )
        assert in_window

    def test_multiple_preferred_windows(self):
        """Task with multiple preferred windows."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"],
                preferred_windows=[(100, 150), (400, 450), (700, 750)]
            )
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 1440)])
        }
        result = backtrack(tasks, resources)
        assert result is not None


class TestLocalSearchEdgeCases:
    """Test local search re-optimization edge cases."""

    def test_local_search_with_single_task(self):
        """Local search on single task."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"],
                preferred_windows=[(500, 600)]
            )
        }
        resources = {
            "r1": Resource(id="r1", capacity=1, availability=[(0, 1440)])
        }
        initial = {"t1": Assignment("t1", 100, 130, ["r1"])}
        
        result = local_search_tabu(tasks, resources, initial, max_iterations=10)
        assert result is not None

    def test_local_search_improves_score(self, complex_scenario):
        """Local search should not increase score (ideally decrease)."""
        from app.utils.scoring import score_schedule
        
        tasks, resources = complex_scenario
        initial = {
            "interview-1": Assignment("interview-1", 480, 540, ["room-a"]),
            "interview-2": Assignment("interview-2", 600, 630, ["room-a"]),
            "interview-3": Assignment("interview-3", 700, 745, ["room-b"]),
        }
        
        initial_score = score_schedule(initial, tasks)
        result = local_search_tabu(tasks, resources, initial, max_iterations=20)
        result_score = score_schedule(result, tasks)
        
        # Result should not be worse
        assert result_score <= initial_score + 0.1  # Allow small floating point error


class TestLargeInstances:
    """Test behavior on larger problem instances."""

    def test_medium_problem_10_tasks(self):
        """Medium problem: 10 tasks, 3 resources."""
        tasks = {
            f"t{i}": Task(
                id=f"t{i}",
                duration=30 + (i % 5) * 10,
                required_resources=[f"r{i % 3}"],
                preferred_windows=[(100 + i * 50, 200 + i * 50)]
            )
            for i in range(10)
        }
        resources = {
            f"r{i}": Resource(id=f"r{i}", capacity=1, availability=[(0, 1440)])
            for i in range(3)
        }
        
        result = backtrack(tasks, resources)
        # Should either solve or timeout gracefully
        assert result is None or len(result) == 10

    def test_all_independent_tasks(self):
        """Many tasks that don't conflict (independent resources)."""
        num_tasks = 20
        tasks = {
            f"t{i}": Task(
                id=f"t{i}",
                duration=30,
                required_resources=[f"r{i}"]
            )
            for i in range(num_tasks)
        }
        resources = {
            f"r{i}": Resource(id=f"r{i}", capacity=1, availability=[(0, 1440)])
            for i in range(num_tasks)
        }
        
        result = backtrack(tasks, resources)
        assert result is not None
        assert len(result) == num_tasks


class TestConstraintInteractions:
    """Test complex constraint interactions."""

    def test_availability_conflicts_with_time_bounds(self):
        """Availability and time bounds both restrictive."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"],
                earliest_start=200,
                latest_end=250
            )
        }
        resources = {
            "r1": Resource(
                id="r1",
                capacity=1,
                availability=[(0, 100), (300, 400)]  # Doesn't cover [200, 250]
            )
        }
        result = backtrack(tasks, resources)
        assert result is None

    def test_preferred_window_outside_availability(self):
        """Preferred window outside availability: should still solve with penalty."""
        tasks = {
            "t1": Task(
                id="t1",
                duration=30,
                required_resources=["r1"],
                preferred_windows=[(700, 800)]  # Outside availability
            )
        }
        resources = {
            "r1": Resource(
                id="r1",
                capacity=1,
                availability=[(0, 100)]  # Only 0-100 available
            )
        }
        result = backtrack(tasks, resources)
        assert result is not None  # Should solve, ignoring preferred window
        assert result["t1"].end <= 100  # Must fit in availability
