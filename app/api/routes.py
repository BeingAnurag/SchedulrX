from typing import Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator

from app.engine.reoptimize import reoptimize
from app.engine.solver import backtrack
from app.models.entities import Assignment, Resource, Task
from app.utils.scoring import score_schedule
from app.storage.database import get_db
from app.storage.repositories import TaskRepository, ResourceRepository, ScheduleRepository
from app.storage.cache import ScheduleCache
from sqlalchemy.orm import Session

router = APIRouter()
cache = ScheduleCache()


class ResourceDTO(BaseModel):
    id: str
    capacity: int = 1
    availability: List[List[int]]

    @validator("availability")
    def validate_windows(cls, v: List[List[int]]):
        for win in v:
            if len(win) != 2 or win[0] >= win[1]:
                raise ValueError("availability windows must be [start, end] with start < end")
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

    @validator("preferred_windows")
    def validate_pref_windows(cls, v: Optional[List[List[int]]]):
        if v is None:
            return v
        for win in v:
            if len(win) != 2 or win[0] >= win[1]:
                raise ValueError("preferred windows must be [start, end] with start < end")
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


class ReoptimizeRequest(BaseModel):
    tasks: List[TaskDTO]
    resources: List[ResourceDTO]
    existing_schedule: Optional[Dict[str, AssignmentDTO]] = None


@router.post("/schedule/generate", response_model=ScheduleResponse)
def generate(req: GenerateRequest, db: Session = Depends(get_db)):
    # Check cache first
    constraint_hash = ScheduleCache.hash_constraints(
        [t.dict() for t in req.tasks],
        [r.dict() for r in req.resources]
    )
    cached_result = cache.get(constraint_hash)
    if cached_result:
        return {"schedule": cached_result["schedule"], "score": cached_result["score"], "cached": True}
    
    task_map = {t.id: t.to_domain() for t in req.tasks}
    res_map = {r.id: r.to_domain() for r in req.resources}
    
    # Save to DB
    task_repo = TaskRepository(db)
    resource_repo = ResourceRepository(db)
    for task in task_map.values():
        task_repo.save(task)
    for resource in res_map.values():
        resource_repo.save(resource)
    
    result = backtrack(task_map, res_map)
    if result is None:
        raise HTTPException(status_code=422, detail="No feasible schedule found")
    
    dto_map = {tid: AssignmentDTO.from_domain(a) for tid, a in result.items()}
    final_score = score_schedule(result, task_map)
    
    # Cache result
    cache_data = {
        "schedule": {k: v.dict() for k, v in dto_map.items()},
        "score": final_score
    }
    cache.set(constraint_hash, cache_data)
    
    return {"schedule": dto_map, "score": final_score, "cached": False}


@router.post("/schedule/reoptimize", response_model=ScheduleResponse)
def reoptimize_endpoint(req: ReoptimizeRequest, db: Session = Depends(get_db)):
    task_map = {t.id: t.to_domain() for t in req.tasks}
    res_map = {r.id: r.to_domain() for r in req.resources}
    existing = None
    if req.existing_schedule:
        existing = {tid: Assignment(**a.dict()) for tid, a in req.existing_schedule.items()}
    result = reoptimize(task_map, res_map, existing)
    if result is None:
        raise HTTPException(status_code=422, detail="No feasible schedule found")
    dto_map = {tid: AssignmentDTO.from_domain(a) for tid, a in result.items()}
    return {"schedule": dto_map, "score": score_schedule(result, task_map), "cached": False}
