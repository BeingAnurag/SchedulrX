from typing import Dict, List, Optional

from app.engine.solver import backtrack
from app.engine.ortools_solver import solve_with_ortools
from app.engine.local_search import local_search_tabu, partial_reoptimize
from app.models.entities import Assignment, Resource, Task
from app.config.settings import get_settings


settings = get_settings()


def reoptimize(
    tasks: Dict[str, Task],
    resources: Dict[str, Resource],
    existing: Optional[Dict[str, Assignment]] = None,
    changed_task_ids: Optional[List[str]] = None,
    use_local_search: bool = True,
) -> Optional[Dict[str, Assignment]]:
    """
    Re-optimize schedule when constraints change.
    If existing solution provided, uses local search; otherwise fresh solve.
    """
    if existing and use_local_search:
        # Local search from existing solution
        return local_search_tabu(tasks, resources, existing, max_iterations=50)
    
    # Fresh solve: use configured solver
    if settings.solver_type == "ortools":
        return solve_with_ortools(tasks, resources, settings.ortools_time_limit_seconds)
    elif settings.solver_type == "backtracking":
        return backtrack(tasks, resources)
    else:  # "auto"
        # Auto-select based on problem size
        if len(tasks) >= 15:
            return solve_with_ortools(tasks, resources, settings.ortools_time_limit_seconds)
        else:
            return backtrack(tasks, resources)
