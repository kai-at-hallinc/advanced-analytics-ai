# Tasks: Ramp Resource LP — Ground Handling Worker Scheduling

**Input**: Design documents from `/specs/001-ramp-resource-lp/`
**Branch**: `001-ramp-resource-lp`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅

**Tests**: Included — Constitution Principle III requires `tests/lp/` and `tests/utils/` mirroring `src/` with every public function covered.

**Organization**: Tasks grouped by user story (US1–US9) to enable independent implementation and testing of each story.

**Last updated**: 2026-05-02 — audited against `src/lp/` and `tests/lp/`; T031 updated to `src/utils/efhk_loader.py`; T035–T037 added for completed utils module.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependencies)
- **[Story]**: Which user story this task belongs to (US1–US9)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create module skeleton, install dependencies, configure tools.

- [X] T001 Create directories `src/lp/`, `tests/lp/`, `notebooks/planning/` per plan.md structure
- [X] T002 Update `pyproject.toml` — add `[project.optional-dependencies]` group `lp = ["ortools"]`
- [X] T003 [P] Create `src/lp/__init__.py` stub (empty exports list, docstring)
- [X] T004 [P] Create `tests/lp/__init__.py` stub (empty file)

---

## Phase 1b: Utils Module (src/utils/)

**Purpose**: Integration layer — EFHK CSV loader, UTC→Helsinki conversion, ICAO mapping (constitution rule 5: data-loading utilities in `src/utils/`).

- [X] T035 [P] Create `src/utils/__init__.py` — re-exports `load_efhk`, `ICAO_TO_LP_CATEGORY`
- [X] T036 [P] Implement `src/utils/efhk_loader.py` — UTC→Helsinki via `ZoneInfo("Europe/Helsinki")`; ICAO code → `AircraftType` mapping (`AT75`, `AT76`, A320/B737-family → `NARROW_BODY`; A330/A350/B77x-family → `WIDE_BODY`; `flight_type_iata=F` → `CARGO`); operating-window filter (05:00–23:00 Helsinki); aggregate to `list[FlightSlotInput]`; extract `actual_arrival_time`/`actual_departure_time` → `FlightMovementInput` by default (`extract_actuals=True`); null actual → `actual_minutes=None`; `use_actual_times=True` aggregates slots by actual time (falls back to scheduled when null)
- [X] T037 [P] Write `tests/utils/test_efhk_loader.py` — ICAO mapping (AT76 → NARROW_BODY, A359 → WIDE_BODY, `flight_type_iata=F` overrides airframe); UTC→Helsinki conversion (2026-03-27 UTC+2); all hours within operating window; no duplicate hours; actuals extracted by default; actuals suppressed when `extract_actuals=False`; all movements have valid `op_type`; all `scheduled_minutes` in window

---

## Phase 2: Foundational — Types Module (Blocking Prerequisites)

**Purpose**: All dataclasses, enums, and default constants in `src/lp/types.py` must exist before any solver function can be written or tested.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T005 Implement `src/lp/types.py` — `AircraftType` enum (NARROW_BODY, WIDE_BODY, CARGO); dataclasses `FlightSlotInput` (hour, arrival_counts, departure_counts), `FlightMovementInput` (aircraft_type, op_type: Literal['A','D'], scheduled_minutes: int, actual_minutes: int|None), `DemandConfig` (staffing_standards, arrival_window_slots, departure_staffing_standards, departure_window_slots, tolerance_minutes, pool_size, operating_day_start, operating_day_end), `DemandResult` (demand_curve, arrival_demand_curve, departure_demand_curve, feasible, infeasible_slots, operating_hours), `ShiftConfig`, `ShiftSchedule`, `BottleneckResult`, `ComparisonReport`; constants `DEFAULT_STAFFING_STANDARDS`, `DEFAULT_ARRIVAL_WINDOW_SLOTS`, `DEFAULT_DEPARTURE_STAFFING_STANDARDS`, `DEFAULT_DEPARTURE_WINDOW_SLOTS`, `DEFAULT_OPERATING_HOURS`
- [X] T006 [P] Write `tests/lp/test_types.py` — validate `AircraftType` enum values; `DemandConfig` defaults (3/5/6, 1/2/3 slots); `FlightSlotInput` missing-type defaults to 0; `FlightMovementInput` validation (invalid op_type raises `ValueError`, out-of-range `scheduled_minutes` raises `ValueError`); `DemandResult` invariants: `len(demand_curve) == len(arrival_demand_curve) == len(departure_demand_curve) == len(operating_hours)` and `demand_curve[i] == arrival_demand_curve[i] + departure_demand_curve[i]`; `ShiftSchedule` invariant `daily_headcount == sum(shift_starts_rounded.values())`; `ComparisonReport` list-length invariants; `ValueError` raised for out-of-range hour and negative counts

