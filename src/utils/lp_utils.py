from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from src.lp.types import AircraftType, FlightSlotInput

FlightCounts = dict[int, dict[AircraftType, float]]


def _resolve_flight_counts(
    scheduled: list[FlightSlotInput],
    actuals: list[FlightSlotInput] | None,
    arrival_delay_flags: dict[AircraftType, bool] | None,
    departure_delay_flags: dict[AircraftType, bool] | None,
    operating_day_end: int,
) -> tuple[FlightCounts, FlightCounts]:
    arr_counts: FlightCounts = defaultdict(lambda: defaultdict(float))
    dep_counts: FlightCounts = defaultdict(lambda: defaultdict(float))

    if actuals is not None:
        for slot in actuals:
            for ac_type, c in slot.arrival_counts.items():
                arr_counts[slot.hour][ac_type] = float(c)
            for ac_type, c in slot.departure_counts.items():
                dep_counts[slot.hour][ac_type] = float(c)
    else:
        for slot in scheduled:
            for ac_type in AircraftType:
                arr_c = slot.arrival_counts.get(ac_type, 0)
                dep_c = slot.departure_counts.get(ac_type, 0)

                if arrival_delay_flags and arr_c:
                    if arrival_delay_flags.get(ac_type, False):
                        arr_counts[slot.hour][ac_type] += arr_c * 0.2
                        next_hour = slot.hour + 1
                        if next_hour < operating_day_end:
                            arr_counts[next_hour][ac_type] += arr_c * 0.8
                    else:
                        arr_counts[slot.hour][ac_type] += float(arr_c)
                elif arr_c:
                    arr_counts[slot.hour][ac_type] = float(arr_c)

                if departure_delay_flags and dep_c:
                    if departure_delay_flags.get(ac_type, False):
                        dep_counts[slot.hour][ac_type] += dep_c * 0.2
                        next_hour = slot.hour + 1
                        if next_hour < operating_day_end:
                            dep_counts[next_hour][ac_type] += dep_c * 0.8
                    else:
                        dep_counts[slot.hour][ac_type] += float(dep_c)
                elif dep_c:
                    dep_counts[slot.hour][ac_type] = float(dep_c)

    return arr_counts, dep_counts


def _spread_demand(
    counts: Mapping[int, Mapping[AircraftType, float]],
    hour_to_idx: Mapping[int, int],
    n_slots: int,
    standards: Mapping[AircraftType, float],
    windows: Mapping[AircraftType, int],
    *,
    backward: bool = False,
) -> list[float]:
    demand = [0.0] * n_slots
    for hour, ac_counts in counts.items():
        if hour not in hour_to_idx:
            continue
        idx = hour_to_idx[hour]
        for ac_type, count in ac_counts.items():
            w = windows[ac_type]
            slots = range(max(0, idx - w + 1), idx + 1) if backward else range(idx, min(idx + w, n_slots))
            for i in slots:
                demand[i] += count * standards[ac_type]
    return demand
