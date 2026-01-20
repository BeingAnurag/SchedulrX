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
  - Pluggable custom constraint system.
- **app/utils**: scoring, benchmarking, logging, and helpers.
- **app/api**: FastAPI routes with solver selection, benchmarking endpoint, full OpenAPI docs.
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

## Deployment

### Quick Start (Docker)
```bash
# Development
./deploy.sh dev

# Production
./deploy.sh prod
```

### Manual Setup
```bash
# Start infrastructure
docker-compose up -d postgres redis

# Local development
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Full Stack (Docker Compose)
```bash
docker-compose up -d
```
Access:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Environment Configuration
Create `.env` from template:
```bash
cp .env.example .env
```

**Key Settings:**
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/schedulrx
REDIS_URL=redis://localhost:6379/0
SOLVER_TYPE=auto  # "backtracking", "ortools", or "auto"
ORTOOLS_TIME_LIMIT_SECONDS=10
DEBUG=false
```

**Environment Files:**
- `.env.dev`: development (debug on, backtracking default)
- `.env.prod`: production (debug off, ortools default, longer timeout)

## API Endpoints

### POST /api/v1/schedule/generate
Generate a schedule. Query parameters:
- `solver` (default "auto"): "backtracking", "ortools", or "auto".

Response includes:
- `schedule`: task assignments.
- `score`: soft constraint penalty sum.
- `solver_used`: which solver ran.
- `cached`: whether result was cached.

### POST /api/v1/schedule/reoptimize
Re-optimize given existing schedule. Query parameters:
- `use_local_search` (default true): use tabu search from existing solution.

### POST /api/v1/schedule/benchmark
Compare solvers on same problem instance. Returns timing and quality metrics.

## Extensibility

### Custom Soft Constraints
```python
from app.engine.custom_constraints import SoftConstraint, ConstraintRegistry

class MyCustomConstraint(SoftConstraint):
    def evaluate(self, task, assignment):
        # Your logic here
        return penalty_value

registry = ConstraintRegistry()
registry.register_task_constraint(MyCustomConstraint(weight=1.0))
```

See [examples/custom_constraints_example.py](examples/custom_constraints_example.py) for full examples.

## Example request
```bash
curl -X POST "http://localhost:8000/api/v1/schedule/generate?solver=auto" \
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
curl -X POST "http://localhost:8000/api/v1/schedule/benchmark" \
  -H "Content-Type: application/json" \
  -d '{ ... same task/resource payload ... }'
```

## Testing
```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Quick run
./run_tests.sh
```

## Monitoring & Logging
- Structured logging to stdout (JSON-friendly for log aggregation)
- Health check endpoint: `/health`
- Docker healthchecks enabled for all services
- Log level controlled by `DEBUG` env var

## Production Considerations
1. Use environment-specific `.env` files
2. Enable HTTPS/TLS termination at load balancer
3. Scale horizontally (stateless API, shared DB/Redis)
4. Monitor solver time limits and cache hit rates
5. Consider read replicas for PostgreSQL at scale
6. Use Redis Sentinel or Cluster for cache HA

## Next steps
1. Add Prometheus metrics endpoint
2. Kubernetes deployment manifests
3. Performance profiling and bottleneck analysis
4. Multi-objective optimization (Pareto frontier)
