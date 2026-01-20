import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestGenerateEndpoint:
    """Integration tests for /schedule/generate endpoint."""

    def test_generate_simple_schedule(self, complex_scenario):
        """Generate endpoint should return valid schedule."""
        tasks, resources = complex_scenario
        
        # Convert to JSON-serializable format
        tasks_json = [
            {
                "id": t.id,
                "duration": t.duration,
                "required_resources": t.required_resources,
                "preferred_windows": t.preferred_windows,
                "earliest_start": t.earliest_start,
                "latest_end": t.latest_end,
            }
            for t in tasks.values()
        ]
        resources_json = [
            {
                "id": r.id,
                "capacity": r.capacity,
                "availability": r.availability,
            }
            for r in resources.values()
        ]
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
        }
        
        response = client.post("/schedule/generate", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "schedule" in data
        assert "score" in data
        assert "solver_used" in data
        assert isinstance(data["score"], (int, float))

    def test_generate_with_solver_query_param(self, complex_scenario):
        """Generate should respect solver query parameter."""
        tasks, resources = complex_scenario
        
        tasks_json = [
            {
                "id": t.id,
                "duration": t.duration,
                "required_resources": t.required_resources,
                "preferred_windows": t.preferred_windows,
                "earliest_start": t.earliest_start,
                "latest_end": t.latest_end,
            }
            for t in tasks.values()
        ]
        resources_json = [
            {
                "id": r.id,
                "capacity": r.capacity,
                "availability": r.availability,
            }
            for r in resources.values()
        ]
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
        }
        
        # Test with backtracking
        response = client.post("/schedule/generate?solver=backtracking", json=payload)
        assert response.status_code == 200
        assert response.json()["solver_used"] == "backtracking"
        
        # Test with ortools
        response = client.post("/schedule/generate?solver=ortools", json=payload)
        assert response.status_code == 200
        assert response.json()["solver_used"] == "ortools"

    def test_generate_infeasible_returns_422(self, infeasible_scenario):
        """Infeasible problem returns 422 error."""
        tasks, resources = infeasible_scenario
        
        tasks_json = [
            {
                "id": t.id,
                "duration": t.duration,
                "required_resources": t.required_resources,
                "preferred_windows": t.preferred_windows,
                "earliest_start": t.earliest_start,
                "latest_end": t.latest_end,
            }
            for t in tasks.values()
        ]
        resources_json = [
            {
                "id": r.id,
                "capacity": r.capacity,
                "availability": r.availability,
            }
            for r in resources.values()
        ]
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
        }
        
        response = client.post("/schedule/generate", json=payload)
        assert response.status_code == 422

    def test_generate_invalid_availability_format(self):
        """Invalid window format should return validation error."""
        payload = {
            "tasks": [
                {
                    "id": "task-1",
                    "duration": 60,
                    "required_resources": ["resource-1"],
                }
            ],
            "resources": [
                {
                    "id": "resource-1",
                    "capacity": 1,
                    "availability": [[100, 100]],  # Invalid: start == end
                }
            ],
        }
        
        response = client.post("/schedule/generate", json=payload)
        assert response.status_code == 422


class TestReoptimizeEndpoint:
    """Integration tests for /schedule/reoptimize endpoint."""

    def test_reoptimize_with_existing_schedule(self, complex_scenario):
        """Reoptimize should accept existing schedule."""
        tasks, resources = complex_scenario
        
        tasks_json = [
            {
                "id": t.id,
                "duration": t.duration,
                "required_resources": t.required_resources,
                "preferred_windows": t.preferred_windows,
                "earliest_start": t.earliest_start,
                "latest_end": t.latest_end,
            }
            for t in tasks.values()
        ]
        resources_json = [
            {
                "id": r.id,
                "capacity": r.capacity,
                "availability": r.availability,
            }
            for r in resources.values()
        ]
        
        existing_schedule = {
            "interview-1": {
                "task_id": "interview-1",
                "start": 480,
                "end": 540,
                "resource_ids": ["room-a"]
            },
            "interview-2": {
                "task_id": "interview-2",
                "start": 600,
                "end": 630,
                "resource_ids": ["room-a"]
            },
            "interview-3": {
                "task_id": "interview-3",
                "start": 650,
                "end": 695,
                "resource_ids": ["room-b"]
            },
        }
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
            "existing_schedule": existing_schedule,
        }
        
        response = client.post("/schedule/reoptimize?use_local_search=true", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "schedule" in data
        assert data["solver_used"] == "local_search"

    def test_reoptimize_without_local_search(self, complex_scenario):
        """Reoptimize should support fresh solve without local search."""
        tasks, resources = complex_scenario
        
        tasks_json = [
            {
                "id": t.id,
                "duration": t.duration,
                "required_resources": t.required_resources,
                "preferred_windows": t.preferred_windows,
                "earliest_start": t.earliest_start,
                "latest_end": t.latest_end,
            }
            for t in tasks.values()
        ]
        resources_json = [
            {
                "id": r.id,
                "capacity": r.capacity,
                "availability": r.availability,
            }
            for r in resources.values()
        ]
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
        }
        
        response = client.post("/schedule/reoptimize?use_local_search=false", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["solver_used"] == "backtracking"


class TestBenchmarkEndpoint:
    """Integration tests for /schedule/benchmark endpoint."""

    def test_benchmark_compares_solvers(self, simple_task, simple_resource):
        """Benchmark should return results for both solvers."""
        tasks_json = [
            {
                "id": simple_task.id,
                "duration": simple_task.duration,
                "required_resources": simple_task.required_resources,
                "preferred_windows": simple_task.preferred_windows,
                "earliest_start": simple_task.earliest_start,
                "latest_end": simple_task.latest_end,
            }
        ]
        resources_json = [
            {
                "id": simple_resource.id,
                "capacity": simple_resource.capacity,
                "availability": simple_resource.availability,
            }
        ]
        
        payload = {
            "tasks": tasks_json,
            "resources": resources_json,
        }
        
        response = client.post("/schedule/benchmark", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) >= 2
        
        # Check result structure
        for result in data["results"]:
            assert "solver_name" in result
            assert "time_seconds" in result
            assert "score" in result
            assert "success" in result


class TestHealthCheck:
    """Integration test for health check endpoint."""

    def test_health_check(self):
        """Health endpoint should return OK."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "app" in data
