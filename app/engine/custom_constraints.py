from abc import ABC, abstractmethod
from typing import Dict, List
from app.models.entities import Task, Assignment


class SoftConstraint(ABC):
    """
    Abstract base class for custom soft constraints.
    Extend this to add domain-specific soft constraints.
    """

    def __init__(self, weight: float = 1.0):
        self.weight = weight

    @abstractmethod
    def evaluate(self, task: Task, assignment: Assignment) -> float:
        """
        Evaluate constraint violation penalty.
        Returns 0.0 if satisfied, positive float otherwise.
        """
        pass


class PreferredWindowConstraint(SoftConstraint):
    """Default: task should be within preferred time windows."""

    def evaluate(self, task: Task, assignment: Assignment) -> float:
        if not task.preferred_windows:
            return 0.0
        for win_start, win_end in task.preferred_windows:
            if assignment.start >= win_start and assignment.end <= win_end:
                return 0.0
        return self.weight


class FairnessConstraint(SoftConstraint):
    """
    Penalize uneven distribution of tasks across resources.
    Use in schedule-level scoring.
    """

    def evaluate_schedule(self, assignments: Dict[str, Assignment], tasks: Dict[str, Task]) -> float:
        """Compute fairness penalty across all assignments."""
        resource_usage: Dict[str, int] = {}
        for assign in assignments.values():
            for r_id in assign.resource_ids:
                resource_usage[r_id] = resource_usage.get(r_id, 0) + 1
        
        if not resource_usage:
            return 0.0
        
        usage_values = list(resource_usage.values())
        mean_usage = sum(usage_values) / len(usage_values)
        variance = sum((u - mean_usage) ** 2 for u in usage_values) / len(usage_values)
        return self.weight * variance


class MinimizeGapsConstraint(SoftConstraint):
    """
    Penalize large gaps between consecutive tasks on same resource.
    Encourages compact schedules.
    """

    def evaluate_schedule(self, assignments: Dict[str, Assignment], tasks: Dict[str, Task]) -> float:
        """Compute gap penalty across schedule."""
        resource_assignments: Dict[str, List[Assignment]] = {}
        for assign in assignments.values():
            for r_id in assign.resource_ids:
                if r_id not in resource_assignments:
                    resource_assignments[r_id] = []
                resource_assignments[r_id].append(assign)
        
        total_penalty = 0.0
        for r_id, assigns in resource_assignments.items():
            # Sort by start time
            sorted_assigns = sorted(assigns, key=lambda a: a.start)
            for i in range(len(sorted_assigns) - 1):
                gap = sorted_assigns[i + 1].start - sorted_assigns[i].end
                if gap > 60:  # Penalty for gaps > 1 hour
                    total_penalty += self.weight * (gap - 60) / 60
        
        return total_penalty


class ConstraintRegistry:
    """
    Registry for pluggable soft constraints.
    Allows users to register custom constraints dynamically.
    """

    def __init__(self):
        self.task_constraints: List[SoftConstraint] = []
        self.schedule_constraints: List[SoftConstraint] = []

    def register_task_constraint(self, constraint: SoftConstraint):
        """Register constraint evaluated per-task."""
        self.task_constraints.append(constraint)

    def register_schedule_constraint(self, constraint: SoftConstraint):
        """Register constraint evaluated on full schedule."""
        self.schedule_constraints.append(constraint)

    def evaluate_task(self, task: Task, assignment: Assignment) -> float:
        """Evaluate all task-level constraints."""
        return sum(c.evaluate(task, assignment) for c in self.task_constraints)

    def evaluate_schedule(self, assignments: Dict[str, Assignment], tasks: Dict[str, Task]) -> float:
        """Evaluate all schedule-level constraints."""
        penalty = sum(
            c.evaluate_schedule(assignments, tasks)
            for c in self.schedule_constraints
        )
        # Add per-task penalties
        for tid, assign in assignments.items():
            penalty += self.evaluate_task(tasks[tid], assign)
        return penalty
