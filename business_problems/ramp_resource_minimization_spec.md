# Spec: Aviation Ground Handling Worker Scheduling (LP)

## Metadata

| Field | Value |
|-------|-------|
| Status | `draft` |
| Owner | hallinc |
| Phase | 1 of 2 |
| Solver target | Python / ORTools |
| Primary reference | Sahadevan et al. 2023 |
| Supporting reference | LP_operations_research.pdf §3.5, §3.12 |
| Roadmap reference | Sheibani 2018 (Phase 2 — turnaround window) |

---

## 1. Problem

Ground handling at Finavia airports requires workers to be present for every arriving and departing flight. Demand fluctuates by hour. The current approach staffs to peak demand, which wastes resources during low-traffic hours.

**We need an LP model that:**
- Computes the minimum worker headcount required each hour given the actual flight schedule and delay status
- Schedules the minimum number of worker shifts to meet that hourly demand
- Produces a roster with no duplicate shift assignments

---

## 2. User Stories

### Roles

| Role | Description |
|------|-------------|
| **Resource Planner** | Plans daily ground handling staffing levels based on the flight schedule |
| **Roster Manager** | Assigns individual workers to shifts and produces the daily duty roster |
| **Operations Manager** | Oversees airport ground operations; accountable for cost and service levels |
| **Ground Handler** | Worker assigned to aircraft turnaround tasks; receives a shift assignment |

---

### US-01 — Hourly Demand from Flight Schedule

> **As a** Resource Planner,
> **I want** the system to compute the minimum workers required at each hour of the day from the flight schedule and aircraft types,
> **so that** I have an accurate hourly demand curve to plan against instead of guessing or defaulting to peak staffing all day.

**Scenario 1: Standard scheduled day**
```gherkin
Given a flight schedule with s_ij counts per aircraft type per slot
And resource requirements c_i defined for each aircraft type
And no delays (d_i = 0 for all types)
When the Stage 1 LP runs
Then r_j is computed for every slot j
And r_j equals the sum of z_ij · c_i · x_ij across all aircraft types at that slot
And no slot returns a negative or null value
```

**Scenario 2: Sahadevan Table 7 validation**
```gherkin
Given the exact s_ij and c_i values from Sahadevan Table 7
And no delays
When the Stage 1 LP runs for slot 06:00–07:00
Then r_j equals 221
```

**Maps to:** Stage 1, Constraints 5 and 7, Section 5.1

---

### US-02 — Delay-Adjusted Demand

> **As a** Resource Planner,
> **I want** the demand calculation to account for flight delays,
> **so that** I do not under-staff the slot where delayed flights actually land and over-staff the slot where they were originally scheduled.

**Scenario 1: Delayed aircraft type reduces count at original slot**
```gherkin
Given aircraft type B38M is scheduled with s_ij = 3 at slot 08:00
And d_i = 1 (B38M is delayed)
When the delay adjustment (constraint 6) is applied
Then n_ij for B38M at slot 08:00 equals 0.2 · 3 = 0.6 (rounded: 1)
And the remaining 80% is attributed to the actual arrival slot
```

**Scenario 2: On-time aircraft type is unaffected**
```gherkin
Given aircraft type A320 is scheduled with s_ij = 3 at slot 08:00
And d_i = 0 (A320 is on time)
When the delay adjustment is applied
Then n_ij for A320 at slot 08:00 equals 3
```

**Scenario 3: Sahadevan Table 7 actual arrivals validation**
```gherkin
Given the exact a_ij values from Sahadevan Table 7 (actual movements)
When the Stage 1 LP runs for slot 06:00–07:00
Then r_j equals 269
```

**Maps to:** Stage 1, Constraint 6, Section 5.1.6

---

### US-03 — Minimum Shift Schedule

> **As a** Roster Manager,
> **I want** the system to produce a shift schedule that covers the hourly demand with the minimum total number of workers,
> **so that** I have a cost-optimal baseline roster to work from each day.

**Scenario 1: All hours covered**
```gherkin
Given d_t values for all operating hours t = 1 to H
And shift length L = 8
When the Stage 2 LP is solved
Then x_t ≥ 0 for all t
And for every hour t, the sum of x_i for i in [max(1, t−L+1), t] is ≥ d_t
```

**Scenario 2: Minimum is better than naive baseline**
```gherkin
Given a day with peak demand d_peak = max(d_t) across all hours
And naive baseline = d_peak workers scheduled every hour
When the Stage 2 LP is solved
Then Σ x_t < d_peak · H / L
```