**Checkpoint**: All types are importable and type-checked — user story implementation can now begin.

---

## Phase 3: US1 — Hourly Demand from Flight Schedule (Priority: P1) 🎯 MVP

**Goal**: `compute_demand()` in scheduled-only mode produces a correct per-slot arrival demand curve using the arrival window for each aircraft type.

**Independent Test**: Pass a single-slot schedule with 2 wide-body arrivals; confirm demand_curve at that slot equals 2 × 5 = 10 and spans 2 slots (wide-body arrival window = 2 h). Confirm all other slots are 0.

- [X] T007 [US1] Write `tests/lp/test_demand.py` for US1 — single-type single-slot (narrow/wide/cargo); multi-type same slot sums independently; arrival window spanning multiple slots; empty schedule returns all-zero curve; out-of-range hour raises `ValueError`; duplicate hour raises `ValueError`
- [X] T008 [US1] Implement `compute_demand()` in `src/lp/demand.py` — scheduled-only mode; iterate slots, expand each arrival count forward across `arrival_window_slots` for its type; return `DemandResult` with demand_curve, arrival_demand_curve (= computed arrival demand), departure_demand_curve (= all-zeros; no departures in US1 scheduled-only mode), feasible=True, infeasible_slots=[], operating_hours
- [X] T009 [US1] Update `src/lp/__init__.py` — export `compute_demand`, `AircraftType`, `FlightSlotInput`, `FlightMovementInput`, `DemandConfig`, `DemandResult`, `DEFAULT_DEMAND_CONFIG`

**Checkpoint**: `compute_demand(scheduled=[...])` returns a correct demand curve — US1 fully functional.

---

## Phase 4: US2 — Independent Departure Demand (Priority: P2)

**Goal**: `compute_demand()` computes backward-looking departure demand from `departure_counts` in `scheduled`, using `departure_window_slots` and `departure_staffing_standards`, and sums it independently with arrival demand. Departure window clipped silently at `operating_day_start`. Result carries separate `arrival_demand_curve` and `departure_demand_curve` sub-curves alongside the combined `demand_curve`.

**Independent Test**: Pass a schedule with zero arrivals and 1 wide-body departure at 14:00; confirm `demand_curve` is non-zero at slots 13:00 and 14:00 (backward window = 2 h), values equal 1 × 5 = 5 each, all other slots 0. Confirm `departure_demand_curve` matches and `arrival_demand_curve` is all-zeros.

- [X] T026 [US2] Add departure demand tests to `tests/lp/test_demand.py` — departure-only schedule produces non-zero demand; arrival+departure independent (different standards, no cross-contamination); backward window correct (dep at slot m → demand at m−W_dep+1…m); departure boundary clipping (dep at 05:00 with 3-slot window clips to 05:00 only, no pre-day slots); `DemandResult.departure_demand_curve` non-zero, `arrival_demand_curve` all-zero for departure-only input; same slot with both arrivals and departures: demands summed independently
- [X] T027 [US2] Extend `compute_demand()` in `src/lp/demand.py` — add backward departure window loop iterating `departure_counts` per slot from `scheduled`; apply `departure_staffing_standards`; clip window at `operating_day_start`; sum arrival and departure contributions into `demand_curve`; populate `arrival_demand_curve` and `departure_demand_curve` as separate outputs on `DemandResult`

**Checkpoint**: `compute_demand()` produces correct combined demand with independent sub-curves — US2 fully functional.

---

## Phase 5: US3 — Delay-Adjusted Demand (Priority: P3)

**Goal**: `compute_demand()` applies the 20/80 heuristic via `arrival_delay_flags` / `departure_delay_flags` (FR-002) independently per direction, and accepts slot-level actual counts via `actuals` as a higher-precedence override for both arrivals (FR-003) and departures (FR-015). Four-mode precedence per direction: actual_movements → actuals → arrival_delay_flags / departure_delay_flags → scheduled.

