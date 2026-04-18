# Aviation Ground Handling Worker Scheduling — LP Problem Formulation

## 1. Problem Statement

Finavia operates airports where ground handling requires workers to be present for each arriving and departing flight. The number of workers needed fluctuates hour by hour depending on the flight schedule, aircraft types, and arrival delays.

**Goal:** Minimise the total number of workers scheduled while guaranteeing sufficient coverage at every operational hour.

---

## 2. References

| Reference | Role |
|-----------|------|
| Sahadevan et al. (2023) — *Optimising Airport Ground Resource Allocation* | **Primary** — LP formulation, variable definitions, delay adjustment, c_i values |
| LP_operations_research.pdf — Sections 3.5, 3.12 | Supporting — shift-start variable structure, multi-period rolling horizon |
| Sheibani (2018) — *Scheduling Aircraft Ground Handling Operations Under Uncertainty* | **Roadmap item** — CPM/PERT + Monte Carlo for turnaround window W; to be implemented in a later phase |

---

## 3. Solution Architecture

The problem is solved in two linked stages:

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1 — DEMAND                                           │
│  How many workers are needed at each time slot j?           │
│                                                             │
│  Inputs:  flight schedule (s_ij), aircraft types (c_i),    │
│           delay status (d_i), turnaround window W           │
│  Output:  r_j = workers required at each slot               │
│  Method:  Sahadevan LP                                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ r_j becomes d_t
┌──────────────────────────▼──────────────────────────────────┐
│  STAGE 2 — SHIFT SCHEDULING                                 │
│  How do we assign worker shifts to meet demand d_t?         │
│                                                             │
│  Input:   d_t = r_j from Stage 1                            │
│  Output:  x_t = workers starting shift at hour t            │
│  Method:  Textbook shift-start LP (Post Office Problem)     │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Stage 1 — Demand Computation (Sahadevan LP)

*Source: Sahadevan et al. 2023, Section 2*

### 4.1 Objective

Minimise total resources required across all time slots:

$$\min \sum_j r_j \quad \forall j$$

The objective takes into account the scheduled and actual arrival times of each aircraft type, the maximum number of resources necessary for each aircraft type, and the availability of resources at each time slot. By incorporating these variables, the LP formulation enables mathematical modelling of the ground resource allocation problem and identifies optimal solutions. *(Sahadevan, p. 3)*

### 4.2 Decision Variables

These are variables the model controls directly. *(Sahadevan, paper item 1)*

| Variable | Type | Definition |
|----------|------|-----------|
| x_ij | Binary | 1 if aircraft type i arrives at time slot j; 0 otherwise |
| y_ij | Binary | 1 if aircraft type i arrives **within** the scheduled time slot j; 0 otherwise |
| z_ij | Binary | 1 if aircraft type i **requires resource allocation** at time slot j; 0 otherwise |
| t_ij | Continuous | Estimated arrival time for aircraft type i at time slot j |

### 4.3 Result Variables

These are derived outcomes computed from decision and uncontrollable variables. *(Sahadevan, paper item 2)*

| Variable | Type | Definition |
|----------|------|-----------|
| r_j  | Integer | Total number of resources (workers) required at time slot j |
| d_i  | Binary  | 1 if aircraft type i is delayed; 0 otherwise |
| n_ij | Integer | Revised number of aircraft type i arriving at slot j after delay adjustment |
| t_ij | Continuous | Estimated arrival time for aircraft type i at time slot j |

### 4.4 Uncontrollable Variables and the Status of c_i

These are external inputs the model cannot directly change — they must be observed or predicted. *(Sahadevan, paper item 3)*

| Variable | Definition |
|----------|-----------|
| s_ij | Number of aircraft type i **scheduled** to arrive at time slot j |
| a_ij | Number of aircraft type i **actually** arriving at time slot j |
| c_i  | Maximum number of resources (workers) required per aircraft of type i |

#### Discussion: Should c_i be a decision variable?

Sahadevan classifies c_i as **uncontrollable** — it is the maximum resource requirement set by the airline, airport authority, and safety regulations for a given aircraft type. In the paper's model, c_i is a fixed input, not something the LP can reduce.

However, this is a valid design question. In practice, ground handling contracts and airline SLAs typically specify a **minimum required staffing level** per aircraft type, not necessarily a fixed level. There is often a range:

```
c_i_min  ≤  actual deployment  ≤  c_i_max
```