**Scenario 3: Integer solution after rounding**
```gherkin
Given the LP relaxation produces fractional x_t values
When all fractional x_t values are rounded up to the nearest integer
Then all coverage constraints Σ x_i ≥ d_t still hold for every hour t
```

**Maps to:** Stage 2, Sections 5.2.4 – 5.2.6

---

### US-04 — Accurate Daily Headcount

> **As a** Roster Manager,
> **I want** the total worker count for the day to reflect each person exactly once,
> **so that** the headcount I report to HR and finance is accurate with no duplicate shift assignments.

**Scenario 1: No duplicate counting**
```gherkin
Given a solved shift schedule with x_t values across H hours
When the daily total z is computed as Σ x_t
Then z equals the number of distinct shift-start assignments
And a worker who starts at hour t is not counted again at hours t+1 through t+L
```

**Scenario 2: Headcount is payroll-ready**
```gherkin
Given a solved schedule with z = 45
When the output is passed to an HR or payroll system
Then the system receives exactly 45 worker-shift records
And no deduplication step is required
```

**Maps to:** Stage 2, Section 5.2.1

---

### US-05 — Capacity Constraint Enforcement

> **As an** Operations Manager,
> **I want** the model to respect the total available workforce pool,
> **so that** the schedule never requires more staff than Finavia actually has available.

**Scenario 1: Demand within capacity**
```gherkin
Given R = 300 available workers
And r_j ≤ 300 for all slots j
When the Stage 1 LP runs
Then the model returns a feasible solution
And r_j ≤ R holds at every slot
```

**Scenario 2: Demand exceeds capacity**
```gherkin
Given R = 200 available workers
And one or more slots j where r_j would exceed 200
When the Stage 1 LP runs
Then the solver returns an infeasibility status
And the output identifies which slots j have r_j > R
And no silent undercount or zero-result is returned
```

**Maps to:** Stage 1, Constraint 8, Section 5.1.6

---

### US-06 — Aircraft-Type Staffing Standards

> **As a** Resource Planner,
> **I want** the staffing requirement per flight to be set by aircraft type from our ground handling SLA,
> **so that** wide-body and narrow-body flights are always resourced to the correct standard.

**Scenario 1: c_i is configurable per aircraft type**
```gherkin
Given c_i = 13 for A320 and c_i = 26 for B772
And both types are present at slot 10:00
When the Stage 1 LP runs
Then r_j at slot 10:00 includes 13 workers per A320 flight
And r_j at slot 10:00 includes 26 workers per B772 flight
```

**Scenario 2: Changing c_i for one type does not affect others**
```gherkin
Given c_i is updated from 13 to 15 for B738 only
When the Stage 1 LP runs
Then r_j changes only at slots where B738 is present
And r_j at slots with no B738 is unchanged
```

**Scenario 3: Default reference values are available**
```gherkin
Given no custom c_i values are provided by the user
When the system initialises
Then c_i defaults to 13 for narrow-body types (A20N, A320, B38M, B738)
And c_i defaults to 26 for wide-body types (B772, B788)
And c_i defaults to 27 for A388
```

**Maps to:** Section 5.1.4, Section 5.1.7

---

### US-07 — Bottleneck Hour Identification

> **As an** Operations Manager,
> **I want** to see which hours are driving the total workforce size,
> **so that** I can target schedule negotiations or operational changes at the hours that matter most.

**Scenario 1: Shadow prices returned for binding constraints**
```gherkin
Given a solved Stage 2 LP
When the dual variables are extracted
Then a shadow price value is returned for every coverage constraint t = 1 to H
And constraints where the shadow price > 0 are flagged as bottleneck hours
```

**Scenario 2: Non-binding hours have zero shadow price**
```gherkin
Given hour t = 03:00 with d_t = 2 and actual coverage = 10
When the dual variables are extracted
Then the shadow price for t = 03:00 equals 0
```

**Scenario 3: Output is human-readable**
```gherkin
Given a set of bottleneck hours with non-zero shadow prices
When the output is formatted
Then each row contains the hour label and the shadow price value
And the output can be read without parsing raw solver output
```

**Maps to:** Verification Step 6, Section 9

---

### US-08 — On-Time Window Classification

> **As a** Resource Planner,
> **I want** flights that arrive outside the ±15-minute scheduled window to trigger resource reallocation to the correct slot,
> **so that** workers are deployed at the hour when the aircraft actually needs them, not when it was scheduled.

