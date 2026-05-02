# Research: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-18 (updated 2026-05-02: dataset, timezone, actuals extraction)

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

| actuals provided | arrival_delay_flags / departure_delay_flags provided | Mode applied |
| ---------------- | ---------------------------------------------------- | ------------ |
| Yes | — | Actual counts used directly (per direction) |
| No | Yes | 20/80 heuristic on scheduled counts (per direction independently) |
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

## Decision 6: ICAO → LP Category Mapping and Pre-filtering Ownership

**Decision**: ICAO code mapping and operating-window pre-filtering are the caller's responsibility, implemented in `src/utils/efhk_loader.py` (constitution rule 5: data-loading utilities belong in `src/utils/`). The `src/lp/` module is strict: it raises `ValueError` for any `FlightSlotInput` with an out-of-range hour.

**Rationale**: Separation of concerns — the LP module solves the optimisation problem; the business layer handles airport-specific data preparation. The EFHK dataset has pre-dawn and post-midnight flights that fall outside the 05:00–23:00 Helsinki operating day. The LP must not silently discard them (would mask data quality issues); the loader must explicitly filter.

**ICAO → LP category mapping** (for the EFHK reference dataset):

| LP category | ICAO codes (present in dataset) | Rationale |
| ----------- | ------------------------------- | --------- |
| narrow_body | AT75, AT76, A319, A320, A321, A20N, A21N, B738, B38M, BCS3, E190 | Single-aisle aircraft ≤180 seats |
| wide_body | A332, A333, A359 | Twin-aisle aircraft >180 seats |
| cargo | Any type where `flight_type_iata = F` | Cargo designation overrides airframe class |

**Pre-filtering rule** (implemented in `business_problems/ramp_resource_lp.py`):

```python
from zoneinfo import ZoneInfo
hel = ZoneInfo("Europe/Helsinki")
helsinki_dt = utc_dt.astimezone(hel)
# keep only movements where 5 <= helsinki_dt.hour < 23
```

**Reference dataset** (updated 2026-05-02): `data/finavia_flights_efhk_20260327.csv` — 422 rows, 209 arrivals + 213 departures, EFHK 2026-03-27. Dominant aircraft type: AT76 (100 movements). 10 cargo movements (`flight_type_iata = F`). Timestamps in UTC (`Z` suffix); Helsinki is UTC+2 (EET) on this pre-DST date. `airline_iata` column is not populated in this file.

---

## Decision 7: UTC → Helsinki Timezone Conversion

**Decision**: Use `ZoneInfo("Europe/Helsinki")` from the Python standard library (`zoneinfo`, available in Python 3.9+) for all UTC → Helsinki local time conversions in the integration layer.

**Rationale**: A hardcoded offset (e.g., +02:00) would be correct for 2026-03-27 (before DST) but silently wrong for any date in EEST (UTC+3, after DST on March 29). IANA timezone-aware conversion is one line of code with no extra dependencies and is correct for all dates. The operating-window filter and slot assignment (`floor(helsinki_hour)`) both depend on this conversion.

**Alternatives considered**:
- Fixed `timedelta(hours=2)`: correct for this file, brittle for any other date — rejected.
- `pytz` / `dateutil`: external dependencies not needed when `zoneinfo` (stdlib) is available — rejected.

**Implementation pattern**:
```python
from zoneinfo import ZoneInfo
from datetime import datetime

HEL = ZoneInfo("Europe/Helsinki")

def utc_to_helsinki_hour(utc_iso: str) -> int:
    dt = datetime.fromisoformat(utc_iso.replace('Z', '+00:00'))
    return dt.astimezone(HEL).hour
```

---

## Decision 8: Actuals Extraction from CSV (Default-On)

**Decision**: The integration loader (`business_problems/ramp_resource_lp.py`) extracts `actual_arrival_time` and `actual_departure_time` from the CSV by default and builds `FlightMovementInput` records passed as `actual_movements` to `compute_demand()`. The caller may suppress this by passing `actual_movements=None` explicitly.

**Rationale**: The actuals are already embedded in the EFHK dataset — ignoring them by default would mean FR-011 tolerance-window reclassification is never exercised in the standard integration path. Default-on extraction ensures realistic slot assignment out of the box. Rows where the actual time column is null/empty are treated as on-time (i.e., `actual_minutes = None` → `FlightMovementInput.actual_minutes = None`).

**Null handling rule**:
```python
actual_minutes = None  # if actual_arrival_time / actual_departure_time is null or empty
# FlightMovementInput.actual_minutes = None → treated as on-time (no reclassification)
```

**Alternatives considered**:
- Opt-in flag: forces caller awareness but means FR-011 is never tested by default — rejected.
- Separate loader functions: unnecessary duplication for a single boolean switch — rejected.

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
| Out-of-range hour handling | `ValueError` raised by LP; caller pre-filters |
| ICAO mapping ownership | `business_problems/ramp_resource_lp.py` (not `src/lp/`) |
| Test dataset | `data/finavia_flights_efhk_20260327.csv` — 422 EFHK movements, 2026-03-27 (UTC timestamps, 16 cols, embedded actuals) |
| UTC→Helsinki conversion | `ZoneInfo("Europe/Helsinki")` — DST-aware, stdlib, no extra deps |
| Actuals extraction from CSV | Default-on; loader builds `FlightMovementInput` from actual time columns; null → treated as on-time |
