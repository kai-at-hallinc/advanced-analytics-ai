# Data Model: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18
**Source file**: `src/lp/types.py`

---

## Entities

### AircraftType (Enum)

```python
class AircraftType(str, Enum):
    NARROW_BODY = "narrow_body"   # A320/B737 family — 3 workers/flight, 1h window
    WIDE_BODY   = "wide_body"     # A330/B777/A350  — 5 workers/flight, 2h window
    CARGO       = "cargo"         # B747F/B777F     — 6 workers/flight, 3h window
```

**Canonical categories**: exactly three. No other categories are supported in this version.
**Validation rule**: Any `AircraftType` value outside this enum raises `ValueError`.

---

### FlightSlotInput

Represents the aircraft counts at one hourly operating slot, provided by the caller.

```python
@dataclass
class FlightSlotInput:
    hour: int                                   # Clock hour (5..22 for 05:00–22:00)
    arrival_counts: dict[AircraftType, int] = field(default_factory=dict)    # aircraft type → arriving count
    departure_counts: dict[AircraftType, int] = field(default_factory=dict)  # aircraft type → departing count
```

**Validation rules**:

- `hour` must be in `[operating_day_start, operating_day_end)`.
- All `arrival_counts` and `departure_counts` values must be ≥ 0.
- Missing aircraft types in either dict default to 0 (not an error).
- A slot may contain arrivals only, departures only, or both.

**Uniqueness**: One `FlightSlotInput` per hour. Duplicate hours in the same list are an error.

---

### FlightMovementInput

Represents a single flight movement with minute-level timestamps. Used when tolerance-window slot reclassification (FR-011) is needed. Pass a list of these as `predicted_movements` to `compute_demand()`.

```python
@dataclass
class FlightMovementInput:
    aircraft_type: AircraftType
    op_type: Literal['A', 'D']       # 'A' = arrival, 'D' = departure
    scheduled_minutes: int           # minutes from midnight (scheduled time)
    predicted_minutes: int | None = None  # minutes from midnight (predicted time); None → use scheduled_minutes
```

**Validation rules**:

- `scheduled_minutes` must be in `[operating_day_start * 60, operating_day_end * 60)`.
- `predicted_minutes` if provided: departure pre-window clipping applies silently if it falls before `operating_day_start * 60`; an out-of-window predicted arrival is silently ignored (effective slot not in `hour_to_idx`).
- `aircraft_type` must be a valid `AircraftType` member.
- `op_type` must be `'A'` or `'D'`; any other value raises `ValueError`.

**Slot assignment**: `floor(scheduled_minutes / 60)` or `floor(predicted_minutes / 60)` after tolerance check.

---

### DemandConfig

All configurable parameters for Stage 1.

```python
@dataclass
class DemandConfig:
    staffing_standards: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 3,
            AircraftType.WIDE_BODY:   5,
            AircraftType.CARGO:       6,
        }
    )
    arrival_window_slots: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 1,
            AircraftType.WIDE_BODY:   2,
            AircraftType.CARGO:       3,
        }
    )
    departure_staffing_standards: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 3,
            AircraftType.WIDE_BODY:   5,
            AircraftType.CARGO:       6,
        }
    )
    departure_window_slots: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 1,
            AircraftType.WIDE_BODY:   2,
            AircraftType.CARGO:       3,
        }
    )
    tolerance_minutes: int = 15            # ±V window; default ±15 min (applies to both arrivals and departures)
    pool_size: int         = 9999          # R — workforce ceiling; set to a large number if unconstrained
    operating_day_start: int = 5           # 05:00
    operating_day_end:   int = 23          # 23:00 (exclusive; slots 5..22 = 18 slots)
```

**Validation rules**:

- `staffing_standards` and `departure_staffing_standards` must each contain a value for all three `AircraftType` members.
- All staffing standard values must be ≥ 1.
- All `arrival_window_slots` and `departure_window_slots` values must be ≥ 1.
- `tolerance_minutes` must be ≥ 0 and < 60.
- `pool_size` must be ≥ 1.
- `operating_day_end > operating_day_start`.

**Departure window boundary**: when a departure's backward window extends before `operating_day_start`, the window is clipped silently to `operating_day_start`. No error is raised.

---

### DemandResult

Output of `compute_demand()` — Stage 1 result.

```python
@dataclass
class DemandResult:
    demand_curve: list[int]                # combined workers per slot (arrival + departure)
    arrival_demand_curve: list[int]        # arrival component only; index 0 = operating_day_start
    departure_demand_curve: list[int]      # departure component only; index 0 = operating_day_start
    feasible: bool                         # False if any slot exceeds pool_size
    infeasible_slots: list[int]            # clock hours where demand > pool_size (empty if feasible)
    operating_hours: list[int]             # clock hours covered, e.g. [5, 6, ..., 22]
```

**Invariants**:

- `len(demand_curve) == len(arrival_demand_curve) == len(departure_demand_curve) == len(operating_hours)`.
- `demand_curve[i] == arrival_demand_curve[i] + departure_demand_curve[i]` for all `i`.
- When `feasible=True`, `infeasible_slots` is empty.
- All values in all three curves ≥ 0.
- Neither `arrival_demand_curve` nor `departure_demand_curve` is derived from the other (FR-013).

