"""
End-to-end integration test and performance benchmark — Phase 12 (T033, T034).

Uses the real EFHK dataset (422 flights) at data/finavia_flights_efhk_20260327.csv.
"""
import time

import pytest

from src.utils.efhk_loader import load_efhk
from src.lp import (
    compute_demand,
    schedule_shifts,
    identify_bottlenecks,
    comparison_report,
)

DATA_PATH = "data/finavia_flights_efhk_20260327.csv"


# ---------------------------------------------------------------------------
# T033 — end-to-end integration
# ---------------------------------------------------------------------------


def test_efhk_end_to_end_no_error():
    """Full pipeline on the 422-flight EFHK dataset raises no ValueError."""
    scheduled, movements = load_efhk(DATA_PATH)
    assert len(scheduled) > 0, "Expected at least one slot from the CSV"

    demand = compute_demand(scheduled, tau_movements=movements)
    assert demand.feasible, f"Demand infeasible at: {demand.infeasible_slots}"
    assert any(d > 0 for d in demand.demand_curve), "Demand curve is all zeros"

    schedule = schedule_shifts(demand)
    assert schedule.daily_headcount > 0
    assert schedule.coverage_satisfied, f"Coverage shortfalls: {schedule.coverage_shortfalls}"

    bottlenecks = identify_bottlenecks(demand, schedule)
    # bottleneck_hours is a valid list (may be empty on some datasets — not an error)
    assert isinstance(bottlenecks.bottleneck_hours, list)
    for h in bottlenecks.bottleneck_hours:
        assert h in bottlenecks.demand_at_bottleneck


def test_efhk_demand_curve_spans_operating_hours():
    """Non-zero demand exists across multiple operating hours."""
    scheduled, _ = load_efhk(DATA_PATH, extract_tau=False)
    demand = compute_demand(scheduled)
    non_zero = [h for h, d in zip(demand.operating_hours, demand.demand_curve) if d > 0]
    assert len(non_zero) >= 5, f"Expected demand across ≥5 hours, got {non_zero}"


def test_efhk_comparison_report():
    """comparison_report() runs end-to-end on real data without error."""
    scheduled, _ = load_efhk(DATA_PATH, extract_tau=False)
    tau_slots, _ = load_efhk(DATA_PATH, use_tau_times=True, extract_tau=False)
    report = comparison_report(scheduled, tau_slots)
    assert len(report.hours) > 0
    assert len(report.arrival_gap_absolute) == len(report.hours)
    assert len(report.departure_gap_absolute) == len(report.hours)


# ---------------------------------------------------------------------------
# T034 — performance benchmark (SC-001: < 30 s)
# ---------------------------------------------------------------------------


def test_compute_demand_performance():
    """compute_demand() on the full 422-flight EFHK dataset completes in < 30 s."""
    scheduled, movements = load_efhk(DATA_PATH)
    start = time.perf_counter()
    compute_demand(scheduled, tau_movements=movements)
    elapsed = time.perf_counter() - start
    assert elapsed < 30, f"compute_demand took {elapsed:.2f}s (limit 30s)"
