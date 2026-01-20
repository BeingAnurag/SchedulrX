import pytest
from app.models.entities import Task, Resource, Assignment


@pytest.fixture
def simple_task():
    """Single task with one resource."""
    return Task(
        id="task-1",
        duration=60,
        required_resources=["resource-1"],
        preferred_windows=[(480, 720)],
        earliest_start=0,
        latest_end=1440
    )


@pytest.fixture
def simple_resource():
    """Single resource with full availability."""
    return Resource(
        id="resource-1",
        capacity=1,
        availability=[(0, 1440)]
    )


@pytest.fixture
def conflicting_tasks():
    """Two tasks sharing a resource."""
    return {
        "task-1": Task(
            id="task-1",
            duration=60,
            required_resources=["room-a"],
            preferred_windows=[(480, 720)],
        ),
        "task-2": Task(
            id="task-2",
            duration=30,
            required_resources=["room-a"],
            preferred_windows=[(600, 900)],
        ),
    }


@pytest.fixture
def simple_resources():
    """Basic resources for testing."""
    return {
        "room-a": Resource(id="room-a", capacity=1, availability=[(0, 1440)]),
        "room-b": Resource(id="room-b", capacity=1, availability=[(0, 1440)]),
    }


@pytest.fixture
def complex_scenario():
    """Multi-task, multi-resource scheduling problem."""
    tasks = {
        "interview-1": Task(
            id="interview-1",
            duration=60,
            required_resources=["room-a", "alice"],
            preferred_windows=[(540, 720)],
            earliest_start=480,
            latest_end=900
        ),
        "interview-2": Task(
            id="interview-2",
            duration=30,
            required_resources=["room-a", "bob"],
            preferred_windows=[(600, 780)],
        ),
        "interview-3": Task(
            id="interview-3",
            duration=45,
            required_resources=["room-b", "charlie"],
            preferred_windows=[(600, 1020)],
        ),
    }
    resources = {
        "room-a": Resource(id="room-a", capacity=1, availability=[(480, 1020)]),
        "room-b": Resource(id="room-b", capacity=1, availability=[(480, 1020)]),
        "alice": Resource(id="alice", capacity=1, availability=[(540, 900)]),
        "bob": Resource(id="bob", capacity=1, availability=[(600, 960)]),
        "charlie": Resource(id="charlie", capacity=1, availability=[(600, 1020)]),
    }
    return tasks, resources


@pytest.fixture
def infeasible_scenario():
    """Scenario with no valid solution (conflicting constraints)."""
    tasks = {
        "task-1": Task(
            id="task-1",
            duration=100,
            required_resources=["room-a"],
            earliest_start=0,
            latest_end=50  # Impossible: duration > window
        ),
    }
    resources = {
        "room-a": Resource(id="room-a", capacity=1, availability=[(0, 1440)]),
    }
    return tasks, resources


@pytest.fixture
def sample_assignment():
    """Sample assignment for testing."""
    return Assignment(
        task_id="task-1",
        start=480,
        end=540,
        resource_ids=["room-a"]
    )