**Independent Test**: Mark narrow-body as delayed (`arrival_delay_flags`); confirm original arrival slot drops to 20% and actual slot receives 80%. Mark wide-body as departure-delayed (`departure_delay_flags`); confirm same split for departures independently. Then pass `actuals` directly and confirm no 20/80 split is applied for either direction.

- [X] T010 [US3] Add `arrival_delay_flags` and `departure_delay_flags` test cases to `tests/lp/test_demand.py` — arrival delayed type: 20% at original slot, 80% at actual slot; departure delayed type: same heuristic applied independently; on-time type unchanged in both directions; mixed delayed/on-time in same slot; `actuals.arrival_counts` overrides arrival delay heuristic; `actuals.departure_counts` overrides departure delay heuristic (FR-015); scheduled used unchanged when neither provided; arrival_delay_flags does not affect departure counts and vice versa
- [X] T011 [US3] Extend `compute_demand()` in `src/lp/demand.py` — add `arrival_delay_flags` branch applying `n_ij = s_ij · (1 − 0.8·d_i)` per delayed arrival type; add `departure_delay_flags` branch applying same heuristic per delayed departure type independently; add `actuals` branch using `arrival_counts`/`departure_counts` directly per direction (FR-015 precedence for departures); enforce per-direction precedence (actual_movements → actuals → arrival_delay_flags / departure_delay_flags → scheduled)

**Checkpoint**: All delay modes work correctly for both directions — US3 fully functional.

---

## Phase 6: US4 — Minimum Shift Schedule (Priority: P4)

**Goal**: `schedule_shifts()` solves the shift-start LP via GLOP, rounds up fractional values with `math.ceil`, re-verifies coverage post-rounding (SC-006).

**Independent Test**: Pass a demand curve of [5, 5, 5, ..., 5] across 18 slots with shift_length=8. Confirm total workers < 18 × 5 ÷ 8 = 11.25 (naive ceiling), coverage_satisfied=True, and all shifts in shift_starts_rounded are integers ≥ 0.

- [X] T012 [US4] Write `tests/lp/test_scheduling.py` for US4 — total workers < naive peak-staffing total (SC-002); all coverage constraints met post-rounding (SC-006); coverage_satisfied=True; coverage_shortfalls empty; raises `ValueError` when demand.feasible=False
- [X] T013 [US4] Implement `schedule_shifts()` in `src/lp/scheduling.py` — build GLOP LP (`pywraplp.Solver.CreateSolver('GLOP')`); add shift-start variables; add coverage constraints per operating hour; solve; apply `math.ceil` to each `x_t`; re-verify all coverage constraints on rounded values; return `ShiftSchedule`
- [X] T014 [US4] Update `src/lp/__init__.py` — export `schedule_shifts`, `ShiftConfig`, `ShiftSchedule`

**Checkpoint**: `schedule_shifts()` produces a minimum-cost integer shift plan — US4 fully functional.

---

## Phase 7: US5 — Accurate Daily Headcount (Priority: P5)

**Goal**: `daily_headcount` in `ShiftSchedule` equals the sum of `shift_starts_rounded` — no deduplication required.

**Independent Test**: Sum `shift_starts_rounded.values()` manually and confirm it equals `daily_headcount` on several varied demand inputs including uniform, peak-morning, and bi-modal curves.

- [X] T015 [US5] Add headcount accuracy tests to `tests/lp/test_scheduling.py` — `daily_headcount == sum(shift_starts_rounded.values())` for uniform demand; peak-morning demand; bi-modal demand; zero-demand edge case returns headcount=0; single-slot demand
- [X] T016 [US5] Verify `daily_headcount` assignment in `src/lp/scheduling.py` — computed as `sum(ceil(x_t) for all t)` immediately after rounding; confirm SC-004 invariant holds across all test inputs

**Checkpoint**: Headcount output is payroll-ready with no downstream deduplication — US5 fully functional.

---

## Phase 8: US6 — Capacity Constraint Enforcement (Priority: P6)

**Goal**: When any slot's combined demand exceeds `pool_size`, `compute_demand()` returns `feasible=False` with `infeasible_slots` listing all violating clock hours. The full `demand_curve` is still returned.

