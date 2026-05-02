"""
Stage 1: compute per-slot worker demand from flight schedule.

US1 (scheduled-only): arrival_counts drive a forward-looking demand curve.
US2 (departure): departure_counts drive a backward-looking demand curve, summed independently.

Forward arrival window:  arrival at slot j contributes to slots j, j+1, ..., j+W_arr-1.
Backward departure window: departure at slot m contributes to slots max(day_start, m-W_dep+1)..m.
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

    # --- Arrival demand (forward window) ---
    arrival_demand = [0] * n_slots
    for slot in scheduled:
        for ac_type in AircraftType:
            count = slot.arrival_counts.get(ac_type, 0)
            if count == 0:
                continue
            standard = config.staffing_standards[ac_type]
            window = config.arrival_window_slots[ac_type]
            start_idx = hour_to_idx[slot.hour]
            for k in range(window):
                target_idx = start_idx + k
                if target_idx < n_slots:
                    arrival_demand[target_idx] += count * standard

    # --- Departure demand (backward window) ---
    departure_demand = [0] * n_slots
    for slot in scheduled:
        for ac_type in AircraftType:
            count = slot.departure_counts.get(ac_type, 0)
            if count == 0:
                continue
            standard = config.departure_staffing_standards[ac_type]
            window = config.departure_window_slots[ac_type]
            dep_idx = hour_to_idx[slot.hour]
            # Backward: departure at slot m contributes to slots m-W+1 .. m
            # Clipped silently at operating_day_start (no error raised)
            for k in range(window):
                target_idx = dep_idx - k
                if target_idx >= 0:
                    departure_demand[target_idx] += count * standard

    # --- Combine and pool check ---
    demand_curve = [a + d for a, d in zip(arrival_demand, departure_demand)]
    infeasible_slots = [
        operating_hours[i]
        for i, r in enumerate(demand_curve)
        if r > config.pool_size
    ]

    return DemandResult(
        demand_curve=demand_curve,
        arrival_demand_curve=arrival_demand,
        departure_demand_curve=departure_demand,
        feasible=len(infeasible_slots) == 0,
        infeasible_slots=infeasible_slots,
        operating_hours=operating_hours,
    )
