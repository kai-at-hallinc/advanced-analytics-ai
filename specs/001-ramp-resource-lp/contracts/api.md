# Public API Contract: src/lp

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18
**Module**: `src/lp/__init__.py` (re-exports all four functions)

All types are defined in `src/lp/types.py`. See [data-model.md](../data-model.md) for full field definitions.

---

## compute_demand

**Location**: `src/lp/demand.py`
**Spec coverage**: FR-001, FR-002, FR-003, FR-004, FR-007, FR-010, FR-011

```python
def compute_demand(
    scheduled: list[FlightSlotInput],
    actuals: list[FlightSlotInput] | None = None,
    delay_flags: dict[AircraftType, bool] | None = None,
    config: DemandConfig = DEFAULT_DEMAND_CONFIG,
) -> DemandResult:
```

### Behaviour

| Inputs supplied | Mode applied |
|-----------------|-------------|
| `actuals` provided | FR-003: use actual counts directly as `a_ij`; no 20/80 split |
| `delay_flags` only (no `actuals`) | FR-002: apply `n_ij = s_ij · (1 − 0.8·d_i)` per delayed type |
| Neither `actuals` nor `delay_flags` | Scheduled counts used unchanged |

### Demand computation per slot (FR-001)

For each operating hour `j` in `[operating_day_start, operating_day_end)`:

```
r_j = Σ_i  Σ_{k=0}^{W_i - 1}  arrivals_at(i, j−k) · c_i
```

where `arrivals_at(i, j−k)` is the (delay-adjusted or actual) count of type `i` that arrived at slot `j−k` and are still on stand at slot `j` (multi-slot turnaround, FR-001).

### On-time classification (FR-011)

When `actuals` are provided at a finer-than-slot granularity (minute-level `t_ij`):
- `|t_ij − scheduled_j| ≤ tolerance_minutes` → on time, resources at `scheduled_j`
- Otherwise → resources at `actual_arrival_slot(t_ij)`

When only `delay_flags` are used, the 80% shifted portion is attributed to the next operating slot.

### Early arrivals (FR-010)

An early arrival (actual slot < scheduled slot and outside tolerance) is treated as a full-demand arrival at its actual slot. The resource count at the actual slot is not reduced below the standard `c_i`.

### Workforce pool enforcement (FR-004)

After computing all `r_j`, the function checks `r_j ≤ pool_size` for every slot. If any slot violates this:
- `feasible = False`
- `infeasible_slots` = list of violating clock hours
- The function still returns the full `demand_curve` (so the caller can inspect magnitudes).

### Raises

- `ValueError`: invalid `FlightSlotInput` (negative count, out-of-range hour, duplicate hour).
- `ValueError`: `DemandConfig` validation failure (see data-model.md).

---

## schedule_shifts

**Location**: `src/lp/scheduling.py`
**Spec coverage**: FR-005, FR-006, SC-002, SC-006

```python
def schedule_shifts(
    demand: DemandResult,
    config: ShiftConfig = DEFAULT_SHIFT_CONFIG,
) -> ShiftSchedule:
```

### Behaviour

Solves the textbook shift-start LP:
```
min  Σ_t x_t
s.t. Σ_{i=max(0, t−L+1)}^{t} x_i  ≥  d_t   for all t
     x_t ≥ 0
```

Using OR-Tools GLOP (`pywraplp.Solver.CreateSolver('GLOP')`).

Post-solve: each `x_t` is rounded up via `math.ceil` to produce `shift_starts_rounded`. Coverage constraints are re-verified on the rounded values (SC-006).

`daily_headcount = Σ shift_starts_rounded` counts each worker exactly once (FR-006, SC-004).

### Raises

- `ValueError`: `demand.feasible` is `False` — caller must handle infeasibility before scheduling.
- `RuntimeError`: GLOP solver returns non-OPTIMAL status (unexpected; should not occur on valid input).

---

## identify_bottlenecks

**Location**: `src/lp/analysis.py`
**Spec coverage**: FR-009, US8

```python
def identify_bottlenecks(
    demand: DemandResult,
    schedule: ShiftSchedule,
) -> BottleneckResult:
```

### Behaviour

A slot is a **bottleneck** when the number of workers on duty equals demand exactly (no surplus). This is equivalent to a positive dual value on that slot's coverage constraint in the Stage 2 LP.

Implementation: compare active worker count at each hour against `demand.demand_curve`. Hours where `active_workers == demand` are bottlenecks.

Returns each bottleneck hour labelled with its clock time and the binding demand value (FR-009, US8 AC-3).

---

## comparison_report

**Location**: `src/lp/analysis.py`
**Spec coverage**: FR-008, SC-003

```python
def comparison_report(
    scheduled: list[FlightSlotInput],
    actuals: list[FlightSlotInput],
    config: DemandConfig = DEFAULT_DEMAND_CONFIG,
) -> ComparisonReport:
```

### Behaviour

Calls `compute_demand(scheduled)` and `compute_demand(actuals=actuals)` separately, then computes per-slot and aggregate gap figures. The aggregate `gap_pct_total` is expected to be ≥ 15% on realistic Finavia data (SC-003).

Produces the Table 7-style report described in FR-008: scheduled manpower vs actual manpower per slot.

---

## Module Re-exports (`src/lp/__init__.py`)

```python
from .types import (
    AircraftType,
    FlightSlotInput,
    DemandConfig,
    DemandResult,
    ShiftConfig,
    ShiftSchedule,
    BottleneckResult,
    ComparisonReport,
    DEFAULT_DEMAND_CONFIG,
    DEFAULT_SHIFT_CONFIG,
    DEFAULT_STAFFING_STANDARDS,
    DEFAULT_TURNAROUND_SLOTS,
    DEFAULT_OPERATING_HOURS,
)
from .demand import compute_demand
from .scheduling import schedule_shifts
from .analysis import identify_bottlenecks, comparison_report

__all__ = [
    "AircraftType", "FlightSlotInput", "DemandConfig", "DemandResult",
    "ShiftConfig", "ShiftSchedule", "BottleneckResult", "ComparisonReport",
    "DEFAULT_DEMAND_CONFIG", "DEFAULT_SHIFT_CONFIG",
    "compute_demand", "schedule_shifts", "identify_bottlenecks", "comparison_report",
]
```
