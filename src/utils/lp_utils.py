from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from src.lp.types import AircraftType, FlightMovementInput, FlightSlotInput

FlightCounts = dict[int, dict[AircraftType, float]]


def _resolve_flight_counts(
    scheduled: list[FlightSlotInput],
    tau: list[FlightSlotInput] | None,
    arrival_delay_flags: dict[AircraftType, bool] | None,
    departure_delay_flags: dict[AircraftType, bool] | None,
    operating_day_end: int,
) -> tuple[FlightCounts, FlightCounts]:
    """Resolve effective per-hour arrival and departure counts from slot-level inputs.

    Applies input mode precedence for each direction independently:

    - ``tau`` provided: its arrival/departure counts are used directly — delay flags ignored.
    - ``tau`` is None + delay flag set for a type: 20/80 split — 20% of count stays at the
      original hour, 80% moves to ``hour + 1`` (capped at ``operating_day_end``).
    - ``tau`` is None + no delay flag: scheduled counts used unchanged.

    Args:
        scheduled: baseline slot counts for each hour.
        tau: optional slot-level override (τ); takes full precedence over delay flags.
        arrival_delay_flags: per-type bool; True applies the 20/80 heuristic to arrivals.
        departure_delay_flags: per-type bool; True applies the 20/80 heuristic to departures.
        operating_day_end: exclusive upper hour bound; prevents spilling into the next day.

    Returns:
        ``(arr_counts, dep_counts)`` — nested dicts mapping ``hour → AircraftType → float``.
    """
    arr_counts: FlightCounts = defaultdict(lambda: defaultdict(float))
    dep_counts: FlightCounts = defaultdict(lambda: defaultdict(float))

    if tau is not None:
        for slot in tau:
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


def _aggregate_tau_movements(
    movements: list[FlightMovementInput],
    tolerance_minutes: int,
) -> tuple[FlightCounts, FlightCounts]:
    """Aggregate per-flight movements into hourly counts using tolerance-window classification.

    For each movement, the effective slot is chosen as:
    - ``tau_minutes`` is None → ``floor(scheduled_minutes / 60)`` (treated as on-time).
    - ``|tau_minutes - scheduled_minutes| <= tolerance_minutes`` → scheduled slot (on-time).
    - Otherwise → ``floor(tau_minutes / 60)`` (reclassified; early arrivals keep full count).

    Args:
        movements: list of individual flight records with scheduled and τ (tau) minute timestamps.
        tolerance_minutes: on-time window half-width; flights within ±this value are not reclassified.

    Returns:
        ``(arr_counts, dep_counts)`` — nested dicts mapping ``hour → AircraftType → float``.
    """
    arr_counts: FlightCounts = defaultdict(lambda: defaultdict(float))
    dep_counts: FlightCounts = defaultdict(lambda: defaultdict(float))

    for m in movements:
        sched_slot = m.scheduled_minutes // 60
        if m.tau_minutes is not None:
            delta = abs(m.tau_minutes - m.scheduled_minutes)
            effective_slot = sched_slot if delta <= tolerance_minutes else m.tau_minutes // 60
        else:
            effective_slot = sched_slot

        if m.op_type == "A":
            arr_counts[effective_slot][m.aircraft_type] += 1.0
        else:
            dep_counts[effective_slot][m.aircraft_type] += 1.0

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
    """Spread per-hour aircraft counts into a worker demand array using staffing windows.

    Each count at a given hour is multiplied by the aircraft-type staffing standard and
    added to every slot in its window:
    - Forward (arrivals, ``backward=False``): slot idx spreads to ``idx … idx + W - 1``.
    - Backward (departures, ``backward=True``): slot idx spreads to ``max(0, idx - W + 1) … idx``.

    Hours not present in ``hour_to_idx`` (outside the operating window) are silently skipped.

    Args:
        counts: nested dict ``hour → AircraftType → flight count`` from a resolve/aggregate fn.
        hour_to_idx: maps clock hour to array index; defines the valid operating window.
        n_slots: length of the output demand array.
        standards: per-type worker count per flight (staffing standard).
        windows: per-type number of slots the demand spans.
        backward: if True, applies the backward departure window; default False (arrival).

    Returns:
        ``list[float]`` of length ``n_slots`` — worker demand contribution per slot.
    """
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
