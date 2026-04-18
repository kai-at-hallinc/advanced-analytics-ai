# Feature Specification: Ramp Resource LP — Ground Handling Worker Scheduling

**Feature Branch**: `001-ramp-resource-lp`
**Created**: 2026-04-17
**Updated**: 2026-04-18 (departure demand extension)
**Status**: Draft
**Input**: User description: "A two-stage LP that converts a flight schedule and actual arrival data into the minimum number of ground-handling worker shifts needed to cover every operational hour at a Finavia airport. Stage 1 computes per-slot worker demand adjusted for aircraft type and delays; Stage 2 schedules the fewest shift-starts that satisfy that demand across the full operating day"

## Clarifications

### Session 2026-04-18

- Q: Default staffing standards (workers/flight) for narrow-body, wide-body, cargo? → A: 3 / 5 / 6
- Q: Which Python LP solver library? → A: Google OR-Tools (GLOP solver)
- Q: Input/output interface type? → A: Python module with typed function signatures
- Q: Does one aircraft arrival generate demand across multiple consecutive slots? → A: Yes — demand spans the full arrival window per aircraft type (narrow-body 1 h, wide-body 2 h, cargo 3 h)
- Q: Default operating day start and end hours? → A: 05:00–23:00 (18 hourly slots)
- Q: Python API types for compute_demand() and schedule_shifts() inputs/outputs? → A: dataclasses / TypedDict — typed, zero extra dependencies
- Q: How do FR-002 (delay-flag model) and FR-003 (actual-arrivals mode) combine in compute_demand()? → A: Single function — compute_demand(scheduled, actuals=None, delay_flags=None); actuals used directly when provided, 20/80 heuristic applied when only delay flags given
- Q: Is 'superjumbo' in Key Entities a real supported category or illustrative only? → A: Illustrative only — canonical categories are narrow-body, wide-body, and cargo
- Q: Do departing aircraft contribute to worker demand independently of whether a same-day arrival at HEL exists? → A: Yes — ground time may span hours or days, aircraft may come from maintenance or a prior-day rotation, and hub feeder traffic means arrival handling and departure preparation are unrelated operations; each movement triggers demand independently.
- Q: Does the arrival window cover the full ground cycle including departure preparation, or only the arrival handling portion? → A: Arrival handling only (unloading, cleaning, catering after landing). Departure preparation is a separate backward-looking window ending at the departure slot. Operators should recalibrate arrival window values to reflect arrival handling duration, not full ground time.
- Q: Are departure staffing standards (workers per departing flight) the same as arrival standards, or configurable separately? → A: Default to the same values (narrow-body 3, wide-body 5, cargo 6); configurable independently per run.
- Q: Are departure window durations the same as arrival window durations? → A: Default to the same durations (narrow-body 1 h, wide-body 2 h, cargo 3 h); configurable independently per run.
- Q: How are departure delays modelled? → A: The same 20/80 heuristic as arrivals: 20% of scheduled departure count attributed to the original slot, 80% to the actual departure slot.
- Q: What happens when a departure's backward preparation window extends before the operating day start (e.g., 06:00 departure with a 2-hour window needing demand at 04:00)? → A: Clip silently — the departure window is truncated at operating day start; only slots within the operating day contribute to the demand curve.
- Q: Should FR-008's comparison report be extended to cover departure demand (scheduled vs actual) alongside arrivals, or remain arrival-only? → A: Extend FR-008 — one unified report covering scheduled vs actual demand for both arrivals and departures per aircraft type per slot.
- Q: Do departure counts support the same 3-mode input pattern as arrivals (scheduled-only, delay flags, or actual departure counts)? → A: Yes — same 3-mode pattern: actual departure counts take precedence over the heuristic when provided; delay flags apply the 20/80 heuristic when no actuals are supplied; scheduled counts are used unchanged when neither is provided.
- Q: Should the ±15-minute on-time tolerance window (FR-011) apply to departures as well as arrivals — reclassifying departure demand to the actual departure slot when outside tolerance? → A: Yes — same ±15-minute tolerance applies; departure demand is reclassified to the actual departure slot when the flight departs outside the window.
- Q: SC-003 asserts a ≥15% gap between actual and scheduled demand — is this a meaningful system criterion or an empirical observation from Sahadevan? → A: It is a dataset observation, not a system guarantee. The system does not predict or enforce any gap magnitude; it faithfully reflects whatever difference exists in the input counts. SC-003 should be reframed as a verifiable system property rather than a threshold tied to a specific study.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hourly Demand from Flight Schedule (Priority: P1)

