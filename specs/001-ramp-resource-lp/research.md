# Research: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18

All NEEDS CLARIFICATION items from Technical Context are resolved. Findings consolidated below.

---

## Decision 1: LP Solver — Google OR-Tools GLOP

**Decision**: Use `ortools` Python package, `GLOP` linear solver for both stages.

**Rationale**: GLOP is Google's production LP solver, handles constraint matrices of this scale
(18 slots × 3 types) in microseconds, produces dual values (shadow prices) natively for bottleneck
identification (FR-009), and detects infeasibility via `INFEASIBLE` solve status (FR-004).
Deterministic output satisfies Principle IV (Reproducibility).

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

## Decision 2: Stage 1 Demand Formula — Arrival + Departure Additive Model

**Decision**: Implement demand as the sum of two independent forward/backward window computations.

**Source**: `business_problems/ramp_resource_minimization_formulation.md` (mathematical reference).

**Revised demand formula**:

```
r_j = arr_j + dep_j

arr_j = Σ_i  Σ_{k=0}^{W_arr_i - 1}  arrivals(i, j−k) · c_arr_i
          (forward-looking: arrival at slot j−k contributes to slots j−k … j−k+W_arr_i−1)

dep_j = Σ_i  Σ_{k=0}^{W_dep_i - 1}  departures(i, j+k) · c_dep_i
          (backward-looking: departure at slot j+k contributes to slots j … j+k)
          (equivalently: departure at slot m contributes to slots max(day_start, m−W_dep_i+1) … m)
```

**Arrival window** (FR-001): covers arrival handling only (unloading, cleaning, catering). Forward-looking from arrival slot.

**Departure window** (FR-013): covers departure preparation only (fuelling, boarding, checks). Backward-looking ending at departure slot. Window clipped silently at `operating_day_start` — no error raised.

**Original Sahadevan constraints (5)–(9)** retained for arrival side:

| Constraint | Formula | Purpose |
| ---------- | ------- | ------- |
| (5) | `r_j = arr_j + dep_j` | Total workers at slot j (extended) |
| (6) | `n_ij = s_ij · (1 − 0.8·d_i)` | Delay-adjusted arrival count (20/80 split) |
| (7) | `z_ij = x_ij · y_ij · n_ij` | Resource allocation flag |
| (8) | `r_j ≤ R` | Workforce pool ceiling |
| (9) | `\|t_ij − j\| ≤ V` | On-time tolerance window (arrivals and departures) |

**Input modes** (arrivals and departures each independently support 3 modes per FR-003/FR-015):

| actuals provided | delay_flags provided | Mode applied |
| ---------------- | -------------------- | ------------ |
| Yes | — | Actual counts used directly |
| No | Yes | 20/80 heuristic on scheduled counts |
| No | No | Scheduled counts used unchanged |

**Infeasibility**: When `r_j > R` for any slot `j`, detected pre-solve; structured error identifies offending slots.

---

## Decision 3: Stage 2 LP — Textbook Shift-Start Formulation

**Decision**: Implement the Post Office Problem shift-start LP.

**Source**: `business_problems/ramp_resource_minimization_formulation.md` §5.

**Formulation** (unchanged — Stage 2 consumes `DemandResult.demand_curve` regardless of source):
```
min  Σ_{t} x_t
s.t. Σ_{i=max(0, t-L+1)}^{t} x_i  ≥  d_t   for all t in [0, H-1]
     x_t ≥ 0
```
Solve LP relaxation with GLOP, then apply `math.ceil` to each `x_t`. Re-verify all coverage constraints post-rounding (SC-006).

**Daily headcount**: `Σ x_t` counts each worker exactly once (FR-006, SC-004).

**Bottleneck identification**: `ct.dual_value()` on binding coverage constraints after OPTIMAL solve. Slot is bottleneck when dual value > 0 (FR-009).

---

## Decision 4: Python Data Types

**Decision**: Python `dataclasses` for structured inputs/outputs; `enum.Enum` for aircraft type; `typing` for all annotations.

**Rationale**: Typed, IDE-friendly, zero external dependencies. `dataclasses.field(default_factory=...)` for mutable defaults.

**Key type changes from departure extension**:
```python
@dataclass
class FlightSlotInput:
    hour: int
    arrival_counts: dict[AircraftType, int] = field(default_factory=dict)   # renamed from counts
    departure_counts: dict[AircraftType, int] = field(default_factory=dict)  # NEW

@dataclass
class DemandConfig:
    staffing_standards: dict[AircraftType, int]          # arrival workers per flight
    arrival_window_slots: dict[AircraftType, int]        # renamed from turnaround_slots
    departure_staffing_standards: dict[AircraftType, int] # NEW — defaults match arrival
    departure_window_slots: dict[AircraftType, int]      # NEW — defaults match arrival
    tolerance_minutes: int = 15
    pool_size: int = 9999
    operating_day_start: int = 5
    operating_day_end: int = 23
```

**`ComparisonReport` extended** (FR-008 now covers both directions):

```python
@dataclass
class ComparisonReport:
    hours: list[int]
    # Arrival direction
    scheduled_arrival_demand: list[int]
    actual_arrival_demand: list[int]
    arrival_gap_absolute: list[int]
    arrival_gap_pct_total: float
    # Departure direction
    scheduled_departure_demand: list[int]
    actual_departure_demand: list[int]
    departure_gap_absolute: list[int]
    departure_gap_pct_total: float
    # Combined
    total_scheduled_demand: list[int]
    total_actual_demand: list[int]
```

---

## Decision 5: Module Layout

**Decision**: `src/lp/` new module with four files (types, demand, scheduling, analysis). Unchanged from original decision.

**Existing asset to preserve**: `business_problems/ramp_resource_minimization_formulation.md`. New `business_problems/ramp_resource_lp.py` calls `src/lp/`.

---

## Resolved Items

| Item | Resolution |
| ---- | ---------- |
| LP solver | OR-Tools GLOP |
| Interface type | Python module, typed function signatures |
| Arrival staffing defaults | narrow-body 3, wide-body 5, cargo 6 |
| Departure staffing defaults | Same as arrival — narrow-body 3, wide-body 5, cargo 6 |
| Arrival window defaults | narrow-body 1h, wide-body 2h, cargo 3h (arrival handling only) |
| Departure window defaults | Same as arrival — narrow-body 1h, wide-body 2h, cargo 3h |
| Departure window boundary | Clipped silently at operating day start |
| Delay/actuals pattern | Same 3-mode pattern for both arrivals and departures |
| Departure tolerance classification | Same ±15 min window; departure slot reclassified when outside |
| FR-008 scope | Extended to cover both arrival and departure gaps separately |
| SC-003 | Reframed: system faithfully reflects input differences; no empirical threshold |
| Operating day | 05:00–23:00 (18 slots) |
| Aircraft categories | narrow-body, wide-body, cargo only |
| Integer rounding | `math.ceil` post-solve, not MIP |
| Bottleneck identification | Dual values from GLOP coverage constraints |