- **c_i_min** is the regulatory/safety floor (cannot go below this)
- **c_i_max** is the full-service standard from the airline contract

If Finavia has flexibility within this range, c_i could be redefined as a **bounded decision variable**, allowing the LP to choose the deployment level per aircraft type per slot. This would turn constraint (5) into a tighter optimisation:

```
r_j = Σ_i  z_ij · c_ij_actual · x_ij    where  c_i_min ≤ c_ij_actual ≤ c_i_max
```

**Sahadevan's position:** The paper does not model this flexibility — c_i is treated as a fixed maximum input from the airline. This simplifies the formulation and reflects how most ground handling contracts work (staffing levels are contractually fixed per aircraft type).

**Recommendation for Finavia:** Keep c_i as an uncontrollable parameter in the initial implementation, sourced from Finavia's ground handling service agreements. If contract flexibility exists, the bounded decision variable extension can be added in a later phase alongside the Sheibani turnaround window work.

### 4.5 Parameters

| Parameter | Definition |
|-----------|-----------|
| R | Total number of available resources at each time slot (capacity ceiling) |
| V | Maximum allowable variation in arrival time — typically ±15 min |

### 4.6 Constraints

*Constraint numbering follows Sahadevan et al. 2023, items 5–10.*

---

**(5) Total resources required at time slot j**

$$r_j = \sum_{k=0}^{n} z_{ij} \cdot c_i \cdot x_{ij} \quad \forall i, j$$

This constraint computes how many workers are needed at each time slot. For every aircraft type i active at slot j, the term z_ij · c_i · x_ij contributes c_i workers if and only if the aircraft has arrived (x_ij = 1) and requires allocation (z_ij = 1). The total r_j is the sum of these contributions across all aircraft types.

This formulation *"takes into account the scheduled and actual arrival times of each aircraft type, the maximum number of resources necessary for each aircraft type, and the availability of resources at each time slot."* *(Sahadevan, p. 3)*

---

**(6) Revised aircraft count due to delay**

$$n_{ij} = s_{ij}(1 - d_i) + 0.2 \cdot s_{ij} \cdot d_i \quad \forall i, j$$

Simplified:

$$n_{ij} = s_{ij}(1 - 0.8 \cdot d_i)$$

This constraint adjusts the number of aircraft expected at a slot when delays are present. When d_i = 0 (on time): n_ij = s_ij — all scheduled aircraft arrive as planned. When d_i = 1 (delayed): n_ij = 0.2 · s_ij — only 20% of the scheduled count materialises at the planned slot; the remaining 80% shifts to a later slot.

*"By incorporating the actual number of aircraft that arrive, the model can robustly optimise the allocation of ground resources and reduce inefficiencies in airport operations. Enforcing this constraint enables the LP model to minimise resource allocation conflicts and avoid resource shortages or over-provisioning."* *(Sahadevan, p. 4–5)*

---

**(7) Resource allocation flag**

$$z_{ij} = x_{ij} \cdot y_{ij} \cdot n_{ij} \quad \forall i, j$$

This constraint links the three binary decision variables to determine whether resources are actually deployed for aircraft type i at slot j. Resources are allocated only when all three conditions hold simultaneously: the aircraft has arrived at this slot (x_ij = 1), it arrived within the scheduled tolerance window (y_ij = 1), and the delay-adjusted count is non-zero (n_ij > 0). If the aircraft is outside the ±V tolerance window, y_ij = 0 and z_ij = 0, triggering reallocation to the correct slot.

---

**(8) Resource capacity constraint**

$$r_j \leq R \quad \forall j$$

Total resources deployed at any slot cannot exceed the total available workforce R. This is a hard upper bound representing the staffing pool size — the total number of trained ground handling workers available to Finavia at any given time. If r_j would exceed R for some slot, the model is infeasible and either R must increase (hire more staff) or the demand inputs must be revised.

---

**(9) Arrival time variation constraint**

$$|t_{ij} - j| \leq V \quad \forall i, j$$

The actual estimated arrival time t_ij must not deviate from the scheduled slot j by more than V (typically ±15 min). This constraint formalises the on-time classification used in the paper: flights within ±15 min are considered on time (y_ij = 1); flights outside this window are reclassified to the slot where they actually arrive, and resources must be reassigned accordingly. *"Flight delay or early arrival usually results in a different stand allocation and resource planning."* *(Sahadevan, p. 7)*

---

**(10) Binary variable declarations**

$$x_{ij},\ y_{ij},\ z_{ij},\ d_i \in \{0, 1\}$$

