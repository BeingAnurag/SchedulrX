from typing import Dict, Set, List, Tuple

from app.models.entities import Task, Resource


class ConstraintPropagator:
    """
    Implements basic constraint propagation and arc consistency for CSP.
    Prunes infeasible values from domains early.
    """

    def __init__(self, tasks: Dict[str, Task], resources: Dict[str, Resource]):
        self.tasks = tasks
        self.resources = resources

    def prune_infeasible_values(self, task_id: str, candidate_windows: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Remove windows that violate hard constraints."""
        task = self.tasks[task_id]
        feasible = []

        for start, end in candidate_windows:
            # Check time bounds
            if task.earliest_start and start < task.earliest_start:
                continue
            if task.latest_end and end > task.latest_end:
                continue

            # Check availability of required resources
            valid_for_all = True
            for r_id in task.required_resources:
                r = self.resources.get(r_id)
                if not r:
                    valid_for_all = False
                    break

                if not r.availability:
                    continue

                # Check if window overlaps with any availability window
                has_availability = False
                for avail_start, avail_end in r.availability:
                    if start >= avail_start and end <= avail_end:
                        has_availability = True
                        break

                if not has_availability:
                    valid_for_all = False
                    break

            if valid_for_all:
                feasible.append((start, end))

        return feasible

    def compute_task_conflicts(self) -> Dict[str, Set[str]]:
        """Build conflict graph: edges = shared resource usage."""
        graph: Dict[str, Set[str]] = {tid: set() for tid in self.tasks.keys()}

        for i, (tid1, task1) in enumerate(self.tasks.items()):
            for tid2, task2 in list(self.tasks.items())[i + 1:]:
                shared = set(task1.required_resources) & set(task2.required_resources)
                if shared:
                    graph[tid1].add(tid2)
                    graph[tid2].add(tid1)

        return graph

    def estimate_domain_size(self, task_id: str) -> int:
        """Estimate feasible assignment count for a task (heuristic)."""
        task = self.tasks[task_id]
        total_windows = 0

        for r_id in task.required_resources:
            r = self.resources.get(r_id)
            if r and r.availability:
                for start, end in r.availability:
                    # Approximate slots per window (30-min slots)
                    slots = max(0, (end - start - task.duration) // 30)
                    total_windows += slots

        return max(1, total_windows)
