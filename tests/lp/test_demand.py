"""
Tests for compute_demand() — covers US1 through US8 incrementally.
Phase 3 (T007): US1 scheduled-only arrival demand tests.
Phase 4 (T026): US2 departure demand tests (added below).
"""
import pytest

from src.lp.types import (
    AircraftType,
    DemandConfig,
    FlightSlotInput,
    DEFAULT_DEMAND_CONFIG,
)
from src.lp.demand import compute_demand


# ---------------------------------------------------------------------------
# US1: Hourly Demand from Flight Schedule (scheduled-only, arrivals)
# ---------------------------------------------------------------------------

def test_single_narrow_body_single_slot():
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 2})]
    result = compute_demand(scheduled)
    idx = result.operating_hours.index(10)
    assert result.demand_curve[idx] == 6       # 2 × 3
    assert result.arrival_demand_curve[idx] == 6
    assert result.departure_demand_curve[idx] == 0
    for i, h in enumerate(result.operating_hours):
        if h != 10:
            assert result.demand_curve[i] == 0


def test_wide_body_arrival_window_spans_two_slots():
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.WIDE_BODY: 1})]
    result = compute_demand(scheduled)
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    assert result.demand_curve[idx_10] == 5    # 1 × 5
    assert result.demand_curve[idx_11] == 5
    for i, h in enumerate(result.operating_hours):
        if h not in (10, 11):
            assert result.demand_curve[i] == 0


def test_cargo_arrival_window_spans_three_slots():
    scheduled = [FlightSlotInput(hour=8, arrival_counts={AircraftType.CARGO: 1})]
    result = compute_demand(scheduled)
    for h in (8, 9, 10):
        idx = result.operating_hours.index(h)
        assert result.demand_curve[idx] == 6   # 1 × 6
    for i, h in enumerate(result.operating_hours):
        if h not in (8, 9, 10):
            assert result.demand_curve[i] == 0


def test_multi_type_same_slot_sums_independently():
    scheduled = [FlightSlotInput(
        hour=12,
        arrival_counts={AircraftType.NARROW_BODY: 2, AircraftType.WIDE_BODY: 1},
    )]
    result = compute_demand(scheduled)
    idx_12 = result.operating_hours.index(12)
    idx_13 = result.operating_hours.index(13)
    assert result.demand_curve[idx_12] == 11   # 2×3 + 1×5
    assert result.demand_curve[idx_13] == 5    # only wide_body window continues


def test_multiple_slots_accumulate():
    scheduled = [
        FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1}),
        FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 2}),
    ]
    result = compute_demand(scheduled)
    idx_9 = result.operating_hours.index(9)
    idx_10 = result.operating_hours.index(10)
    assert result.demand_curve[idx_9] == 3     # 1×3 at slot 9
    assert result.demand_curve[idx_10] == 6    # 2×3 at slot 10


def test_empty_schedule_returns_all_zero_curve():
    result = compute_demand([])
    assert all(v == 0 for v in result.demand_curve)
    assert all(v == 0 for v in result.arrival_demand_curve)
    assert all(v == 0 for v in result.departure_demand_curve)
    assert result.feasible is True
    assert result.infeasible_slots == []
    assert result.operating_hours == list(range(5, 23))


def test_out_of_range_hour_before_start_raises():
    with pytest.raises(ValueError, match="hour"):
        compute_demand([FlightSlotInput(hour=4)])


def test_out_of_range_hour_at_end_raises():
    with pytest.raises(ValueError, match="hour"):
        compute_demand([FlightSlotInput(hour=23)])


def test_duplicate_hour_raises():
    with pytest.raises(ValueError, match="duplicate"):
        compute_demand([
            FlightSlotInput(hour=10),
            FlightSlotInput(hour=10),
        ])


def test_demand_result_operating_hours():
    result = compute_demand([])
    assert result.operating_hours == list(range(5, 23))
    assert len(result.demand_curve) == 18
    assert len(result.arrival_demand_curve) == 18
    assert len(result.departure_demand_curve) == 18


def test_demand_result_combined_equals_sum_of_subcurves():
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 3})]
    result = compute_demand(scheduled)
    for i in range(len(result.operating_hours)):
        assert result.demand_curve[i] == result.arrival_demand_curve[i] + result.departure_demand_curve[i]


def test_arrival_window_clips_at_operating_day_end():
    # CARGO at hour 21 with window=3 → would hit 21, 22, 23; but 23 is out of range
    scheduled = [FlightSlotInput(hour=21, arrival_counts={AircraftType.CARGO: 1})]
    result = compute_demand(scheduled)
    idx_21 = result.operating_hours.index(21)
    idx_22 = result.operating_hours.index(22)
    assert result.demand_curve[idx_21] == 6
    assert result.demand_curve[idx_22] == 6
    assert 23 not in result.operating_hours


def test_feasible_true_when_demand_within_pool():
    cfg = DemandConfig(pool_size=100)
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 5})]
    result = compute_demand(scheduled, config=cfg)
    assert result.feasible is True
    assert result.infeasible_slots == []


# ---------------------------------------------------------------------------
# US2: Independent Departure Demand (T026)
# ---------------------------------------------------------------------------

