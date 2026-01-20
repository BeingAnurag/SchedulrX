from typing import Dict, List, Optional
import logging

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, validator

from app.engine.reoptimize import reoptimize
from app.engine.solver import backtrack
from app.engine.ortools_solver import solve_with_ortools
from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule
from app.utils.benchmarking import benchmark_solvers
from app.storage.database import get_db
from app.storage.repositories import TaskRepository, ResourceRepository, ScheduleRepository
from app.storage.cache import ScheduleCache
from app.config.settings import get_settings
from sqlalchemy.orm import Session

router = APIRouter()
cache = ScheduleCache()
settings = get_settings()
logger = logging.getLogger(__name__)


class ResourceDTO(BaseModel):
    id: str
    capacity: int = 1
    availability: List[List[int]]

    @validator("availability")
    def validate_windows(cls, v: List[List[int]]):
        """Validate availability windows format and constraints."""
        for win in v:
            if len(win) != 2 or win[0] >= win[1]:
                raise ValueError("availability windows must be [start, end] with start < end")
            if win[0] < 0 or win[1] > 1440:
                raise ValueError("time values must be in [0, 1440] (minutes in a day)")
        return v

    def to_domain(self) -> Resource:
        return Resource(id=self.id, capacity=self.capacity, availability=[(w[0], w[1]) for w in self.availability])


class TaskDTO(BaseModel):
    id: str
    duration: int
    required_resources: List[str] = Field(..., min_items=1)
    preferred_windows: Optional[List[List[int]]] = None
    earliest_start: Optional[int] = None
    latest_end: Optional[int] = None

    @validator("duration")
    def validate_duration(cls, v: int):
        """Ensure task duration is reasonable (1 min to 24 hours)."""
        if v < 1 or v > 1440:
            raise ValueError("duration must be between 1 and 1440 minutes")
        return v

    @validator("preferred_windows")
    def validate_pref_windows(cls, v: Optional[List[List[int]]]):
        """Validate preferred time windows format."""
        if v is None:
            return v
        for win in v:
            if len(win) != 2 or win[0] >= win[1]:
                raise ValueError("preferred windows must be [start, end] with start < end")
            if win[0] < 0 or win[1] > 1440:
                raise ValueError("time values must be in [0, 1440] (minutes in a day)")
        return v

    def to_domain(self) -> Task:
        prefs = None if self.preferred_windows is None else [(w[0], w[1]) for w in self.preferred_windows]
        return Task(
            id=self.id,
            duration=self.duration,
            required_resources=self.required_resources,
            preferred_windows=prefs,
            earliest_start=self.earliest_start,
            latest_end=self.latest_end,
        )


class AssignmentDTO(BaseModel):
    task_id: str
    start: int
    end: int
    resource_ids: List[str]

    @classmethod
    def from_domain(cls, a: Assignment) -> "AssignmentDTO":
        return cls(task_id=a.task_id, start=a.start, end=a.end, resource_ids=a.resource_ids)


class GenerateRequest(BaseModel):
    tasks: List[TaskDTO]
    resources: List[ResourceDTO]


class ScheduleResponse(BaseModel):
    schedule: Dict[str, AssignmentDTO]
    score: float
    cached: bool = False
    solver_used: str = "backtracking"


class BenchmarkEntry(BaseModel):
    solver_name: str
    time_seconds: float
    score: float
    success: bool


class BenchmarkResponse(BaseModel):
    results: List[BenchmarkEntry]
    num_tasks: int


class ReoptimizeRequest(BaseModel):
    tasks: List[TaskDTO]
    resources: List[ResourceDTO]
    existing_schedule: Optional[Dict[str, AssignmentDTO]] = None


