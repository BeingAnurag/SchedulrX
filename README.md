# SchedulrX

SchedulrX is a constraint-based scheduling and optimization engine (not a calendar UI). It models scheduling as a CSP with hard constraints (must never break) and soft constraints (penalized) to generate conflict-free, optimized timetables for rooms, people, and tasks.

## Architecture
- **app/models**: domain entities (`Task`, `Resource`, `Assignment`), constraint metadata.
- **app/graph**: conflict graph construction for ordering and pruning.
- **app/engine**: 
  - CSP backtracking solver with heuristics.
  - OR-Tools CP-SAT solver for large instances.
  - Local search (tabu) for re-optimization.
  - Constraint propagation module.
- **app/utils**: scoring, benchmarking, and helpers.
- **app/api**: FastAPI routes with solver selection, benchmarking endpoint.
- **app/config**: settings via `pydantic` BaseSettings.
- **app/storage**: PostgreSQL ORM models, repositories (Task/Resource/Schedule), Redis cache.

## Solvers

### Backtracking (default for < 15 tasks)
- MRV (min remaining values) + degree heuristic for variable ordering.
- Least-constraining value ordering.
- Forward-checking with consistency pruning.
- Time complexity: worst-case $O(b^d)$ where b = domain size, d = num tasks.

### OR-Tools CP-SAT (default for >= 15 tasks)
- Google's constraint programming solver.
- Handles larger instances and complex constraints.
- Configurable time limit (default 10s).
- Better quality for large problems.

### Local Search (tabu, for re-optimization)
- Efficient neighborhood exploration from existing schedule.
- Shifts task start times; maintains hard constraints.
- Useful when constraints change incrementally.

## Database & Cache
- **PostgreSQL**: stores tasks, resources, and schedules with automatic schema creation.
- **Redis**: caches recently generated schedules by constraint hash; 1-hour TTL.

## Setup & Running

### Start services
```bash
docker-compose up -d
```

### Install and run
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs for Swagger UI.

### Environment
Copy `.env.example` to `.env`:
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/schedulrx
REDIS_URL=redis://localhost:6379/0
SOLVER_TYPE=auto  # "backtracking", "ortools", or "auto"
ORTOOLS_TIME_LIMIT_SECONDS=10
```

## API Endpoints

### POST /schedule/generate
Generate a schedule. Query parameters:
- `solver` (default "auto"): "backtracking", "ortools", or "auto".

Response includes:
- `schedule`: task assignments.
- `score`: soft constraint penalty sum.
- `solver_used`: which solver ran.
- `cached`: whether result was cached.

### POST /schedule/reoptimize
Re-optimize given existing schedule. Query parameters:
- `use_local_search` (default true): use tabu search from existing solution.

### POST /schedule/benchmark
Compare solvers on same problem instance. Returns timing and quality metrics.

## Example request
```bash
curl -X POST "http://localhost:8000/schedule/generate?solver=auto" \
  -H "Content-Type: application/json" \
  -d '{
    "tasks": [
      {"id": "interview-1", "duration": 60, "required_resources": ["room-a", "alice"], "preferred_windows": [[540, 720]], "earliest_start": 480, "latest_end": 900},
      {"id": "interview-2", "duration": 30, "required_resources": ["room-a", "bob"], "preferred_windows": [[600, 780]]}
    ],
    "resources": [
      {"id": "room-a", "capacity": 1, "availability": [[480, 1020]]},
      {"id": "alice", "capacity": 1, "availability": [[540, 900]]},
      {"id": "bob", "capacity": 1, "availability": [[600, 960]]}
    ]
  }'
```

### Benchmark solvers
```bash
curl -X POST "http://localhost:8000/schedule/benchmark" \
  -H "Content-Type: application/json" \
  -d '{ ... same task/resource payload ... }'
```

## Next steps
1. Expand soft constraints (fairness, gaps, load balancing).
2. Add comprehensive unit tests for all solvers and heuristics.
3. Implement Dockerfile for application container.
4. Add query optimization for large PostgreSQL datasets.
