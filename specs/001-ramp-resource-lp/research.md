# Research: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18

All NEEDS CLARIFICATION items from Technical Context are resolved. Findings consolidated below.

---

## Decision 1: LP Solver — Google OR-Tools GLOP

**Decision**: Use `ortools` Python package, `GLOP` linear solver for both stages.

**Rationale**: GLOP is Google's production LP solver, handles constraint matrices of this scale (18 slots × 3 types) in microseconds, produces dual values (shadow prices) natively for bottleneck identification (FR-009), and detects infeasibility via `INFEASIBLE` solve status (FR-004). Deterministic output satisfies Principle IV (Reproducibility).

**Alternatives considered**:
- PuLP + CBC: original recommendation, replaced by user preference for OR-Tools.
- `scipy.optimize.linprog`: no integer support, no named constraints, no dual values, rejected.
- Pyomo: heavier dependency, not needed at this scale.

**OR-Tools LP API pattern**:
```python
from ortools.linear_solver import pywraplp
solver = pywraplp.Solver.CreateSolver('GLOP')
x = solver.NumVar(0.0, solver.infinity(), 'x')
ct = solver.Constraint(demand, solver.infinity())
ct.SetCoefficient(x, 1.0)
solver.Minimize(solver.Sum([x]))
status = solver.Solve()
# status == pywraplp.Solver.INFEASIBLE → FR-004 path
# ct.dual_value() after OPTIMAL → shadow price for FR-009
```

**pyproject.toml change**: Add `lp = ["ortools"]` optional dependency group.

---

## Decision 2: Stage 1 LP — Sahadevan Formulation

**Decision**: Implement Sahadevan constraints (5)–(9) with multi-slot turnaround extension.

**Source**: `business_problems/ramp_resource_minimization_formulation.md` (already fully documented).

**Key constraints**:

| Constraint | Formula | Purpose |
|------------|---------|---------|
| (5) | `r_j = Σ_i z_ij · c_i · x_ij` | Total workers at slot j |
| (6) | `n_ij = s_ij · (1 − 0.8·d_i)` | Delay-adjusted count (20/80 split) |
| (7) | `z_ij = x_ij · y_ij · n_ij` | Resource allocation flag |
| (8) | `r_j ≤ R` | Workforce pool ceiling |
| (9) | `|t_ij − j| ≤ V` | On-time tolerance window |

**Multi-slot extension** (from clarification): A single aircraft arrival at slot `j` contributes `c_i` workers at slots `j, j+1, ..., j + W_i − 1` where `W_i` is the turnaround window for type `i`. This means `r_j` sums contributions from arrivals in the current and prior `W_i − 1` slots.

**Demand modes** (from clarification):
- `actuals` provided → use directly as `a_ij`, no 20/80 split.
- `delay_flags` provided, no actuals → apply constraint (6).
- Neither provided → scheduled counts used unchanged.

**Infeasibility**: When `r_j > R` for any slot `j`, solver returns `INFEASIBLE`; the plan is to detect this pre-solve and raise a structured error identifying the offending slots.

---

## Decision 3: Stage 2 LP — Textbook Shift-Start Formulation

**Decision**: Implement the Post Office Problem shift-start LP (LP_operations_research.pdf §3.5).

**Source**: `business_problems/ramp_resource_minimization_formulation.md` §5.

**Formulation**:
```
min  Σ_{t} x_t
s.t. Σ_{i=max(0, t-L+1)}^{t} x_i  ≥  d_t   for all t in [0, H-1]
     x_t ≥ 0
```
Solve LP relaxation with GLOP, then apply `math.ceil` to each `x_t`. Re-verify all coverage constraints hold post-rounding (SC-006).

**Daily headcount**: `Σ x_t` (shift-starts) counts each worker exactly once (FR-006, SC-004).

**Bottleneck identification**: After solve, dual variable `ct.dual_value()` on binding coverage constraints identifies bottleneck slots for FR-009. A slot is a bottleneck when its dual value > 0 (i.e., relaxing that constraint's RHS by 1 reduces the objective by 1).

---

## Decision 4: Python Data Types

**Decision**: Python `dataclasses` for structured inputs/outputs; `enum.Enum` for aircraft type; `typing` for all annotations.

**Rationale**: Typed, IDE-friendly, zero external dependencies (Principle IV, pyproject.toml stays clean). `dataclasses.field(default_factory=...)` used for mutable defaults.

**Key types sketched**:
```python
from enum import Enum
from dataclasses import dataclass, field

class AircraftType(Enum):
    NARROW_BODY = "narrow_body"
    WIDE_BODY   = "wide_body"
    CARGO       = "cargo"

@dataclass
class FlightSlotInput:
    hour: int                               # 0-indexed from operating_day_start (e.g., 5 = 05:00)
    counts: dict[AircraftType, int] = field(default_factory=dict)

@dataclass
class DemandConfig:
    staffing_standards: dict[AircraftType, int]  # workers per flight
    turnaround_slots:   dict[AircraftType, int]  # hours of stand occupancy
    tolerance_minutes:  int = 15
    pool_size:          int = 999               # R — effectively unbounded if not set
    operating_day_start: int = 5               # 05:00
    operating_day_end:   int = 23              # 23:00 (exclusive last slot)
```

---

## Decision 5: Module Layout

**Decision**: `src/lp/` new module with four files (types, demand, scheduling, analysis).

**Rationale**: Keeps Stage 1, Stage 2, and analysis logic independently testable. Constitution Principle I requires one module per domain; OR scheduling is distinct from the classical planning already in `src/planning/`.

**Existing asset to preserve**: `business_problems/ramp_resource_minimization_formulation.md` — kept as the mathematical reference. New `business_problems/ramp_resource_lp.py` will instantiate defaults and call `src/lp/`.

---

## Resolved NEEDS CLARIFICATION Items

All items from Technical Context were fully resolved by spec clarifications and existing formulation doc. No external research tasks were needed beyond what was already documented in `business_problems/ramp_resource_minimization_formulation.md`.

| Item | Resolution |
|------|-----------|
| LP solver | OR-Tools GLOP |
| Interface type | Python module, typed function signatures |
| Staffing defaults | narrow-body 3, wide-body 5, cargo 6 |
| Turnaround defaults | narrow-body 1h, wide-body 2h, cargo 3h |
| Delay/actuals unification | Single `compute_demand()` with optional params |
| Operating day | 05:00–23:00 (18 slots, 0-indexed as hours 5–22) |
| Aircraft categories | narrow-body, wide-body, cargo only (superjumbo removed) |
| Integer rounding | `math.ceil` post-solve, not MIP |
| Bottleneck identification | Dual values from GLOP coverage constraints |
