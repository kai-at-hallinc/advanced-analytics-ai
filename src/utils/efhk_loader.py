"""EFHK Finavia CSV loader for the Ramp Resource LP.

Handles all airport-specific data preparation:
- UTC → Helsinki local time conversion (ZoneInfo, DST-aware)
- ICAO code → LP aircraft category mapping
- Operating-window filtering (default 05:00–23:00 Helsinki)
- Aggregation to hourly FlightSlotInput records
- Predicted times extraction from CSV columns → FlightMovementInput (default-on)
"""

import csv
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from src.lp.types import AircraftType, FlightMovementInput, FlightSlotInput

HEL = ZoneInfo("Europe/Helsinki")

# ICAO type code → LP aircraft category.
# cargo designation (flight_type_iata = 'F') overrides airframe class — see _map_aircraft_type.
ICAO_TO_LP_CATEGORY: dict[str, AircraftType] = {
    # narrow_body — single-aisle aircraft
    "AT75": AircraftType.NARROW_BODY,
    "AT76": AircraftType.NARROW_BODY,
    "A318": AircraftType.NARROW_BODY,
    "A319": AircraftType.NARROW_BODY,
    "A320": AircraftType.NARROW_BODY,
    "A321": AircraftType.NARROW_BODY,
    "A20N": AircraftType.NARROW_BODY,
    "A21N": AircraftType.NARROW_BODY,
    "B737": AircraftType.NARROW_BODY,
    "B738": AircraftType.NARROW_BODY,
    "B739": AircraftType.NARROW_BODY,
    "B38M": AircraftType.NARROW_BODY,
    "BCS1": AircraftType.NARROW_BODY,
    "BCS3": AircraftType.NARROW_BODY,
    "E170": AircraftType.NARROW_BODY,
    "E175": AircraftType.NARROW_BODY,
    "E190": AircraftType.NARROW_BODY,
    "E195": AircraftType.NARROW_BODY,
    "DH8D": AircraftType.NARROW_BODY,
    # wide_body — twin-aisle aircraft
    "A332": AircraftType.WIDE_BODY,
    "A333": AircraftType.WIDE_BODY,
    "A339": AircraftType.WIDE_BODY,
    "A350": AircraftType.WIDE_BODY,
    "A359": AircraftType.WIDE_BODY,
    "A35K": AircraftType.WIDE_BODY,
    "B763": AircraftType.WIDE_BODY,
    "B772": AircraftType.WIDE_BODY,
    "B773": AircraftType.WIDE_BODY,
    "B77W": AircraftType.WIDE_BODY,
    "B788": AircraftType.WIDE_BODY,
    "B789": AircraftType.WIDE_BODY,
}


def _utc_iso_to_helsinki_minutes(utc_iso: str) -> int:
    """Convert a UTC ISO-8601 string to minutes-from-midnight in Helsinki local time."""
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    hel_dt = dt.astimezone(HEL)
    return hel_dt.hour * 60 + hel_dt.minute


def _map_aircraft_type(icao: str, flight_type_iata: str) -> AircraftType | None:
    """Return LP aircraft category for a row, or None if the type is unrecognised."""
    if flight_type_iata == "F":
        return AircraftType.CARGO
    return ICAO_TO_LP_CATEGORY.get(icao)


def load_efhk(
    path: str,
    operating_day_start: int = 5,
    operating_day_end: int = 23,
    extract_tau: bool = True,
    use_tau_times: bool = False,
) -> tuple[list[FlightSlotInput], Optional[list[FlightMovementInput]]]:
    """Load a Finavia EFHK CSV and return scheduled slots and optional per-flight movements.

    Scheduled times (UTC) are converted to Helsinki local time via
    ``ZoneInfo("Europe/Helsinki")`` before slot assignment and window filtering.
    Rows outside ``[operating_day_start, operating_day_end)`` are discarded.
    Rows with unrecognised ICAO codes are skipped silently.

    Parameters
    ----------
    path:
        Path to the CSV file (e.g. ``"data/finavia_flights_efhk_20260327.csv"``).
    operating_day_start:
        First operating hour in Helsinki local time (inclusive). Default 5.
    operating_day_end:
        Last operating hour in Helsinki local time (exclusive). Default 23.
    extract_tau:
        When ``True`` (default), build ``FlightMovementInput`` records from the
        ``actual_arrival_time`` / ``actual_departure_time`` columns (tau
        times). Rows where the column is empty are treated as on-time
        (``tau_minutes=None``). When ``False``, the second return value is
        ``None``.
    use_tau_times:
        When ``True``, aggregate ``FlightSlotInput`` slots by tau arrival/
        departure time instead of scheduled time. Rows with a null tau time
        fall back to scheduled time for slot assignment. Useful for building
        the ``tau`` argument to ``compute_demand()``. Default ``False``.

    Returns
    -------
    tuple[list[FlightSlotInput], Optional[list[FlightMovementInput]]]
        Slots aggregated by the chosen time (scheduled or tau), and per-flight
        movement records (only when ``extract_tau=True``).
    """
    arrival_counts: dict[int, dict[AircraftType, int]] = defaultdict(lambda: defaultdict(int))
    departure_counts: dict[int, dict[AircraftType, int]] = defaultdict(lambda: defaultdict(int))
    movements: list[FlightMovementInput] = []

    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            icao = row["aircraft_type_icao"].strip()
            flight_type = row.get("flight_type_iata", "").strip()
            op_type = row["op_type"].strip()
            scheduled_utc = row["scheduled_time"].strip()

            ac_type = _map_aircraft_type(icao, flight_type)
            if ac_type is None:
                continue  # unrecognised ICAO — skip (non-revenue / unclassified)

            scheduled_minutes = _utc_iso_to_helsinki_minutes(scheduled_utc)

            # Determine which time drives slot assignment
            if use_tau_times:
                tau_col = "actual_arrival_time" if op_type == "A" else "actual_departure_time"
                tau_raw_for_slot = row.get(tau_col, "").strip()
                slot_minutes = (
                    _utc_iso_to_helsinki_minutes(tau_raw_for_slot)
                    if tau_raw_for_slot
                    else scheduled_minutes  # fall back when tau is null
                )
            else:
                slot_minutes = scheduled_minutes

            slot_hour = slot_minutes // 60

            if not (operating_day_start <= slot_hour < operating_day_end):
                continue  # outside operating window

            if op_type == "A":
                arrival_counts[slot_hour][ac_type] += 1
            elif op_type == "D":
                departure_counts[slot_hour][ac_type] += 1
            else:
                continue  # unrecognised op_type

            if extract_tau:
                tau_col = "actual_arrival_time" if op_type == "A" else "actual_departure_time"
                tau_raw = row.get(tau_col, "").strip()
                tau_minutes: int | None = (
                    _utc_iso_to_helsinki_minutes(tau_raw) if tau_raw else None
                )
                movements.append(
                    FlightMovementInput(
                        aircraft_type=ac_type,
                        op_type=op_type,
                        scheduled_minutes=scheduled_minutes,
                        tau_minutes=tau_minutes,
                    )
                )

    all_hours = sorted(set(arrival_counts) | set(departure_counts))
    slots = [
        FlightSlotInput(
            hour=h,
            arrival_counts=dict(arrival_counts[h]),
            departure_counts=dict(departure_counts[h]),
        )
        for h in all_hours
    ]

    return slots, (movements if extract_tau else None)
