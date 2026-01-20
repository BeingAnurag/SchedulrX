# SchedulrX Architecture

## Overview
SchedulrX is a production-grade constraint-based scheduling engine built with clean architecture principles. This document explains the design decisions, module responsibilities, and scalability considerations.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Layer                          │
│  (API Routes, Request Validation, Response Formatting)      │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│                   Orchestration Layer                        │
│  (Solver Selection, Caching Strategy, Logging)              │
└─┬──────────────┬──────────────┬────────────────────────────┘
  │              │              │
  │              │              │
┌─▼──────────┐ ┌─▼────────────┐ ┌▼───────────────────────────┐
│ Backtracking│ │ OR-Tools     │ │ Local Search (Tabu)        │
│ Solver      │ │ CP-SAT Solver│ │ Re-optimization            │
│ (< 15 tasks)│ │ (>= 15 tasks)│ │ (from existing solution)   │
└─────────────┘ └──────────────┘ └────────────────────────────┘
       │                │                    │
       └────────────────┴────────────────────┘
                        │
       ┌────────────────▼────────────────────────┐
       │     Constraint & Scoring Layer          │
       │  (Hard Constraints, Soft Constraints,   │
       │   Score Calculation, Conflict Graph)    │
       └─────────────────────────────────────────┘
                        │
       ┌────────────────┴────────────────────────┐
       │                                         │
   ┌───▼───────────┐                    ┌────────▼────────┐
   │ PostgreSQL     │                    │ Redis Cache     │
   │ (Persistence)  │                    │ (TTL: 1 hour)   │
   └────────────────┘                    └─────────────────┘
