"""
Tests for identify_bottlenecks() — US9.
Phase 11 (T023): bottleneck hour identification.
"""
import pytest

from src.lp.types import (
    BottleneckResult,
    DemandResult,
    ShiftConfig,
    ShiftSchedule,
)
from src.lp.analysis import identify_bottlenecks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _demand(curve: list[int], start: int = 5) -> DemandResult:
    """Build a minimal DemandResult from a demand curve."""
    n = len(curve)
    hours = list(range(start, start + n))
    return DemandResult(
        demand_curve=curve,
        arrival_demand_curve=curve,
        departure_demand_curve=[0] * n,
        feasible=True,
        infeasible_slots=[],
        operating_hours=hours,
    )


def _schedule(rounded: dict[int, int]) -> ShiftSchedule:
    """Build a ShiftSchedule from a rounded starts dict."""
    return ShiftSchedule(
        shift_starts={h: float(v) for h, v in rounded.items()},
        shift_starts_rounded=rounded,
        daily_headcount=sum(rounded.values()),
        coverage_satisfied=True,
        coverage_shortfalls=[],
    )


# shift_length=1 makes active_workers_at_hour[h] == shift_starts_rounded[h],
# eliminating window-arithmetic ambiguity in the tests below.
CFG1 = ShiftConfig(shift_length=1, operating_hours=list(range(5, 23)))


# ---------------------------------------------------------------------------
# US9: Bottleneck Hour Identification (T023)
# ---------------------------------------------------------------------------


def test_exact_coverage_flagged_as_bottleneck():
    # demand=5 at hour 7; 5 workers start at 7 with shift_length=1 → active=5 == demand
    hours = list(range(5, 23))
    curve = [0] * 18
    curve[2] = 5  # index 2 = hour 7
    demand = _demand(curve)
    schedule = _schedule({h: 0 for h in hours} | {7: 5})
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert 7 in result.bottleneck_hours
    assert result.demand_at_bottleneck[7] == 5


def test_surplus_not_flagged_as_bottleneck():
    # demand=5 at hour 7; 8 workers start → active=8 > demand=5 → no bottleneck
    hours = list(range(5, 23))
    curve = [0] * 18
    curve[2] = 5
    demand = _demand(curve)
    schedule = _schedule({h: 0 for h in hours} | {7: 8})
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert 7 not in result.bottleneck_hours


def test_bottleneck_labelled_with_correct_demand_value():
    hours = list(range(5, 23))
    curve = [0] * 18
    curve[5] = 10  # index 5 = hour 10
    demand = _demand(curve)
    schedule = _schedule({h: 0 for h in hours} | {10: 10})
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert 10 in result.bottleneck_hours
    assert result.demand_at_bottleneck[10] == 10


def test_empty_bottleneck_list_when_all_hours_have_surplus():
    # Every hour has 1 extra worker → no bottlenecks
    hours = list(range(5, 23))
    curve = [3] * 18
    demand = _demand(curve)
    schedule = _schedule({h: 4 for h in hours})  # 4 > 3 everywhere
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert result.bottleneck_hours == []
    assert result.demand_at_bottleneck == {}


def test_multiple_bottleneck_hours():
    # Hours 5 and 10 are tight; hour 8 has surplus
    hours = list(range(5, 23))
    curve = [0] * 18
    curve[0] = 4   # hour 5
    curve[3] = 6   # hour 8
    curve[5] = 9   # hour 10
    demand = _demand(curve)
    schedule = _schedule({h: 0 for h in hours} | {5: 4, 8: 7, 10: 9})
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert 5 in result.bottleneck_hours
    assert 8 not in result.bottleneck_hours   # 7 > 6 → surplus
    assert 10 in result.bottleneck_hours
    assert result.demand_at_bottleneck[5] == 4
    assert result.demand_at_bottleneck[10] == 9


def test_zero_demand_hours_not_flagged():
    # Hours with demand=0 and 0 active workers are not bottlenecks
    hours = list(range(5, 23))
    curve = [0] * 18
    demand = _demand(curve)
    schedule = _schedule({h: 0 for h in hours})
    result = identify_bottlenecks(demand, schedule, CFG1)
    assert result.bottleneck_hours == []


def test_independent_test_from_spec():
    # Spec: hour 7 has workers == demand; hour 10 has workers > demand + 2
    # Using shift_length=8 (default) with a hand-crafted schedule
    hours = list(range(5, 23))
    n = len(hours)
    h7_idx = hours.index(7)
    h10_idx = hours.index(10)

    curve = [0] * n
    curve[h7_idx] = 5
    curve[h10_idx] = 3
    demand = _demand(curve)

    # With shift_length=1 for simplicity: active at h == shift_starts_rounded[h]
    rounded = {h: 0 for h in hours}
    rounded[7] = 5   # exact coverage → bottleneck
    rounded[10] = 6  # demand=3, active=6 → surplus → not bottleneck
    schedule = _schedule(rounded)

    result = identify_bottlenecks(demand, schedule, CFG1)
    assert result.bottleneck_hours == [7]
    assert result.demand_at_bottleneck == {7: 5}
    assert 10 not in result.bottleneck_hours
