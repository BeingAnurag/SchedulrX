from typing import Dict

from app.models.entities import Assignment, Task


def soft_penalty(task: Task, assignment: Assignment) -> float:
    if not task.preferred_windows:
        return 0.0
    for win_start, win_end in task.preferred_windows:
        if assignment.start >= win_start and assignment.end <= win_end:
            return 0.0
    return 1.0


def score_schedule(assignments: Dict[str, Assignment], tasks: Dict[str, Task]) -> float:
    return sum(soft_penalty(tasks[tid], a) for tid, a in assignments.items())
