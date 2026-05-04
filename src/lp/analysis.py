"""
src.lp.analysis — Post-solve analysis functions.

US9: identify_bottlenecks() — hours where active workers == demand (no surplus).
FR-008: comparison_report()  — direction-level gap between scheduled and tau demand.
"""
from __future__ import annotations

from .demand import compute_demand
from .types import (
    BottleneckResult,
    ComparisonReport,
    DEFAULT_SHIFT_CONFIG,
    DemandResult,
    FlightSlotInput,
    DemandConfig,
    DEFAULT_DEMAND_CONFIG,
    ShiftConfig,
    ShiftSchedule,
)


def identify_bottlenecks(
    demand: DemandResult,
    schedule: ShiftSchedule,
    config: ShiftConfig = DEFAULT_SHIFT_CONFIG,
) -> BottleneckResult:
    """Identify operating hours where worker coverage exactly meets demand (no surplus).

    A slot is a bottleneck when ``active_workers == demand`` at that hour — equivalent
    to a binding coverage constraint in the Stage 2 LP. Slots with zero demand are
    never flagged.

    Active workers at index ``t`` is the sum of ``shift_starts_rounded`` for all shift
    starts ``s`` whose shift window covers ``t``:
        active[t] = Σ shift_starts_rounded[hours[i]]  for i in [max(0, t-L+1), t]

    Args:
        demand: output of ``compute_demand()``; provides the demand curve and hours.
        schedule: output of ``schedule_shifts()``; provides ``shift_starts_rounded``.
        config: shift configuration providing ``shift_length`` (default 8).

    Returns:
        ``BottleneckResult`` with ``bottleneck_hours`` and ``demand_at_bottleneck``.
    """
    hours = demand.operating_hours
    d = demand.demand_curve
    L = config.shift_length

    bottleneck_hours: list[int] = []
    demand_at_bottleneck: dict[int, int] = {}

    for t, h in enumerate(hours):
        if d[t] == 0:
            continue  # zero-demand slots are never binding
        active = sum(
            schedule.shift_starts_rounded.get(hours[i], 0)
            for i in range(max(0, t - L + 1), t + 1)
        )
        if active == d[t]:
            bottleneck_hours.append(h)
            demand_at_bottleneck[h] = d[t]

    return BottleneckResult(
        bottleneck_hours=bottleneck_hours,
        demand_at_bottleneck=demand_at_bottleneck,
    )


def comparison_report(
    scheduled: list[FlightSlotInput],
    tau: list[FlightSlotInput],
    config: DemandConfig = DEFAULT_DEMAND_CONFIG,
) -> ComparisonReport:
    """Produce a direction-level demand gap report between scheduled and tau inputs.

    Calls ``compute_demand(scheduled)`` and ``compute_demand(tau=tau)`` separately,
    then reads ``arrival_demand_curve`` and ``departure_demand_curve`` from each result
    directly — no recomputation. Per-slot gaps and aggregate pct_total are computed
    for each direction independently (FR-008, SC-003).

    Args:
        scheduled: scheduled flight slots.
        tau: tau (predicted/actual) flight slots.
        config: demand configuration (default uses standard staffing and windows).

    Returns:
        ``ComparisonReport`` with per-slot and aggregate gap figures per direction.
    """
    sched_result = compute_demand(scheduled, config=config)
    tau_result = compute_demand(tau, config=config)

    hours = sched_result.operating_hours
    n = len(hours)

    # Align tau curve to same hours list; fill zeros for any missing hour
    tau_hour_to_idx: dict[int, int] = {h: i for i, h in enumerate(tau_result.operating_hours)}

    def _align(curve: list[int], src_hours: list[int]) -> list[int]:
        idx_map = {h: i for i, h in enumerate(src_hours)}
        return [curve[idx_map[h]] if h in idx_map else 0 for h in hours]

    sched_arr = sched_result.arrival_demand_curve
    sched_dep = sched_result.departure_demand_curve
    tau_arr = _align(tau_result.arrival_demand_curve, tau_result.operating_hours)
    tau_dep = _align(tau_result.departure_demand_curve, tau_result.operating_hours)

    arr_gap = [tau_arr[i] - sched_arr[i] for i in range(n)]
    dep_gap = [tau_dep[i] - sched_dep[i] for i in range(n)]

    total_sched_arr = sum(sched_arr)
    total_sched_dep = sum(sched_dep)

    arr_pct = (sum(arr_gap) / total_sched_arr * 100) if total_sched_arr else 0.0
    dep_pct = (sum(dep_gap) / total_sched_dep * 100) if total_sched_dep else 0.0

    return ComparisonReport(
        hours=hours,
        scheduled_arrival_demand=sched_arr,
        tau_arrival_demand=tau_arr,
        arrival_gap_absolute=arr_gap,
        arrival_gap_pct_total=arr_pct,
        scheduled_departure_demand=sched_dep,
        tau_departure_demand=tau_dep,
        departure_gap_absolute=dep_gap,
        departure_gap_pct_total=dep_pct,
        total_scheduled_demand=[sched_arr[i] + sched_dep[i] for i in range(n)],
        total_tau_demand=[tau_arr[i] + tau_dep[i] for i in range(n)],
    )
