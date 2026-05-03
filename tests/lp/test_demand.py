"""
Tests for compute_demand() — covers US1 through US8 incrementally.
Phase 3 (T007): US1 scheduled-only arrival demand tests.
Phase 4 (T026): US2 departure demand tests (added below).
"""
import pytest

from src.lp.types import (
    AircraftType,
    DemandConfig,
    FlightMovementInput,
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
# US6: Capacity Constraint Enforcement (T017) — infeasible cases only
# (feasible=True case covered above by test_feasible_true_when_demand_within_pool)
# ---------------------------------------------------------------------------

def test_pool_exceeded_at_one_slot_marks_infeasible():
    # 3 narrow-body arrivals at hour 10 → demand = 3 × 3 = 9; pool_size=5 → infeasible
    cfg = DemandConfig(pool_size=5)
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 3})]
    result = compute_demand(scheduled, config=cfg)
    assert result.feasible is False
    assert 10 in result.infeasible_slots
    # Full demand curve is still returned
    idx = result.operating_hours.index(10)
    assert result.demand_curve[idx] == 9


def test_pool_exceeded_curve_still_returned():
    # Caller must be able to inspect magnitudes even when infeasible
    cfg = DemandConfig(pool_size=1)
    scheduled = [
        FlightSlotInput(hour=8, arrival_counts={AircraftType.WIDE_BODY: 2}),
        FlightSlotInput(hour=12, arrival_counts={AircraftType.NARROW_BODY: 1}),
    ]
    result = compute_demand(scheduled, config=cfg)
    assert result.feasible is False
    assert len(result.demand_curve) == len(result.operating_hours)
    assert all(v >= 0 for v in result.demand_curve)


def test_only_violating_slots_in_infeasible_list():
    # hour 10: 3 × 5 = 15 > pool=10 → infeasible
    # hour 14: 1 × 3 = 3 ≤ pool=10 → feasible
    cfg = DemandConfig(pool_size=10)
    scheduled = [
        FlightSlotInput(hour=10, arrival_counts={AircraftType.WIDE_BODY: 3}),
        FlightSlotInput(hour=14, arrival_counts={AircraftType.NARROW_BODY: 1}),
    ]
    result = compute_demand(scheduled, config=cfg)
    assert result.feasible is False
    assert 10 in result.infeasible_slots
    assert 14 not in result.infeasible_slots


def test_pool_size_zero_all_nonzero_slots_infeasible():
    # pool_size=0 means every slot with any demand is infeasible
    cfg = DemandConfig(pool_size=0)
    scheduled = [
        FlightSlotInput(hour=8, arrival_counts={AircraftType.NARROW_BODY: 1}),
        FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 1}),
    ]
    result = compute_demand(scheduled, config=cfg)
    assert result.feasible is False
    # Every hour with non-zero demand must be in infeasible_slots
    for i, h in enumerate(result.operating_hours):
        if result.demand_curve[i] > 0:
            assert h in result.infeasible_slots


def test_default_pool_size_is_unconstrained():
    # Default config (pool_size=math.inf) never triggers infeasibility
    import math
    scheduled = [
        FlightSlotInput(hour=h, arrival_counts={AircraftType.CARGO: 99})
        for h in range(5, 23)
    ]
    result = compute_demand(scheduled)
    assert result.feasible is True
    assert result.infeasible_slots == []
    assert DemandConfig().pool_size == math.inf


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


# ---------------------------------------------------------------------------
# US3: Delay-Adjusted Demand (T010)
# ---------------------------------------------------------------------------

def test_arrival_delay_flag_narrow_body_20_80_split():
    # 5 NB arrivals at hour 10 delayed: 20% (1 flight) stays at 10, 80% (4 flights) shifts to 11
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 5})]
    result = compute_demand(scheduled, arrival_delay_flags={AircraftType.NARROW_BODY: True})
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    assert result.arrival_demand_curve[idx_10] == 3    # round(5*0.2)*3 = 1*3
    assert result.arrival_demand_curve[idx_11] == 12   # round(5*0.8)*3 = 4*3
    assert all(result.departure_demand_curve[i] == 0 for i in range(len(result.operating_hours)))


