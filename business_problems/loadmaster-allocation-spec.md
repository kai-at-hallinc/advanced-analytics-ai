# Feature Specification: Loadmaster Allocation Scheduler

**Feature Branch**: `001-loadmaster-allocation`
**Created**: 2026-04-26
**Status**: Draft
**Input**: Ground handling operation — optimal allocation of a fixed pool of loadmasters to arriving and departing flight events within a fixed shift block, with minimal total delay.

---

## Problem Classification *(AIMA framework)*

This problem is formally classified as a **real-world search problem** (Norvig & Russell, Ch. 3.2) with characteristics of both a **shortest-path problem** and a **Constraint Satisfaction Problem (CSP)** (Ch. 6).

- The state space is a **time-ordered directed acyclic graph (DAG)** — flight events are vertices ordered by scheduled time; edges represent feasible sequential assignments a single loadmaster can perform.
- Because delay is permitted (no hard infeasibility for any K ≥ 1), the problem is **always solvable**. Quality is entirely determined by **path cost** (total accumulated delay in minutes).
- The output is an **assignment schedule** — a mapping of loadmasters to flight events — not a routing or classification.

---

## Problem Structure — AIMA Five Components

This section is the authoritative specification of the problem. All functional requirements below are derived from it.

### 1. State

A state `S` is a snapshot of the assignment process at a point in time:

```
S = {
  assignment   : FlightEvent → Loadmaster | UNASSIGNED,
  availability : Loadmaster  → FREE | BUSY_until(T),
  current_time : T,
  delay_accrued: FlightEvent → minutes
}
```

**What is included:** assignment map, loadmaster availability, current time position, accumulated delay per flight event.

**What is excluded (abstracted away):** aircraft type, cargo content, gate number, loadmaster identity beyond availability — any detail that does not affect the allocation decision.

**Key derived attribute — `duty_starttime(f)`:**

```
duty_starttime(f) =
  arrival_time(f)                      if f is ARRIVAL
  departure_time(f) − duty_duration    if f is DEPARTURE
```

For arrivals, the loadmaster is needed when the aircraft arrives. For departures, the loadmaster must be present *before* pushback — exactly `duty_duration` minutes ahead of the scheduled departure time. This is the operationally correct anchor for all scheduling and delay calculations.

### 2. Initial State

```
S₀ = {
  assignment   : all flight events → UNASSIGNED,
  availability : all K loadmasters → FREE,
  current_time : T_shift_start,
  delay_accrued: all flight events → 0
}
```

All flight events in the shift block are unassigned. All K loadmasters are free at shift start. Zero delay has accrued.

### 3. Actions

Two action types are defined. Both have explicit preconditions.

**ASSIGN(loadmaster_k, flight_f)**
- Preconditions: flight_f is UNASSIGNED; loadmaster_k is FREE
- Effect: flight_f assigned to loadmaster_k; loadmaster_k becomes BUSY_until(duty_starttime(f) + duty_duration); delay_accrued[f] = max(0, current_time − duty_starttime(f))

**RELEASE(loadmaster_k, flight_f)**
- Preconditions: loadmaster_k is assigned to flight_f; current_time ≥ duty_starttime(f) + duty_duration
- Effect: loadmaster_k becomes FREE; available for next ASSIGN action

### 4. Transition Model

```
RESULT(S, ASSIGN(k, f)):
  assignment[f]    ← k
  availability[k]  ← BUSY_until(duty_starttime(f) + duty_duration)
  delay_accrued[f] ← max(0, current_time − duty_starttime(f))

RESULT(S, RELEASE(k, f)):
  availability[k]  ← FREE
```

The transition model is **deterministic** — scheduled times are known in advance within the shift block.

### 5. Goal Test

```
GOAL-TEST(S) = TRUE iff:
  ∀ flight event f in shift block: assignment[f] ≠ UNASSIGNED
```

Every flight event in the shift block must be served. Because delay is permitted, this is always reachable for any K ≥ 1. The goal test determines *when* the search terminates; path cost determines *which* solution is preferred.

### 6. Path Cost

```
PATH-COST = Σ max(0, assignment_time(f) − duty_starttime(f))  for all f
```