def test_departure_only_wide_body_backward_window():
    # 1 wide-body departure at 14:00 → backward window=2 → demand at slots 13 and 14
    scheduled = [FlightSlotInput(hour=14, departure_counts={AircraftType.WIDE_BODY: 1})]
    result = compute_demand(scheduled)
    idx_13 = result.operating_hours.index(13)
    idx_14 = result.operating_hours.index(14)
    assert result.demand_curve[idx_13] == 5    # 1 × 5
    assert result.demand_curve[idx_14] == 5
    assert result.departure_demand_curve[idx_13] == 5
    assert result.departure_demand_curve[idx_14] == 5
    assert all(v == 0 for v in result.arrival_demand_curve)
    for i, h in enumerate(result.operating_hours):
        if h not in (13, 14):
            assert result.demand_curve[i] == 0


def test_departure_only_narrow_body_backward_window_one_slot():
    scheduled = [FlightSlotInput(hour=10, departure_counts={AircraftType.NARROW_BODY: 3})]
    result = compute_demand(scheduled)
    idx_10 = result.operating_hours.index(10)
    assert result.demand_curve[idx_10] == 9    # 3 × 3, window=1
    for i, h in enumerate(result.operating_hours):
        if h != 10:
            assert result.demand_curve[i] == 0


def test_departure_only_cargo_backward_window_three_slots():
    # CARGO departure at 12:00, window=3 → demand at slots 10, 11, 12
    scheduled = [FlightSlotInput(hour=12, departure_counts={AircraftType.CARGO: 1})]
    result = compute_demand(scheduled)
    for h in (10, 11, 12):
        idx = result.operating_hours.index(h)
        assert result.demand_curve[idx] == 6   # 1 × 6
    for i, h in enumerate(result.operating_hours):
        if h not in (10, 11, 12):
            assert result.demand_curve[i] == 0


def test_arrival_and_departure_independent_no_cross_contamination():
    # 1 NB arrival at 10 (standard=3), 1 WB departure at 10 (standard=5)
    scheduled = [FlightSlotInput(
        hour=10,
        arrival_counts={AircraftType.NARROW_BODY: 1},
        departure_counts={AircraftType.WIDE_BODY: 1},
    )]
    result = compute_demand(scheduled)
    idx_9 = result.operating_hours.index(9)
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    # arrival at 10: window=1 → demand at 10 only
    assert result.arrival_demand_curve[idx_9] == 0
    assert result.arrival_demand_curve[idx_10] == 3
    assert result.arrival_demand_curve[idx_11] == 0
    # departure at 10: window=2 → demand at 9 and 10
    assert result.departure_demand_curve[idx_9] == 5
    assert result.departure_demand_curve[idx_10] == 5
    # combined
    assert result.demand_curve[idx_9] == 5
    assert result.demand_curve[idx_10] == 8    # 3 + 5
    assert result.demand_curve[idx_11] == 0


def test_departure_backward_window_clips_at_operating_day_start():
    # NB departure at 05:00 (first slot), window=1 → only slot 5; no pre-day slots
    scheduled = [FlightSlotInput(hour=5, departure_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled)
    idx_5 = result.operating_hours.index(5)
    assert result.demand_curve[idx_5] == 3
    for i, h in enumerate(result.operating_hours):
        if h != 5:
            assert result.demand_curve[i] == 0


def test_departure_backward_window_clips_silently_at_day_start():
    # CARGO departure at 06:00 with window=3 → backward: slots 4, 5, 6; slot 4 is pre-day → clip to 5, 6
    scheduled = [FlightSlotInput(hour=6, departure_counts={AircraftType.CARGO: 1})]
    result = compute_demand(scheduled)
    idx_5 = result.operating_hours.index(5)
    idx_6 = result.operating_hours.index(6)
    assert result.demand_curve[idx_5] == 6
    assert result.demand_curve[idx_6] == 6
    assert 4 not in result.operating_hours
    for i, h in enumerate(result.operating_hours):
        if h not in (5, 6):
            assert result.demand_curve[i] == 0


def test_departure_demand_curve_non_zero_arrival_all_zero():
    scheduled = [FlightSlotInput(hour=15, departure_counts={AircraftType.WIDE_BODY: 2})]
    result = compute_demand(scheduled)
    assert any(v > 0 for v in result.departure_demand_curve)
    assert all(v == 0 for v in result.arrival_demand_curve)


def test_same_slot_arrivals_and_departures_summed_independently():
    # Different staffing standards, should not contaminate each other
    cfg = DemandConfig(
        staffing_standards={AircraftType.NARROW_BODY: 3, AircraftType.WIDE_BODY: 5, AircraftType.CARGO: 6},
        departure_staffing_standards={AircraftType.NARROW_BODY: 4, AircraftType.WIDE_BODY: 5, AircraftType.CARGO: 6},
    )
    scheduled = [FlightSlotInput(
        hour=12,
        arrival_counts={AircraftType.NARROW_BODY: 1},
        departure_counts={AircraftType.NARROW_BODY: 1},
    )]
    result = compute_demand(scheduled, config=cfg)
    idx_12 = result.operating_hours.index(12)
    # arrival at 12 with standard=3, window=1
    assert result.arrival_demand_curve[idx_12] == 3
    # departure at 12 with departure_standard=4, window=1 → only slot 12
    assert result.departure_demand_curve[idx_12] == 4
    assert result.demand_curve[idx_12] == 7


def test_custom_departure_staffing_standard_does_not_affect_arrival():
    cfg = DemandConfig(
        departure_staffing_standards={
            AircraftType.NARROW_BODY: 10,
            AircraftType.WIDE_BODY: 5,
            AircraftType.CARGO: 6,
        }
    )
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled, config=cfg)
    idx_10 = result.operating_hours.index(10)
    # arrival uses staffing_standards (default 3), NOT departure_staffing_standards
    assert result.arrival_demand_curve[idx_10] == 3
    assert result.departure_demand_curve[idx_10] == 0
