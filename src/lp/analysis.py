"""
src.lp.analysis — Post-solve analysis functions.

US9: identify_bottlenecks() — hours where active workers == demand (no surplus).
"""
from __future__ import annotations

from .types import (
    BottleneckResult,
    DEFAULT_SHIFT_CONFIG,
    DemandResult,
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