All four binary variables take only the values 0 or 1. This makes the problem a **Mixed Integer Linear Program (MILP)**. In practice it is solved using standard MILP solvers (PuLP, Pyomo, or Excel Solver as referenced in Sahadevan p. 5).

---

### 4.7 Numerical Example — Sahadevan Table 7

Dubai International Airport, hour 06:00–07:00.

Applying constraint (5) with scheduled vs actual flight counts:

| Aircraft Type | s_ij (scheduled) | c_i (workers/flight) | Scheduled manpower | a_ij (actual) | Actual manpower |
|--------------|-----------------|----------------------|-------------------|--------------|-----------------|
| A20N | 4 | 13 | 52 | 4 | 52 |
| A320 | 3 | 13 | 39 | 3 | 39 |
| B38M | 3 | 13 | 39 | 4 | 52 |
| B738 | 3 | 13 | 39 | 3 | 39 |
| B772 | 1 | 26 | 26 | 1 | 26 |
| B788 | 1 | 26 | 26 | 1 | 26 |
| A388 | 0 | 27 | 0 | 1 | 27 |
| SU95 | 0 | 8 | 0 | 1 | 8 |
| **Total** | **15 flights** | | **221 workers** | **18 flights** | **269 workers** |

**Result:** Using only the schedule underestimates demand by **22%** (269 vs 221 workers).
This is the core justification for using a_ij (actual/predicted arrivals) rather than s_ij alone.

---

### 4.8 Aircraft-Type Resource Requirements (c_i)

From Sahadevan Table 7 data:

| Category | Aircraft types | c_i (workers / flight) | Typical turnaround |
|----------|---------------|------------------------|-------------------|
| Narrow-body | A20N, A320, B38M, B738 | 13 | 50–100 min |
| Wide-body | B772, B788 | 26 | 50–100 min |
| Superjumbo | A388 | 27 | min 114 min, avg 160 min |

**Note (Sahadevan Figure 9):** Early arrivals require a *longer* turnaround than on-time or delayed arrivals for most aircraft types. Early arrivals must not be modelled as lower demand — they increase resource occupancy, not reduce it.

---

## 5. Stage 2 — Worker Shift Scheduling (Textbook LP)

*Source: LP_operations_research.pdf, Section 3.5, pp. 72–75*

Once r_j is known from Stage 1, determine the minimum number of worker shifts to meet that demand at every hour.

### 5.1 The Shift-Start Variable — Why x_t and Not "Workers Present"

The key modelling decision is to define x_t as the number of workers **starting** their shift at hour t, not the number currently on duty.

**Why this matters:**

If you instead modelled "workers present at hour t" as your variable, the same worker would be counted at every hour of their shift — an 8-hour worker would be counted 8 times in the objective function. This inflates the apparent total and makes the minimisation meaningless.

By counting only shift **starts**, each worker appears in the objective exactly once, on the hour they begin work:

```
Total workers hired  =  Σ x_t  =  x_1 + x_2 + ... + x_H
```

This gives the true daily headcount — the number of unique individuals who came to work that day. No worker is double-counted regardless of how long their shift is. This is the correct quantity to minimise for workforce planning and cost control. *(LP_operations_research.pdf, Section 3.5, p. 72 — common error warning)*

**At end of day:** summing all x_t gives the exact total number of distinct worker-shifts rostered, with no duplicates. Shadow prices on binding constraints then reveal which specific hours are driving that total.

### 5.2 Parameters

| Symbol | Definition |
|--------|-----------|
| H | Total operating hours (e.g., H = 19 for 05:00–24:00) |
| L | Shift length in hours (e.g., L = 8) |
| d_t | Minimum workers required at hour t — set equal to r_t from Stage 1 |

### 5.3 Decision Variable

```
x_t  =  number of workers beginning their shift at hour t
         where t = 1, 2, …, H
```

### 5.4 Objective Function

```
min  z = x_1 + x_2 + ... + x_H  =  Σ_{t=1}^{H} x_t
```

Each worker counted exactly once at their shift start. This is the true total workforce size for the day.

### 5.5 Coverage Constraints

Workers on duty at hour t are all those who started a shift within the previous L hours:

```
For each t = 1, …, H:
  Σ_{i = max(1, t−L+1)}^{t}  x_i  ≥  d_t
```

Example with L = 8, at hour t = 10:
Workers who started at hours 3, 4, 5, 6, 7, 8, 9, or 10 are all still on duty.
Their combined count must be ≥ d_10.

