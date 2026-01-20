# SchedulrX

SchedulrX is a constraint-based scheduling and optimization engine (not a calendar UI). It models scheduling as a CSP with hard constraints (must never break) and soft constraints (penalized) to generate conflict-free, optimized timetables for rooms, people, and tasks.

## Architecture
- app/models: domain entities (Task, Resource, Assignment), constraint metadata.
- app/graph: conflict graph construction for ordering and pruning.
- app/engine: CSP solver (backtracking + heuristics) and re-optimization hook.
- app/utils: scoring and helpers.
- app/api: FastAPI routes and DTOs.
- app/config: settings via pydantic BaseSettings.
- app/storage: repository and cache interfaces (PostgreSQL, Redis placeholders).

## Algorithms
- Variables: tasks; domains: feasible (start, resource) assignments.
- Hard constraints: availability windows, no overlapping resource usage, time bounds.
- Soft constraints: preferred windows scored via penalties.
- Solver: backtracking with MRV + degree heuristic, least-constraining value ordering, forward pruning via consistency checks.

## Running locally
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Then open http://127.0.0.1:8000/docs for Swagger.

## Example request
```bash
curl -X POST http://localhost:8000/schedule/generate \
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

## Next steps
1. Implement PostgreSQL repositories and migrations for tasks/resources.
2. Add Redis-backed schedule cache keyed by constraint hash.
3. Add OR-Tools solver path with time limits for larger instances.
4. Expand soft constraints (fairness, gaps) and add unit tests for edge cases.
