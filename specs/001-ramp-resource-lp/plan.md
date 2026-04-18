# Implementation Plan: Ramp Resource LP — Ground Handling Worker Scheduling

**Branch**: `001-ramp-resource-lp` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-ramp-resource-lp/spec.md`

## Summary

Two-stage LP that converts a Finavia flight schedule and optional actual-arrival data into the minimum number of ground-handling worker shifts needed to cover every operating hour. Stage 1 (Sahadevan LP) computes per-slot demand accounting for aircraft type, multi-slot turnaround occupancy, delay/early-arrival reclassification, and a workforce pool ceiling. Stage 2 (textbook shift-start LP) schedules the fewest shift-starts that satisfy that demand across an 18-slot operating day (05:00–23:00). Implemented as a Python module using Google OR-Tools GLOP solver, with all public types as dataclasses and tests in pytest.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: `ortools` (GLOP LP solver), Python standard library (`dataclasses`, `typing`, `math`)
**Storage**: N/A — in-memory computation, no persistent state
**Testing**: `pytest`
**Target Platform**: Any Python 3.10+ environment (Windows / Linux / macOS)
**Project Type**: library (Python module)
**Performance Goals**: Full-day demand curve in <30 seconds (SC-001); Stage 2 LP on 18 slots solves in milliseconds
**Constraints**: No external serialisation dependencies; deterministic LP solve; integer rounding via `math.ceil` post-solve only
**Scale/Scope**: 18 hourly slots, 3 canonical aircraft types, single-day batch

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I. Module-First | New `src/lp/` module, self-contained, independently importable and testable | ✅ Pass |
| II. Notebook-Driven | `notebooks/planning/ramp_resource_lp.ipynb` prototype first; `src/lp/` is the extraction target | ✅ Pass |
| III. Test Coverage | `tests/lp/` mirrors `src/lp/`; every public function has a corresponding test; pytest only | ✅ Pass |
| IV. Reproducibility | GLOP is deterministic; `ortools` declared in `pyproject.toml` under new `lp` optional group | ✅ Pass |
| V. Simplicity | Two-stage LP follows Sahadevan + textbook formulations; YAGNI applied; no premature generalisation | ✅ Pass |
| Dev Workflow Rule 4 | `business_problems/ramp_resource_lp.py` references `src/lp/` solver, does not re-implement inline | ✅ Pass |

**No violations. Complexity Tracking not required.**

**Post-Phase 1 re-check**: Re-verify after data-model.md and contracts/ are finalised; confirm no new abstractions were introduced beyond what the spec requires.

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
├── types.py                    ← dataclasses: FlightSlotInput, AircraftType, DemandConfig, DemandResult, ShiftConfig, ShiftSchedule, BottleneckResult, ComparisonReport
├── demand.py                   ← Stage 1: compute_demand() — Sahadevan LP constraints (5)–(9)
├── scheduling.py               ← Stage 2: schedule_shifts() — textbook shift-start LP
└── analysis.py                 ← identify_bottlenecks(), comparison_report()

tests/lp/                       ← NEW: test suite mirroring src/lp/
├── __init__.py
├── test_types.py               ← validates defaults and dataclass invariants
├── test_demand.py              ← US1–US2, US5–US7, FR-001 to FR-004, FR-010–FR-011
├── test_scheduling.py          ← US3–US4, FR-005–FR-006, SC-002, SC-006
└── test_analysis.py            ← US8, FR-008–FR-009, SC-003–SC-005

notebooks/planning/
└── ramp_resource_lp.ipynb      ← NEW: prototype notebook (Principle II); imports src/lp once extracted

business_problems/
├── ramp_resource_minimization_formulation.md    ← EXISTING: mathematical derivation (keep)
└── ramp_resource_lp.py                          ← NEW: Finavia-specific instantiation calling src/lp

pyproject.toml                  ← UPDATE: add `lp = ["ortools"]` optional dependency group
```

**Structure Decision**: Single-project layout (Option 1). New `src/lp/` module follows the existing `src/<domain>/` convention. `business_problems/ramp_resource_lp.py` satisfies Dev Workflow Rule 4 (business formulations reference `src/` solvers). The existing `business_problems/ramp_resource_minimization_formulation.md` is preserved as the mathematical reference document.

## Complexity Tracking

> No violations — table not required.