The step cost of ASSIGN(k, f) is the number of minutes by which the assignment is late relative to `duty_starttime(f)`. For arrivals this is lateness relative to arrival time; for departures this is lateness relative to `departure_time − duty_duration`. Zero-delay assignments contribute zero cost. This is an **additive path cost**, making the problem tractable for optimal search algorithms (A*, uniform-cost search).

### Key Parameters (Problem Inputs)

| Parameter | Type | Description |
|---|---|---|
| K | Integer (given, fixed) | Total loadmaster pool size for the shift |
| duty_duration | Minutes (fixed, all events) | How long a loadmaster is occupied per flight event |
| arrival_time(f) | Time (given, arrivals only) | Scheduled arrival time — equals duty_starttime for arrivals |
| departure_time(f) | Time (given, departures only) | Scheduled departure time — duty_starttime = departure_time − duty_duration |
| duty_starttime(f) | Time (derived) | When loadmaster must be present: arrival_time for ARR; departure_time − duty_duration for DEP |
| T_shift | Interval [T_start, T_end] | The shift block boundary |

### Hard Constraint (Mutual Exclusion)

```
∀ loadmaster k, at any time T:
  a loadmaster may be assigned to at most one flight event simultaneously
```

This constraint is physical and inviolable. It is the reason K must be at least equal to the maximum number of simultaneously active duties to achieve zero delay. Below that threshold, the system produces valid schedules with non-zero cost.

### Feasibility Note

The lower bound `K ≥ max simultaneous flights at any T` is **not a feasibility requirement** — it is the condition for a zero-delay optimal solution. For K below this threshold, the system remains fully solvable; flight events queue for the next available loadmaster and accrue delay cost. The path cost function absorbs all quality differentiation.

---

## Problem Structure — DAG Visualisation

The problem state space is a **time-ordered DAG** where:

- **Vertices** = flight events (arrivals and departures), positioned left-to-right by scheduled time, plus a START node and GOAL node
- **Directed edges** = feasible sequential assignments (one loadmaster can serve source before target)
- **Edge weight** = delay cost in minutes (0 if loadmaster finishes before next flight is needed; positive otherwise)
- **Conflict markers** (no edge) = flight pairs whose duty windows overlap — no single loadmaster can serve both

```
Toy example: 2 loadmasters (LM-A, LM-B), 4 events, duty = 30 min

  ARR-1: arrives T=10  → duty_starttime = T=10,  duty window T=10–40
  ARR-2: arrives T=20  → duty_starttime = T=20,  duty window T=20–50
  DEP-3: departs T=70  → duty_starttime = T=40,  duty window T=40–70
  DEP-4: departs T=85  → duty_starttime = T=55,  duty window T=55–85

Timeline (duty_starttime): T=0──────T=10──────T=20──────────T=40──────T=55──

                    [ARR-1]              [DEP-3]
                    dst=T=10             dst=T=40
                    duty→T=40            duty→T=70
                         \             / \
                          cost=0  cost=0   cost=0
                           \       /         \
                    [ARR-2]  \   /          [DEP-4]
                    dst=T=20  X             dst=T=55
                    duty→T=50  \            duty→T=85
                                cost=0 ────/

  START ──→ ARR-1 ──(cost=0)──→ DEP-3 ──→ GOAL
        \         \──(cost=0)──→ DEP-4 ──→ GOAL
         \                     /
          \──→ ARR-2 ─(cost=0)─/

  dst = duty_starttime

  Conflicts (no edge, same LM cannot serve both):
    ARR-1 ↔ ARR-2  (duty windows overlap T=20–40)
    DEP-3 ↔ DEP-4  (duty windows overlap T=55–70)

  Optimal paths: LM-A → ARR-1 → DEP-3   (cost=0)
                 LM-B → ARR-2 → DEP-4   (cost=0)
  Total path cost = 0 (zero delay schedule)

  If K=1: LM-A → ARR-1 → DEP-3 (cost=0), ARR-2 waits until T=40 (cost=20), DEP-4 follows.
  Total path cost = 20 min delay.
```

The DAG structure means:
1. No cycles are possible (time only moves forward)
2. Shortest-path algorithms (Dijkstra, A*) apply directly
3. The branching factor is at most K per assignment decision
4. The search depth equals the number of flight events N

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Dispatcher generates shift schedule (Priority: P1)

