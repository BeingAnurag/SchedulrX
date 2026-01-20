from typing import Dict, List, Optional

from app.graph.conflict_graph import build_conflict_graph
from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule


def is_overlap(a: Assignment, b: Assignment) -> bool:
    return max(a.start, b.start) < min(a.end, b.end)


def feasible(task: Task, start: int, resources: List[Resource]) -> bool:
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
    unassigned.sort(key=lambda tid: (len(domains[tid]), -len(graph[tid])))
    return unassigned[0]


def order_values(values: List[Assignment], domains: Dict[str, List[Assignment]], graph: Dict[str, set]) -> List[Assignment]:
    return sorted(values, key=lambda v: sum(len(domains[n]) for n in graph[v.task_id]))


def backtrack(tasks: Dict[str, Task], resources: Dict[str, Resource]) -> Optional[Dict[str, Assignment]]:
    graph = build_conflict_graph(list(tasks.values()))
    domains = {tid: candidate_values(t, resources) for tid, t in tasks.items()}
    assignment: Dict[str, Assignment] = {}
    best = {"score": float("inf"), "assign": None}

    def consistent(a: Assignment) -> bool:
        for other in assignment.values():
            if set(a.resource_ids) & set(other.resource_ids) and is_overlap(a, other):
                return False
        return True

    def dfs(unassigned: List[str]):
        if not unassigned:
            s = score_schedule(assignment, tasks)
            if s < best["score"]:
                best["score"] = s
                best["assign"] = assignment.copy()
            return
        var = select_var(unassigned, domains, graph)
        for val in order_values(domains[var], domains, graph):
            if not consistent(val):
                continue
            assignment[var] = val
            dfs([u for u in unassigned if u != var])
            del assignment[var]

    dfs(list(tasks.keys()))
    return best["assign"]