A Resource Planner starts with the day's flight schedule — how many aircraft of each type are expected each hour — and wants to know the minimum number of ground workers required at each hour. If the planner defaults to peak-hour staffing all day he wastes resources during quiet hours. The system computes an accurate per-hour demand curve using the aircraft types present and each type's contractual staffing standard.

**Why this priority**: Without an accurate demand curve, the shift scheduling step (Stage 2) has nothing to optimise against. This is the foundation of the entire solution.

**Independent Test**: Can be validated by manually computing worker totals for a single hour using a known flight schedule and confirming the system matches the manual result.

**Acceptance Scenarios**:

1. **Given** a flight schedule with aircraft counts per hour and staffing standards per aircraft type, **When** the demand calculation runs, **Then** it produces a worker count for every operating hour, with no hour returning a negative or null value.
2. **Given** only wide-body aircraft in a slot, **When** demand is calculated, **Then** the worker count for that slot equals the number of wide-body flights multiplied by the wide-body staffing standard.

---

### User Story 2 - Delay-Adjusted Demand (Priority: P2)

A Resource Planner knows that the flight schedule does not always reflect reality — delays shift aircraft into later slots, changing where workers are needed. When delays are expected or confirmed, the planner wants the demand curve to reflect actual rather than scheduled movements, so they do not over-staff the original slot and under-staff the slot where the flight actually lands.

**Why this priority**: The primary quantified business case (22% demand underestimate from schedule-only planning) lives here. Accurate delay adjustment is what separates this system from a simple timetable lookup.

**Independent Test**: Can be validated by marking one aircraft type as delayed and confirming the demand at the original slot drops to 20% of scheduled count, with the remainder credited to the actual arrival slot.

**Acceptance Scenarios**:

1. **Given** an aircraft type is marked as delayed, **When** demand is calculated, **Then** only 20% of that type's scheduled count is attributed to the original slot and 80% is attributed to the actual arrival slot.
2. **Given** an aircraft type is on time, **When** demand is calculated, **Then** its count at the scheduled slot is unchanged.

---

### User Story 3 - Minimum Shift Schedule (Priority: P3)

A Resource Planner receives the hourly demand curve from Stage 1 and needs to know: how few workers need to be hired to meet that demand across the full operating day? A worker hired for ie. an 8-hour shift covers multiple hours, so hiring one more person at 06:00 satisfies demand at 06:00 through 13:00. The system finds the fewest shift starts that ensure every hour is covered.

**Why this priority**: This converts the demand signal into a directly actionable, cost-minimised roster.

**Independent Test**: Can be validated by checking that the total worker count is strictly less than peak-hour demand multiplied by total operating hours divided by shift length (the naive baseline), and that every hour's coverage constraint is satisfied.

**Acceptance Scenarios**:

1. **Given** hourly demand values for all operating hours and a configured shift length, **When** the scheduling optimisation runs, **Then** the total workers scheduled is less than the naive peak-staffing total.
2. **Given** a solved schedule, **When** coverage is checked for each hour, **Then** the number of active workers at every hour meets or exceeds the demand for that hour.
3. **Given** the optimisation produces fractional shift counts, **When** values are rounded up to whole workers, **Then** all coverage requirements still hold.

---