**Independent Test**: Set `pool_size=0` and pass any non-empty schedule; confirm `feasible=False`, `infeasible_slots` contains every non-zero-demand slot, and `demand_curve` is non-empty.

- [ ] T017 [US6] Add pool enforcement tests to `tests/lp/test_demand.py` — demand > pool_size at one slot → feasible=False, that slot in infeasible_slots, curve still returned; pool_size=0 with any demand → all demand slots in infeasible_slots *(note: feasible=True case already covered by existing test_feasible_true_when_demand_within_pool — add the infeasible=True cases only)*
- [X] T018 [US6] Add pool_size post-check to `compute_demand()` in `src/lp/demand.py` — after building demand_curve, scan each slot; if `r_j > pool_size` add to infeasible_slots; set feasible=False when infeasible_slots non-empty; always return full curve

**Checkpoint**: Infeasibility is surfaced clearly with specific slot identification — US6 fully functional.

---

## Phase 9: US7 — Aircraft-Type Staffing Standards (Priority: P7)

**Goal**: `staffing_standards` and `departure_staffing_standards` in `DemandConfig` are configurable per aircraft type independently. Defaults are 3/5/6 for narrow/wide/cargo. Overriding one type does not affect others.

**Independent Test**: Override only the narrow-body arrival standard to 4; run a schedule with 1 narrow-body and 1 wide-body in the same slot; confirm narrow contributes 4 and wide contributes 5 (unchanged default).

- [X] T019 [P] [US7] Add custom arrival staffing standard tests to `tests/lp/test_demand.py` — overriding narrow standard doesn't affect wide or cargo; all-default produces 3/5/6; zero-count slot unchanged regardless of standard
- [X] T020 [P] [US7] Add custom departure staffing standard tests to `tests/lp/test_demand.py` — departure standard override does not cross-contaminate arrival standard for same aircraft type; `departure_staffing_standards` defaults match `staffing_standards`

**Checkpoint**: Both arrival and departure staffing standards are independently configurable — US7 fully functional.

---

## Phase 10: US8 — On-Time Window Classification (Priority: P8)

**Goal**: Arrivals outside ±`tolerance_minutes` of their scheduled slot are reclassified to the actual slot. Early arrivals receive equal or greater demand (FR-010). Applies to both arrivals and departures (FR-011).

**Independent Test**: Provide a flight scheduled at 09:00 that actually arrives at 08:40 (early, outside 15-min tolerance); confirm resources appear at 08:00 slot (actual hour), not 09:00, and the count at 08:00 equals the full staffing standard (not reduced).

- [ ] T021 [US8] Add on-time classification tests to `tests/lp/test_demand.py` using `actual_movements: list[FlightMovementInput]` — inside window (±14 min): demand at scheduled slot; outside window late (25 min late): demand at actual slot; outside window early (20 min early): demand at actual slot, not reduced (FR-010); tolerance configurable (set to 10 min, 12-min-late flight → reclassified); departure outside window: departure window anchored at `floor(actual_minutes/60)`; slot-level `actuals` (no `actual_movements`): no reclassification applied
- [ ] T022 [US8] Implement on-time classification in `compute_demand()` in `src/lp/demand.py` — when `actual_movements` provided, aggregate per `aircraft_type`/`op_type` after tolerance check: compute `|actual_minutes − scheduled_minutes|` per `FlightMovementInput`; if within `tolerance_minutes` assign to `floor(scheduled_minutes/60)`, else assign to `floor(actual_minutes/60)`; for early arrivals: use actual slot, demand not reduced below standard (FR-010); for departures: departure window anchored at reclassified slot; populate `arrival_demand_curve` and `departure_demand_curve` separately before summing into `demand_curve`

**Checkpoint**: Slot reclassification works for late, early, and on-time flights in both directions — US8 fully functional.

---

## Phase 11: US9 — Bottleneck Hour Identification (Priority: P9)

**Goal**: `identify_bottlenecks()` returns every operating hour where workers on duty exactly equals demand (no surplus). Each bottleneck is labelled with its clock hour and binding demand value.

**Independent Test**: Construct a `DemandResult` and `ShiftSchedule` where hour 07:00 has workers == demand and hour 10:00 has workers > demand + 2; confirm bottleneck_hours = [7], demand_at_bottleneck = {7: demand_value}, hour 10 absent.