A ground handling dispatcher opens the scheduler for an upcoming shift. They provide the shift time block, the number of available loadmasters, and the list of flight events (arrivals and departures with scheduled times). The system computes and presents an optimal assignment schedule for human review before the shift begins.

**Why this priority**: This is the core value delivery. Without it nothing else matters. It directly replaces manual scheduling, which is error-prone and time-consuming.

**Independent test**: Can be fully tested by providing a known flight list and K loadmasters, running the scheduler, and verifying that every flight has an assignment and total delay equals the minimum achievable for that K.

**Acceptance scenarios**:

1. **Given** a shift block with N flight events and K loadmasters where K ≥ peak simultaneous demand, **When** the dispatcher requests a schedule, **Then** the system produces a schedule where every flight is assigned and total delay = 0 minutes.

2. **Given** a shift block where K < peak simultaneous demand, **When** the dispatcher requests a schedule, **Then** the system produces a schedule where every flight is assigned and total delay is the minimum achievable (no alternative assignment sequence produces lower delay).

3. **Given** a valid schedule has been computed, **When** the dispatcher reviews it, **Then** each assignment shows: flight identifier, type (arrival/departure), scheduled time, assigned loadmaster, and delay (0 or positive minutes).

---

### User Story 2 — Dispatcher identifies understaffing before shift (Priority: P2)

Before committing to a shift plan, the dispatcher wants to know whether the given number of loadmasters K is sufficient for zero delay, and if not, by how many minutes total delay will occur. This allows staffing decisions to be made proactively.

**Why this priority**: High operational value — prevents delays rather than just minimising them. Requires P1 to be complete first.

**Independent test**: Can be tested by running the scheduler with K deliberately set below peak demand and verifying that the reported minimum delay matches hand-calculated expectation from the flight schedule.

**Acceptance scenarios**:

1. **Given** a shift with K below peak simultaneous demand, **When** the schedule is generated, **Then** the system reports the total minimum delay in minutes and identifies which specific flight events are delayed and by how much.

2. **Given** a shift with K exactly equal to peak demand, **When** the schedule is generated, **Then** the system confirms zero total delay is achievable and the output schedule has zero delay on all events.

---

### User Story 3 — Dispatcher approves or rejects the proposed schedule (Priority: P3)

After the system presents a schedule, the dispatcher can approve it for execution or reject it and request a re-run (e.g. after changing K or adjusting shift boundaries).

**Why this priority**: Required for the human-in-the-loop output model. Depends on P1.

**Independent test**: Can be tested by presenting a schedule and confirming the approval action is recorded and the rejection action triggers re-computation with updated parameters.

**Acceptance scenarios**:

1. **Given** a schedule has been presented, **When** the dispatcher approves it, **Then** the schedule is marked as confirmed and locked for execution reference.

2. **Given** a schedule has been presented, **When** the dispatcher rejects it and changes K, **Then** the system re-runs the allocation algorithm with the new K and presents a fresh schedule.

---

### Edge Cases

