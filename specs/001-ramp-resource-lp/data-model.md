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
    demand_curve: list[int]           # workers required at each slot; index 0 = operating_day_start hour
    feasible: bool                    # False if any slot exceeds pool_size
    infeasible_slots: list[int]       # clock hours where demand > pool_size (empty if feasible)
    operating_hours: list[int]        # clock hours covered, e.g. [5, 6, ..., 22]
```

**Invariants**:

- `len(demand_curve) == len(operating_hours)`.
- When `feasible=True`, `infeasible_slots` is empty.
- All `demand_curve` values ≥ 0.
- `demand_curve[i]` is the sum of arrival contributions and departure contributions at that slot — neither is derived from the other.

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

Output of `comparison_report()` — FR-008 Table 7-style output covering both movement directions.

```python
@dataclass
class ComparisonReport:
    hours: list[int]                         # clock hours covered

    # Arrival direction
    scheduled_arrival_demand: list[int]      # arrival demand curve from scheduled counts
    actual_arrival_demand: list[int]         # arrival demand curve from actual counts
    arrival_gap_absolute: list[int]          # actual_arrival[i] - scheduled_arrival[i] per slot
    arrival_gap_pct_total: float             # (Σ actual_arr - Σ sched_arr) / Σ sched_arr × 100

    # Departure direction
    scheduled_departure_demand: list[int]    # departure demand curve from scheduled counts
    actual_departure_demand: list[int]       # departure demand curve from actual counts
    departure_gap_absolute: list[int]        # actual_dep[i] - scheduled_dep[i] per slot
    departure_gap_pct_total: float           # (Σ actual_dep - Σ sched_dep) / Σ sched_dep × 100

    # Combined
    total_scheduled_demand: list[int]        # scheduled_arrival_demand[i] + scheduled_departure_demand[i]
    total_actual_demand: list[int]           # actual_arrival_demand[i] + actual_departure_demand[i]
```

**Invariants**:

- All list fields have the same length as `hours`.
- `arrival_gap_absolute[i] = actual_arrival_demand[i] - scheduled_arrival_demand[i]`
- `departure_gap_absolute[i] = actual_departure_demand[i] - scheduled_departure_demand[i]`
- `total_scheduled_demand[i] = scheduled_arrival_demand[i] + scheduled_departure_demand[i]`
- `total_actual_demand[i] = actual_arrival_demand[i] + actual_departure_demand[i]`

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
FlightSlotInput ──(many)──> compute_demand() ──> DemandResult
DemandConfig    ──(config)──|                        |
                                                     |
                                              schedule_shifts() ──> ShiftSchedule
                                              ShiftConfig ──(config)──|

DemandResult + ShiftSchedule ──> identify_bottlenecks() ──> BottleneckResult

FlightSlotInput (scheduled) + FlightSlotInput (actuals) ──> comparison_report() ──> ComparisonReport
```