- [ ] T023 [US9] Write `tests/lp/test_analysis.py` for US9 — hour where workers == demand flagged as bottleneck; hour where workers > demand not flagged; bottleneck labelled with clock hour and demand value; empty bottleneck list when all hours have surplus
- [ ] T024 [US9] Implement `identify_bottlenecks()` in `src/lp/analysis.py` — compute active_workers_at_hour for each operating hour from `shift_starts_rounded` and `shift_length`; compare against `demand.demand_curve`; collect hours where active == demand; return `BottleneckResult`
- [ ] T025 [US9] Update `src/lp/__init__.py` — export `identify_bottlenecks`, `BottleneckResult`

**Checkpoint**: Bottleneck hours are correctly identified and labelled — US9 fully functional.

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: `comparison_report()`, full EFHK integration test, and notebook prototype.

- [ ] T028 [P] Write `tests/lp/test_analysis.py` for comparison_report (FR-008) — `arrival_gap_absolute` and `departure_gap_absolute` computed correctly per slot from `DemandResult.arrival_demand_curve` / `departure_demand_curve`; aggregate pct_total formula correct; `total_scheduled/actual_demand[i] == arrival[i] + departure[i]`; all list lengths equal `len(hours)`; faithfully reflects input differences with no smoothing (SC-003)
- [ ] T029 [P] Implement `comparison_report()` in `src/lp/analysis.py` — call `compute_demand(scheduled)` and `compute_demand(actuals=actuals)` separately; read `DemandResult.arrival_demand_curve` and `departure_demand_curve` directly (no recomputation); compute per-slot gaps and aggregate pct_total for each direction; return `ComparisonReport`
- [ ] T030 Update `src/lp/__init__.py` — export `schedule_shifts`, `identify_bottlenecks`, `comparison_report`, `ComparisonReport`, `ShiftConfig`, `ShiftSchedule`, `BottleneckResult`, `DEFAULT_DEPARTURE_STAFFING_STANDARDS`, `DEFAULT_DEPARTURE_WINDOW_SLOTS`, `DEFAULT_ARRIVAL_WINDOW_SLOTS`
- [X] T031 [P] Create `src/utils/efhk_loader.py` — EFHK CSV loader reading `data/finavia_flights_efhk_20260327.csv`; UTC→Helsinki via `ZoneInfo("Europe/Helsinki")`; ICAO → LP category mapping; operating-window pre-filter (drop hours outside 05:00–23:00 Helsinki); aggregate to `list[FlightSlotInput]`; extract `actual_arrival_time`/`actual_departure_time` → `FlightMovementInput` (default-on)
- [ ] T032 [P] Create `notebooks/planning/ramp_resource_lp.ipynb` — validation notebook importing from `src/lp` and `src/utils`; load EFHK data via `load_efhk("data/finavia_flights_efhk_20260327.csv")`; call `compute_demand()` and `schedule_shifts()`; display demand curve, shift schedule, and bottleneck hours (Constitution Principle II)
- [ ] T033 Run full end-to-end integration with `data/finavia_flights_efhk_20260327.csv` (422 flights) — verify demand curve is non-zero across operating hours, schedule_shifts produces feasible headcount, identify_bottlenecks returns results, no ValueError raised after ICAO mapping and window pre-filtering
- [ ] T034 [P] Write performance benchmark in `tests/lp/` — run `compute_demand()` on the full 422-flight EFHK dataset (all 18 slots pre-filtered via `load_efhk`); assert wall-clock time < 30 s (SC-001)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Utils (Phase 1b)**: Depends on Phase 2 (imports `src/lp/types`); can be developed in parallel with Phase 2
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **US1 (Phase 3)**: Depends on Phase 2 — first story, no story dependencies
- **US2 (Phase 4)**: Depends on Phase 3 (extends compute_demand with departure backward window)
- **US3 (Phase 5)**: Depends on Phase 4 (applies delay adjustment to both arrival and departure directions)
- **US4 (Phase 6)**: Depends on Phase 3 (consumes DemandResult from compute_demand; implements schedule_shifts)
- **US5 (Phase 7)**: Depends on Phase 6 (extends ShiftSchedule; verifies headcount invariant)
- **US6 (Phase 8)**: Depends on Phase 3 (adds pool_size post-check to compute_demand)
- **US7 (Phase 9)**: Depends on Phase 4 (both departure and arrival staffing standards must be present)
- **US8 (Phase 10)**: Depends on Phase 4 (actual_movements classification applies to both directions)
- **US9 (Phase 11)**: Depends on Phase 6 (requires ShiftSchedule output from schedule_shifts)
- **Polish (Phase 12)**: Depends on Phases 5, 7, 8, 9, 10, 11 — all stories complete