- What happens when two flight events have exactly the same scheduled time? Both require a loadmaster simultaneously — this must be reflected correctly in the conflict graph (no single loadmaster can serve both; K must be ≥ 2 for zero delay on that pair).
- What happens when K = 0? The system must reject this as an invalid input — the problem has no solution.
- What happens when the shift block contains zero flight events? The system should return an empty schedule with zero delay immediately without running the search.
- What happens when a flight's duty window extends beyond the shift block end time? The assignment is still valid — the loadmaster's duty completion time may exceed the shift boundary, but the flight must still be served.
- What happens when duty_duration is longer than the gap between any two consecutive flights for a single loadmaster? The system must assign those flights to different loadmasters and correctly reflect the cost when no loadmaster is available.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept as input: shift start time, shift end time, K (number of loadmasters), duty duration (minutes, fixed for all events), and a list of flight events each with: identifier, type (arrival or departure), and scheduled time (arrival time for arrivals; departure time for departures). The system derives duty_starttime internally.
- **FR-002**: System MUST produce a schedule that assigns exactly one loadmaster to every flight event in the shift block.
- **FR-003**: System MUST ensure no single loadmaster is assigned to two flight events whose duty windows overlap (mutual exclusion constraint).
- **FR-004**: System MUST minimise total delay — defined as the sum of max(0, assignment_time(f) − duty_starttime(f)) across all flight events.
- **FR-005**: System MUST produce a schedule that is optimal — no alternative valid assignment has lower total delay for the given K.
- **FR-006**: System MUST report per-flight delay (0 or positive minutes) and total delay for the produced schedule.
- **FR-007**: System MUST present the schedule for human dispatcher approval before the schedule is treated as confirmed.
- **FR-008**: System MUST support re-computation when the dispatcher rejects a schedule and changes input parameters.
- **FR-009**: System MUST validate inputs and reject: K = 0, empty flight list, shift end time ≤ shift start time, negative duty duration.
- **FR-010**: System MUST represent the problem internally as a time-ordered DAG where flight events are vertices ordered by scheduled time and edges represent feasible same-loadmaster sequential assignments weighted by delay cost.
- **FR-011**: System MUST use a search algorithm that guarantees optimality — either exact shortest-path (Dijkstra / uniform-cost search) or heuristic search with an admissible heuristic (A*). Greedy or random assignment is not acceptable.

### Key Entities

- **FlightEvent**: Represents a single loadmaster duty requirement. Attributes: identifier, type (ARRIVAL | DEPARTURE), arrival_time (arrivals only), departure_time (departures only), duty_starttime (derived: arrival_time for ARR; departure_time − duty_duration for DEP), duty_end_time (= duty_starttime + duty_duration). Treated independently — the same physical aircraft generates two separate flight events (one arrival, one departure).
- **Loadmaster**: A resource unit. Attributes: identifier, availability_status (FREE | BUSY_until_T). Loadmasters are treated as interchangeable (no skills differentiation in v1).
- **Assignment**: A resolved pairing of one loadmaster to one flight event. Attributes: loadmaster_id, flight_event_id, assignment_time, delay_minutes.
- **Schedule**: The complete output for a shift. Attributes: shift_block, K, duty_duration, list of assignments, total_delay_minutes, status (DRAFT | APPROVED).
- **ShiftBlock**: The planning window. Attributes: start_time, end_time.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any valid input where K ≥ peak simultaneous demand, the system produces a schedule with total delay = 0 minutes.
- **SC-002**: For any valid input where K < peak simultaneous demand, the system produces a schedule whose total delay equals the theoretical minimum (verifiable by exhaustive enumeration on small instances).
- **SC-003**: The system produces a complete schedule (all flights assigned) for a shift block containing up to 50 flight events within 10 seconds of computation time.
- **SC-004**: Every produced schedule satisfies the mutual exclusion constraint — no loadmaster is assigned to two overlapping duties (verifiable by automated post-hoc constraint check).
- **SC-005**: A dispatcher can provide inputs, receive a schedule, and approve or reject it in under 3 minutes of total interaction time.
- **SC-006**: The system correctly identifies and reports which flight events are delayed and by how many minutes in 100% of test cases.

---

## Assumptions

- Loadmasters are interchangeable — they have equal capability and no role differentiation applies in v1. If skills or certifications differentiate loadmasters in future, this is a v2 concern.
- Duty duration is fixed and identical for all flight events (both arrivals and departures, all aircraft types). Variable duty duration is out of scope for v1.
- Scheduled flight times are known in advance and fixed for the duration of the shift block. Real-time flight updates (early arrivals, diversions) are out of scope for v1.
- The shift block boundary is fixed at input time. Rolling windows and continuous re-planning are out of scope for v1.
- A loadmaster becomes available immediately upon duty completion — there is no transit time between aircraft or rest requirement modelled between consecutive duties in v1.
- The dispatcher is the sole approver. No multi-party approval workflow is required.
- Flight events are treated as independent scheduling units. Turnaround coupling (the physical aircraft that arrives on ARR-1 departs on DEP-X) is not a constraint in this model — loadmaster assignments for the arrival and departure of the same aircraft are independent.
- The system is a scheduling decision support tool. It does not communicate assignments to loadmasters directly — that operational handoff is out of scope.
