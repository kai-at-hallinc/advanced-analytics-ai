"""
Stage 1: compute per-slot worker demand from flight schedule.

US1 (scheduled-only): arrival_counts drive a forward-looking demand curve.
US2 (departure): departure_counts drive a backward-looking demand curve, summed independently.
US3 (delay/actuals): delay flags apply 20/80 heuristic per direction; actuals override at slot level.

Forward arrival window:  arrival at slot j contributes to slots j, j+1, ..., j+W_arr-1.
Backward departure window: departure at slot m contributes to slots max(day_start, m-W_dep+1)..m.

Precedence per direction (highest to lowest):
    actual_movements (US8, not yet implemented) > actuals > delay_flags > scheduled
"""
from __future__ import annotations

from src.lp.types import (
    AircraftType,
    DemandConfig,
    DemandResult,
    FlightMovementInput,
    FlightSlotInput,
    DEFAULT_DEMAND_CONFIG,
)
from src.utils.lp_utils import _resolve_flight_counts, _spread_demand


def compute_demand(
    scheduled: list[FlightSlotInput],
    actuals: list[FlightSlotInput] | None = None,
    arrival_delay_flags: dict[AircraftType, bool] | None = None,
    departure_delay_flags: dict[AircraftType, bool] | None = None,
    actual_movements: list[FlightMovementInput] | None = None,
    config: DemandConfig = DEFAULT_DEMAND_CONFIG,
) -> DemandResult:
    # --- Entry validation ---
    hours_seen = [s.hour for s in scheduled]
    if len(hours_seen) != len(set(hours_seen)):
        raise ValueError("duplicate hour in scheduled")

    for slot in scheduled:
        if not (config.operating_day_start <= slot.hour < config.operating_day_end):
            raise ValueError(
                f"hour {slot.hour} out of operating window "
                f"[{config.operating_day_start}, {config.operating_day_end})"
            )

    # --- Index mapping ---
    operating_hours = list(range(config.operating_day_start, config.operating_day_end))
    n_slots = len(operating_hours)
    hour_to_idx = {h: i for i, h in enumerate(operating_hours)}

    # --- Resolve effective arrival/departure counts per hour ---
    # Precedence: actual_movements (US8, not implemented) > actuals > delay_flags > scheduled
    arr_counts, dep_counts = _resolve_flight_counts(
        scheduled, actuals, arrival_delay_flags, departure_delay_flags, config.operating_day_end
    )

    # --- Arrival demand (forward window) ---
    arrival_demand = _spread_demand(arr_counts, hour_to_idx, n_slots, config.staffing_standards, config.arrival_window_slots)

    # --- Departure demand (backward window) ---
    departure_demand = _spread_demand(dep_counts, hour_to_idx, n_slots, config.departure_staffing_standards, config.departure_window_slots, backward=True)

    # --- Convert to int and combine ---
    arrival_int = [round(v) for v in arrival_demand]
    departure_int = [round(v) for v in departure_demand]
    demand_curve = [a + d for a, d in zip(arrival_int, departure_int)]

    infeasible_slots = [
        operating_hours[i]
        for i, r in enumerate(demand_curve)
        if r > config.pool_size
    ]

    return DemandResult(
        demand_curve=demand_curve,
        arrival_demand_curve=arrival_int,
        departure_demand_curve=departure_int,
        feasible=len(infeasible_slots) == 0,
        infeasible_slots=infeasible_slots,
        operating_hours=operating_hours,
    )