### User Story Dependencies (summary)

```text
Phase 1 → Phase 2 → US1 (P1) → US2 (P2) → US3 (P3) → US8 (P8)
                             ↘ US2 (P2) → US7 (P7)
                             ↘ US1 (P1) → US4 (P4) → US5 (P5)
                             ↘ US1 (P1) → US4 (P4) → US9 (P9)
                             ↘ US1 (P1) → US6 (P6)
All of the above → Polish (Phase 12)
```

### Within Each User Story

- Tests MUST be written and confirmed failing before implementation
- Implementation tasks within a phase follow: types → compute logic → exports
- Each phase checkpoint validates the story independently before advancing

### Parallel Opportunities (within Phases)

- **Phase 1**: T003 and T004 are parallel (different stub files)
- **Phase 1b**: T035, T036, T037 are parallel (different files)
- **Phase 2**: T005 and T006 are parallel (types.py vs test_types.py)
- **After US1 (Phase 3)**: US4 (Phase 6) and US6 (Phase 8) can both begin immediately (US4 needs only DemandResult; US6 only adds a post-check to compute_demand)
- **After US2 (Phase 4)**: US3 (Phase 5), US7 (Phase 9), and US8 (Phase 10) can all begin in parallel (all require both directions to be present)
- **Phase 12**: T028/T029, T032, T034 can all run in parallel (different files)

---

## Parallel Example: After US2 Complete

Once Phase 4 (US2) is done, these stories can run concurrently:

```text
Developer A: US3 (Phase 5) → US8 (Phase 10)
Developer B: US4 (Phase 6) → US5 (Phase 7) | US9 (Phase 11) [parallel after US4]
Developer C: US6 (Phase 8) → US7 (Phase 9)
```

Merge compute_demand() extensions from US3, US6, US8 carefully — all modify the same function; coordinate branch strategy to avoid conflicts.

---

## Implementation Strategy

### Current Status (as of 2026-05-02)

Completed phases: **1, 1b, 2, 3, 4, 5, 6, 7** (US1 + US2 + US3 + US4 fully done; US6 implementation done, tests partial; US7 tests done; `load_efhk()` extended with `use_actual_times` parameter)

Next up: **US8 (Phase 10)** — on-time classification (T021, T022); **US9 (Phase 11)** — bottleneck analysis (T023-T025)

### Incremental Delivery

1. ✅ Setup + Utils + Foundational → types importable, EFHK loader working
2. ✅ US1 → `compute_demand()` working on scheduled arrivals → MVP
3. ✅ US2 → departure demand → full two-direction demand model
4. → US3 → delay adjustment (both directions) → delay-aware demand
5. → US4 → `schedule_shifts()` working → shift plan produceable
6. → US5 → daily headcount → payroll-ready output
7. → US6 → infeasibility detection tests → safe for production inputs
8. → US7 → configurable standards (implementation done; tests verified)
9. → US8 → on-time classification → actuals-ready
10. → US9 → bottleneck analysis → operational insight
11. → Phase 12 → comparison report + end-to-end integration + notebook

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel within a phase
- `[Story]` label maps every implementation task to a spec user story for traceability
- `compute_demand()` is extended incrementally across US1→US2→US3→US6→US8; test each extension independently before merging
- The ICAO → LP category mapping and operating-window pre-filtering are in `src/utils/efhk_loader.py` (constitution rule 5); the LP module (`src/lp/`) never sees raw ICAO codes
- Operating-window pre-filtering must run before `compute_demand()` — flights before 05:00 or after 22:00 Helsinki time raise `ValueError` if passed to the LP
- T030 consolidates all remaining `__init__.py` exports (schedule_shifts, identify_bottlenecks, comparison_report) — do in one pass after US4/US9/Polish are complete
- Commit after each phase checkpoint
- Run `pytest tests/lp/ tests/utils/` from repo root after every phase
