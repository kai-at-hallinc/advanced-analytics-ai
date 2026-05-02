# advanced-analytics-ai Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-02

## Active Technologies
- N/A — in-memory computation, no persistent state (001-ramp-resource-lp)
- Python 3.10+ (required by constitution) + `ortools` (GLOP LP solver) — declared as `lp` optional group in `pyproject.toml`; standard library only (`dataclasses`, `typing`, `math`, `zoneinfo`, `enum`) (001-ramp-resource-lp)

- Python 3.10+ + `ortools` (GLOP LP solver), Python standard library (`dataclasses`, `typing`, `math`) (main)

## Project Structure

```text
src/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.10+: Follow standard conventions

## Recent Changes
- 001-ramp-resource-lp: Added Python 3.10+ (required by constitution) + `ortools` (GLOP LP solver) — declared as `lp` optional group in `pyproject.toml`; standard library only (`dataclasses`, `typing`, `math`, `zoneinfo`, `enum`)
- 001-ramp-resource-lp: Added Python 3.10+ + `ortools` (GLOP LP solver), Python standard library (`dataclasses`, `typing`, `math`)

- main: Added Python 3.10+ + `ortools` (GLOP LP solver), Python standard library (`dataclasses`, `typing`, `math`)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
