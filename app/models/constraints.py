from dataclasses import dataclass
from app.models.entities import ConstraintType


@dataclass(frozen=True)
class Constraint:
    name: str
    type: ConstraintType
    weight: float = 1.0  # for soft penalties
