"""
src.lp.scheduling — Shift-start LP solver (US4).

Solves the textbook shift scheduling LP via GLOP:
    min  Σ x_t
    s.t. Σ_{i=max(0,t-L+1)}^{t} x_i ≥ d_t  ∀t
         x_t ≥ 0

Post-solve: each x_t is rounded up via math.ceil; coverage is re-verified
on the rounded values (SC-006).
"""
from __future__ import annotations

import math

from ortools.linear_solver import pywraplp

from .types import DEFAULT_SHIFT_CONFIG, DemandResult, ShiftConfig, ShiftSchedule


def schedule_shifts(
    demand: DemandResult,
    config: ShiftConfig = DEFAULT_SHIFT_CONFIG,
) -> ShiftSchedule:
    """Return the minimum-cost integer shift plan that covers *demand*.

    Raises:
        ValueError: if ``demand.feasible`` is False.
        RuntimeError: if GLOP does not return OPTIMAL status.
    """
    if not demand.feasible:
        raise ValueError(
            "demand.feasible is False — resolve pool-size infeasibility before scheduling"
        )

    hours = demand.operating_hours
    n = len(hours)
    d = demand.demand_curve
    L = config.shift_length

    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("Failed to create GLOP solver instance")

    # Decision variables: x[t] = shift starts at operating_hours[t]
    x = [solver.NumVar(0.0, solver.infinity(), f"x_{t}") for t in range(n)]

    # Objective: minimise total shift starts
    objective = solver.Objective()
    for t in range(n):
        objective.SetCoefficient(x[t], 1.0)
    objective.SetMinimization()

    # Coverage constraints: workers on duty at index t ≥ d[t]
    for t in range(n):
        ct = solver.Constraint(float(d[t]), solver.infinity())
        for i in range(max(0, t - L + 1), t + 1):
            ct.SetCoefficient(x[i], 1.0)

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError(f"GLOP returned non-OPTIMAL status: {status}")

    shift_starts: dict[int, float] = {hours[t]: x[t].solution_value() for t in range(n)}
    shift_starts_rounded: dict[int, int] = {
        hours[t]: math.ceil(x[t].solution_value()) for t in range(n)
    }

    # Re-verify coverage on rounded values (SC-006)
    coverage_shortfalls: list[int] = []
    for t in range(n):
        workers = sum(
            shift_starts_rounded[hours[i]] for i in range(max(0, t - L + 1), t + 1)
        )
        if workers < d[t]:
            coverage_shortfalls.append(hours[t])

    return ShiftSchedule(
        shift_starts=shift_starts,
        shift_starts_rounded=shift_starts_rounded,
        daily_headcount=sum(shift_starts_rounded.values()),
        coverage_satisfied=len(coverage_shortfalls) == 0,
        coverage_shortfalls=coverage_shortfalls,
    )