**Scenario 1: Flight arrives within tolerance — resources allocated at scheduled slot**
```gherkin
Given a flight scheduled at slot j = 09:00
And actual arrival t_ij = 09:10 (10 minutes late)
And V = 15 minutes
When constraint 9 is evaluated
Then |t_ij − j| = 10 ≤ 15
And y_ij = 1
And z_ij is eligible to be 1 at slot 09:00
```

**Scenario 2: Flight arrives outside tolerance — resources reallocated**
```gherkin
Given a flight scheduled at slot j = 09:00
And actual arrival t_ij = 09:25 (25 minutes late)
And V = 15 minutes
When constraint 9 is evaluated
Then |t_ij − j| = 25 > 15
And y_ij = 0
And z_ij = 0 at slot 09:00
And the flight is allocated to the slot matching t_ij = 09:25
```

**Scenario 3: Tolerance window is configurable**
```gherkin
Given V is set to 10 minutes by the operator
And a flight arrives 12 minutes late
When constraint 9 is evaluated
Then |t_ij − j| = 12 > 10
And y_ij = 0
And the allocation is moved to the actual arrival slot
```

**Maps to:** Stage 1, Constraint 9, Section 5.1.6

---

## 3. Goals

- [x] Define demand r_j per time slot using aircraft type, scheduled counts, and delay adjustment
- [x] Schedule worker shifts x_t to cover demand d_t at minimum total headcount
- [x] Count total daily workforce exactly once — no double-counting of workers across hours
- [x] Parameterise c_i (workers per aircraft type) from Finavia's ground handling SLA
- [ ] Extend c_i to a bounded decision variable if contract flexibility exists *(Phase 2)*
- [ ] Derive turnaround window W probabilistically via Sheibani CPM/PERT + Monte Carlo *(Phase 2)*

## 3. Non-Goals

- Predicting actual arrival time a_ij — this is a separate ML task; the LP takes a_ij as input
- Optimising gate/stand allocation — out of scope
- Real-time rescheduling — this spec covers the pre-shift planning horizon (8–10 h ahead)

---

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1 — DEMAND  (Sahadevan LP)                           │
│                                                             │
│  Inputs:  s_ij, a_ij, c_i, d_i, R, V                       │
│  Output:  r_j  (workers required at each time slot j)       │
└──────────────────────────┬──────────────────────────────────┘
                           │  r_j  →  d_t
┌──────────────────────────▼──────────────────────────────────┐
│  STAGE 2 — SHIFT SCHEDULING  (Textbook LP)                  │
│                                                             │
│  Inputs:  d_t, H, L                                         │
│  Output:  x_t  (workers starting shift at hour t)           │
│           z    (total daily headcount = Σ x_t)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Specification

### 5.1 Stage 1 — Demand Computation (Sahadevan LP)

**Source:** Sahadevan et al. 2023, Section 2

#### 5.1.1 Objective

```
Min  Σ r_j,   ∀ j
```

Minimise total resources required across all time slots. The formulation accounts for scheduled and actual arrival times per aircraft type, the maximum resources per type, and available capacity per slot.

#### 5.1.2 Decision Variables

| Variable | Type | Description |
|----------|------|-------------|
| `x_ij` | `binary` | 1 if aircraft type `i` arrives at time slot `j`; else 0 |
| `y_ij` | `binary` | 1 if aircraft type `i` arrives **within** scheduled slot `j`; else 0 |
| `z_ij` | `binary` | 1 if aircraft type `i` requires resource allocation at slot `j`; else 0 |
| `t_ij` | `float`  | Estimated arrival time for aircraft type `i` at slot `j` |

#### 5.1.3 Result Variables

| Variable | Type | Description |
|----------|------|-------------|
| `r_j`  | `int`    | Total workers required at slot `j` |
| `d_i`  | `binary` | 1 if aircraft type `i` is delayed; else 0 |
| `n_ij` | `int`    | Delay-adjusted count of aircraft type `i` at slot `j` |

#### 5.1.4 Uncontrollable Variables (Inputs)

| Variable | Type | Description | Source |
|----------|------|-------------|--------|
| `s_ij` | `int`   | Aircraft type `i` **scheduled** at slot `j` | Finavia flight schedule |
| `a_ij` | `int`   | Aircraft type `i` **actually** arriving at slot `j` | Operations data |
| `c_i`  | `int`   | Max workers required per aircraft of type `i` | Finavia SLA / ground handling standards |

