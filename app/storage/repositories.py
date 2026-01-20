from typing import Dict, List

from app.models.entities import Resource, Task


class TaskRepository:
    # Placeholder: implement with async DB calls (PostgreSQL)
    def list_tasks(self) -> List[Task]:
        raise NotImplementedError

    def save_tasks(self, tasks: List[Task]) -> None:
        raise NotImplementedError


class ResourceRepository:
    def list_resources(self) -> List[Resource]:
        raise NotImplementedError

    def save_resources(self, resources: List[Resource]) -> None:
        raise NotImplementedError


class ScheduleCache:
    # Placeholder: implement with Redis
    def get(self, key: str) -> Dict[str, str]:
        raise NotImplementedError

    def set(self, key: str, value: Dict[str, str], ttl_seconds: int = 300) -> None:
        raise NotImplementedError