def test_departure_delay_flag_wide_body_20_80_split():
    # 5 WB departures at hour 14 delayed: 1 on-time at 14, 4 delayed at 15
    # WB departure window=2 (backward); standard=5
    # On-time (1 dep at 14): demand at slots 13, 14 = 5 each
    # Delayed (4 deps at 15): demand at slots 14, 15 = 20 each
    scheduled = [FlightSlotInput(hour=14, departure_counts={AircraftType.WIDE_BODY: 5})]
    result = compute_demand(scheduled, departure_delay_flags={AircraftType.WIDE_BODY: True})
    idx_13 = result.operating_hours.index(13)
    idx_14 = result.operating_hours.index(14)
    idx_15 = result.operating_hours.index(15)
    assert result.departure_demand_curve[idx_13] == 5    # on-time only
    assert result.departure_demand_curve[idx_14] == 25   # 5 (on-time) + 20 (delayed)
    assert result.departure_demand_curve[idx_15] == 20   # delayed only
    assert all(result.arrival_demand_curve[i] == 0 for i in range(len(result.operating_hours)))


def test_mixed_arrival_delayed_and_on_time_same_slot():
    # 5 NB arrivals (delayed) + 5 WB arrivals (on-time) at hour 10
    # NB: 1 at slot 10, 4 at slot 11 (delay heuristic)
    # WB: 5 at slots 10 and 11 (window=2, on-time)
    scheduled = [FlightSlotInput(
        hour=10,
        arrival_counts={AircraftType.NARROW_BODY: 5, AircraftType.WIDE_BODY: 5},
    )]
    result = compute_demand(scheduled, arrival_delay_flags={AircraftType.NARROW_BODY: True})
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    # slot 10: NB 1*3=3 + WB 5*5=25 = 28
    assert result.arrival_demand_curve[idx_10] == 28
    # slot 11: NB delayed 4*3=12 + WB window 5*5=25 = 37
    assert result.arrival_demand_curve[idx_11] == 37


def test_arrival_delay_flag_does_not_affect_departure_counts():
    # NB arrivals delayed; NB departure counts must remain at scheduled values
    scheduled = [FlightSlotInput(
        hour=10,
        arrival_counts={AircraftType.NARROW_BODY: 5},
        departure_counts={AircraftType.NARROW_BODY: 5},
    )]
    result = compute_demand(scheduled, arrival_delay_flags={AircraftType.NARROW_BODY: True})
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    # Arrivals: 1 at 10 (20%), 4 at 11 (80%)
    assert result.arrival_demand_curve[idx_10] == 3
    assert result.arrival_demand_curve[idx_11] == 12
    # Departures: NB window=1 backward → slot 10 only (unchanged by arrival flag)
    assert result.departure_demand_curve[idx_10] == 15   # 5*3
    assert result.departure_demand_curve[idx_11] == 0    # no departure shift


def test_departure_delay_flag_does_not_affect_arrival_counts():
    # NB departures delayed; NB arrival counts must remain at scheduled values
    scheduled = [FlightSlotInput(
        hour=10,
        arrival_counts={AircraftType.NARROW_BODY: 5},
        departure_counts={AircraftType.NARROW_BODY: 5},
    )]
    result = compute_demand(scheduled, departure_delay_flags={AircraftType.NARROW_BODY: True})
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    # Arrivals: 5 NB on-time, window=1 → slot 10 only (unchanged by departure flag)
    assert result.arrival_demand_curve[idx_10] == 15   # 5*3
    assert result.arrival_demand_curve[idx_11] == 0
    # Departures: 1 on-time at 10 (window=1 → 3), 4 delayed at 11 (window=1 → 12)
    assert result.departure_demand_curve[idx_10] == 3
    assert result.departure_demand_curve[idx_11] == 12


def test_predicted_overrides_arrival_delay_flag():
    # predicted provided with 4 NB arrivals → delay heuristic on arrivals must not apply
    scheduled = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 5})]
    predicted = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 4})]
    result = compute_demand(
        scheduled,
        predicted=predicted,
        arrival_delay_flags={AircraftType.NARROW_BODY: True},
    )
    idx_10 = result.operating_hours.index(10)
    idx_11 = result.operating_hours.index(11)
    # predicted wins: 4 NB at 10, window=1 → demand=12; no delay split
    assert result.arrival_demand_curve[idx_10] == 12
    assert result.arrival_demand_curve[idx_11] == 0


def test_predicted_overrides_departure_delay_flag():
    # predicted provided with 3 WB departures → delay heuristic on departures must not apply
    scheduled = [FlightSlotInput(hour=14, departure_counts={AircraftType.WIDE_BODY: 5})]
    predicted = [FlightSlotInput(hour=14, departure_counts={AircraftType.WIDE_BODY: 3})]
    result = compute_demand(
        scheduled,
        predicted=predicted,
        departure_delay_flags={AircraftType.WIDE_BODY: True},
    )
    idx_13 = result.operating_hours.index(13)
    idx_14 = result.operating_hours.index(14)
    idx_15 = result.operating_hours.index(15)
    # predicted wins: 3 WB at 14, window=2 backward → slots 13, 14 = 15 each; no shift to 15
    assert result.departure_demand_curve[idx_13] == 15
    assert result.departure_demand_curve[idx_14] == 15
    assert result.departure_demand_curve[idx_15] == 0


