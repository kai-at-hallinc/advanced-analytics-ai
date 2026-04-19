# Quickstart: Ramp Resource LP

**Feature**: `001-ramp-resource-lp` | **Date**: 2026-04-19

---

## Installation

```bash
# Install the lp optional dependency group
pip install -e ".[lp]"
# or, if you haven't installed the package yet:
pip install -e ".[lp,dev]"
```

This installs `ortools` alongside the package. No other non-standard dependencies are required.

---

## Minimal Example

```python
from src.lp import (
    AircraftType, FlightSlotInput, compute_demand, schedule_shifts,
    identify_bottlenecks, comparison_report
)

# --- Define a simple one-day schedule (05:00–10:00 excerpt) ---
scheduled = [
    FlightSlotInput(hour=5,  arrival_counts={AircraftType.NARROW_BODY: 2}),
    FlightSlotInput(hour=6,  arrival_counts={AircraftType.NARROW_BODY: 4, AircraftType.WIDE_BODY: 1}),
    FlightSlotInput(hour=7,  arrival_counts={AircraftType.NARROW_BODY: 3, AircraftType.WIDE_BODY: 2}),
    FlightSlotInput(hour=8,  arrival_counts={AircraftType.NARROW_BODY: 2, AircraftType.CARGO: 1}),
    FlightSlotInput(hour=9,  arrival_counts={AircraftType.NARROW_BODY: 1}),
    # ... add remaining hours up to 22 for a full-day run
]

# --- Stage 1: compute demand curve (schedule-only, no delays) ---
demand = compute_demand(scheduled)
print("Demand curve:", demand.demand_curve)
print("Feasible:", demand.feasible)

# --- Stage 2: find minimum shift schedule ---
schedule = schedule_shifts(demand)
print("Daily headcount:", schedule.daily_headcount)
print("Shift starts:", schedule.shift_starts_rounded)

# --- Identify bottleneck hours ---
bottlenecks = identify_bottlenecks(demand, schedule)
print("Bottleneck hours:", bottlenecks.bottleneck_hours)
```

---

## With Delay Flags

```python
# Mark wide-body arrivals as delayed — applies 20% / 80% split to arrival counts
demand_delayed = compute_demand(
    scheduled,
    arrival_delay_flags={AircraftType.WIDE_BODY: True},
)
print("Delay-adjusted demand:", demand_delayed.demand_curve)

# Mark wide-body departures as delayed independently
demand_dep_delayed = compute_demand(
    scheduled,
    departure_delay_flags={AircraftType.WIDE_BODY: True},
)
```

---

## With Actual Arrival Counts

```python
# Provide actual counts — used directly, overrides delay heuristic
actuals = [
    FlightSlotInput(hour=5,  arrival_counts={AircraftType.NARROW_BODY: 2}),
    FlightSlotInput(hour=6,  arrival_counts={AircraftType.NARROW_BODY: 3, AircraftType.WIDE_BODY: 2}),  # one wide-body shifted to 06:00
    # ...
]

demand_actual = compute_demand(scheduled, actuals=actuals)

# Compare scheduled vs actual demand (direction-level report)
report = comparison_report(scheduled, actuals)
print(f"Scheduled total: {sum(report.total_scheduled_demand)}")
print(f"Actual total:    {sum(report.total_actual_demand)}")
print(f"Arrival gap:   {report.arrival_gap_pct_total:.1f}%")
print(f"Departure gap: {report.departure_gap_pct_total:.1f}%")
```

---

## Infeasibility Handling

```python
from src.lp import DemandConfig

# Set a tight workforce pool
config = DemandConfig(pool_size=10)
demand_tight = compute_demand(scheduled, config=config)

if not demand_tight.feasible:
    print("Infeasible at hours:", demand_tight.infeasible_slots)
else:
    schedule = schedule_shifts(demand_tight)
```

---

## Notebook

A full validation notebook with plots is in:
```
notebooks/planning/ramp_resource_lp.ipynb
```

The notebook imports from `src/lp` and demonstrates all nine user stories against the EFHK reference dataset.

---

## Running Tests

```bash
pytest tests/lp/ -v
```

All tests are in `tests/lp/` mirroring the `src/lp/` module structure.
