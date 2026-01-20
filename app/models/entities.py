from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class ConstraintType(str, Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(frozen=True)
class Resource:
    id: str
    capacity: int = 1
    availability: List[Tuple[int, int]] = None  # list of (start, end) epoch minutes


@dataclass(frozen=True)
class Task:
    id: str
    duration: int  # minutes
    required_resources: List[str]
    preferred_windows: Optional[List[Tuple[int, int]]] = None  # soft windows
    earliest_start: Optional[int] = None
    latest_end: Optional[int] = None


@dataclass(frozen=True)
class Assignment:
    task_id: str
    start: int
    end: int
    resource_ids: List[str]