@router.post("/schedule/generate", response_model=ScheduleResponse, summary="Generate optimized schedule")
def generate(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    solver: str = Query("auto", regex="^(auto|backtracking|ortools)$", description="Solver: auto, backtracking, or ortools")
):
    """
    Generate an optimized schedule for tasks and resources.
    
    **Algorithm**:
    1. Validate input (DTOs with Pydantic validators)
    2. Check cache for identical problem
    3. Select solver (auto, backtracking, or ortools)
    4. Solve CSP and compute soft constraint score
    5. Store in database and cache
    
    **Solver Selection:**
    - `auto`: Automatically selects solver based on problem size (backtracking < 15 tasks, ortools >= 15)
    - `backtracking`: CSP backtracking with heuristics (faster for small problems)
    - `ortools`: Google OR-Tools CP-SAT solver (better for large/complex problems)
    
    **Error Handling:**
    - 400: Invalid input (malformed windows, negative durations, etc.)
    - 422: Infeasible schedule (no valid assignment exists)
    - 500: Solver internal error
    
    **Returns:**
    - `schedule`: Map of task_id to assignment (start, end, resource_ids)
    - `score`: Soft constraint penalty sum (lower is better)
    - `solver_used`: Which solver was used
    - `cached`: Whether result was retrieved from cache
    """
    logger.info(f"Generate request: {len(req.tasks)} tasks, {len(req.resources)} resources, solver={solver}")
    
    # Input validation: check resource IDs exist
    resource_ids = {r.id for r in req.resources}
    for task in req.tasks:
        for r_id in task.required_resources:
            if r_id not in resource_ids:
                logger.warning(f"Task {task.id} references unknown resource {r_id}")
                raise HTTPException(status_code=400, detail=f"Task {task.id} requires unknown resource {r_id}")
    
    # Check cache first
    constraint_hash = ScheduleCache.hash_constraints(
        [t.dict() for t in req.tasks],
        [r.dict() for r in req.resources]
    )
    cached_result = cache.get(constraint_hash)
    if cached_result:
        logger.info("Cache hit")
        return {
            "schedule": cached_result["schedule"],
            "score": cached_result["score"],
            "cached": True,
            "solver_used": cached_result.get("solver_used", "cached")
        }
    
    task_map = {t.id: t.to_domain() for t in req.tasks}
    res_map = {r.id: r.to_domain() for r in req.resources}
    
    # Save to DB
    task_repo = TaskRepository(db)
    resource_repo = ResourceRepository(db)
    for task in task_map.values():
        task_repo.save(task)
    for resource in res_map.values():
        resource_repo.save(resource)
    
    # Select solver
    solver_choice = solver if solver != "auto" else ("ortools" if len(task_map) >= 15 else "backtracking")
    logger.info(f"Using solver: {solver_choice}")
    
    if solver_choice == "ortools":
        result = solve_with_ortools(task_map, res_map, settings.ortools_time_limit_seconds)
    else:
        result = backtrack(task_map, res_map)
    
    if result is None:
        logger.warning("No feasible schedule found")
        raise HTTPException(status_code=422, detail="No feasible schedule found")
    
    dto_map = {tid: AssignmentDTO.from_domain(a) for tid, a in result.items()}
    final_score = score_schedule(result, task_map)
    
    logger.info(f"Schedule generated: score={final_score:.2f}")
    
    # Cache result
    cache_data = {
        "schedule": {k: v.dict() for k, v in dto_map.items()},
        "score": final_score,
        "solver_used": solver_choice
    }
    cache.set(constraint_hash, cache_data)
    
    return {"schedule": dto_map, "score": final_score, "cached": False, "solver_used": solver_choice}


@router.post("/schedule/reoptimize", response_model=ScheduleResponse, summary="Re-optimize existing schedule")
def reoptimize_endpoint(
    req: ReoptimizeRequest,
    db: Session = Depends(get_db),
    use_local_search: bool = Query(True, description="Use tabu search from existing solution")
):
    """
    Re-optimize a schedule when constraints change.
    
    **Local Search Mode:**
    - When `use_local_search=true` and `existing_schedule` provided: uses tabu search from existing solution
    - When `use_local_search=false`: performs fresh solve
    
    **Use Cases:**
    - Constraint changes (new availability, preference updates)
    - Adding/removing tasks
    - Incremental optimization
    """
    logger.info(f"Reoptimize request: {len(req.tasks)} tasks, local_search={use_local_search}")
    
    task_map = {t.id: t.to_domain() for t in req.tasks}
    res_map = {r.id: r.to_domain() for r in req.resources}
    existing = None
    if req.existing_schedule:
        existing = {tid: Assignment(**a.dict()) for tid, a in req.existing_schedule.items()}
        logger.info(f"Starting from existing schedule with {len(existing)} assignments")
    
    result = reoptimize(task_map, res_map, existing, use_local_search=use_local_search)
    if result is None:
        logger.warning("Re-optimization failed")
        raise HTTPException(status_code=422, detail="No feasible schedule found")
    
    dto_map = {tid: AssignmentDTO.from_domain(a) for tid, a in result.items()}
    solver_used = "local_search" if (existing and use_local_search) else "backtracking"
    
    logger.info(f"Re-optimization complete: solver={solver_used}")
    return {"schedule": dto_map, "score": score_schedule(result, task_map), "cached": False, "solver_used": solver_used}


@router.post("/schedule/benchmark", response_model=BenchmarkResponse, summary="Benchmark solvers")
def benchmark(req: GenerateRequest):
    """
    Compare backtracking vs OR-Tools solvers on the same problem instance.
    
    **Returns:**
    - Timing, score, and success metrics for each solver
    - Useful for understanding solver performance on your problem domain
    """
    logger.info(f"Benchmark request: {len(req.tasks)} tasks")
    
    task_map = {t.id: t.to_domain() for t in req.tasks}
    res_map = {r.id: r.to_domain() for r in req.resources}
    results = benchmark_solvers(task_map, res_map)
    
    logger.info(f"Benchmark complete: {len(results)} solvers compared")
    
    return {
        "results": [
            BenchmarkEntry(
                solver_name=r.solver_name,
                time_seconds=r.time_seconds,
                score=r.score,
                success=r.success
            )
            for r in results
        ],
        "num_tasks": len(task_map)
    }
