"""
Tests for schedule_shifts() — US4: Minimum Shift Schedule.
Phase 6 (T012).
"""
import pytest

from src.lp.types import (
    AircraftType,
    DemandResult,
    FlightSlotInput,
    ShiftConfig,
    DEFAULT_SHIFT_CONFIG,
)
from src.lp.demand import compute_demand
from src.lp.scheduling import schedule_shifts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _demand(curve: list[int], operating_hours: list[int] | None = None) -> DemandResult:
    """Build a feasible DemandResult from a raw demand curve."""
    if operating_hours is None:
        operating_hours = list(range(5, 5 + len(curve)))
    n = len(curve)
    return DemandResult(
        demand_curve=curve,
        arrival_demand_curve=curve[:],
        departure_demand_curve=[0] * n,
        feasible=True,
        infeasible_slots=[],
        operating_hours=operating_hours,
    )


# ---------------------------------------------------------------------------
# SC-002: LP beats naive upper bound
# ---------------------------------------------------------------------------

def test_uniform_demand_total_workers_below_naive():
    # 18 slots of demand-5 each; naive = 18 × 5 = 90 separate workers.
    # LP with shift_length=8 should produce far fewer shift starts.
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    assert schedule.daily_headcount < 90, (
        f"Expected LP to beat naive 90, got {schedule.daily_headcount}"
    )


def test_uniform_demand_coverage_satisfied():
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    assert schedule.coverage_satisfied is True
    assert schedule.coverage_shortfalls == []


# ---------------------------------------------------------------------------
# SC-006: All coverage constraints met post-rounding
# ---------------------------------------------------------------------------

def test_all_coverage_constraints_met_after_rounding():
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    hours = demand.operating_hours
    L = DEFAULT_SHIFT_CONFIG.shift_length
    n = len(hours)
    for t in range(n):
        workers = sum(
            schedule.shift_starts_rounded[hours[i]]
            for i in range(max(0, t - L + 1), t + 1)
        )
        assert workers >= demand.demand_curve[t], (
            f"Coverage shortfall at hour {hours[t]}: {workers} < {demand.demand_curve[t]}"
        )


def test_peak_morning_coverage_satisfied():
    # Realistic peak-morning profile across 18 operating hours (05:00–22:00)
    curve = [2, 4, 8, 12, 10, 8, 6, 5, 4, 3, 3, 3, 3, 3, 4, 5, 4, 2]
    demand = _demand(curve)
    schedule = schedule_shifts(demand)
    assert schedule.coverage_satisfied is True
    assert schedule.coverage_shortfalls == []


def test_bimodal_demand_coverage_satisfied():
    curve = [3, 8, 12, 8, 3, 2, 2, 2, 2, 2, 2, 2, 3, 8, 12, 8, 3, 2]
    demand = _demand(curve)
    schedule = schedule_shifts(demand)
    assert schedule.coverage_satisfied is True
    assert schedule.coverage_shortfalls == []


# ---------------------------------------------------------------------------
# Shift schedule structure invariants
# ---------------------------------------------------------------------------

def test_shift_starts_rounded_are_non_negative_integers():
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    for hour, count in schedule.shift_starts_rounded.items():
        assert isinstance(count, int), f"shift_starts_rounded[{hour}] is not int"
        assert count >= 0, f"shift_starts_rounded[{hour}] is negative"


def test_daily_headcount_equals_sum_of_rounded_starts():
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    assert schedule.daily_headcount == sum(schedule.shift_starts_rounded.values())


def test_shift_starts_keys_match_operating_hours():
    demand = _demand([5] * 18)
    schedule = schedule_shifts(demand)
    assert set(schedule.shift_starts.keys()) == set(demand.operating_hours)
    assert set(schedule.shift_starts_rounded.keys()) == set(demand.operating_hours)


# ---------------------------------------------------------------------------
# ValueError when demand is infeasible
# ---------------------------------------------------------------------------

def test_raises_value_error_when_demand_infeasible():
    infeasible = DemandResult(
        demand_curve=[5] * 18,
        arrival_demand_curve=[5] * 18,
        departure_demand_curve=[0] * 18,
        feasible=False,
        infeasible_slots=[5, 6],
        operating_hours=list(range(5, 23)),
    )
    with pytest.raises(ValueError):
        schedule_shifts(infeasible)


# ---------------------------------------------------------------------------
# Custom ShiftConfig
# ---------------------------------------------------------------------------

def test_custom_shift_length_4():
    demand = _demand([5] * 18)
    config = ShiftConfig(shift_length=4)
    schedule = schedule_shifts(demand, config=config)
    assert schedule.coverage_satisfied is True
    assert schedule.daily_headcount < 90


def test_via_compute_demand_pipeline():
    # End-to-end: compute_demand → schedule_shifts
    scheduled = [
        FlightSlotInput(hour=h, arrival_counts={AircraftType.NARROW_BODY: 2})
        for h in range(7, 13)
    ]
    demand = compute_demand(scheduled)
    assert demand.feasible
    schedule = schedule_shifts(demand)
    assert schedule.coverage_satisfied is True
    assert schedule.daily_headcount >= 0