### 5.6 Sign Restrictions

```
x_t ≥ 0,  integer    for all t = 1, …, H
```

Solve the LP relaxation first (allow fractional x_t), then round all values up to the nearest integer. The rounded solution is feasible and near-optimal. *(p. 73–74)*

### 5.7 Complete Formulation

```
min  z = x_1 + x_2 + ... + x_H

subject to:
  hour 1:     x_1                              ≥  d_1
  hour 2:     x_1 + x_2                        ≥  d_2
  hour 3:     x_1 + x_2 + x_3                  ≥  d_3
  ...
  hour L:     x_1 + x_2 + ... + x_L            ≥  d_L
  hour L+1:        x_2 + x_3 + ... + x_{L+1}   ≥  d_{L+1}
  ...
  hour H:     x_{H−L+1} + ... + x_H            ≥  d_H

  x_t ≥ 0,  integer    for all t
```

### 5.8 Toy Example — Shift-Start Headcount Verification

**Toy setup:** H = 6 hours, L = 3h. Each task takes 1 hour; a worker finishing a task is free for the next task within the same shift.

```
Demand:  Hour:  1   2   3   4   5   6
         d_t:   2   3   4   3   2   1
```

**LP variables and objective:**

```
# x[t] = workers starting at hour t — minimise total unique hires:
min  x1 + x2 + x3 + x4 + x5 + x6

# Coverage: workers on duty at t = all who started within the last L=3 hours
hour 1:  x1                  ≥ 2
hour 2:  x1 + x2             ≥ 3
hour 3:  x1 + x2 + x3        ≥ 4
hour 4:       x2 + x3 + x4   ≥ 3
hour 5:            x3 + x4 + x5  ≥ 2
hour 6:                 x4 + x5 + x6  ≥ 1
```

**Optimal solution:** x = [2, 1, 1, 1, 0, 0] → Σ x_t = **5 unique workers**.

---

## 6. Extensions

### 6.1 Multiple Worker Roles and Shift Types

#### 6.1.1 Multiple Worker Roles

Different tasks within a turnaround (fuelling, baggage loading, catering, cleaning) require different skills. Extend the model by adding a role index r:

- Define x_{t,r} = workers of role r starting at hour t
- Separate coverage constraints per role: Σ x_{i,r} ≥ d_{t,r}
- Separate c_i,r values per aircraft type and role
- Objective: min Σ_{t,r} x_{t,r} (or cost-weighted if roles have different wages)

#### 6.1.2 Multiple Shift Types (Morning / Evening)

When the operation runs distinct shift windows (e.g., morning 05:00–13:00 and evening 13:00–21:00) with potentially different shift lengths L_M and L_E, introduce a shift-type index s ∈ {M, E}:

**Decision variables:**

```
x_t^M  =  morning workers starting at hour t,   t ∈ {1 .. t_cut}
x_t^E  =  evening workers starting at hour t,   t ∈ {t_start_E .. H}
```

**Objective — each worker still counted exactly once:**

```
min  Σ_t x_t^M  +  Σ_t x_t^E
```

**Coverage constraint at each hour t:**

```
Σ_{i ∈ M-window(t)} x_i^M  +  Σ_{i ∈ E-window(t)} x_i^E  ≥  d_t
```

where M-window(t) = {max(1, t−L_M+1) .. t} intersected with the morning start domain, and E-window(t) is the equivalent for evening starts.

**Why not two separate LP runs?**

Running separate LPs for morning and evening is only correct if the two windows are strictly non-overlapping *and* no morning worker's shift extends past the boundary hour. In practice, morning workers starting near the boundary are still on duty during the first evening hours. A separate evening LP does not see them and over-hires to compensate:

```
Hour:     1    2    3    4    5    6    7    8  │  9   10   11   ...
                                                │
  x_7^M (starts hr 7, L=8):  [=========8h=========]  ← still on at hrs 9–14
  x_8^M (starts hr 8, L=8):       [=========8h=========]  ← still on at hrs 9–15
                                                │
  Separate evening LP sees 0 workers on duty here  ← over-hires
```

The single joint LP credits morning tail-enders toward early-evening demand, hiring fewer evening starters.

**Toy example** (L_M = L_E = 3h, hours 1–6, boundary at hour 4, demand d = [2, 3, 4, 3, 2, 1]):

