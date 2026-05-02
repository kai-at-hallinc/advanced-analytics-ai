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

from collections import defaultdict

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

    # --- Resolve effective arrival counts per hour ---
    # Precedence: actual_movements (US8, not implemented) > actuals > arrival_delay_flags > scheduled
    arr_counts: dict[int, dict[AircraftType, float]] = defaultdict(lambda: defaultdict(float))
    if actuals is not None:
        for slot in actuals:
            for ac_type, c in slot.arrival_counts.items():
                arr_counts[slot.hour][ac_type] = float(c)
    elif arrival_delay_flags:
        for slot in scheduled:
            for ac_type in AircraftType:
                c = slot.arrival_counts.get(ac_type, 0)
                if c == 0:
                    continue
                if arrival_delay_flags.get(ac_type, False):
                    # 20/80 heuristic: 20% stay at original slot, 80% shift to next
                    arr_counts[slot.hour][ac_type] += c * 0.2
                    next_hour = slot.hour + 1
                    if next_hour < config.operating_day_end:
                        arr_counts[next_hour][ac_type] += c * 0.8
                else:
                    arr_counts[slot.hour][ac_type] += float(c)
    else:
        for slot in scheduled:
            for ac_type, c in slot.arrival_counts.items():
                arr_counts[slot.hour][ac_type] = float(c)

    # --- Resolve effective departure counts per hour ---
    # Precedence: actual_movements (US8, not implemented) > actuals > departure_delay_flags > scheduled
    dep_counts: dict[int, dict[AircraftType, float]] = defaultdict(lambda: defaultdict(float))
    if actuals is not None:
        for slot in actuals:
            for ac_type, c in slot.departure_counts.items():
                dep_counts[slot.hour][ac_type] = float(c)
    elif departure_delay_flags:
        for slot in scheduled:
            for ac_type in AircraftType:
                c = slot.departure_counts.get(ac_type, 0)
                if c == 0:
                    continue
                if departure_delay_flags.get(ac_type, False):
                    # 20/80 heuristic: 20% stay at original slot, 80% shift to next
                    dep_counts[slot.hour][ac_type] += c * 0.2
                    next_hour = slot.hour + 1
                    if next_hour < config.operating_day_end:
                        dep_counts[next_hour][ac_type] += c * 0.8
                else:
                    dep_counts[slot.hour][ac_type] += float(c)
    else:
        for slot in scheduled:
            for ac_type, c in slot.departure_counts.items():
                dep_counts[slot.hour][ac_type] = float(c)

    # --- Arrival demand (forward window) ---
    arrival_demand = [0.0] * n_slots
    for hour, counts in arr_counts.items():
        if hour not in hour_to_idx:
            continue
        start_idx = hour_to_idx[hour]
        for ac_type, count in counts.items():
            if count == 0.0:
                continue
            standard = config.staffing_standards[ac_type]
            window = config.arrival_window_slots[ac_type]
            for k in range(window):
                target_idx = start_idx + k
                if target_idx < n_slots:
                    arrival_demand[target_idx] += count * standard

    # --- Departure demand (backward window) ---
    departure_demand = [0.0] * n_slots
    for hour, counts in dep_counts.items():
        if hour not in hour_to_idx:
            continue
        dep_idx = hour_to_idx[hour]
        for ac_type, count in counts.items():
            if count == 0.0:
                continue
            standard = config.departure_staffing_standards[ac_type]
            window = config.departure_window_slots[ac_type]
            for k in range(window):
                target_idx = dep_idx - k
                if target_idx >= 0:
                    departure_demand[target_idx] += count * standard

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
