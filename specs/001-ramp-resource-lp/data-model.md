# Data Model: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18
**Source file**: `src/lp/types.py`

---

## Entities

### AircraftType (Enum)

```python
class AircraftType(str, Enum):
    NARROW_BODY = "narrow_body"   # A320/B737 family — 3 workers/flight, 1h turnaround
    WIDE_BODY   = "wide_body"     # A330/B777/A350  — 5 workers/flight, 2h turnaround
    CARGO       = "cargo"         # B747F/B777F     — 6 workers/flight, 3h turnaround
```

**Canonical categories**: exactly three. No other categories are supported in this version.
**Validation rule**: Any `AircraftType` value outside this enum raises `ValueError`.

---

### FlightSlotInput

Represents the aircraft counts at one hourly operating slot, provided by the caller.

```python
@dataclass
class FlightSlotInput:
    hour: int                              # Clock hour (5..22 for 05:00–22:00)
    counts: dict[AircraftType, int]        # aircraft type → count in this slot
```

**Validation rules**:
- `hour` must be in `[operating_day_start, operating_day_end)`.
- All `counts` values must be ≥ 0.
- Missing aircraft types default to 0 (not an error).

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
    turnaround_slots: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 1,
            AircraftType.WIDE_BODY:   2,
            AircraftType.CARGO:       3,
        }
    )
    tolerance_minutes: int = 15            # ±V window; default ±15 min
    pool_size: int         = 9999          # R — workforce ceiling; set to a large number if unconstrained
    operating_day_start: int = 5           # 05:00
    operating_day_end:   int = 23          # 23:00 (exclusive; slots 5..22 = 18 slots)
```

**Validation rules**:
- `staffing_standards` must contain a value for all three `AircraftType` members.
- All staffing standard values must be ≥ 1.
- All turnaround slot values must be ≥ 1.
- `tolerance_minutes` must be ≥ 0 and < 60.
- `pool_size` must be ≥ 1.
- `operating_day_end > operating_day_start`.

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
    shift_starts: dict[int, float]    # clock_hour → fractional workers starting (pre-ceiling)
    shift_starts_rounded: dict[int, int]  # clock_hour → workers starting (post-ceil)
    daily_headcount: int              # Σ shift_starts_rounded — distinct shift assignments
    coverage_satisfied: bool          # True if all hourly demand met after rounding
    coverage_shortfalls: list[int]    # clock hours where rounded coverage fails (empty if satisfied)
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

Output of `comparison_report()` — FR-008 Table 7-style output.

```python
@dataclass
class ComparisonReport:
    hours: list[int]                  # clock hours covered
    scheduled_demand: list[int]       # demand curve from scheduled counts
    actual_demand: list[int]          # demand curve from actual counts
    gap_absolute: list[int]           # actual_demand[i] - scheduled_demand[i] per slot
    gap_pct_total: float              # (Σ actual - Σ scheduled) / Σ scheduled × 100
```

**Invariants**:
- All three lists have the same length.
- `gap_pct_total` ≈ 22.0 on a day similar to the Sahadevan Table 7 reference case (SC-003 proxy).

---

## Default Constants (src/lp/types.py)

```python
DEFAULT_STAFFING_STANDARDS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 3,
    AircraftType.WIDE_BODY:   5,
    AircraftType.CARGO:       6,
}

DEFAULT_TURNAROUND_SLOTS: dict[AircraftType, int] = {
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

```
FlightSlotInput ──(many)──→ compute_demand() ──→ DemandResult
DemandConfig    ──(config)──↗                        │
                                                      ↓
                                              schedule_shifts() ──→ ShiftSchedule
                                              ShiftConfig ──(config)──↗

DemandResult + ShiftSchedule ──→ identify_bottlenecks() ──→ BottleneckResult

FlightSlotInput (scheduled) + FlightSlotInput (actuals) ──→ comparison_report() ──→ ComparisonReport
```