> **Design note on `c_i`:** Sahadevan classifies `c_i` as uncontrollable — it is the maximum staffing requirement fixed by airline contract and safety regulation. In the current phase, `c_i` is treated as a fixed input. If Finavia's contracts allow a range `[c_i_min, c_i_max]`, a future extension can convert `c_i` into a bounded decision variable, letting the LP choose the deployment level within that range.

#### 5.1.5 Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `R` | `int`   | Total available resources per slot (capacity ceiling) | From staffing pool |
| `V` | `float` | Max allowable arrival time deviation (minutes) | `15` |

#### 5.1.6 Constraints

---

**Constraint 5 — Total resources at slot j**

```
r_j = Σ_i  z_ij · c_i · x_ij     ∀ i, j
```

Computes workers needed at slot `j`. For each aircraft type `i`, contributes `c_i` workers if and only if the aircraft has arrived (`x_ij = 1`) and requires allocation (`z_ij = 1`). Accounts for scheduled and actual arrival times and the maximum resources per type.

---

**Constraint 6 — Delay-adjusted aircraft count**

```
n_ij = s_ij · (1 − d_i) + 0.2 · s_ij · d_i     ∀ i, j
     = s_ij · (1 − 0.8 · d_i)
```

Adjusts the aircraft count when delays are present.

| `d_i` value | Meaning | Effect on `n_ij` |
|------------|---------|-----------------|
| `0` (on time) | All scheduled aircraft arrive at planned slot | `n_ij = s_ij` |
| `1` (delayed) | Only 20% arrive at planned slot; 80% shift to a later slot | `n_ij = 0.2 · s_ij` |

This constraint prevents over-provisioning at the original slot and under-provisioning at the later slot. It enables the model to *"robustly optimise the allocation of ground resources and reduce inefficiencies"* when delays occur.

---

**Constraint 7 — Resource allocation flag**

```
z_ij = x_ij · y_ij · n_ij     ∀ i, j
```

Resources are deployed at slot `j` for type `i` only when all three conditions hold:
- `x_ij = 1` — aircraft arrived
- `y_ij = 1` — arrived within the ±`V` tolerance window
- `n_ij > 0` — non-zero delay-adjusted count

If the aircraft arrives outside the tolerance window (`y_ij = 0`), `z_ij = 0` and the allocation is moved to the correct slot.

---

**Constraint 8 — Resource capacity**

```
r_j ≤ R     ∀ j
```

Workers deployed at any slot cannot exceed the available pool `R`. If `r_j > R` for any slot, the model is infeasible — either hire more staff or revise demand inputs.

---

**Constraint 9 — Arrival time variation**

```
|t_ij − j| ≤ V     ∀ i, j
```

Arrival time `t_ij` must not deviate from scheduled slot `j` by more than `V` minutes (typically ±15 min). This formalises the on-time classification: flights inside the window set `y_ij = 1`; outside the window, `y_ij = 0` and resources are reallocated to the actual arrival slot.

---

**Constraint 10 — Binary declarations**

```
x_ij, y_ij, z_ij, d_i  ∈  {0, 1}
```

Makes the Stage 1 problem a **Mixed Integer Linear Program (MILP)**.

---

#### 5.1.7 Reference Values for c_i

From Sahadevan Table 7 (Dubai Airport empirical data):

| Aircraft category | Examples | `c_i` | Typical turnaround |
|------------------|----------|-------|-------------------|
| Narrow-body | A20N, A320, B38M, B738 | `13` | 50–100 min |
| Wide-body | B772, B788 | `26` | 50–100 min |
| Superjumbo | A388 | `27` | 114–160 min |

> **Caution:** Early arrivals require a *longer* turnaround than on-time or delayed arrivals (Sahadevan Figure 9). Do not treat early arrivals as reduced demand.

#### 5.1.8 Validation Case — Sahadevan Table 7

Dubai International Airport, 06:00–07:00:

| Aircraft | `s_ij` | `c_i` | Sched. workers | `a_ij` | Actual workers |
|----------|--------|-------|----------------|--------|----------------|
| A20N | 4 | 13 | 52 | 4 | 52 |
| A320 | 3 | 13 | 39 | 3 | 39 |
| B38M | 3 | 13 | 39 | 4 | 52 |
| B738 | 3 | 13 | 39 | 3 | 39 |
| B772 | 1 | 26 | 26 | 1 | 26 |
| B788 | 1 | 26 | 26 | 1 | 26 |
| A388 | 0 | 27 | 0  | 1 | 27 |
| SU95 | 0 | 8  | 0  | 1 | 8  |
| **Total** | **15** | | **221** | **18** | **269** |

