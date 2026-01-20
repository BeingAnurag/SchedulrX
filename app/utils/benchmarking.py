import time
from typing import Dict, Optional
from dataclasses import dataclass

from app.models.entities import Assignment, Resource, Task
from app.engine.solver import backtrack
from app.engine.ortools_solver import solve_with_ortools
from app.utils.scoring import score_schedule


@dataclass
class BenchmarkResult:
    solver_name: str
    time_seconds: float
    score: float
    success: bool
    num_tasks: int


def benchmark_solvers(tasks: Dict[str, Task], resources: Dict[str, Resource]) -> list:
    """
    Compare backtracking vs OR-Tools on same instance.
    Returns list of BenchmarkResult.
    """
    results = []

    # Backtracking
    start = time.time()
    bt_result = backtrack(tasks, resources)
    bt_time = time.time() - start
    if bt_result:
        bt_score = score_schedule(bt_result, tasks)
        results.append(BenchmarkResult(
            solver_name="backtracking",
            time_seconds=bt_time,
            score=bt_score,
            success=True,
            num_tasks=len(tasks),
        ))
    else:
        results.append(BenchmarkResult(
            solver_name="backtracking",
            time_seconds=bt_time,
            score=float("inf"),
            success=False,
            num_tasks=len(tasks),
        ))

    # OR-Tools (10-second limit)
    start = time.time()
    ort_result = solve_with_ortools(tasks, resources, time_limit_seconds=10)
    ort_time = time.time() - start
    if ort_result:
        ort_score = score_schedule(ort_result, tasks)
        results.append(BenchmarkResult(
            solver_name="ortools",
            time_seconds=ort_time,
            score=ort_score,
            success=True,
            num_tasks=len(tasks),
        ))
    else:
        results.append(BenchmarkResult(
            solver_name="ortools",
            time_seconds=ort_time,
            score=float("inf"),
            success=False,
            num_tasks=len(tasks),
        ))

    return results


def select_solver(num_tasks: int) -> str:
    """
    Heuristic: choose solver based on problem size.
    Small: backtracking (faster for < 15 tasks)
    Large: OR-Tools (better for >= 15 tasks)
    """
    return "ortools" if num_tasks >= 15 else "backtracking"