### User Story 4 - Accurate Daily Headcount (Priority: P4)

A Resource Planner needs to review the headcounts with a Unit Manager. The presented count must reflect distinct individuals — a worker covering an 8-hour shift must appear once, not once per hour. The system must produce a total that is payroll-ready with no deduplication required downstream.

**Why this priority**: Accuracy of the headcount output is a trust and compliance requirement. An inflated or duplicate count would undermine confidence in the system.

**Independent Test**: Can be validated by summing the shift-start counts and confirming the total matches the number of distinct shift assignments in the output roster.

**Acceptance Scenarios**:

1. **Given** a solved shift schedule, **When** the daily total is computed, **Then** it equals the sum of workers starting shifts — with no worker counted more than once regardless of shift length.
2. **Given** a roster passed to a downstream payroll or HR system, **When** records are counted, **Then** no deduplication step is needed to arrive at the correct headcount.

---

### User Story 5 - Capacity Constraint Enforcement (Priority: P5)

An Operations Manager needs assurance that the model never schedules more workers than there actually are in ground-handling pool. If demand at any hour would exceed the available workforce, the system must surface this clearly rather than silently under-reporting.

**Why this priority**: Scheduling against a workforce that does not exist produces useless output. Infeasibility detection prevents false confidence.

**Independent Test**: Can be validated by setting the workforce pool to zero and confirming the system returns an infeasibility signal rather than a zero-worker schedule.

**Acceptance Scenarios**:

1. **Given** hourly demand that stays within the workforce pool at all hours, **When** Stage 1 runs, **Then** the solution is feasible and all demands are met.
2. **Given** hourly demand that exceeds the workforce pool at one or more hours, **When** Stage 1 runs, **Then** the system reports infeasibility, identifies the exceeding hours, and does not return a silent zero or partial result.

---

### User Story 6 - Aircraft-Type Staffing Standards (Priority: P6)

A Resource Planner needs the staffing level per flight to automatically reflect the feasible or contractual standard for each aircraft category — narrow-body flights require fewer workers than wide-body. When no custom standard has been configured for a type, the system must fall back to known category defaults so the planner never needs to look up the number manually or risk using an inconsistent figure.

**Why this priority**: Staffing standards are the multiplier applied to every flight count. An incorrect or missing standard silently distorts every demand figure the system produces. Correct defaults are a prerequisite for trustworthy output.

**Independent Test**: Can be validated by running a single-slot calculation with two aircraft types of different categories and confirming each type contributes the expected worker count independently of the other.

**Acceptance Scenarios**:

1. **Given** a narrow-body flight and a wide-body flight both present in the same hour, **When** demand is calculated, **Then** the narrow-body contributes 3 workers per flight and the wide-body contributes 5 workers per flight, summed independently.
2. **Given** a staffing standard is updated for one aircraft type only, **When** demand is calculated, **Then** only the hours containing that aircraft type change; all other hours remain unchanged.
3. **Given** no custom staffing standard is supplied by the operator, **When** the system initialises, **Then** it defaults to 3 workers per flight for narrow-body types, 5 for wide-body types, and 6 for cargo types.

---

### User Story 7 - On-Time Window Classification (Priority: P7)

A Resource Planner needs flights that miss their scheduled slot by more than the agreed tolerance — whether delayed or arriving early — to have their worker allocation automatically moved to the actual arrival slot. If a flight scheduled at 09:00 lands at 09:25, workers standing at the gate since 09:00 are idle for 25 minutes; if it lands at 08:40, the crew scheduled for 09:00 arrives too late. The system must detect both cases and reallocate demand to the correct slot.

**Why this priority**: Misaligned resource allocation is the core operational problem this system solves. Correct slot reclassification is what translates the flight schedule into a meaningful ground deployment plan.

**Independent Test**: Can be validated by providing one flight inside the tolerance window and one outside, then confirming the inside-window flight's workers stay at the original slot while the outside-window flight's workers move to the actual arrival slot.