```
Coverage constraint at boundary hour 4:
  x_2^M + x_3^M          (morning tail-enders still on duty)
  + x_4^E                (first evening starters)          ≥  3

Joint LP solution:
  x_1^M=2, x_2^M=1, x_3^M=1, x_4^E=1  →  total = 5 workers

Separate LPs see d_4 = 3 with no morning credit:
  x_4^E must cover all 3 alone           →  total = 7 workers

Saving: 2 hires avoided by crediting morning overlap at the boundary.
```

### 6.2 Multiperiod / Rolling Horizon

*(LP_operations_research.pdf, Section 3.12, pp. 109–111)*

When demand varies week-to-week (summer vs winter schedule, holiday peaks):

- Solve the LP for the next 7 days using the current a_ij forecast
- Implement the schedule for day 1 only
- Re-solve with updated flight data and delay predictions for the next 7 days
- Produces a continuously updated roster that adapts to changing demand

### 6.3 Part-Time Workers

*(LP_operations_research.pdf, Section 3.5 Problem 1, p. 75)*

Introduce part-time workers with shift length L/2:

- Define p_t = part-time workers starting at hour t
- Add to coverage constraints alongside x_t
- Objective: min Σ c_full · x_t + Σ c_part · p_t (cost-weighted)

### 6.4 Variable c_i (Future Extension)

As discussed in section 4.4, if Finavia's contracts allow staffing flexibility within a range [c_i_min, c_i_max], c_i can be converted from an uncontrollable parameter into a bounded decision variable. This would allow the LP to optimise deployment levels per aircraft type in addition to shift timing.

### 6.5 Turnaround Window Optimisation — Sheibani (Roadmap)

The turnaround window W (how many consecutive slots a flight occupies) is currently treated as a fixed input. A future phase will use Sheibani's CPM/PERT + Monte Carlo method to derive W probabilistically per aircraft type from the ground handling task network. This produces a statistically robust W_95 (95th percentile window) that accounts for task duration uncertainty.

---

## 7. Data Requirements for Finavia Implementation

| Data item | Source | Used in |
|-----------|--------|---------|
| s_ij — scheduled arrivals/departures per hour | Finavia flight schedule | Sahadevan constraint (6) |
| a_ij — actual/predicted arrivals per hour | Operations data | Sahadevan constraint (5) |
| c_i — workers per flight by aircraft type | Finavia ground handling SLA / standards | Sahadevan constraint (5) |
| d_i — delay status per aircraft type | Operations monitoring | Sahadevan constraint (6) |
| Shift length L | HR / labour agreement | Stage 2 LP |
| Operating hours H | Airport schedule | Stage 2 LP |
| Resource capacity R | Total staffing pool size | Sahadevan constraint (8) |

---

## 8. Critical Source Files

| File | Role |
|------|------|
| `Deepudev Sahadevan - Optimising Airport Ground Resource Allocation...pdf` | Primary LP formulation: objective, constraints (5)–(10), variable definitions, c_i empirical values, 22% schedule gap finding |
| `LP_operations_research.pdf` | Shift-start variable formulation (Stage 2); Section 3.5 Post Office Problem; Section 3.12 rolling horizon |
| `K. Sheibani - Scheduling Aircraft Ground Handling Operations Under Uncertainty...pdf` | Roadmap — CPM/PERT + Monte Carlo for turnaround window W; not in current implementation scope |

---

## 9. Verification Steps

1. **Manual demand check** — For one sample hour using Finavia schedule data, compute r_j manually via constraints (5)–(7). Compare r_j using s_ij (schedule only) vs a_ij (actual). Expect a gap in the range of the 22% found by Sahadevan.

2. **LP feasibility check** — After solving Stage 2, verify all coverage constraints hold: for every hour t, the sum of active x_i values meets or exceeds d_t.

3. **No-duplicate check** — Sum all x_t values. This must equal the total unique worker headcount for the day. Cross-check against any roster system — no worker should appear in more than one shift-start slot.

4. **Baseline comparison** — Compare the LP-optimal total z against the naive approach of always staffing to the peak-hour requirement. The LP should yield a meaningful reduction.

5. **Integer rounding** — Round any fractional x_t values up to the nearest integer. Re-verify all coverage constraints still hold.

6. **Shadow prices** — Inspect dual variables on binding coverage constraints to identify the bottleneck hours driving total workforce size.

7. **Solver** — Implement in Python using PuLP (`pip install pulp`) or `scipy.optimize.linprog`. Excel Solver is also viable for smaller instances as demonstrated in the textbook.
