# Feature Specification: Ramp Resource LP — Ground Handling Worker Scheduling

**Feature Branch**: `001-ramp-resource-lp`
**Created**: 2026-04-17
**Updated**: 2026-04-18
**Status**: Draft
**Input**: User description: "A two-stage LP that converts a flight schedule and actual arrival data into the minimum number of ground-handling worker shifts needed to cover every operational hour at a Finavia airport. Stage 1 computes per-slot worker demand adjusted for aircraft type and delays; Stage 2 schedules the fewest shift-starts that satisfy that demand across the full operating day"

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

1. **Given** a narrow-body flight and a wide-body flight both present in the same hour, **When** demand is calculated, **Then** the narrow-body contributes {to-be-set} workers per flight and the wide-body contributes {to-be-set} workers per flight, summed independently.
2. **Given** a staffing standard is updated for one aircraft type only, **When** demand is calculated, **Then** only the hours containing that aircraft type change; all other hours remain unchanged.
3. **Given** no custom staffing standard is supplied by the operator, **When** the system initialises, **Then** it defaults to {to-be-set} workers per flight for narrow-body types, {to-be-set} for wide-body types, and {to-be-set} for cargo types.

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

### Edge Cases

- What happens when all aircraft types are delayed simultaneously? (All slots shift; original-hour demand drops to 20% across the board.)
- What happens when demand at a slot equals exactly the workforce pool limit R? (Feasible — constraint holds at equality; system proceeds normally.)
- What happens when the operating day is shorter than one shift length? (Coverage constraints reduce in scope; scheduler still minimises shift-starts across the available hours.)
- What happens when two aircraft types with different staffing standards arrive in the same slot? (Demands are summed independently per type before being totalled for the slot.)
- What happens when an aircraft arrives ahead of its scheduled slot? (Early arrivals require a longer on-stand turnaround than on-time arrivals for most aircraft types — they must not be modelled as reduced demand. Resource occupancy increases, not decreases, and the allocation must be moved to the actual early-arrival slot if it falls outside the tolerance window.)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute the minimum workers required at each operating hour from the flight schedule and per-aircraft-type staffing standards.
- **FR-002**: System MUST adjust per-slot aircraft counts when a type is delayed, attributing 20% of scheduled count to the original slot and 80% to the actual arrival slot.
- **FR-003**: System MUST accept actual-arrival counts as an alternative to scheduled counts, producing a demand curve that reflects real movements.
- **FR-004**: System MUST enforce a workforce pool ceiling: if demand at any slot would exceed total available workers, the system MUST report infeasibility and identify the affected slots.
- **FR-005**: System MUST produce a shift-start schedule that covers hourly demand using the fewest total workers, given a configurable uniform shift length.
- **FR-006**: System MUST count each worker exactly once in the daily total, regardless of shift length.
- **FR-007**: System MUST accept staffing standards (workers per flight) as a configurable input per aircraft type. These defaults apply when no custom value is provided.
- **FR-008**: System MUST produce a comparison output showing scheduled-arrival demand versus actual-arrival demand per aircraft type for the same time slot (Table 7-style report).
- **FR-009**: System MUST expose the bottleneck hours driving total workforce size, labelled by clock time and showing the demand figure that is binding.
- **FR-010**: System MUST treat early-arriving aircraft as generating equal or greater resource demand per flight compared to on-time arrivals. An early arrival must not reduce the resource allocation for that arrival slot.
- **FR-011**: System MUST classify each flight as on-time, delayed, or early based on a configurable tolerance window (default ±15 minutes) and allocate resources to the slot matching the actual arrival time when the flight falls outside that window.

### Key Entities

- **Flight Slot**: A one-hour window defined by its position in the operating day; characterised by the count of each aircraft type scheduled and actually arriving within it.
- **Aircraft Type**: A category of aircraft (e.g., narrow-body, wide-body, superjumbo) defined by its staffing standard — the number of workers required per flight of that type.
- **Demand Curve**: The ordered series of minimum worker counts required at each slot across the full operating day; the output of Stage 1 and the input to Stage 2.
- **Worker Shift**: A block of consecutive hours worked by one person, defined by a start hour and a fixed length; the unit of decision in Stage 2.
- **Daily Headcount**: The total number of distinct worker-shifts rostered for the day; the primary output of Stage 2 and the figure submitted to HR and Finance.
- **Bottleneck Hour**: An operating hour where the number of workers on duty exactly matches demand, leaving no surplus — the binding constraint on the total daily headcount.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A planner can produce a full-day demand curve from any valid flight schedule in under 30 seconds without manual calculation.
- **SC-002**: The total workers scheduled by Stage 2 is strictly less than the naive peak-staffing total (peak demand × operating hours ÷ shift length) for any realistic input schedule.
- **SC-003**: Running Stage 1 on actual-arrival data produces a demand figure at least 15% higher than the scheduled-only figure on the same day's movements, consistent with the ~22% gap documented in the reference case.
- **SC-004**: The daily headcount output requires no deduplication before submission to HR or payroll — the number reported equals the number of distinct shift assignments.
- **SC-005**: When demand exceeds the workforce pool at any hour, the system surfaces the infeasibility within the same run, identifying the specific hours at fault.
- **SC-006**: The shift-start schedule produced by Stage 2 satisfies all hourly coverage requirements after rounding fractional values up to whole workers.

---

## Assumptions

- Shift length is uniform for all workers within a single run; the default is 8 hours, configurable per run.
- Staffing standards per aircraft type (workers per flight) are provided as external inputs from ground handling service agreements or GOM; the system does not derive them. The staffing standard for each aircraft type is treated as a fixed parameter, not something the optimiser controls. If contracts allow a range of flexibility between a regulatory floor and a full-service ceiling, converting the standard to a bounded range is a planned extension.
- The on-time tolerance window is configurable; the default is ±15 minutes from the scheduled slot. Flights deviating beyond this window in either direction — whether arriving late or early — are reclassified to the actual arrival slot for resource allocation purposes.
- The turnaround window (how many consecutive slots a flight occupies at stand) is treated as a fixed input per aircraft category; its value is determined by the aircraft type, not computed by the model. Probabilistic turnaround modelling from ground handling task networks is a planned future phase.
- All workers are assumed to have equivalent skills covering all ground-handling tasks; role differentiation (ramp loading, truck, baggage, etc) is a planned extension, not in scope here.
- The workforce pool size is a fixed known input for each run; the system does not model hiring or dynamic pool expansion.
- Scheduled and actual arrival counts are provided as inputs; the system does not fetch or predict them. Predicting actual arrival times is a separate forecasting task outside this scope.
- The following are explicitly out of scope for this version: stand and gate allocation optimisation; real-time rescheduling; predicting actual flight arrival times.
- The following are planned extensions to be addressed in later phases: (1) multiple worker roles per aircraft turn with role-specific staffing standards; (2) morning and evening joint shift scheduling with configurable boundary hours; (3) rolling 7-day horizon with daily forecast refresh; (4) part-time workers with half-length shifts; (5) variable staffing standard per aircraft type within a contractual min/max range; (6) probabilistic turnaround window derived from ground handling task networks using Monte Carlo simulation.
