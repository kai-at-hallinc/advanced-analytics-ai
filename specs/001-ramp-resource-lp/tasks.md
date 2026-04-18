# Tasks: Ramp Resource LP — Ground Handling Worker Scheduling

**Input**: Design documents from `/specs/001-ramp-resource-lp/`
**Branch**: `001-ramp-resource-lp`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅

**Tests**: Included — Constitution Principle III requires `tests/lp/` mirroring `src/lp/` with every public function covered.

**Organization**: Tasks grouped by user story (US1–US9) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependencies)
- **[Story]**: Which user story this task belongs to (US1–US9)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module skeleton, install dependencies, configure tools.

- [ ] T001 Create directories `src/lp/`, `tests/lp/`, `notebooks/planning/` per plan.md structure
- [ ] T002 Update `pyproject.toml` — add `[project.optional-dependencies]` group `lp = ["ortools"]`
- [ ] T003 [P] Create `src/lp/__init__.py` stub (empty exports list, docstring)
- [ ] T004 [P] Create `tests/lp/__init__.py` stub (empty file)

---

## Phase 2: Foundational — Types Module (Blocking Prerequisites)

**Purpose**: All dataclasses, enums, and default constants in `src/lp/types.py` must exist before any solver function can be written or tested.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [ ] T005 Implement `src/lp/types.py` — `AircraftType` enum (NARROW_BODY, WIDE_BODY, CARGO); dataclasses `FlightSlotInput` (hour, arrival_counts, departure_counts), `DemandConfig` (staffing_standards, arrival_window_slots, departure_staffing_standards, departure_window_slots, tolerance_minutes, pool_size, operating_day_start, operating_day_end), `DemandResult`, `ShiftConfig`, `ShiftSchedule`, `BottleneckResult`, `ComparisonReport`; constants `DEFAULT_STAFFING_STANDARDS`, `DEFAULT_ARRIVAL_WINDOW_SLOTS`, `DEFAULT_DEPARTURE_STAFFING_STANDARDS`, `DEFAULT_DEPARTURE_WINDOW_SLOTS`, `DEFAULT_OPERATING_HOURS`
- [ ] T006 [P] Write `tests/lp/test_types.py` — validate `AircraftType` enum values; `DemandConfig` defaults (3/5/6, 1/2/3 slots); `FlightSlotInput` missing-type defaults to 0; `DemandResult` invariant `len(demand_curve) == len(operating_hours)`; `ShiftSchedule` invariant `daily_headcount == sum(shift_starts_rounded.values())`; `ComparisonReport` list-length invariants; `ValueError` raised for out-of-range hour and negative counts

**Checkpoint**: All types are importable and type-checked — user story implementation can now begin.

---

## Phase 3: US1 — Hourly Demand from Flight Schedule (Priority: P1) 🎯 MVP

**Goal**: `compute_demand()` in scheduled-only mode produces a correct per-slot arrival demand curve using the arrival window for each aircraft type.

**Independent Test**: Pass a single-slot schedule with 2 wide-body arrivals; confirm demand_curve at that slot equals 2 × 5 = 10 and spans 2 slots (wide-body arrival window = 2 h). Confirm all other slots are 0.

- [ ] T007 [US1] Write `tests/lp/test_demand.py` for US1 — single-type single-slot (narrow/wide/cargo); multi-type same slot sums independently; arrival window spanning multiple slots; empty schedule returns all-zero curve; out-of-range hour raises `ValueError`; duplicate hour raises `ValueError`
- [ ] T008 [US1] Implement `compute_demand()` in `src/lp/demand.py` — scheduled-only mode; iterate slots, expand each arrival count forward across `arrival_window_slots` for its type; return `DemandResult` with demand_curve, feasible=True, infeasible_slots=[], operating_hours
- [ ] T009 [US1] Update `src/lp/__init__.py` — export `compute_demand`, `AircraftType`, `FlightSlotInput`, `DemandConfig`, `DemandResult`, `DEFAULT_DEMAND_CONFIG`

