# Feature Specification: Ramp Resource LP — Ground Handling Worker Scheduling

**Feature Branch**: `001-ramp-resource-lp`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "A two-stage LP that converts a flight schedule and actual arrival data into the minimum number of ground-handling worker shifts needed to cover every operational hour at a Finavia airport. Stage 1 computes per-slot worker demand adjusted for aircraft type and delays; Stage 2 schedules the fewest shift-starts that satisfy that demand across the full operating day"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hourly Demand from Flight Schedule (Priority: P1)

A Resource Planner starts with the day's flight schedule — how many aircraft of each type are expected each hour — and wants to know the minimum number of ground workers required at each hour. Today, the planner defaults to peak-hour staffing all day, which wastes resources during quiet hours. The system computes an accurate per-hour demand curve using the aircraft types present and each type's contractual staffing standard.

**Why this priority**: Without an accurate demand curve, the shift scheduling step (Stage 2) has nothing to optimise against. This is the foundation of the entire solution.

**Independent Test**: Can be validated by manually computing worker totals for a single hour using a known flight schedule and confirming the system matches the manual result.

**Acceptance Scenarios**:

1. **Given** a flight schedule with aircraft counts per hour and staffing standards per aircraft type, **When** the demand calculation runs, **Then** it produces a worker count for every operating hour, with no hour returning a negative or null value.
2. **Given** only wide-body aircraft in a slot, **When** demand is calculated, **Then** the worker count for that slot equals the number of wide-body flights multiplied by the wide-body staffing standard.
3. **Given** the published Sahadevan Table 7 inputs (Dubai 06:00–07:00 schedule), **When** demand runs against scheduled arrivals only, **Then** total demand equals 221 workers.

---

### User Story 2 - Delay-Adjusted Demand (Priority: P2)

A Resource Planner knows that the flight schedule does not always reflect reality — delays shift aircraft into later slots, changing where workers are needed. When delays are expected or confirmed, the planner wants the demand curve to reflect actual rather than scheduled movements, so they do not over-staff the original slot and under-staff the slot where the flight actually lands.

**Why this priority**: The primary quantified business case (22% demand underestimate from schedule-only planning) lives here. Accurate delay adjustment is what separates this system from a simple timetable lookup.

**Independent Test**: Can be validated by marking one aircraft type as delayed and confirming the demand at the original slot drops to 20% of scheduled count, with the remainder credited to the actual arrival slot.

**Acceptance Scenarios**:

1. **Given** an aircraft type is marked as delayed, **When** demand is calculated, **Then** only 20% of that type's scheduled count is attributed to the original slot and 80% is attributed to the actual arrival slot.
2. **Given** an aircraft type is on time, **When** demand is calculated, **Then** its count at the scheduled slot is unchanged.
3. **Given** the Sahadevan Table 7 actual-arrival inputs, **When** demand runs against actual movements, **Then** total demand equals 269 workers — 22% above the schedule-only figure.

---

### User Story 3 - Minimum Shift Schedule (Priority: P3)

A Roster Manager receives the hourly demand curve from Stage 1 and needs to know: how few workers need to be hired to meet that demand across the full operating day? Today, the answer is "staff to peak" — but a worker hired for an 8-hour shift covers multiple hours, so hiring one more person at 06:00 satisfies demand at 06:00 through 13:00. The system finds the fewest shift starts that ensure every hour is covered.

**Why this priority**: This converts the demand signal into a directly actionable, cost-minimised roster. It is the output Finavia Finance and HR care about most.

**Independent Test**: Can be validated by checking that the total worker count is strictly less than peak-hour demand multiplied by total operating hours divided by shift length (the naive baseline), and that every hour's coverage constraint is satisfied.

**Acceptance Scenarios**:

1. **Given** hourly demand values for all operating hours and a configured shift length, **When** the scheduling optimisation runs, **Then** the total workers scheduled is less than the naive peak-staffing total.
2. **Given** a solved schedule, **When** coverage is checked for each hour, **Then** the number of active workers at every hour meets or exceeds the demand for that hour.
3. **Given** the optimisation produces fractional shift counts, **When** values are rounded up to whole workers, **Then** all coverage requirements still hold.

---

### User Story 4 - Accurate Daily Headcount (Priority: P4)

A Roster Manager needs to submit a daily headcount to HR and Finance. The count must reflect distinct individuals — a worker covering an 8-hour shift must appear once, not once per hour. The system must produce a total that is payroll-ready with no deduplication required downstream.

**Why this priority**: Accuracy of the headcount output is a trust and compliance requirement. An inflated or duplicate count would undermine confidence in the system.

