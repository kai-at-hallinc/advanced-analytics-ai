"""Tests for src/utils/efhk_loader.py"""

import pytest
from pathlib import Path

from src.utils.efhk_loader import ICAO_TO_LP_CATEGORY, load_efhk
from src.lp.types import AircraftType

DATASET = Path("data/finavia_flights_efhk_20260327.csv")
REQUIRES_DATASET = pytest.mark.skipif(
    not DATASET.exists(), reason="Reference dataset not present"
)


class TestIcaoMapping:
    def test_at76_maps_to_narrow_body(self):
        assert ICAO_TO_LP_CATEGORY["AT76"] == AircraftType.NARROW_BODY

    def test_at75_maps_to_narrow_body(self):
        assert ICAO_TO_LP_CATEGORY["AT75"] == AircraftType.NARROW_BODY

    def test_a359_maps_to_wide_body(self):
        assert ICAO_TO_LP_CATEGORY["A359"] == AircraftType.WIDE_BODY

    def test_unknown_icao_not_in_mapping(self):
        assert ICAO_TO_LP_CATEGORY.get("XXXX") is None

    def test_cargo_flight_type_overrides_icao(self):
        from src.utils.efhk_loader import _map_aircraft_type
        # A321 is normally narrow_body, but F flight type → cargo
        assert _map_aircraft_type("A321", "F") == AircraftType.CARGO

    def test_non_cargo_flight_type_uses_icao(self):
        from src.utils.efhk_loader import _map_aircraft_type
        assert _map_aircraft_type("A321", "J") == AircraftType.NARROW_BODY


class TestUtcToHelsinkiMinutes:
    def test_known_utc_before_dst(self):
        # 2026-03-27T03:20:00Z → Helsinki 05:20 (UTC+2, before DST)
        from src.utils.efhk_loader import _utc_iso_to_helsinki_minutes
        result = _utc_iso_to_helsinki_minutes("2026-03-27T03:20:00.000Z")
        assert result == 5 * 60 + 20  # 320

    def test_z_suffix_handled(self):
        from src.utils.efhk_loader import _utc_iso_to_helsinki_minutes
        # should not raise
        _utc_iso_to_helsinki_minutes("2026-03-27T10:00:00.000Z")


@REQUIRES_DATASET
class TestLoadEfhk:
    def test_returns_nonempty_slots(self):
        slots, _ = load_efhk(str(DATASET))
        assert len(slots) > 0

    def test_all_hours_within_operating_window(self):
        slots, _ = load_efhk(str(DATASET))
        for s in slots:
            assert 5 <= s.hour < 23, f"Hour {s.hour} outside window"

    def test_no_duplicate_hours(self):
        slots, _ = load_efhk(str(DATASET))
        hours = [s.hour for s in slots]
        assert len(hours) == len(set(hours))

    def test_tau_extracted_by_default(self):
        _, movements = load_efhk(str(DATASET))
        assert movements is not None
        assert len(movements) > 0

    def test_tau_suppressed_when_disabled(self):
        _, movements = load_efhk(str(DATASET), extract_tau=False)
        assert movements is None

    def test_all_movements_have_valid_op_type(self):
        _, movements = load_efhk(str(DATASET))
        for m in movements:
            assert m.op_type in ("A", "D")

    def test_all_scheduled_minutes_within_operating_window(self):
        _, movements = load_efhk(str(DATASET))
        for m in movements:
            assert 5 * 60 <= m.scheduled_minutes < 23 * 60

    def test_use_tau_times_returns_slots_in_operating_window(self):
        slots, _ = load_efhk(str(DATASET), use_tau_times=True)
        assert len(slots) > 0
        for s in slots:
            assert 5 <= s.hour < 23, f"Hour {s.hour} outside window"

    def test_use_tau_times_no_duplicate_hours(self):
        slots, _ = load_efhk(str(DATASET), use_tau_times=True)
        hours = [s.hour for s in slots]
        assert len(hours) == len(set(hours))

    def test_use_tau_times_false_is_default_behaviour(self):
        # Both calls should produce the same slot aggregation
        slots_default, _ = load_efhk(str(DATASET))
        slots_explicit, _ = load_efhk(str(DATASET), use_tau_times=False)
        assert [s.hour for s in slots_default] == [s.hour for s in slots_explicit]
