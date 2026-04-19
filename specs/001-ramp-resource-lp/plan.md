# Implementation Plan: Ramp Resource LP — Ground Handling Worker Scheduling

**Branch**: `001-ramp-resource-lp` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ramp-resource-lp/spec.md`

## Summary

Two-stage LP that converts a Finavia flight schedule and optional actual movement data into the
minimum number of ground-handling worker shifts needed to cover every operating hour. Stage 1
computes per-slot worker demand from two independent sources: arrival handling (forward-looking
arrival window per aircraft type) and departure preparation (backward-looking departure window per
aircraft type), each adjusted for movement delays and on-time slot classification. Stage 2 schedules
the fewest shift-starts that satisfy that combined demand across the 18-slot operating day
(05:00–23:00). Implemented as a Python module using Google OR-Tools GLOP solver, with all public
types as dataclasses and tests in pytest.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `ortools` (GLOP LP solver), Python standard library (`dataclasses`, `typing`, `math`)
**Storage**: N/A — in-memory computation, no persistent state
**Testing**: `pytest`
**Target Platform**: Any Python 3.10+ environment (Windows / Linux / macOS)
**Project Type**: library (Python module)
**Performance Goals**: Full-day demand curve in <30 seconds (SC-001); Stage 2 LP on 18 slots solves in milliseconds
**Constraints**: No external serialisation dependencies; deterministic LP solve; integer rounding via `math.ceil` post-solve only; departure window clipped silently at operating day boundary; `compute_demand()` raises `ValueError` for out-of-range hours — caller must pre-filter
**Scale/Scope**: 18 hourly slots, 3 canonical aircraft types, single-day batch, two movement directions
**Test Dataset**: `data/finavia_flights_efhk_20260330.csv` — 447 EFHK movements (223 arrivals, 224 departures) on 2026-03-30; dominant type AT75 (narrow-body), A359 (wide-body); 7 cargo movements; pre-dawn/post-midnight flights must be filtered before calling `compute_demand()`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
| --------- | ----------- | ------ |
| I. Module-First | New `src/lp/` module, self-contained, independently importable and testable | ✅ Pass |
| II. Notebook-Driven Validation | `notebooks/planning/ramp_resource_lp.ipynb` validates `src/lp/` against realistic EFHK inputs; imports from `src/` — logic not re-implemented inline | ✅ Pass |
| III. Test Coverage | `tests/lp/` mirrors `src/lp/`; every public function has a corresponding test; pytest only | ✅ Pass |
| IV. Reproducibility | GLOP is deterministic; `ortools` declared in `pyproject.toml` under `lp` optional group | ✅ Pass |
| V. Simplicity | Two-stage LP follows Sahadevan + textbook formulations; YAGNI applied; departure demand added as additive term, not new solver stage | ✅ Pass |
| Dev Workflow Rule 4 | `business_problems/ramp_resource_lp.py` references `src/lp/` solver, does not re-implement inline | ✅ Pass |

**No violations. Complexity Tracking not required.**

**Post-Phase 1 re-check**: Departure demand extension adds fields to `FlightSlotInput` and `DemandConfig` and a new `DepartureComparisonReport` structure. Confirmed no new abstractions beyond what the spec requires.

## Project Structure

### Documentation (this feature)

```text
specs/001-ramp-resource-lp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── api.md           # Phase 1 output — typed function signatures
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/lp/                         ← NEW: LP solver module
├── __init__.py                 ← exports compute_demand, schedule_shifts, identify_bottlenecks, comparison_report
├── types.py                    ← dataclasses: FlightSlotInput, AircraftType, DemandConfig, DemandResult,
│                                  ShiftConfig, ShiftSchedule, BottleneckResult, ComparisonReport
├── demand.py                   ← Stage 1: compute_demand() — arrival window (forward) + departure window (backward)
├── scheduling.py               ← Stage 2: schedule_shifts() — textbook shift-start LP
└── analysis.py                 ← identify_bottlenecks(), comparison_report()

tests/lp/                       ← NEW: test suite mirroring src/lp/
├── __init__.py
├── test_types.py               ← validates defaults and dataclass invariants (including departure fields)
├── test_demand.py              ← US1–US3, US6–US8, FR-001 to FR-004, FR-010–FR-015; departure boundary clipping
├── test_scheduling.py          ← US4–US5, FR-005–FR-006, SC-002, SC-006
└── test_analysis.py            ← US9, FR-008–FR-009, SC-003–SC-005

notebooks/planning/
└── ramp_resource_lp.ipynb      ← NEW: prototype notebook (Principle II); imports src/lp once extracted

business_problems/
├── ramp_resource_minimization_formulation.md    ← EXISTING: mathematical derivation (keep)
└── ramp_resource_lp.py                          ← NEW: Finavia-specific instantiation calling src/lp
                                                    owns: ICAO → LP category mapping, operating-window
                                                    pre-filtering, and CSV parsing from data/

data/
└── finavia_flights_efhk_20260330.csv            ← EXISTING: reference dataset (447 EFHK movements,
                                                    2026-03-30); used in notebook prototype and
                                                    parametrised integration tests

pyproject.toml                  ← UPDATE: add `lp = ["ortools"]` optional dependency group
```

**Structure Decision**: Single-project layout. New `src/lp/` module follows the existing `src/<domain>/` convention. `business_problems/ramp_resource_lp.py` satisfies Dev Workflow Rule 4. The existing `business_problems/ramp_resource_minimization_formulation.md` is preserved as the mathematical reference.

## Complexity Tracking

> No violations — table not required.
