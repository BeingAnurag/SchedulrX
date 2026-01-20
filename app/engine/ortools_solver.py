from typing import Dict, Optional

from ortools.sat.python import cp_model

from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule


def solve_with_ortools(tasks: Dict[str, Task], resources: Dict[str, Resource], time_limit_seconds: int = 10) -> Optional[Dict[str, Assignment]]:
    """
    Solve scheduling problem using Google OR-Tools CP-SAT solver.
    Automatically handles hard constraints; soft constraints added as penalties.
    """
    model = cp_model.CpModel()

    # Variables: for each task, store (resource_id, start_time)
    task_vars: Dict[str, tuple] = {}
    all_resources = list(resources.values())
    max_end_time = max(
        max(win[1] for win in r.availability or [(0, 1440)]) 
        for r in all_resources
    ) if all_resources else 1440

    for task_id, task in tasks.items():
        # Start time variable
        start_var = model.NewIntVar(0, max_end_time - task.duration, f"{task_id}_start")
        
        # Apply time bound constraints
        if task.earliest_start:
            model.Add(start_var >= task.earliest_start)
        if task.latest_end:
            model.Add(start_var + task.duration <= task.latest_end)
        
        task_vars[task_id] = {"start": start_var, "task": task, "end": start_var + task.duration}

    # Hard constraints: no overlapping on shared resources
    for i, (tid1, vars1) in enumerate(task_vars.items()):
        for tid2, vars2 in list(task_vars.items())[i + 1:]:
            task1 = vars1["task"]
            task2 = vars2["task"]
            shared_resources = set(task1.required_resources) & set(task2.required_resources)
            
            if shared_resources:
                # Either task1 ends before task2 starts OR task2 ends before task1 starts
                start1, end1 = vars1["start"], vars1["end"]
                start2, end2 = vars2["start"], vars2["end"]
                
                # Binary variable: 1 if task1 before task2, 0 otherwise
                before = model.NewBoolVar(f"{tid1}_{tid2}_before")
                model.Add(end1 <= start2).OnlyEnforceIf(before)
                model.Add(end2 <= start1).OnlyEnforceIf(before.Not())

    # Hard constraints: availability windows
    for task_id, vars_dict in task_vars.items():
        task = vars_dict["task"]
        start_var = vars_dict["start"]
        
        # At least one resource must have availability
        resource_available = False
        for r_id in task.required_resources:
            r = resources[r_id]
            if r.availability:
                for win_start, win_end in r.availability:
                    # Create a boolean for this window
                    in_window = model.NewBoolVar(f"{task_id}_{r_id}_win")
                    model.Add(start_var >= win_start).OnlyEnforceIf(in_window)
                    model.Add(start_var + task.duration <= win_end).OnlyEnforceIf(in_window)
                    resource_available = True
        
        if not resource_available:
            # If no windows defined, assume full day availability
            pass

    # Soft constraints: preferred windows (penalty-based)
    penalties = []
    for task_id, vars_dict in task_vars.items():
        task = vars_dict["task"]
        start_var = vars_dict["start"]
        
        if task.preferred_windows:
            for win_start, win_end in task.preferred_windows:
                in_pref = model.NewBoolVar(f"{task_id}_pref")
                model.Add(start_var >= win_start).OnlyEnforceIf(in_pref)
                model.Add(start_var + task.duration <= win_end).OnlyEnforceIf(in_pref)
                # Penalty if NOT in preferred window
                penalty = model.NewBoolVar(f"{task_id}_penalty")
                model.Add(penalty == in_pref.Not())
                penalties.append(penalty)

    # Objective: minimize soft constraint violations
    if penalties:
        model.Minimize(sum(penalties))

    # Solve with time limit
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        return None

    # Extract solution
    result: Dict[str, Assignment] = {}
    for task_id, vars_dict in task_vars.items():
        start = solver.Value(vars_dict["start"])
        task = vars_dict["task"]
        result[task_id] = Assignment(
            task_id=task_id,
            start=int(start),
            end=int(start + task.duration),
            resource_ids=task.required_resources,
        )

    return result