---

### ShiftConfig

Parameters for Stage 2.

```python
@dataclass
class ShiftConfig:
    shift_length: int    = 8           # L — hours per shift; default 8
    operating_hours: list[int] = field(default_factory=lambda: list(range(5, 23)))
```

**Validation rules**:

- `shift_length` ≥ 1.
- `len(operating_hours)` ≥ `shift_length` (otherwise no valid shift start exists).

---

### ShiftSchedule

Output of `schedule_shifts()` — Stage 2 result.

```python
@dataclass
class ShiftSchedule:
    shift_starts: dict[int, float]        # clock_hour → fractional workers starting (pre-ceiling)
    shift_starts_rounded: dict[int, int]  # clock_hour → workers starting (post-ceil)
    daily_headcount: int                  # Σ shift_starts_rounded — distinct shift assignments
    coverage_satisfied: bool              # True if all hourly demand met after rounding
    coverage_shortfalls: list[int]        # clock hours where rounded coverage fails (empty if satisfied)
```

**Invariants**:

- `daily_headcount == sum(shift_starts_rounded.values())`.
- When `coverage_satisfied=True`, `coverage_shortfalls` is empty.
- `daily_headcount < (peak_demand × operating_hours ÷ shift_length)` for any non-trivially flat demand (SC-002).

---

### BottleneckResult

Output of `identify_bottlenecks()`.

```python
@dataclass
class BottleneckResult:
    bottleneck_hours: list[int]            # clock hours where dual value > 0
    demand_at_bottleneck: dict[int, int]   # clock_hour → binding demand value
```

**Invariants**:

- Each `bottleneck_hours` entry has a corresponding `demand_at_bottleneck` entry.
- Hours not in `bottleneck_hours` have surplus workers (active count > demand).

---

### ComparisonReport

Output of `comparison_report()` — FR-008 direction-level output covering arrival and departure gaps independently.

**Scope**: Direction-level aggregates only. Per-aircraft-type breakdown is planned extension 9 (see spec.md §Assumptions).

```python
@dataclass
class ComparisonReport:
    hours: list[int]                         # clock hours covered

    # Arrival direction
    scheduled_arrival_demand: list[int]       # arrival demand curve from scheduled counts
    predicted_arrival_demand: list[int]       # arrival demand curve from predicted counts
    arrival_gap_absolute: list[int]           # predicted_arrival[i] - scheduled_arrival[i] per slot
    arrival_gap_pct_total: float              # (Σ predicted_arr - Σ sched_arr) / Σ sched_arr × 100

    # Departure direction
    scheduled_departure_demand: list[int]     # departure demand curve from scheduled counts
    predicted_departure_demand: list[int]     # departure demand curve from predicted counts
    departure_gap_absolute: list[int]         # predicted_dep[i] - scheduled_dep[i] per slot
    departure_gap_pct_total: float            # (Σ predicted_dep - Σ sched_dep) / Σ sched_dep × 100

    # Combined
    total_scheduled_demand: list[int]         # scheduled_arrival_demand[i] + scheduled_departure_demand[i]
    total_predicted_demand: list[int]         # predicted_arrival_demand[i] + predicted_departure_demand[i]
```

**Invariants**:

- All list fields have the same length as `hours`.
- `arrival_gap_absolute[i] = predicted_arrival_demand[i] - scheduled_arrival_demand[i]`
- `departure_gap_absolute[i] = predicted_departure_demand[i] - scheduled_departure_demand[i]`
- `total_scheduled_demand[i] = scheduled_arrival_demand[i] + scheduled_departure_demand[i]`
- `total_predicted_demand[i] = predicted_arrival_demand[i] + predicted_departure_demand[i]`

---

## Default Constants (`src/lp/types.py`)

```python
DEFAULT_STAFFING_STANDARDS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 3,
    AircraftType.WIDE_BODY:   5,
    AircraftType.CARGO:       6,
}

DEFAULT_ARRIVAL_WINDOW_SLOTS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 1,
    AircraftType.WIDE_BODY:   2,
    AircraftType.CARGO:       3,
}

DEFAULT_DEPARTURE_STAFFING_STANDARDS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 3,
    AircraftType.WIDE_BODY:   5,
    AircraftType.CARGO:       6,
}

DEFAULT_DEPARTURE_WINDOW_SLOTS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 1,
    AircraftType.WIDE_BODY:   2,
    AircraftType.CARGO:       3,
}

DEFAULT_OPERATING_HOURS: list[int] = list(range(5, 23))  # 05:00–22:00 inclusive (18 slots)
DEFAULT_TOLERANCE_MINUTES: int = 15
DEFAULT_SHIFT_LENGTH: int = 8
```

---

## Entity Relationship Summary

```text
FlightSlotInput     ──(many)──> compute_demand() ──> DemandResult
FlightMovementInput ──(many)──>      |
DemandConfig    ──(config)──|                        |
                                                     |
                                              schedule_shifts() ──> ShiftSchedule
                                              ShiftConfig ──(config)──|

DemandResult + ShiftSchedule ──> identify_bottlenecks() ──> BottleneckResult

FlightSlotInput (scheduled) + FlightSlotInput (predicted) ──> comparison_report() ──> ComparisonReport
```