```

---

## Module Responsibilities

### 1. API Layer (`app/api/routes.py`)
**Purpose**: External interface for scheduling requests

**Responsibilities**:
- Request validation (Pydantic models)
- Solver selection logic
- Cache lookup/update
- Response formatting
- OpenAPI documentation

**Design Decision**: Versioned routes (`/api/v1/`) to support future API evolution without breaking clients.

---

### 2. Core Engine (`app/engine/`)

#### `solver.py` - Backtracking CSP Solver
**Algorithm**: Depth-first search with intelligent heuristics

**When to Use**: 
- Small problems (< 15 tasks)
- Need optimal or near-optimal solutions
- Acceptable runtime (< 5 seconds)

**Key Heuristics**:
- **MRV (Minimum Remaining Values)**: Select variable with smallest domain first
- **Degree Heuristic**: Break ties by choosing most-constrained task
- **Least-Constraining Value**: Order domain values to preserve maximum flexibility

**Complexity**: O(b^d) worst case, but heavy pruning in practice

**Design Decision**: Chosen for interpretability and control. Custom heuristics outperform naive backtracking by orders of magnitude.

---

#### `ortools_solver.py` - Google OR-Tools Integration
**Algorithm**: CP-SAT (Constraint Programming with SAT encoding)

**When to Use**:
- Large problems (>= 15 tasks)
- Complex constraint interactions
- Need production-grade robustness

**Key Features**:
- Disjunctive constraints for resource conflicts
- Linear relaxations for optimization
- Configurable time limits (default 10s)

**Complexity**: NP-hard, but scales to 100s of tasks with time limits

**Design Decision**: Provides scalability escape hatch. OR-Tools is industry-standard with decades of optimization research.

---

#### `local_search.py` - Tabu Search Re-optimizer
**Algorithm**: Iterative improvement with tabu memory

**When to Use**:
- Have existing feasible solution
- Need quick refinement (< 1s)
- Dynamic updates (task cancellation, preference changes)

**Move Operators**:
- Time-shift: ±30/60 minutes
- (Future: resource swaps)

**Complexity**: O(iterations * tasks * neighbors) ≈ O(400n) with defaults

**Design Decision**: Complements exact solvers. Many real-world scenarios need fast incremental updates, not full re-solve.

---

### 3. Storage Layer (`app/storage/`)

#### `database.py` - PostgreSQL Persistence
**Purpose**: Long-term storage of tasks, resources, schedules

**Schema**:
- `tasks`: Task definitions with constraints
- `resources`: Resource availability
- `schedules`: Generated assignments with metadata

**Design Decision**: 
- Used PostgreSQL over NoSQL for ACID guarantees
- Schedules stored as JSON for flexibility
- Timestamps enable audit trails

---

#### `cache.py` - Redis Caching
**Purpose**: Fast lookup of recently computed schedules

**Strategy**:
- Key: Hash of (tasks + resources + constraints)
- Value: Serialized schedule
- TTL: 1 hour

**Why Redis**:
- Sub-millisecond lookups
- Automatic expiration
- Pub/sub for future real-time features

**Design Decision**: Cache invalidation via TTL avoids stale data. Hash-based keys ensure exact match lookups.

---

### 4. Models (`app/models/`)

#### `entities.py` - Core Domain Models
**Classes**: `Task`, `Resource`, `Assignment`

**Design Principles**:
- Pydantic for validation
- Immutable after creation
- Rich domain logic (e.g., `Task.overlaps()`)

**Trade-off**: Slightly verbose, but prevents invalid states and makes constraints explicit.

---

#### `constraints.py` - Constraint Abstractions
**Base Class**: `SoftConstraint` (abstract)

**Built-in Constraints**:
- `PreferredTimeWindow`
- `BalancedWorkload`
- `MinimizeGaps`

**Extensibility**: Users can subclass `SoftConstraint` for custom penalties.

**Design Decision**: Open-closed principle - system closed for modification, open for extension.

---

### 5. Graph Layer (`app/graph/conflict_graph.py`)
**Purpose**: Model task conflicts for heuristic guidance

**Algorithm**:
- Nodes: Tasks
- Edges: Conflicts (shared resources OR time constraints)

**Usage**:
- Degree heuristic (select high-degree tasks first)
- Conflict detection
- Future: graph coloring algorithms

**Complexity**: O(n^2) construction, O(1) degree lookup

**Design Decision**: Explicit graph representation makes conflict detection O(1) vs O(n) per check.

---

## Key Design Decisions

### 1. Hybrid Solver Strategy
**Decision**: Use backtracking for small instances, OR-Tools for large

**Rationale**:
- Backtracking gives optimal results on small problems
- OR-Tools scales but has overhead
- Threshold: 15 tasks (empirically derived)

**Alternative Considered**: Pure OR-Tools
- Rejected: 2-3x slower on small instances
- Rejected: Less educational value (black-box)

---

### 2. Caching Layer
**Decision**: Redis with hash-based keys and 1-hour TTL

**Rationale**:
- Scheduling requests often repeated (e.g., UI previews)
- Hash ensures exact match
- TTL prevents stale data

**Alternative Considered**: No caching
- Rejected: Wasteful re-computation
- Rejected: Poor UX for interactive tools

**Alternative Considered**: Longer TTL
- Rejected: Real-world schedules change frequently

---

### 3. Pluggable Constraints
**Decision**: Abstract `SoftConstraint` base class

**Rationale**:
- Different orgs have different preferences
- Avoid monolithic scoring function
- Easy to A/B test constraint weights

**Alternative Considered**: Fixed constraint list
- Rejected: Not extensible
- Rejected: Requires code changes for new constraints

---

### 4. Separate Re-optimization Endpoint
**Decision**: `/reoptimize` distinct from `/generate`

**Rationale**:
- Different use cases (initial vs incremental)
- Different algorithms (backtracking vs tabu)
- Explicit about warm-start requirement

**Alternative Considered**: Single endpoint with optional `initial_solution`
- Rejected: Less clear API contract
- Rejected: Harder to optimize separately

---

## Scalability Considerations

### Horizontal Scaling
**Current State**: Single-instance FastAPI + PostgreSQL + Redis

**Future**:
- Multiple API instances behind load balancer
- Redis cluster for cache
- PostgreSQL read replicas

**Bottlenecks**:
- Solver CPU-bound → scale API instances
- Cache hit rate → shard Redis by key prefix
- DB writes → batch inserts, async writes

---

### Algorithmic Scaling
**Current Limits**:
- Backtracking: ~15 tasks (seconds)
- OR-Tools: ~100 tasks (10s limit)
- Tabu search: ~50 tasks (1s refinement)

**Future Optimizations**:
- Constraint propagation (reduce domain sizes earlier)
- Parallelized backtracking (search tree partitioning)
- Heuristic decomposition (split problem into subproblems)

---

### Data Volume
**Current**: All schedules in memory during solving

**Future**:
- Streaming solvers (generate-on-demand)
- Approximate solvers (sacrifice optimality for speed)
- GPU-accelerated constraint checking

---

## Testing Strategy

### Unit Tests
- Pure function tests (e.g., `is_overlap()`)
- Constraint scoring validation
- Domain generation correctness

### Integration Tests
- Full solve workflows
- API endpoint contracts
- Database round-trips

### Edge Cases
- Empty schedules
- Infeasible constraints
- Resource conflicts

**Coverage Goal**: >80% line coverage, 100% critical path coverage

---

## Security Considerations

### Input Validation
- Pydantic schemas reject malformed data
- Task duration bounds (1 min - 24 hours)
- Resource ID existence checks

### Rate Limiting
**Future**: Redis-based rate limiter per API key

### Data Privacy
- No PII in task/resource names
- Schedule IDs use UUIDs (no sequential leaks)
- SQL injection prevention via ORM

---

## Observability

### Logging
**Framework**: Python `logging` with structured JSON

**Log Levels**:
- `DEBUG`: Solver iterations, domain sizes
- `INFO`: API requests, solver selection
- `WARNING`: Cache misses, slow solves
- `ERROR`: Infeasible schedules, DB failures

**Design Decision**: Structured logs enable log aggregation (e.g., ELK stack) in production.

---

### Metrics (Future)
- Solver latency percentiles (p50, p95, p99)
- Cache hit rate
- Infeasibility rate
- API error rates

---

## Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Language** | Python 3.11 | Rich ecosystem, readable, OR-Tools support |
| **API Framework** | FastAPI | Async, auto-docs, Pydantic validation |
| **Database** | PostgreSQL | ACID, JSON support, production-proven |
| **Cache** | Redis | Sub-ms latency, TTL, pub/sub future |
| **Solver Library** | OR-Tools | Industry-standard, scales to 100s of tasks |
| **Testing** | pytest | Rich fixtures, parameterization, coverage |
| **Deployment** | Docker | Reproducible, portable, easy CI/CD |

---

## Future Enhancements

1. **Web UI**: React dashboard for schedule visualization
2. **Real-time Updates**: WebSocket for live schedule changes
3. **Multi-tenancy**: Separate orgs with isolated data
4. **ML-based Heuristics**: Learn from past solves to guide search
5. **Distributed Solving**: Partition problem across workers
6. **Constraint Templates**: Pre-built constraint sets for common scenarios

---

## Interview Talking Points

When discussing this architecture in interviews:

1. **Trade-offs**: "I chose hybrid solvers because..."
2. **Scalability**: "Current system handles X, could scale to Y with..."
3. **Extensibility**: "New constraints added via subclassing, no core changes"
4. **Production-readiness**: "Includes caching, logging, error handling, testing"
5. **Algorithm Knowledge**: "Backtracking uses MRV heuristic because..."

---

**Last Updated**: Phase 6 - Interview-Ready Documentation