**Checkpoint**: `compute_demand(scheduled=[...])` returns a correct demand curve — US1 fully functional.

---

## Phase 4: US2 — Delay-Adjusted Demand (Priority: P2)

**Goal**: `compute_demand()` applies the 20/80 heuristic via `delay_flags` (FR-002) and uses actual counts directly via `actuals` (FR-003). Three-mode precedence: actuals > delay_flags > scheduled.

**Independent Test**: Mark narrow-body as delayed; confirm original slot drops to 20% of scheduled count and the actual slot receives 80%. Then pass actuals directly and confirm no 20/80 split is applied.

- [ ] T010 [US2] Add delay_flags test cases to `tests/lp/test_demand.py` — delayed type: 20% at original slot, 80% at actual slot; on-time type unchanged; mixed delayed/on-time in same slot; actuals override heuristic when both provided; scheduled used unchanged when neither provided
- [ ] T011 [US2] Extend `compute_demand()` in `src/lp/demand.py` — add `delay_flags` branch applying `n_ij = s_ij · (1 − 0.8·d_i)` per delayed type; add `actuals` branch using actual arrival_counts directly; enforce precedence (actuals → delay_flags → scheduled)

**Checkpoint**: All three input modes work correctly and independently — US2 fully functional.

---

## Phase 5: US3 — Minimum Shift Schedule (Priority: P3)

**Goal**: `schedule_shifts()` solves the shift-start LP via GLOP, rounds up fractional values with `math.ceil`, re-verifies coverage post-rounding (SC-006).

**Independent Test**: Pass a demand curve of [5, 5, 5, ..., 5] across 18 slots with shift_length=8. Confirm total workers < 18 × 5 ÷ 8 = 11.25 (naive ceiling), coverage_satisfied=True, and all shifts in shift_starts_rounded are integers ≥ 0.

- [ ] T012 [US3] Write `tests/lp/test_scheduling.py` for US3 — total workers < naive peak-staffing total (SC-002); all coverage constraints met post-rounding (SC-006); coverage_satisfied=True; coverage_shortfalls empty; raises `ValueError` when demand.feasible=False
- [ ] T013 [US3] Implement `schedule_shifts()` in `src/lp/scheduling.py` — build GLOP LP (`pywraplp.Solver.CreateSolver('GLOP')`); add shift-start variables; add coverage constraints per operating hour; solve; apply `math.ceil` to each `x_t`; re-verify all coverage constraints on rounded values; return `ShiftSchedule`
- [ ] T014 [US3] Update `src/lp/__init__.py` — export `schedule_shifts`, `ShiftConfig`, `ShiftSchedule`

**Checkpoint**: `schedule_shifts()` produces a minimum-cost integer shift plan — US3 fully functional.

---

## Phase 6: US4 — Accurate Daily Headcount (Priority: P4)

**Goal**: `daily_headcount` in `ShiftSchedule` equals the sum of `shift_starts_rounded` — no deduplication required.

**Independent Test**: Sum `shift_starts_rounded.values()` manually and confirm it equals `daily_headcount` on several varied demand inputs including uniform, peak-morning, and bi-modal curves.

- [ ] T015 [US4] Add headcount accuracy tests to `tests/lp/test_scheduling.py` — `daily_headcount == sum(shift_starts_rounded.values())` for uniform demand; peak-morning demand; bi-modal demand; zero-demand edge case returns headcount=0; single-slot demand
- [ ] T016 [US4] Verify `daily_headcount` assignment in `src/lp/scheduling.py` — computed as `sum(ceil(x_t) for all t)` immediately after rounding; confirm SC-004 invariant holds across all test inputs

**Checkpoint**: Headcount output is payroll-ready with no downstream deduplication — US4 fully functional.

---

## Phase 7: US5 — Capacity Constraint Enforcement (Priority: P5)

**Goal**: When any slot's demand exceeds `pool_size`, `compute_demand()` returns `feasible=False` with `infeasible_slots` listing all violating clock hours. The full `demand_curve` is still returned.

