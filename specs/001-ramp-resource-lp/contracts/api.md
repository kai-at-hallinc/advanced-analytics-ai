# Public API Contract: src/lp

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18
**Module**: `src/lp/__init__.py` (re-exports all four functions)

All types are defined in `src/lp/types.py`. See [data-model.md](../data-model.md) for full field definitions.

---

## compute_demand

**Location**: `src/lp/demand.py`
**Spec coverage**: FR-001, FR-002, FR-003, FR-004, FR-007, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015

```python
def compute_demand(
    scheduled: list[FlightSlotInput],
    actuals: list[FlightSlotInput] | None = None,
    arrival_delay_flags: dict[AircraftType, bool] | None = None,
    departure_delay_flags: dict[AircraftType, bool] | None = None,
    actual_movements: list[FlightMovementInput] | None = None,
    config: DemandConfig = DEFAULT_DEMAND_CONFIG,
) -> DemandResult:
```

### Input mode precedence (arrivals and departures evaluated independently, FR-003 / FR-015)

| Arrivals | Departures | Mode applied |
| -------- | ---------- | ----------- |
| `actual_movements` provided | `actual_movements` provided | Per-flight tolerance classification against `scheduled_dt`/`actual_dt` |
| `actuals.arrival_counts` | `actuals.departure_counts` | Slot-level actuals used directly; no tolerance reclassification |
| `arrival_delay_flags` | `departure_delay_flags` | 20/80 heuristic: `n_ij = s_ij · (1 − 0.8·d_i)` per flagged type |
| neither | neither | Scheduled counts used unchanged |

`actual_movements` takes precedence over `actuals` for the direction(s) it covers. `actuals` takes precedence over delay flags per direction.

### Demand computation per slot (FR-001, FR-013)

For each operating hour `j` in `[operating_day_start, operating_day_end)`:

$$
\begin{align}
r_j &= \text{arr}_j + \text{dep}_j \\
\\
\text{arr}_j &= \sum_{i} \sum_{k=0}^{W_{\text{arr}_i} - 1} \text{arrivals}(i, j-k) \cdot c_{\text{arr}_i} \\
&\quad \text{(forward-looking: arrival at slot } j-k \text{ contributes to slots } j-k \ldots j-k+W_{\text{arr}_i}-1\text{)} \\
\\
\text{dep}_j &= \sum_{i} \sum_{k=0}^{W_{\text{dep}_i} - 1} \text{departures}(i, j+k) \cdot c_{\text{dep}_i} \\
&\quad \text{(backward-looking: departure at slot } j+k \text{ contributes to slots } j \ldots j+k\text{)} \\
&\quad \text{(equivalently: departure at slot } m \text{ contributes to slots } \max(\text{day\_start}, m-W_{\text{dep}_i}+1) \ldots m\text{)}
\end{align}
$$

### Variable definitions

- **$k$**: window offset index. For arrivals, $k \in [0, W_{\text{arr}_i} - 1]$ spreads an arrival's resource impact forward across multiple consecutive slots. For departures, $k \in [0, W_{\text{dep}_i} - 1]$ spreads a departure's prep work backward.
- **$W_{\text{arr}_i}$**: arrival window size (slots) for aircraft type $i$ — how long resources are needed after landing.
- **$W_{\text{dep}_i}$**: departure window size (slots) for aircraft type $i$ — how long resources are needed before departure.
- **$c_{\text{arr}_i}$, $c_{\text{dep}_i}$**: resource coefficients per movement (e.g., personnel count per aircraft).

Arrival demand and departure demand are computed independently; neither is derived from the other (FR-013).

### On-time classification (FR-011)

Tolerance classification is only available when `actual_movements: list[FlightMovementInput]` is provided. Each `FlightMovementInput` carries `scheduled_dt` and `actual_dt` in minutes-from-midnight.

- `|actual_dt − scheduled_dt| ≤ tolerance_minutes` → on time; resources attributed to `floor(scheduled_dt / 60)`
- Otherwise → resources attributed to `floor(actual_dt / 60)`

Applies to both arrival (`op_type='A'`) and departure (`op_type='D'`) movements (FR-011).

When only slot-level `actuals: list[FlightSlotInput]` are provided (no `actual_movements`), flights are already pre-aggregated to their actual slot — no tolerance reclassification is applied.

### Early arrivals (FR-010)

An early arrival (actual slot < scheduled slot and outside tolerance) is treated as a full-demand arrival at its actual slot. The resource count is not reduced below the standard `c_arr_i`.

### Departure window boundary clipping

When a departure's backward preparation window extends before `operating_day_start`, the window is silently clipped to `operating_day_start`. No error is raised.

### Workforce pool enforcement (FR-004)

After computing all `r_j`, the function checks `r_j ≤ pool_size` for every slot. If any slot violates:

- `feasible = False`
- `infeasible_slots` = list of violating clock hours
- The full `demand_curve` is still returned (caller can inspect magnitudes).

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

$$
\begin{align}
\text{min} \quad &\sum_{t} x_t \\
\text{s.t.} \quad &\sum_{i=\max(0, t-L+1)}^{t} x_i \geq d_t \quad \forall t \\
&x_t \geq 0
\end{align}
$$

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

Calls `compute_demand(scheduled)` and `compute_demand(actuals=actuals)` separately, decomposing results into arrival and departure demand components. Computes per-slot and aggregate gap figures for each direction independently (FR-008).

Produces a direction-level comparison report (see `ComparisonReport` in data-model.md for full field layout):

- Per-slot arrival gap: `actual_arrival_demand[i] - scheduled_arrival_demand[i]`
- Per-slot departure gap: `actual_departure_demand[i] - scheduled_departure_demand[i]`
- Aggregate `arrival_gap_pct_total` and `departure_gap_pct_total` as percentages of scheduled totals
- Combined `total_scheduled_demand` and `total_actual_demand` per slot

The report faithfully reflects whatever difference exists in the inputs (SC-003). No empirical threshold is asserted. Per-aircraft-type breakdown is a planned extension (spec.md §Assumptions, extension 9).

---

## Module Re-exports (`src/lp/__init__.py`)

```python
from .types import (
    AircraftType,
    FlightSlotInput,
    FlightMovementInput,
    DemandConfig,
    DemandResult,
    ShiftConfig,
    ShiftSchedule,
    BottleneckResult,
    ComparisonReport,
    DEFAULT_DEMAND_CONFIG,
    DEFAULT_SHIFT_CONFIG,
    DEFAULT_STAFFING_STANDARDS,
    DEFAULT_ARRIVAL_WINDOW_SLOTS,
    DEFAULT_DEPARTURE_STAFFING_STANDARDS,
    DEFAULT_DEPARTURE_WINDOW_SLOTS,
    DEFAULT_OPERATING_HOURS,
)
from .demand import compute_demand
from .scheduling import schedule_shifts
from .analysis import identify_bottlenecks, comparison_report

__all__ = [
    "AircraftType", "FlightSlotInput", "FlightMovementInput", "DemandConfig", "DemandResult",
    "ShiftConfig", "ShiftSchedule", "BottleneckResult", "ComparisonReport",
    "DEFAULT_DEMAND_CONFIG", "DEFAULT_SHIFT_CONFIG",
    "compute_demand", "schedule_shifts", "identify_bottlenecks", "comparison_report",
]
```
