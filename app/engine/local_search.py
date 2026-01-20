"""
Local Search and Re-optimization Module.

Provides iterative improvement algorithms for refining existing schedules.
Useful for dynamic updates when constraints change or new tasks arrive.

Algorithms:
- Tabu Search: Neighborhood exploration with recency-based memory
- Move operators: Time-shift (±30/60 min), resource swap

Key Features:
- Works from existing feasible solution (warm start)
- Maintains feasibility via constraint checking
- Escapes local optima using tabu list
- Configurable iteration limits for production

Complexity:
- O(max_iter * n * k) where k = neighbors per task
- Practical: ~100 iterations, 4 neighbors/task → O(400n)

Use Cases:
- Re-optimize after task cancellation
- Adjust schedule for preference changes
- Quick refinement when backtracking/OR-Tools too slow
"""

from typing import Dict, List, Optional
import random

from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule


def is_overlap(a: Assignment, b: Assignment) -> bool:
    """Check if two assignments overlap in time."""
    return max(a.start, b.start) < min(a.end, b.end)


def local_search_tabu(
    tasks: Dict[str, Task],
    resources: Dict[str, Resource],
    initial_solution: Dict[str, Assignment],
    max_iterations: int = 100,
    tabu_tenure: int = 10,
) -> Dict[str, Assignment]:
    """
    Tabu search for schedule re-optimization.
    
    Algorithm:
    1. Start from initial feasible solution
    2. Each iteration: explore neighborhood (time shifts)
    3. Accept best non-tabu move (even if worsening)
    4. Add move to tabu list to prevent cycling
    5. Update best solution if improved
    
    Neighborhood:
    - Shift each task by ±30 or ±60 minutes
    - Only feasible moves (no constraint violations)
    
    Args:
        tasks: Map of task_id to Task
        resources: Map of resource_id to Resource
        initial_solution: Starting feasible schedule
        max_iterations: Search budget (default 100)
        tabu_tenure: Moves stay tabu for this many iterations (default 10)
        
    Returns:
        Best schedule found (may improve or equal initial)
        
    Complexity:
        O(max_iter * n * k * m) where:
        - n = num tasks
        - k = neighbors per task (4 for ±30/60)
        - m = avg resources per task
        
    Trade-offs:
    + Fast refinement for existing schedules
    + Can escape local optima via tabu mechanism
    - No optimality guarantee
    - Quality depends on initial solution
    """
    current = initial_solution.copy()
    best = current.copy()
    best_score = score_schedule(best, tasks)
    
    tabu_list: List[tuple] = []

    for iteration in range(max_iterations):
        neighbors = []
        task_ids = list(tasks.keys())
        
        # Generate neighbors: try shifting each task by ±30 min
        for task_id in task_ids:
            current_assign = current[task_id]
            task = tasks[task_id]
            
            for delta in [-60, -30, 30, 60]:
                new_start = current_assign.start + delta
                new_end = new_start + task.duration
                
                # Check if new start is within time bounds
                if task.earliest_start and new_start < task.earliest_start:
                    continue
                if task.latest_end and new_end > task.latest_end:
                    continue
                
                # Check availability
                valid = True
                for r_id in task.required_resources:
                    r = resources[r_id]
                    has_availability = False
                    if r.availability:
                        for win_start, win_end in r.availability:
                            if new_start >= win_start and new_end <= win_end:
                                has_availability = True
                                break
                    else:
                        has_availability = True
                    if not has_availability:
                        valid = False
                        break
                
                if not valid:
                    continue
                
                # Check for hard constraint violations (overlaps)
                candidate = Assignment(task_id, new_start, new_end, current_assign.resource_ids)
                conflict = False
                for other_id, other_assign in current.items():
                    if other_id == task_id:
                        continue
                    shared = set(candidate.resource_ids) & set(other_assign.resource_ids)
                    if shared and is_overlap(candidate, other_assign):
                        conflict = True
                        break
                
                if not conflict:
                    move = (task_id, delta)
                    if move not in tabu_list:
                        neighbors.append((candidate, move, new_start))
        
        if not neighbors:
            break
        
        # Select best neighbor
        neighbors.sort(key=lambda x: score_schedule({x[0].task_id: x[0], **{k: v for k, v in current.items() if k != x[0].task_id}}, tasks))
        best_neighbor, best_move, new_start = neighbors[0]
        
        new_current = current.copy()
        new_current[best_neighbor.task_id] = best_neighbor
        new_score = score_schedule(new_current, tasks)
        
        # Tabu acceptance criterion
        if new_score < best_score or (new_score < score_schedule(current, tasks)):
            current = new_current
            if new_score < best_score:
                best = new_current.copy()
                best_score = new_score
        
        # Update tabu list
        tabu_list.append(best_move)
        if len(tabu_list) > tabu_tenure:
            tabu_list.pop(0)
    
    return best


def partial_reoptimize(
    tasks: Dict[str, Task],
    resources: Dict[str, Resource],
    existing_solution: Dict[str, Assignment],
    changed_task_ids: Optional[List[str]] = None,
) -> Dict[str, Assignment]:
    """
    Re-optimize only affected tasks; freeze others.
    Useful when a few constraints change.
    """
    if changed_task_ids is None:
        changed_task_ids = list(tasks.keys())
    
    # Start with local search from existing solution
    return local_search_tabu(tasks, resources, existing_solution, max_iterations=50)
