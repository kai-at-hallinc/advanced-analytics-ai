"""
src.lp — Ramp Resource LP: ground-handling worker scheduling for Finavia airports.

Implements a two-stage LP:
  Stage 1 (compute_demand):  per-slot worker demand from flight schedule and actuals.
  Stage 2 (schedule_shifts): minimum shift-starts satisfying that demand via GLOP.
  Analysis: identify_bottlenecks(), comparison_report().

Public API: see specs/001-ramp-resource-lp/contracts/api.md.
"""
from .types import (
    AircraftType,
    BottleneckResult,
    ComparisonReport,
    DemandConfig,
    DemandResult,
    FlightMovementInput,
    FlightSlotInput,
    ShiftConfig,
    ShiftSchedule,
    DEFAULT_ARRIVAL_WINDOW_SLOTS,
    DEFAULT_DEMAND_CONFIG,
    DEFAULT_DEPARTURE_STAFFING_STANDARDS,
    DEFAULT_DEPARTURE_WINDOW_SLOTS,
    DEFAULT_OPERATING_HOURS,
    DEFAULT_SHIFT_CONFIG,
    DEFAULT_STAFFING_STANDARDS,
)
from .demand import compute_demand

__all__ = [
    "AircraftType",
    "FlightSlotInput",
    "FlightMovementInput",
    "DemandConfig",
    "DemandResult",
    "DEFAULT_DEMAND_CONFIG",
    "compute_demand",
]