**Independent Test**: Set `pool_size=0` and pass any non-empty schedule; confirm `feasible=False`, `infeasible_slots` contains every non-zero-demand slot, and `demand_curve` is non-empty.

- [ ] T017 [US5] Add pool enforcement tests to `tests/lp/test_demand.py` — demand ≤ pool_size → feasible=True, infeasible_slots=[]; demand > pool_size at one slot → feasible=False, that slot in infeasible_slots, curve still returned; pool_size=0 with any demand → all demand slots in infeasible_slots
- [ ] T018 [US5] Add pool_size post-check to `compute_demand()` in `src/lp/demand.py` — after building demand_curve, scan each slot; if `r_j > pool_size` add to infeasible_slots; set feasible=False when infeasible_slots non-empty; always return full curve

**Checkpoint**: Infeasibility is surfaced clearly with specific slot identification — US5 fully functional.

---

## Phase 8: US6 — Aircraft-Type Staffing Standards (Priority: P6)

**Goal**: `staffing_standards` and `departure_staffing_standards` in `DemandConfig` are configurable per aircraft type independently. Defaults are 3/5/6 for narrow/wide/cargo. Overriding one type does not affect others.

**Independent Test**: Override only the narrow-body arrival standard to 4; run a schedule with 1 narrow-body and 1 wide-body in the same slot; confirm narrow contributes 4 and wide contributes 5 (unchanged default).

- [ ] T019 [P] [US6] Add custom arrival staffing standard tests to `tests/lp/test_demand.py` — overriding narrow standard doesn't affect wide or cargo; all-default produces 3/5/6; zero-count slot unchanged regardless of standard
- [ ] T020 [P] [US6] Add custom departure staffing standard tests to `tests/lp/test_demand.py` — departure standard override does not cross-contaminate arrival standard for same aircraft type; `departure_staffing_standards` defaults match `staffing_standards`

**Checkpoint**: Both arrival and departure staffing standards are independently configurable — US6 fully functional.

---

## Phase 9: US7 — On-Time Window Classification (Priority: P7)

**Goal**: Arrivals outside ±`tolerance_minutes` of their scheduled slot are reclassified to the actual slot. Early arrivals receive equal or greater demand (FR-010). Applies to both arrivals and departures (FR-011).

**Independent Test**: Provide a flight scheduled at 09:00 that actually arrives at 08:40 (early, outside 15-min tolerance); confirm resources appear at 08:00 slot (actual hour), not 09:00, and the count at 08:00 equals the full staffing standard (not reduced).

- [ ] T021 [US7] Add on-time classification tests to `tests/lp/test_demand.py` — inside window (±14 min): demand at scheduled slot; outside window late (25 min late): demand at actual slot; outside window early (20 min early): demand at actual slot, not reduced (FR-010); tolerance configurable (set to 10 min, 12-min-late flight → reclassified); departure outside window: departure window anchored at actual departure slot (FR-011)
- [ ] T022 [US7] Implement on-time classification in `compute_demand()` in `src/lp/demand.py` — when actuals provided with minute-level timestamps, compute `|t_actual − t_scheduled|` per flight; if within `tolerance_minutes` use scheduled slot, else use actual slot; for early arrivals: use actual slot, demand not reduced below standard (FR-010); for departures: departure window anchored at actual departure slot when outside tolerance

**Checkpoint**: Slot reclassification works for late, early, and on-time flights in both directions — US7 fully functional.

---

## Phase 10: US8 — Bottleneck Hour Identification (Priority: P8)

**Goal**: `identify_bottlenecks()` returns every operating hour where workers on duty exactly equals demand (no surplus). Each bottleneck is labelled with its clock hour and binding demand value.

**Independent Test**: Construct a `DemandResult` and `ShiftSchedule` where hour 07:00 has workers == demand and hour 10:00 has workers > demand + 2; confirm bottleneck_hours = [7], demand_at_bottleneck = {7: demand_value}, hour 10 absent.