**Independent Test**: Can be validated by summing the shift-start counts and confirming the total matches the number of distinct shift assignments in the output roster.

**Acceptance Scenarios**:

1. **Given** a solved shift schedule, **When** the daily total is computed, **Then** it equals the sum of workers starting shifts — with no worker counted more than once regardless of shift length.
2. **Given** a roster passed to a downstream payroll or HR system, **When** records are counted, **Then** no deduplication step is needed to arrive at the correct headcount.

---

### User Story 5 - Capacity Constraint Enforcement (Priority: P5)

An Operations Manager needs assurance that the model never schedules more workers than Finavia actually has in its ground-handling pool. If demand at any hour would exceed the available workforce, the system must surface this clearly rather than silently under-reporting.

**Why this priority**: Scheduling against a workforce that does not exist produces useless output. Infeasibility detection prevents false confidence.

**Independent Test**: Can be validated by setting the workforce pool to zero and confirming the system returns an infeasibility signal rather than a zero-worker schedule.

**Acceptance Scenarios**:

1. **Given** hourly demand that stays within the workforce pool at all hours, **When** Stage 1 runs, **Then** the solution is feasible and all demands are met.
2. **Given** hourly demand that exceeds the workforce pool at one or more hours, **When** Stage 1 runs, **Then** the system reports infeasibility, identifies the exceeding hours, and does not return a silent zero or partial result.

---

### Edge Cases

- What happens when all aircraft types are delayed simultaneously? (All slots shift; original-hour demand drops to 20% across the board.)
- What happens when demand at a slot equals exactly the workforce pool limit R? (Feasible — constraint holds at equality; system proceeds normally.)
- What happens when the operating day is shorter than one shift length? (Coverage constraints reduce in scope; scheduler still minimises shift-starts across the available hours.)
- What happens when two aircraft types with different staffing standards arrive in the same slot? (Demands are summed independently per type before being totalled for the slot.)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute the minimum workers required at each operating hour from the flight schedule and per-aircraft-type staffing standards.
- **FR-002**: System MUST adjust per-slot aircraft counts when a type is delayed, attributing 20% of scheduled count to the original slot and 80% to the actual arrival slot.
- **FR-003**: System MUST accept actual-arrival counts as an alternative to scheduled counts, producing a demand curve that reflects real movements.
- **FR-004**: System MUST enforce a workforce pool ceiling: if demand at any slot would exceed total available workers, the system MUST report infeasibility and identify the affected slots.
- **FR-005**: System MUST produce a shift-start schedule that covers hourly demand using the fewest total workers, given a configurable uniform shift length.
- **FR-006**: System MUST count each worker exactly once in the daily total, regardless of shift length.
- **FR-007**: System MUST accept staffing standards (workers per flight) as a configurable input per aircraft type, with reference defaults derived from Sahadevan Table 7.
- **FR-008**: System MUST produce a comparison output showing scheduled-arrival demand versus actual-arrival demand per aircraft type for the same time slot (Table 7-style report).
- **FR-009**: System MUST expose the bottleneck hours driving total workforce size (the hours whose demand is binding on the final headcount).

### Key Entities

- **Flight Slot**: A one-hour window defined by its position in the operating day; characterised by the count of each aircraft type scheduled and actually arriving within it.
- **Aircraft Type**: A category of aircraft (e.g., narrow-body, wide-body) defined by its staffing standard — the number of workers required per flight of that type.
- **Demand Curve**: The ordered series of minimum worker counts required at each slot across the full operating day; the output of Stage 1 and the input to Stage 2.
- **Worker Shift**: A block of consecutive hours worked by one person, defined by a start hour and a fixed length; the unit of decision in Stage 2.
- **Daily Headcount**: The total number of distinct worker-shifts rostered for the day; the primary output of Stage 2 and the figure submitted to HR and Finance.

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
- Staffing standards per aircraft type (workers per flight) are provided as external inputs from Finavia's ground handling service agreements; the system does not derive them.
- A flight is classified as delayed if its actual arrival deviates beyond ±15 minutes from the scheduled slot; this tolerance is configurable.
- All workers are assumed to have equivalent skills covering all ground-handling tasks; role differentiation (fuelling, baggage, catering) is a planned extension, not in scope here.
- The workforce pool size (R) is a fixed known input for each run; the system does not model hiring or dynamic pool expansion.
- Scheduled and actual arrival counts are provided as inputs; the system does not fetch or predict them.
- Part-time shifts (shift length < L) and multi-role scheduling are out of scope for this version.
