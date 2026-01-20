from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.entities import Resource, Task
from app.storage.database import TaskModel, ResourceModel, ScheduleModel


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: str) -> Optional[Task]:
        model = self.db.query(TaskModel).filter(TaskModel.id == task_id).first()
        if not model:
            return None
        return self._model_to_task(model)

    def list_all(self) -> List[Task]:
        models = self.db.query(TaskModel).all()
        return [self._model_to_task(m) for m in models]

    def save(self, task: Task) -> None:
        existing = self.db.query(TaskModel).filter(TaskModel.id == task.id).first()
        if existing:
            existing.duration = task.duration
            existing.required_resources = task.required_resources
            existing.preferred_windows = task.preferred_windows
            existing.earliest_start = task.earliest_start
            existing.latest_end = task.latest_end
        else:
            model = TaskModel(
                id=task.id,
                duration=task.duration,
                required_resources=task.required_resources,
                preferred_windows=task.preferred_windows,
                earliest_start=task.earliest_start,
                latest_end=task.latest_end,
            )
            self.db.add(model)
        self.db.commit()

    def delete(self, task_id: str) -> None:
        self.db.query(TaskModel).filter(TaskModel.id == task_id).delete()
        self.db.commit()

    @staticmethod
    def _model_to_task(model: TaskModel) -> Task:
        return Task(
            id=model.id,
            duration=model.duration,
            required_resources=model.required_resources,
            preferred_windows=model.preferred_windows,
            earliest_start=model.earliest_start,
            latest_end=model.latest_end,
        )


class ResourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, resource_id: str) -> Optional[Resource]:
        model = self.db.query(ResourceModel).filter(ResourceModel.id == resource_id).first()
        if not model:
            return None
        return self._model_to_resource(model)

    def list_all(self) -> List[Resource]:
        models = self.db.query(ResourceModel).all()
        return [self._model_to_resource(m) for m in models]

    def save(self, resource: Resource) -> None:
        existing = self.db.query(ResourceModel).filter(ResourceModel.id == resource.id).first()
        if existing:
            existing.capacity = resource.capacity
            existing.availability = resource.availability
        else:
            model = ResourceModel(
                id=resource.id,
                capacity=resource.capacity,
                availability=resource.availability,
            )
            self.db.add(model)
        self.db.commit()

    def delete(self, resource_id: str) -> None:
        self.db.query(ResourceModel).filter(ResourceModel.id == resource_id).delete()
        self.db.commit()

    @staticmethod
    def _model_to_resource(model: ResourceModel) -> Resource:
        return Resource(
            id=model.id,
            capacity=model.capacity,
            availability=model.availability,
        )


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_schedule(self, task_id: str, schedule_id: str, start: int, end: int, resource_ids: List[str], score: float) -> None:
        model = ScheduleModel(
            id=schedule_id,
            task_id=task_id,
            start=start,
            end=end,
            resource_ids=resource_ids,
            score=score,
        )
        self.db.add(model)
        self.db.commit()

    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        model = self.db.query(ScheduleModel).filter(ScheduleModel.id == schedule_id).first()
        if not model:
            return None
        return {
            "task_id": model.task_id,
            "start": model.start,
            "end": model.end,
            "resource_ids": model.resource_ids,
            "score": model.score,
        }