# ---------------------------------------------------------------------------
# US8: On-Time Window Classification (T021) — predicted_movements
# ---------------------------------------------------------------------------


def test_on_time_movement_demand_at_scheduled_slot():
    # scheduled 09:00 (540 min), predicted 08:50 (530 min) — 10 min early, ≤15 min → on time
    # effective slot = floor(540/60) = 9
    movements = [
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=9 * 60,       # 540
            predicted_minutes=9 * 60 - 10,  # 530 = 08:50
        )
    ]
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled, predicted_movements=movements)
    idx_9 = result.operating_hours.index(9)
    assert result.arrival_demand_curve[idx_9] == 3  # 1 × 3 at scheduled slot 9


def test_late_movement_demand_at_predicted_slot():
    # scheduled 09:50 (590 min), predicted 10:20 (620 min) — 30 min late, >15 min → reclassified
    # effective slot = floor(620/60) = 10
    movements = [
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=9 * 60 + 50,   # 590 = 09:50
            predicted_minutes=10 * 60 + 20,   # 620 = 10:20
        )
    ]
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled, predicted_movements=movements)
    idx_9 = result.operating_hours.index(9)
    idx_10 = result.operating_hours.index(10)
    assert result.arrival_demand_curve[idx_9] == 0   # moved away from scheduled slot
    assert result.arrival_demand_curve[idx_10] == 3  # demand at predicted slot


def test_early_movement_demand_at_predicted_slot_not_reduced():
    # FR-010: early arrival at predicted slot; demand not reduced below standard
    # scheduled 09:00 (540 min), predicted 08:40 (520 min) — 20 min early, >15 min → reclassified
    # effective slot = floor(520/60) = 8
    movements = [
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=9 * 60,        # 540 = 09:00
            predicted_minutes=8 * 60 + 40,   # 520 = 08:40
        )
    ]
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled, predicted_movements=movements)
    idx_8 = result.operating_hours.index(8)
    idx_9 = result.operating_hours.index(9)
    assert result.arrival_demand_curve[idx_9] == 0   # moved from scheduled slot
    assert result.arrival_demand_curve[idx_8] == 3   # full standard, not reduced (FR-010)


def test_custom_tolerance_reclassifies_12min_late_flight():
    # tolerance=10; scheduled 09:50 (590 min), predicted 10:02 (602 min) — 12 min late >10 → reclassified
    # effective slot = floor(602/60) = 10
    movements = [
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=9 * 60 + 50,  # 590 = 09:50
            predicted_minutes=10 * 60 + 2,  # 602 = 10:02
        )
    ]
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1})]
    cfg = DemandConfig(tolerance_minutes=10)
    result = compute_demand(scheduled, predicted_movements=movements, config=cfg)
    idx_9 = result.operating_hours.index(9)
    idx_10 = result.operating_hours.index(10)
    assert result.arrival_demand_curve[idx_9] == 0
    assert result.arrival_demand_curve[idx_10] == 3


def test_departure_outside_window_anchored_at_predicted_slot():
    # WB departure scheduled 13:50 (830 min), predicted 15:10 (910 min) — 80 min late → reclassified
    # effective slot = floor(910/60) = 15; WB backward window=2 → demand at slots 14, 15
    movements = [
        FlightMovementInput(
            aircraft_type=AircraftType.WIDE_BODY,
            op_type="D",
            scheduled_minutes=13 * 60 + 50,  # 830 = 13:50
            predicted_minutes=15 * 60 + 10,  # 910 = 15:10
        )
    ]
    scheduled = [FlightSlotInput(hour=13, departure_counts={AircraftType.WIDE_BODY: 1})]
    result = compute_demand(scheduled, predicted_movements=movements)
    idx_14 = result.operating_hours.index(14)
    idx_15 = result.operating_hours.index(15)
    assert result.departure_demand_curve[idx_14] == 5  # backward window from reclassified slot 15
    assert result.departure_demand_curve[idx_15] == 5


def test_slot_level_predicted_no_reclassification():
    # Slot-level predicted (no predicted_movements) → no tolerance reclassification; used as-is
    scheduled = [FlightSlotInput(hour=9, arrival_counts={AircraftType.NARROW_BODY: 1})]
    predicted = [FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 1})]
    result = compute_demand(scheduled, predicted=predicted)
    idx_9 = result.operating_hours.index(9)
    idx_10 = result.operating_hours.index(10)
    assert result.arrival_demand_curve[idx_9] == 0   # predicted slot-level takes effect directly
    assert result.arrival_demand_curve[idx_10] == 3