- [ ] T023 [US8] Write `tests/lp/test_analysis.py` for US8 — hour where workers == demand flagged as bottleneck; hour where workers > demand not flagged; bottleneck labelled with clock hour and demand value; empty bottleneck list when all hours have surplus
- [ ] T024 [US8] Implement `identify_bottlenecks()` in `src/lp/analysis.py` — compute active_workers_at_hour for each operating hour from `shift_starts_rounded` and `shift_length`; compare against `demand.demand_curve`; collect hours where active == demand; return `BottleneckResult`
- [ ] T025 [US8] Update `src/lp/__init__.py` — export `identify_bottlenecks`, `BottleneckResult`

**Checkpoint**: Bottleneck hours are correctly identified and labelled — US8 fully functional.

---

## Phase 11: US9 — Independent Departure Demand (Priority: P9)

**Goal**: `compute_demand()` computes backward-looking departure demand from `departure_counts` using `departure_window_slots` and `departure_staffing_standards`, sums it independently with arrival demand. Departure window clipped silently at `operating_day_start`. FR-015 (actual departure counts) and departure delay_flags follow the same 3-mode pattern as arrivals.

**Independent Test**: Pass a schedule with zero arrivals and 1 wide-body departure at 14:00; confirm demand_curve is non-zero at slots 13:00 and 14:00 (backward window = 2 h for wide-body), values equal 1 × 5 = 5 each, and all other slots are 0.

- [ ] T026 [US9] Add departure demand tests to `tests/lp/test_demand.py` — departure-only schedule produces non-zero demand; arrival+departure independent (different standards, no cross-contamination); backward window correct (dep at slot m → demand at m−W_dep+1…m); departure boundary clipping (dep at 05:00 with 3-slot window clips to 05:00 only, no pre-day slots); departure delay_flags apply 20/80 heuristic; actual departure counts override heuristic (FR-015)
- [ ] T027 [US9] Extend `compute_demand()` in `src/lp/demand.py` — add backward departure window loop iterating `departure_counts` per slot; apply `departure_staffing_standards`; clip window at `operating_day_start`; add departure delay_flags branch and departure actuals branch (FR-015 precedence); sum arrival and departure contributions at each slot

**Checkpoint**: Departure demand is independently computed and correctly summed — US9 fully functional.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: `comparison_report()`, full integration with EFHK data, and notebook prototype.

- [ ] T028 [P] Write `tests/lp/test_analysis.py` for comparison_report (FR-008) — arrival_gap_absolute and departure_gap_absolute computed correctly per slot; aggregate pct_total formula correct; total_scheduled/actual_demand = arrival + departure; all list lengths equal len(hours); faithfully reflects input differences with no smoothing (SC-003)
- [ ] T029 [P] Implement `comparison_report()` in `src/lp/analysis.py` — call `compute_demand(scheduled)` and `compute_demand(actuals=actuals)` separately; decompose DemandResult into arrival and departure components; compute per-slot gaps and aggregate pct_total for each direction; return `ComparisonReport`
- [ ] T030 Update `src/lp/__init__.py` — export `comparison_report`, `ComparisonReport`, `DEFAULT_DEPARTURE_STAFFING_STANDARDS`, `DEFAULT_DEPARTURE_WINDOW_SLOTS`, `DEFAULT_ARRIVAL_WINDOW_SLOTS`
- [ ] T031 [P] Create `business_problems/ramp_resource_lp.py` — EFHK CSV loader reading `data/finavia_flights_efhk_20260330.csv`; ICAO → LP category mapping (AT75/A320-family/E190/B737-family → narrow_body; A332/A333/A359 → wide_body; flight_type_iata=F → cargo); operating-window pre-filter (drop hours outside 05:00–23:00); aggregates to `list[FlightSlotInput]` and calls `src/lp/`
- [ ] T032 [P] Create `notebooks/planning/ramp_resource_lp.ipynb` — prototype notebook loading EFHK data via `business_problems/ramp_resource_lp.py`; calling `compute_demand()` and `schedule_shifts()`; displaying demand curve, shift schedule, and bottleneck hours (Constitution Principle II)
- [ ] T033 Run full end-to-end integration with `data/finavia_flights_efhk_20260330.csv` — verify demand curve is non-zero across operating hours, schedule_shifts produces feasible headcount, identify_bottlenecks returns results, no ValueError raised after ICAO mapping and window pre-filtering

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **US1 (Phase 3)**: Depends on Phase 2 — first story, no story dependencies
- **US2 (Phase 4)**: Depends on Phase 3 (extends compute_demand)
- **US3 (Phase 5)**: Depends on Phase 3 (consumes DemandResult)
- **US4 (Phase 6)**: Depends on Phase 5 (verifies schedule_shifts output)
- **US5 (Phase 7)**: Depends on Phase 3 (adds post-check to compute_demand)
- **US6 (Phase 8)**: Depends on Phase 3 (tests configurable DemandConfig)
- **US7 (Phase 9)**: Depends on Phase 4 (requires actuals mode in compute_demand)
- **US8 (Phase 10)**: Depends on Phase 5 (requires schedule_shifts output)
- **US9 (Phase 11)**: Depends on Phase 3 (extends compute_demand with departure logic)
- **Polish (Phase 12)**: Depends on Phase 9 and Phase 10 and Phase 11 — all stories complete