**Acceptance Scenarios**:

1. **Given** a flight scheduled at 09:00 that actually arrives at 09:10, and a tolerance window of ±15 minutes, **When** the arrival is classified, **Then** it is treated as on time and resources are allocated at 09:00.
2. **Given** a flight scheduled at 09:00 that actually arrives at 09:25, and a tolerance window of ±15 minutes, **When** the arrival is classified, **Then** it falls outside the window, is reclassified to the 09:00+ slot matching its actual arrival time, and zero resources are allocated at the original 09:00 slot.
3. **Given** the tolerance window is changed from the default 15 minutes to 10 minutes, **When** a flight arrives 12 minutes late, **Then** it is classified as outside the window and reallocated — demonstrating that the threshold is configurable.

---

### User Story 8 - Bottleneck Hour Identification (Priority: P8)

An Unit Manager wants to know which specific hours of the day are forcing the total daily workforce higher. If the 07:00 and 14:00 slots are the binding constraints — meaning no further reduction in total headcount is possible without violating coverage at those hours — the manager can focus schedule negotiations or ramp-up coordination on exactly those hours rather than spreading effort evenly across the day.

**Why this priority**: Without knowing which hours are binding, all cost-reduction efforts are undirected. This output converts the LP solution into a targeted operational insight.

**Independent Test**: Can be validated by artificially reducing demand at a suspected bottleneck hour by one worker and confirming the total daily headcount also drops by one — proving that hour was the binding constraint.

**Acceptance Scenarios**:

1. **Given** a solved shift schedule, **When** bottleneck analysis runs, **Then** it returns a list of hours where demand is exactly met by active workers — with no surplus — identified as bottleneck hours.
2. **Given** an hour where active workers exceed demand by two or more, **When** bottleneck analysis runs, **Then** that hour is not flagged as a bottleneck.
3. **Given** the bottleneck output, **When** it is viewed by an Operations Manager, **Then** each bottleneck hour is labelled with its clock time and the specific demand figure that is binding — no raw model output is exposed.

---

### User Story 9 - Independent Departure Demand (Priority: P9)

A Resource Planner at Helsinki-Vantaa needs the demand curve to reflect departure preparation staffing independently of whether the departing aircraft landed at HEL earlier that day. An aircraft may have arrived the previous day, come from scheduled maintenance, or be repositioned from another stand — in all cases, ground handlers must prepare it for departure and that labour must appear in the demand curve. If the system counts only arrivals, every departure whose associated arrival falls outside the operating day is silently missing, and the schedule produced by Stage 2 will be short-staffed during pre-departure banks.

**Why this priority**: Helsinki-Vantaa is a hub airport with feeder traffic; ground time ranges from under one hour to multiple days. Because flight movements do not follow a fixed cycle, arrival handling demand and departure preparation demand must each be computed from the actual movement slot — not inferred from one another. Failing to do so causes systematic under-staffing at departure-heavy hours regardless of how accurately arrivals are modelled.

**Independent Test**: Can be validated by supplying a schedule containing only departure counts for a single slot (zero arrivals across the entire day) and confirming the system produces a non-zero demand curve at the slots covered by the departure window, equal to departure count multiplied by the departure staffing standard.

**Acceptance Scenarios**:

1. **Given** a schedule containing departures but no arrivals, **When** demand is calculated, **Then** the demand curve is non-zero at the slots covered by the departure window and the system does not treat the day as having zero demand.
2. **Given** a schedule with arrivals at 08:00 and departures at 14:00 for the same aircraft type, **When** demand is calculated, **Then** arrival demand appears at 08:00 (and its arrival window) and departure demand appears ending at 14:00 (its departure window) independently — neither is derived from the other.
3. **Given** a departure staffing standard that differs from the arrival standard for the same aircraft type, **When** demand is calculated, **Then** departures use the departure standard and arrivals use the arrival standard with no cross-contamination.