**Expected result:** `r_j(scheduled) = 221`, `r_j(actual) = 269` — a **+22% gap**.

Any implementation must reproduce this result when fed the table values as input.

---

### 5.2 Stage 2 — Shift Scheduling (Textbook LP)

**Source:** LP_operations_research.pdf, Section 3.5, pp. 72–75

#### 5.2.1 The Shift-Start Variable

`x_t` is defined as workers **starting** their shift at hour `t` — not workers currently on duty.

**Why this is correct:**

If the variable were "workers present at hour t", a single worker on an 8-hour shift would be counted 8 times in the objective — once per hour they are on duty. Summing these across the day gives a meaningless total.

By counting shift **starts**, each worker appears in the objective exactly once. Summing all `x_t` gives the true daily headcount — the number of unique worker-shifts assigned. No worker is counted twice regardless of shift length.

```
Total workers rostered for the day  =  z  =  Σ_{t=1}^{H} x_t
```

This is the quantity being minimised and the quantity that maps directly to payroll cost.

#### 5.2.2 Parameters

| Symbol | Type | Description |
|--------|------|-------------|
| `H` | `int` | Total operating hours (e.g., `19` for 05:00–24:00) |
| `L` | `int` | Shift length in hours (e.g., `8`) |
| `d_t` | `int` | Minimum workers required at hour `t` — equals `r_t` from Stage 1 |

#### 5.2.3 Decision Variable

```
x_t  =  workers beginning their shift at hour t
         t = 1, 2, …, H
         x_t ≥ 0,  integer
```

#### 5.2.4 Objective

```
min  z  =  Σ_{t=1}^{H}  x_t
```

#### 5.2.5 Coverage Constraints

Workers on duty at hour `t` are all those who started within the previous `L` hours:

```
Σ_{i = max(1, t−L+1)}^{t}  x_i  ≥  d_t     ∀ t = 1, …, H
```

#### 5.2.6 Complete Formulation

```
min  z = x_1 + x_2 + ... + x_H

s.t.
  t=1:    x_1                              ≥  d_1
  t=2:    x_1 + x_2                        ≥  d_2
  t=3:    x_1 + x_2 + x_3                  ≥  d_3
  ...
  t=L:    x_1 + ... + x_L                  ≥  d_L
  t=L+1:       x_2 + ... + x_{L+1}         ≥  d_{L+1}
  ...
  t=H:    x_{H−L+1} + ... + x_H            ≥  d_H

  x_t ≥ 0,  integer    ∀ t
```

#### 5.2.7 Solve Strategy

1. Solve LP relaxation (allow fractional `x_t`)
2. Round all fractional values **up** to nearest integer
3. Verify all coverage constraints still hold after rounding

---

## 6. Data Contract

The following inputs must be provided to run the model. All values are per operating day.

| Field | Type | Description | Who provides |
|-------|------|-------------|-------------|
| `schedule` | `Dict[aircraft_type, Dict[slot, int]]` | `s_ij` — scheduled arrivals per type per slot | Finavia schedule system |
| `actuals` | `Dict[aircraft_type, Dict[slot, int]]` | `a_ij` — actual/predicted arrivals per type per slot | Operations / prediction |
| `resources_per_type` | `Dict[aircraft_type, int]` | `c_i` — workers per flight per aircraft type | Finavia SLA |
| `delay_flags` | `Dict[aircraft_type, bool]` | `d_i` — is this type delayed today | Operations monitoring |
| `capacity` | `int` | `R` — total available worker pool | HR |
| `tolerance_minutes` | `float` | `V` — on-time window, default `15.0` | Operations policy |
| `operating_hours` | `int` | `H` — total slots in the day | Airport schedule |
| `shift_length` | `int` | `L` — hours per shift | Labour agreement |

---

## 7. Extensions (Planned)

### 7.1 Multiple Worker Roles

Add role index `r` to both stages:
- `x_{t,r}` = workers of role `r` starting at hour `t`
- `c_{i,r}` = workers of role `r` per flight of type `i`
- Separate coverage constraint per role

