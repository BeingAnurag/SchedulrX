"""
Example: Extending SchedulrX with custom soft constraints

This example shows how to add domain-specific soft constraints
and use them in your scheduling workflow.
"""

from app.engine.custom_constraints import (
    SoftConstraint,
    ConstraintRegistry,
    FairnessConstraint,
    MinimizeGapsConstraint
)
from app.models.entities import Task, Assignment


# 1. Define a custom soft constraint
class PriorityConstraint(SoftConstraint):
    """
    Penalize if high-priority tasks are scheduled late in the day.
    Example: interviews with senior candidates should be earlier.
    """

    def __init__(self, priority_threshold: int = 8, penalty_per_hour: float = 2.0):
        super().__init__(weight=penalty_per_hour)
        self.priority_threshold = priority_threshold

    def evaluate(self, task: Task, assignment: Assignment) -> float:
        # Assume task has a 'priority' metadata field (extend Task class)
        # For this example, we'll check task ID prefix
        if task.id.startswith("vip-"):
            # Penalize if start > 600 (after 10am in minutes from midnight)
            if assignment.start > 600:
                hours_late = (assignment.start - 600) / 60
                return self.weight * hours_late
        return 0.0


# 2. Create a constraint registry
registry = ConstraintRegistry()

# 3. Register built-in and custom constraints
registry.register_task_constraint(PriorityConstraint(penalty_per_hour=3.0))
registry.register_schedule_constraint(FairnessConstraint(weight=0.5))
registry.register_schedule_constraint(MinimizeGapsConstraint(weight=0.2))


# 4. Use registry in solver
def custom_score_schedule(assignments, tasks, registry):
    """Score schedule using custom constraint registry."""
    return registry.evaluate_schedule(assignments, tasks)


# Example usage in solver integration:
# In solver.py or ortools_solver.py, replace score_schedule
# with custom_score_schedule(assignments, tasks, registry)