---

### Edge Cases

- What happens when all aircraft types are delayed simultaneously? (All slots shift; original-hour demand drops to 20% across the board.)
- What happens when demand at a slot equals exactly the workforce pool limit R? (Feasible — constraint holds at equality; system proceeds normally.)
- What happens when the operating day is shorter than one shift length? (Coverage constraints reduce in scope; scheduler still minimises shift-starts across the available hours.)
- What happens when two aircraft types with different staffing standards arrive in the same slot? (Demands are summed independently per type before being totalled for the slot.)
- What happens when an aircraft arrives ahead of its scheduled slot? (Early arrivals require a longer on-stand turnaround than on-time arrivals for most aircraft types — they must not be modelled as reduced demand. Resource occupancy increases, not decreases, and the allocation must be moved to the actual early-arrival slot if it falls outside the tolerance window.)
- What happens when a departing aircraft has no same-day arrival at HEL (multi-day ground time or maintenance routing)? (Departure demand is computed from the departure slot alone using the departure window; no arrival is required to trigger it.)
- What happens when the same slot has both arrivals and departures? (Arrival and departure demands are computed independently using their respective staffing standards and windows, then summed at each affected slot; no netting or double-counting occurs.)
- What happens when all movements in a slot are departures with zero arrivals? (Departure demand is computed normally; the slot is not treated as zero demand.)
- What happens when a departure is delayed? (The 20/80 heuristic applies: 20% of the scheduled departure count stays at the scheduled slot, 80% moves to the actual departure slot — mirroring FR-002 for arrivals.)
- What happens when a departure's preparation window extends before the operating day start? (The window is clipped silently to the operating day start; only slots within the operating day contribute to demand. No error is raised.)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute the minimum workers required at each operating hour from the flight schedule, per-aircraft-type staffing standards, and per-aircraft-type arrival window durations. A single aircraft arrival occupies worker demand across all slots within its arrival window. The arrival window covers arrival handling only; departure preparation demand is computed separately per FR-013.
- **FR-002**: System MUST adjust per-slot aircraft counts when a type is delayed, attributing 20% of scheduled count to the original slot and 80% to the actual arrival slot. This heuristic applies when only delay flags are available (no actual arrival counts).
- **FR-003**: System MUST accept actual-arrival counts as an alternative to the 20/80 delay heuristic; when actuals are provided they are used directly. Both FR-002 and FR-003 are served by a single `compute_demand(scheduled, actuals=None, delay_flags=None)` function: when `actuals` is supplied FR-003 applies; when only `delay_flags` are supplied FR-002 applies; when neither is supplied scheduled counts are used unchanged.
- **FR-004**: System MUST enforce a workforce pool ceiling: if demand at any slot would exceed total available workers, the system MUST report infeasibility and identify the affected slots.
- **FR-005**: System MUST produce a shift-start schedule that covers hourly demand using the fewest total workers, given a configurable uniform shift length.
- **FR-006**: System MUST count each worker exactly once in the daily total, regardless of shift length.
- **FR-007**: System MUST accept staffing standards (workers per flight) as a configurable input per aircraft type. Default values when no custom standard is provided: narrow-body 3 workers/flight, wide-body 5 workers/flight, cargo 6 workers/flight.
- **FR-008**: System MUST produce a comparison output showing scheduled versus actual demand per aircraft type and per movement direction (arrival and departure) for the same time slot. The report must present arrival and departure gaps separately so the two can be analysed independently (Table 7-style report).
- **FR-009**: System MUST expose the bottleneck hours driving total workforce size, labelled by clock time and showing the demand figure that is binding.
- **FR-010**: System MUST treat early-arriving aircraft as generating equal or greater resource demand per flight compared to on-time arrivals. An early arrival must not reduce the resource allocation for that arrival slot.
- **FR-011**: System MUST classify each arrival and each departure as on-time or off-schedule based on a configurable tolerance window (default ±15 minutes). When an arrival falls outside the window, resources are allocated to the slot matching the actual arrival time. When a departure falls outside the window, the departure demand window is anchored to the actual departure slot. The same tolerance threshold applies to both directions; it is configurable per run and shared.
- **FR-012**: System MUST accept per-slot departure counts as a separate input per aircraft type alongside arrival counts. A slot may contain arrivals only, departures only, or both; absence of departure counts for a slot defaults to zero for all types.
- **FR-013**: System MUST compute departure demand at each operating hour using the departure staffing standard and departure window per aircraft type, and sum it with arrival demand at each slot. A departure at slot j contributes workers at each of the W_dep consecutive slots ending at and including j (backward-looking departure window). Departure demand and arrival demand are computed independently and neither is derived from the other.
- **FR-014**: System MUST accept departure staffing standards as a configurable input per aircraft type, independent of arrival staffing standards. Default values when not specified: narrow-body 3 workers per departure, wide-body 5 workers per departure, cargo 6 workers per departure.
- **FR-015**: System MUST accept actual departure counts as an alternative to the 20/80 delay heuristic for departures; when actual departure counts are provided they are used directly. Precedence follows the same logic as FR-003 for arrivals: actual departure counts override departure delay flags; departure delay flags apply the 20/80 heuristic when no actuals are supplied; scheduled departure counts are used unchanged when neither actuals nor delay flags are provided.