### 7.2 Rolling Horizon

*(LP_operations_research.pdf §3.12)*

- Solve for next 7 days; implement day 1; re-solve with updated inputs
- Handles seasonal demand variation (summer/winter schedule)

### 7.3 Part-Time Workers

*(LP_operations_research.pdf §3.5 Problem 1)*

- `p_t` = part-time workers starting at hour `t`, shift length `L/2`
- Objective: `min Σ c_full·x_t + Σ c_part·p_t`

### 7.4 Variable c_i

If contract flexibility exists: convert `c_i` from a fixed parameter to a bounded decision variable `c_{ij} ∈ [c_i_min, c_i_max]`.

### 7.5 Turnaround Window W — Sheibani Phase 2

Derive `W` (slot occupancy duration per flight) using CPM/PERT + Monte Carlo simulation on the ground handling task network. Replace the fixed `W` input with a probabilistic `W_95` (95th percentile). Reference: Sheibani (2018).

---

## 8. Acceptance Criteria

### Stage 1

- [ ] Model produces a comparison table structured like Sahadevan Table 7; data values will differ from Sahadevan's inputs.
  - one row per aircraft type
  - columns for scheduled and actual flight count
  - manpower-per-flight
  - total manpower
  - footer row summing to `r_j`
- [ ] Constraint 6 correctly reduces `n_ij` by 80% when `d_i = 1`
- [ ] Constraint 9 correctly sets `y_ij = 0` for arrivals outside ±15 min window
- [ ] `r_j ≤ R` holds at all slots
- [ ] Model raises infeasibility signal when `r_j > R` cannot be resolved

### Stage 2

- [ ] `Σ x_t` equals the total unique worker-shifts for the day (no duplicates)
- [ ] All coverage constraints `Σ x_i ≥ d_t` hold for every hour `t` after integer rounding
- [ ] Total `z` is strictly less than naive peak-staffing baseline
- [ ] Shadow prices are accessible on all binding coverage constraints

### Integration

- [ ] Stage 2 `d_t` values are sourced directly from Stage 1 `r_j` output
- [ ] End-to-end run on one day of Finavia schedule data completes without error
- [ ] Results are reproducible given identical inputs

---

## 9. Verification Steps

1. **Table 7-style output** — Run Stage 1 on sample inputs. Assert the output contains a comparison table with the structure shown below;
  `r_j` values will differ from Sahadevan's because the sample is not the paper's dataset.

   **Example output table (sample data)**

   | Aircraft Type | Sched. Flights | Manpower/Flight | Sched. Total | Actual Flights | Manpower/Flight | Actual Total |
   | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
   | A320 | 2 | 13 | 26 | 3 | 13 | 39 |
   | B738 | 2 | 13 | 26 | 2 | 13 | 26 |
   | B772 | 1 | 26 | 26 | 1 | 26 | 26 |
   | **Total manpower for hour** | | | **78** | | | **91** |
   | % additional due to actual variation | | | | | | **17%** |

   *Scheduled `r_j = 78`; actual `r_j = 91` in this example. Replace with real Finavia data for production runs.*

2. **Delay scenario** — Set `d_i = 1` for all aircraft types. Assert `n_ij = 0.2 · s_ij` for every `(i, j)` pair.

3. **Coverage check** — After solving Stage 2, assert `Σ_{i=max(1,t−L+1)}^{t} x_i >= d_t` for all `t`.

4. **No-duplicate check** — Assert `Σ x_t == total unique worker-shifts`. Cross-check against a manually constructed roster for a small example.

5. **Infeasibility check** — Set `R = 0`. Assert the solver returns an infeasible status, not a zero solution.

6. **Baseline comparison** — Compute `z_naive = max(d_t) * H / L`. Assert `z < z_naive`.

7. **Integer rounding** — Solve LP relaxation. Round up. Re-assert all coverage constraints hold.

---

## 10. Source Files

| File | Purpose |
|------|---------|
| `Deepudev Sahadevan - Optimising Airport Ground Resource Allocation...pdf` | Stage 1 LP: objective, constraints 5–10, variable definitions, `c_i` reference values |
| `LP_operations_research.pdf` | Stage 2 LP: shift-start formulation §3.5; rolling horizon §3.12 |
| `K. Sheibani - Scheduling Aircraft Ground Handling Operations Under Uncertainty...pdf` | Phase 2 roadmap: turnaround window `W` via CPM/PERT + Monte Carlo |