### User Story Dependencies (summary)

```text
Phase 1 → Phase 2 → US1 (P1) → US2 (P2) → US7 (P7)
                  ↘ US1 (P1) → US3 (P3) → US4 (P4)
                  ↘ US1 (P1) → US5 (P5)
                  ↘ US1 (P1) → US6 (P6)
                  ↘ US1 (P1) → US3 (P3) → US8 (P8)
                  ↘ US1 (P1) → US9 (P9)
All of the above → Polish (Phase 12)
```

### Within Each User Story

- Tests MUST be written and confirmed failing before implementation
- Implementation tasks within a phase follow: types → compute logic → exports
- Each phase checkpoint validates the story independently before advancing

### Parallel Opportunities (within Phases)

- **Phase 1**: T003 and T004 are parallel (different stub files)
- **Phase 2**: T005 and T006 are parallel (types.py vs test_types.py)
- **Phase 5 → 9**: US5, US6, US9 can all begin in parallel once US1 is complete (each extends compute_demand independently before being merged)
- **Phase 12**: T028/T029, T031, T032 can all run in parallel (different files)

---

## Parallel Example: After US1 Complete

Once Phase 3 (US1) is done, these stories can run concurrently:

```text
Developer A: US3 (Phase 5) → US4 (Phase 6) → US8 (Phase 10)
Developer B: US5 (Phase 7) → US9 (Phase 11)
Developer C: US6 (Phase 8) → US7 (Phase 9)
```

Merge compute_demand() extensions from US2, US5, US7, US9 carefully — all modify the same function; coordinate branch strategy to avoid conflicts.

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational types
3. Complete Phase 3: US1 — `compute_demand()` scheduled mode
4. **STOP and VALIDATE**: Run `tests/lp/test_demand.py` for US1 independently
5. Notebook prototype with EFHK scheduled data (T032)

### Incremental Delivery

1. Setup + Foundational → types importable
2. US1 → `compute_demand()` working on scheduled data → MVP
3. US3 + US4 → `schedule_shifts()` working → shift plan produceable
4. US2 → delay adjustment → delay-aware demand
5. US5 → infeasibility detection → safe for production inputs
6. US6 + US7 → configurable standards + tolerance → calibration-ready
7. US8 → bottleneck analysis → operational insight
8. US9 → departure demand → full two-direction model
9. Phase 12 → comparison report + EFHK integration + notebook

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel within a phase
- `[Story]` label maps every implementation task to a spec user story for traceability
- `compute_demand()` is extended incrementally across US1→US2→US5→US7→US9; test each extension independently before merging
- The ICAO → LP category mapping (T031) is the caller's responsibility; the LP module (`src/lp/`) never sees raw ICAO codes
- Operating-window pre-filtering (T031) must run before `compute_demand()` — flights before 05:00 or after 22:00 raise `ValueError` if passed to the LP
- Commit after each phase checkpoint
- Run `pytest tests/lp/` from repo root after every phase