### Key Entities

- **Flight Slot**: A one-hour window defined by its position in the operating day (default range: 05:00–23:00); characterised by the count of each aircraft type arriving within it and the count of each aircraft type departing from it. Total slot demand is the sum of contributions from arrivals whose arrival window covers this slot and from departures whose departure window covers this slot — each computed independently.
- **Aircraft Type**: A category of aircraft — one of narrow-body, wide-body, or cargo — defined by its staffing standard (the number of workers required per flight of that type), its arrival window duration, and its departure window duration.
- **Demand Curve**: The ordered series of minimum worker counts required at each slot across the full operating day; the output of Stage 1 and the input to Stage 2.
- **Worker Shift**: A block of consecutive hours worked by one person, defined by a start hour and a fixed length; the unit of decision in Stage 2.
- **Daily Headcount**: The total number of distinct worker-shifts rostered for the day; the primary output of Stage 2 and the figure submitted to HR and Finance.
- **Bottleneck Hour**: An operating hour where the number of workers on duty exactly matches demand, leaving no surplus — the binding constraint on the total daily headcount.
- **Departure Window**: The number of consecutive slots for which a departing aircraft occupies worker demand, counting backwards from and including the departure slot (pre-departure preparation). Default durations match arrival window values per aircraft type (narrow-body 1 h, wide-body 2 h, cargo 3 h) and are configurable per run independently of arrival window values.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can produce a full-day demand curve from any valid flight schedule in under 30 seconds without manual calculation.
- **SC-002**: The total workers scheduled by Stage 2 is strictly less than the naive peak-staffing total (peak demand × operating hours ÷ shift length) for any realistic input schedule.
- **SC-003**: When scheduled and actual movement counts differ, the demand curves produced from each input set differ in direct proportion to those count differences — no smoothing, rounding, or approximation is applied. The comparison report (FR-008) faithfully reflects the per-slot gap for both arrivals and departures; the magnitude of the gap depends entirely on the input data and is not asserted by the system.
- **SC-004**: The daily headcount output requires no deduplication before submission to HR or payroll — the number reported equals the number of distinct shift assignments.
- **SC-005**: When demand exceeds the workforce pool at any hour, the system surfaces the infeasibility within the same run, identifying the specific hours at fault.
- **SC-006**: The shift-start schedule produced by Stage 2 satisfies all hourly coverage requirements after rounding fractional values up to whole workers.

---

## Assumptions

