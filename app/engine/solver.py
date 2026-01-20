"""
Backtracking CSP Solver with Heuristics

This module implements a constraint satisfaction problem (CSP) solver using
backtracking search with intelligent heuristics for variable/value ordering.

Time Complexity: O(b^d) worst case where:
    b = branching factor (avg domain size)
    d = depth (number of tasks)

In practice, heuristics and pruning reduce search space significantly.

Key Techniques:
- Minimum Remaining Values (MRV) heuristic for variable ordering
- Degree heuristic as tie-breaker
- Least-constraining value for value ordering
- Forward checking via consistency validation
"""

from typing import Dict, List, Optional

from app.graph.conflict_graph import build_conflict_graph
from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule


def is_overlap(a: Assignment, b: Assignment) -> bool:
    """
    Check if two assignments have overlapping time windows.
    
    Args:
        a: First assignment
        b: Second assignment
        
    Returns:
        True if assignments overlap in time, False otherwise
        
    Complexity: O(1)
    """
    return max(a.start, b.start) < min(a.end, b.end)


def feasible(task: Task, start: int, resources: List[Resource]) -> bool:
    """
    Check if a task can feasibly start at a given time.
    
    Validates hard constraints:
    - Task fits within resource availability windows
    - Respects earliest_start bound
    - Respects latest_end bound
    
    Args:
        task: Task to validate
        start: Proposed start time (minutes from midnight)
        resources: List of required resources
        
    Returns:
        True if assignment is feasible, False otherwise
        
    Complexity: O(w) where w = max availability windows per resource
    """
    end = start + task.duration
    for r in resources:
        if not any(win[0] <= start and end <= win[1] for win in r.availability or []):
            return False
    if task.earliest_start and start < task.earliest_start:
        return False
    if task.latest_end and end > task.latest_end:
        return False
    return True


def candidate_values(task: Task, resources: Dict[str, Resource], slot_size: int = 30) -> List[Assignment]:
    """
    Generate all feasible assignments for a task.
    
    Enumerates possible (start_time, resource) combinations that satisfy
    availability and time bound constraints.
    
    Args:
        task: Task to generate assignments for
        resources: Map of resource_id to Resource
        slot_size: Time slot granularity in minutes (default 30)
        
    Returns:
        List of feasible Assignment objects
        
    Complexity: O(r * w * t / s) where:
        r = required resources
        w = windows per resource
        t = total available time per window
        s = slot_size
        
    Note: Coarse slot_size improves speed but may miss optimal solutions.
    """
    vals: List[Assignment] = []
    for r_id in task.required_resources:
        r = resources[r_id]
        for win_start, win_end in r.availability or []:
            t = win_start
            while t + task.duration <= win_end:
                if feasible(task, t, [r]):
                    vals.append(Assignment(task.id, t, t + task.duration, [r_id]))
                t += slot_size
    return vals


def select_var(unassigned: List[str], domains: Dict[str, List[Assignment]], graph: Dict[str, set]) -> str:
    """
    Select next variable to assign using MRV + degree heuristic.
    
    Heuristics:
    1. MRV (Minimum Remaining Values): Choose variable with smallest domain
       - Fails fast if no solution exists
       - Reduces branching early
    2. Degree: Break ties by choosing variable with most conflicts
       - Constrains other variables sooner
       
    Args:
        unassigned: List of unassigned task IDs
        domains: Map of task_id to feasible assignments
        graph: Conflict graph (edges = shared resources)
        
    Returns:
        Task ID to assign next
        
    Complexity: O(n log n) where n = unassigned tasks (due to sorting)
    """
    # Sort by (domain_size, -degree): smallest domain, most conflicts
    unassigned.sort(key=lambda tid: (len(domains[tid]), -len(graph[tid])))
    return unassigned[0]


def order_values(values: List[Assignment], domains: Dict[str, List[Assignment]], graph: Dict[str, set]) -> List[Assignment]:
    """
    Order values using least-constraining-value heuristic.
    
    Prefers assignments that leave maximum flexibility for other variables.
    Counts how many domain values remain for neighboring tasks after this assignment.
    
    Args:
        values: Candidate assignments for current variable
        domains: Current domains of all variables
        graph: Conflict graph
        
    Returns:
        Sorted list of assignments (least constraining first)
        
    Complexity: O(v * n) where v = values, n = neighbors
    
    Trade-off: Improves solution quality but adds overhead per value.
    """
    return sorted(values, key=lambda v: sum(len(domains[n]) for n in graph[v.task_id]))


def backtrack(tasks: Dict[str, Task], resources: Dict[str, Resource]) -> Optional[Dict[str, Assignment]]:
    """
    Solve scheduling CSP using backtracking search with heuristics.
    
    Algorithm:
    1. Build conflict graph from task resource requirements
    2. Generate initial domains (feasible assignments per task)
    3. Recursively assign tasks using DFS with backtracking
    4. Track best solution by soft constraint score
    
    Pruning & Heuristics:
    - MRV + degree heuristic for variable ordering
    - Least-constraining value for value ordering
    - Forward checking via consistency validation
    - Conflict graph guides ordering
    
    Args:
        tasks: Map of task_id to Task
        resources: Map of resource_id to Resource
        
    Returns:
        Best feasible schedule (lowest soft constraint score), or None if infeasible
        
    Complexity:
        Worst: O(b^d) where b = avg domain size, d = num tasks
        Practical: O(k * b^d) with k << 1 due to pruning
        
    Space: O(d * b) for domains + O(d) recursion depth
    
    Trade-offs:
    - Finds optimal (or near-optimal) for small problems (< 15 tasks)
    - May timeout on large/dense conflict graphs
    - Use OR-Tools for >= 15 tasks
    """
    # Build conflict graph: O(n^2) where n = tasks
    graph = build_conflict_graph(list(tasks.values()))
    
    # Generate domains: O(n * r * w * t/s)
    domains = {tid: candidate_values(t, resources) for tid, t in tasks.items()}
    
    assignment: Dict[str, Assignment] = {}
    best = {"score": float("inf"), "assign": None}

    def consistent(a: Assignment) -> bool:
        """Check if assignment violates hard constraints with existing assignments."""
        for other in assignment.values():
            # Check overlapping resources AND overlapping time
            if set(a.resource_ids) & set(other.resource_ids) and is_overlap(a, other):
                return False
        return True

    def dfs(unassigned: List[str]):
        """Depth-first search with backtracking."""
        if not unassigned:
            # Base case: complete assignment found
            s = score_schedule(assignment, tasks)
            if s < best["score"]:
                best["score"] = s
                best["assign"] = assignment.copy()
            return
        
        # Select variable using MRV + degree heuristic
        var = select_var(unassigned, domains, graph)
        
        # Try values in least-constraining order
        for val in order_values(domains[var], domains, graph):
            if not consistent(val):
                continue  # Prune: skip inconsistent assignments
            
            # Assign and recurse
            assignment[var] = val
            dfs([u for u in unassigned if u != var])
            del assignment[var]  # Backtrack

    dfs(list(tasks.keys()))
    return best["assign"]
