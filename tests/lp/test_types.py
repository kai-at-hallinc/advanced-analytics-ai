import pytest

from src.lp.types import (
    AircraftType,
    BottleneckResult,
    ComparisonReport,
    DemandConfig,
    DemandResult,
    FlightMovementInput,
    FlightSlotInput,
    ShiftSchedule,
)


def test_aircraft_type_enum_values():
    assert AircraftType.NARROW_BODY == "narrow_body"
    assert AircraftType.WIDE_BODY == "wide_body"
    assert AircraftType.CARGO == "cargo"
    assert AircraftType("narrow_body") is AircraftType.NARROW_BODY
    assert AircraftType("wide_body") is AircraftType.WIDE_BODY
    assert AircraftType("cargo") is AircraftType.CARGO


def test_demand_config_defaults_staffing_standards():
    cfg = DemandConfig()
    assert cfg.staffing_standards[AircraftType.NARROW_BODY] == 3
    assert cfg.staffing_standards[AircraftType.WIDE_BODY] == 5
    assert cfg.staffing_standards[AircraftType.CARGO] == 6


def test_demand_config_defaults_arrival_windows():
    cfg = DemandConfig()
    assert cfg.arrival_window_slots[AircraftType.NARROW_BODY] == 1
    assert cfg.arrival_window_slots[AircraftType.WIDE_BODY] == 2
    assert cfg.arrival_window_slots[AircraftType.CARGO] == 3


def test_demand_config_defaults_departure_staffing_standards():
    cfg = DemandConfig()
    assert cfg.departure_staffing_standards[AircraftType.NARROW_BODY] == 3
    assert cfg.departure_staffing_standards[AircraftType.WIDE_BODY] == 5
    assert cfg.departure_staffing_standards[AircraftType.CARGO] == 6


def test_demand_config_defaults_departure_windows():
    cfg = DemandConfig()
    assert cfg.departure_window_slots[AircraftType.NARROW_BODY] == 1
    assert cfg.departure_window_slots[AircraftType.WIDE_BODY] == 2
    assert cfg.departure_window_slots[AircraftType.CARGO] == 3


def test_demand_config_defaults_are_independent_instances():
    cfg1 = DemandConfig()
    cfg2 = DemandConfig()
    cfg1.staffing_standards[AircraftType.NARROW_BODY] = 99
    assert cfg2.staffing_standards[AircraftType.NARROW_BODY] == 3


def test_flight_slot_input_missing_type_defaults_to_zero():
    slot = FlightSlotInput(hour=10)
    assert slot.arrival_counts.get(AircraftType.NARROW_BODY, 0) == 0
    assert slot.arrival_counts.get(AircraftType.WIDE_BODY, 0) == 0
    assert slot.departure_counts.get(AircraftType.CARGO, 0) == 0


def test_flight_slot_input_negative_arrival_count_raises():
    with pytest.raises(ValueError):
        FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: -1})


def test_flight_slot_input_negative_departure_count_raises():
    with pytest.raises(ValueError):
        FlightSlotInput(hour=10, departure_counts={AircraftType.CARGO: -2})


def test_flight_slot_input_zero_count_is_valid():
    slot = FlightSlotInput(hour=10, arrival_counts={AircraftType.NARROW_BODY: 0})
    assert slot.arrival_counts[AircraftType.NARROW_BODY] == 0


def test_flight_movement_input_invalid_op_type_raises():
    with pytest.raises(ValueError):
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="X",
            scheduled_minutes=360,
        )


def test_flight_movement_input_out_of_range_scheduled_minutes_negative_raises():
    with pytest.raises(ValueError):
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=-1,
        )


def test_flight_movement_input_out_of_range_scheduled_minutes_too_large_raises():
    with pytest.raises(ValueError):
        FlightMovementInput(
            aircraft_type=AircraftType.NARROW_BODY,
            op_type="A",
            scheduled_minutes=1441,
        )


def test_flight_movement_input_valid_arrival():
    m = FlightMovementInput(
        aircraft_type=AircraftType.WIDE_BODY,
        op_type="A",
        scheduled_minutes=600,
        predicted_minutes=615,
    )
    assert m.op_type == "A"
    assert m.predicted_minutes == 615


def test_flight_movement_input_valid_departure_no_predicted():
    m = FlightMovementInput(
        aircraft_type=AircraftType.CARGO,
        op_type="D",
        scheduled_minutes=720,
    )
    assert m.predicted_minutes is None


def test_demand_result_curve_length_invariant():
    operating_hours = list(range(5, 23))
    n = len(operating_hours)
    result = DemandResult(
        demand_curve=[0] * n,
        arrival_demand_curve=[0] * n,
        departure_demand_curve=[0] * n,
        feasible=True,
        infeasible_slots=[],
        operating_hours=operating_hours,
    )
    assert len(result.demand_curve) == len(result.arrival_demand_curve)
    assert len(result.arrival_demand_curve) == len(result.departure_demand_curve)
    assert len(result.departure_demand_curve) == len(result.operating_hours)
    assert len(result.operating_hours) == 18


def test_demand_result_combined_curve_equals_sum():
    hours = list(range(5, 23))
    arr = list(range(18))
    dep = [i * 2 for i in range(18)]
    combined = [a + d for a, d in zip(arr, dep)]
    result = DemandResult(
        demand_curve=combined,
        arrival_demand_curve=arr,
        departure_demand_curve=dep,
        feasible=True,
        infeasible_slots=[],
        operating_hours=hours,
    )
    for i in range(18):
        assert result.demand_curve[i] == result.arrival_demand_curve[i] + result.departure_demand_curve[i]


def test_shift_schedule_daily_headcount_invariant():
    rounded = {5: 3, 6: 2, 7: 1, 8: 4}
    schedule = ShiftSchedule(
        shift_starts={h: float(v) for h, v in rounded.items()},
        shift_starts_rounded=rounded,
        daily_headcount=sum(rounded.values()),
        coverage_satisfied=True,
        coverage_shortfalls=[],
    )
    assert schedule.daily_headcount == sum(schedule.shift_starts_rounded.values())


def test_comparison_report_list_length_invariants():
    n = 18
    hours = list(range(5, 23))
    zeros = [0] * n
    report = ComparisonReport(
        hours=hours,
        scheduled_arrival_demand=zeros,
        predicted_arrival_demand=zeros,
        arrival_gap_absolute=zeros,
        arrival_gap_pct_total=0.0,
        scheduled_departure_demand=zeros,
        predicted_departure_demand=zeros,
        departure_gap_absolute=zeros,
        departure_gap_pct_total=0.0,
        total_scheduled_demand=zeros,
        total_predicted_demand=zeros,
    )
    for attr in (
        "scheduled_arrival_demand",
        "predicted_arrival_demand",
        "arrival_gap_absolute",
        "scheduled_departure_demand",
        "predicted_departure_demand",
        "departure_gap_absolute",
        "total_scheduled_demand",
        "total_predicted_demand",
    ):
        assert len(getattr(report, attr)) == len(report.hours)


def test_bottleneck_result_structure():
    br = BottleneckResult(bottleneck_hours=[7, 10], demand_at_bottleneck={7: 5, 10: 8})
    assert len(br.bottleneck_hours) == 2
    assert br.demand_at_bottleneck[7] == 5
    assert br.demand_at_bottleneck[10] == 8
