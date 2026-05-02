from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class AircraftType(str, Enum):
    NARROW_BODY = "narrow_body"
    WIDE_BODY = "wide_body"
    CARGO = "cargo"


@dataclass
class FlightSlotInput:
    hour: int
    arrival_counts: dict[AircraftType, int] = field(default_factory=dict)
    departure_counts: dict[AircraftType, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for counts_dict in (self.arrival_counts, self.departure_counts):
            for ac_type, count in counts_dict.items():
                if count < 0:
                    raise ValueError(
                        f"Negative count {count} for {ac_type} in FlightSlotInput(hour={self.hour})"
                    )


@dataclass
class FlightMovementInput:
    aircraft_type: AircraftType
    op_type: Literal["A", "D"]
    scheduled_minutes: int
    actual_minutes: int | None = None

    def __post_init__(self) -> None:
        if self.op_type not in ("A", "D"):
            raise ValueError(f"op_type must be 'A' or 'D', got {self.op_type!r}")
        if not (0 <= self.scheduled_minutes < 24 * 60):
            raise ValueError(
                f"scheduled_minutes {self.scheduled_minutes} out of valid range [0, 1440)"
            )


@dataclass
class DemandConfig:
    staffing_standards: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 3,
            AircraftType.WIDE_BODY: 5,
            AircraftType.CARGO: 6,
        }
    )
    arrival_window_slots: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 1,
            AircraftType.WIDE_BODY: 2,
            AircraftType.CARGO: 3,
        }
    )
    departure_staffing_standards: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 3,
            AircraftType.WIDE_BODY: 5,
            AircraftType.CARGO: 6,
        }
    )
    departure_window_slots: dict[AircraftType, int] = field(
        default_factory=lambda: {
            AircraftType.NARROW_BODY: 1,
            AircraftType.WIDE_BODY: 2,
            AircraftType.CARGO: 3,
        }
    )
    tolerance_minutes: int = 15
    pool_size: int = 9999
    operating_day_start: int = 5
    operating_day_end: int = 23


@dataclass
class DemandResult:
    demand_curve: list[int]
    arrival_demand_curve: list[int]
    departure_demand_curve: list[int]
    feasible: bool
    infeasible_slots: list[int]
    operating_hours: list[int]


@dataclass
class ShiftConfig:
    shift_length: int = 8
    operating_hours: list[int] = field(default_factory=lambda: list(range(5, 23)))


@dataclass
class ShiftSchedule:
    shift_starts: dict[int, float]
    shift_starts_rounded: dict[int, int]
    daily_headcount: int
    coverage_satisfied: bool
    coverage_shortfalls: list[int]


@dataclass
class BottleneckResult:
    bottleneck_hours: list[int]
    demand_at_bottleneck: dict[int, int]


@dataclass
class ComparisonReport:
    hours: list[int]
    scheduled_arrival_demand: list[int]
    actual_arrival_demand: list[int]
    arrival_gap_absolute: list[int]
    arrival_gap_pct_total: float
    scheduled_departure_demand: list[int]
    actual_departure_demand: list[int]
    departure_gap_absolute: list[int]
    departure_gap_pct_total: float
    total_scheduled_demand: list[int]
    total_actual_demand: list[int]


# --- Module-level constants (defined after classes) ---

DEFAULT_STAFFING_STANDARDS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 3,
    AircraftType.WIDE_BODY: 5,
    AircraftType.CARGO: 6,
}

DEFAULT_ARRIVAL_WINDOW_SLOTS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 1,
    AircraftType.WIDE_BODY: 2,
    AircraftType.CARGO: 3,
}

DEFAULT_DEPARTURE_STAFFING_STANDARDS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 3,
    AircraftType.WIDE_BODY: 5,
    AircraftType.CARGO: 6,
}

DEFAULT_DEPARTURE_WINDOW_SLOTS: dict[AircraftType, int] = {
    AircraftType.NARROW_BODY: 1,
    AircraftType.WIDE_BODY: 2,
    AircraftType.CARGO: 3,
}

DEFAULT_OPERATING_HOURS: list[int] = list(range(5, 23))

DEFAULT_DEMAND_CONFIG: DemandConfig = DemandConfig()
DEFAULT_SHIFT_CONFIG: ShiftConfig = ShiftConfig()
