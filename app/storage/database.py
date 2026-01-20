from sqlalchemy import create_engine, Column, String, Integer, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from app.config.settings import get_settings

settings = get_settings()

engine = create_engine(settings.postgres_dsn, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    duration = Column(Integer, nullable=False)
    required_resources = Column(JSON, nullable=False)  # List[str]
    preferred_windows = Column(JSON, nullable=True)  # List[List[int]]
    earliest_start = Column(Integer, nullable=True)
    latest_end = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResourceModel(Base):
    __tablename__ = "resources"

    id = Column(String, primary_key=True)
    capacity = Column(Integer, default=1)
    availability = Column(JSON, nullable=True)  # List[List[int]]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduleModel(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    resource_ids = Column(JSON, nullable=False)  # List[str]
    score = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