- Shift length is uniform for all workers within a single run; the default is 8 hours, configurable per run.
- Staffing standards per aircraft type (workers per flight) are provided as external inputs from ground handling service agreements or GOM; the system does not derive them. The staffing standard for each aircraft type is treated as a fixed parameter, not something the optimiser controls. If contracts allow a range of flexibility between a regulatory floor and a full-service ceiling, converting the standard to a bounded range is a planned extension.
- The on-time tolerance window is configurable; the default is ±15 minutes from the scheduled slot. Flights deviating beyond this window in either direction — whether arriving late or early — are reclassified to the actual arrival slot for resource allocation purposes.
- The arrival window per aircraft category covers arrival handling only (unloading, cleaning, catering from landing until the stand is cleared) — it does not cover departure preparation. The arrival window duration is treated as a fixed input per aircraft category; its value is determined by the aircraft type, not computed by the model. Because departure demand is now modelled separately, operators should recalibrate arrival window values to reflect arrival handling duration rather than full ground time.
- All workers are assumed to have equivalent skills covering all ground-handling tasks; role differentiation (ramp loading, truck, baggage, etc) is a planned extension, not in scope here.
- The workforce pool size is a fixed known input for each run; the system does not model hiring or dynamic pool expansion.
- Scheduled and actual arrival counts are provided as inputs; the system does not fetch or predict them. Predicting actual arrival times is a separate forecasting task outside this scope.
- The following are explicitly out of scope for this version: stand and gate allocation optimisation; real-time rescheduling; predicting actual flight arrival times; linking specific arriving and departing aircraft as turnaround pairs; multi-day ground time modelling.
- The following are planned extensions to be addressed in later phases: (1) multiple worker roles per aircraft turn with role-specific staffing standards; (2) morning and evening joint shift scheduling with configurable boundary hours; (3) rolling 7-day horizon with daily forecast refresh; (4) part-time workers with half-length shifts; (5) variable staffing standard per aircraft type within a contractual min/max range; (6) probabilistic arrival window derived from ground handling task networks using Monte Carlo simulation; (7) linking specific arrival and departure movements as turnaround pairs; (8) multi-day ground time modelling.
- The default operating day runs from 05:00 to 23:00, producing 18 hourly decision-variable slots. Both stages use this window; the boundary is configurable per run.
- The system is delivered as a Python module exposing typed function signatures (e.g., `compute_demand(...)` and `schedule_shifts(...)`). It may be called from scripts, notebooks, or future API layers without coupling to any delivery format.
- The LP implementation uses Google OR-Tools (GLOP linear solver). Integer rounding of fractional shift counts uses ceiling arithmetic applied post-solve, not a MIP branch-and-bound step.
- Public API inputs and outputs use Python dataclasses (or TypedDict where a mutable mapping is more natural). No external serialisation library is required. All public types carry full type hints.
- Arrival window defaults per aircraft category: narrow-body 1 hour, wide-body 2 hours, cargo 3 hours. These values are configurable per run and cover arrival handling only. A flight arriving outside the tolerance window occupies demand starting from its actual arrival slot for the full arrival window duration of its category.
- The departure window per aircraft category covers departure preparation only (fuelling, boarding prep, final checks before pushback). Default durations match arrival window values (narrow-body 1 hour, wide-body 2 hours, cargo 3 hours); configurable independently per run. When a departure's preparation window extends before the operating day start, the window is clipped silently to the day start boundary; no error is raised and no demand is attributed to pre-day slots.
- Departure staffing standards default to the same values as arrival staffing standards (narrow-body 3, wide-body 5, cargo 6) and are configurable independently per run.
- Scheduled and actual departure counts are provided as separate inputs alongside arrival counts; the system does not infer one from the other or derive departure counts from arrival data.
- For turnaround flights appearing in both arrival and departure counts, the system computes and sums both demand contributions independently. Linking a specific arriving and departing aircraft as a pair is not modelled in this version.
