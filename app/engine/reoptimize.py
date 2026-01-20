from typing import Dict, List, Optional

from app.engine.solver import backtrack
from app.models.entities import Assignment, Resource, Task


def reoptimize(
    tasks: Dict[str, Task],
    resources: Dict[str, Resource],
    existing: Optional[Dict[str, Assignment]] = None,
) -> Optional[Dict[str, Assignment]]:
    # Simple approach: restart backtracking; future: seed with existing for local search.
    return backtrack(tasks, resources)
