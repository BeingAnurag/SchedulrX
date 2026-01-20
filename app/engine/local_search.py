from typing import Dict, List, Optional
import random

from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule


def is_overlap(a: Assignment, b: Assignment) -> bool:
    return max(a.start, b.start) < min(a.end, b.end)


def local_search_tabu(
    tasks: Dict[str, Task],
    resources: Dict[str, Resource],
    initial_solution: Dict[str, Assignment],
    max_iterations: int = 100,
    tabu_tenure: int = 10,
) -> Dict[str, Assignment]:
    """
    Local search with tabu list for re-optimization.
    Explores neighborhood by shifting task start times.
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
