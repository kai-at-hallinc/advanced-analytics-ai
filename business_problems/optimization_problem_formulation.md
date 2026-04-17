# Airport Ground Handling Shift Scheduling — Optimization Problem Formulation

> **Source:** Reverse-engineered from `/optimization/` source code. All claims cite specific
> files and line numbers. No external documentation or knowledge from the original team was used.

---

## Problem Description

An airport ground handling operator (ramp crews, loadmasters, check-in agents) receives a daily
flight schedule. Each flight triggers one or more **tasks** — bounded work intervals tied to the
flight's scheduled time. For example, a loadmaster service may start 45 minutes before departure
and end at block-off. The operator must create and time **work shifts** for each role and assign
tasks to those shifts such that:

- Every task is covered by exactly one shift
- No single worker is double-booked within their shift (tasks do not overlap)
- Shift lengths and timing respect labor regulations
- Total paid labor time (clock-in to clock-out, adjusted for splits) is minimized

The solver is **Google OR-Tools CP-SAT** (constraint programming, not LP/MIP). All continuous time
is discretized to **15-minute intervals** (Δ = 900 s).

Two optimization modes exist, run in sequence per time window:

1. **`workshift_count`** — pre-optimization phase; finds the minimum number of shifts required
2. **`total_time`** — primary phase; minimizes total paid labor hours subject to the shift count
   found in phase 1

---

## Sets and Indices

| Symbol | Definition |
|--------|-----------|
| T | Set of all tasks generated from the flight schedule |
| W | Set of all candidate workshifts |
| W_U ⊆ W | Dummy "UNALLOCATED" workshifts — one per task type; a feasibility sink for tasks that cannot be placed |
| W_O ⊆ W | Open workshifts — already started in a prior time window; start time is fixed |
| W_F ⊆ W_O | Fixed workshifts — both start and end are frozen; not optimized at all |
| G | Set of shift groups (e.g., "Loadmaster", "Ramp Loader", "Check-in") |
| W_g ⊆ W | Workshifts belonging to group g ∈ G |
| L | Set of linked workshift pairs (Loadmaster ↔ Ramp Loader paired shifts) |

---

## Parameters

### Temporal Parameters

| Symbol | Default value | Definition |
|--------|--------------|-----------|
| Δ | 900 s (15 min) | Discretization timestep (`classes.py`) |
| τ_t^s | — | Start time of task t in Unix seconds |
| τ_t^e | — | End time of task t in Unix seconds |
| η_before | 900 s (15 min) | Minimum buffer time before first task in a shift (`min_time_before_first_task_in_seconds`) |
| η_after | 900 s (15 min) | Minimum buffer time after last task in a shift (`min_time_after_last_task_in_seconds`) |
| S_max | — | Index of the latest allowed shift start time in the discretized time scale |
| D | — | Allowed start/end time domain — excludes configured peak hours (default: 14:30–17:00) |

### Shift Length Parameters

| Symbol | Default value | Definition |
|--------|--------------|-----------|
| L_min | 24 units = 6 h | Minimum shift length in Δ-units when no split is present (`workshift_min_length_in_seconds`) |
| L_max | 56 units = 14 h | Maximum shift length in Δ-units when no split is present (`workshift_max_length_in_seconds`) |
| L_min^sp | 24 units = 6 h | Minimum shift span in Δ-units when a split is present (`split_shift_min_length_in_seconds`) |
| L_max^sp | 56 units = 14 h | Maximum shift span in Δ-units when a split is present (`split_shift_max_length_in_seconds`) |
| L_split | 18000 s = 5 h | Duration of the off-clock gap in a split shift (`split_min_length_in_seconds`) — **see Issue 1** |
| L_combined | 25200 s = 7 h | Minimum combined on-clock work time when a split is present (`split_shift_min_combined_time_in_seconds`) |

### Task and Shift Matching Parameters

| Symbol | Definition |
|--------|-----------|
| κ_t ∈ (0, 1] | Capacity demand of task t, sourced from `task_rule.capacity`. Fractional values are permitted (e.g., 0.5 for a half-staffing task). |
| ρ_{t,w} ∈ [0, 1] | Relevance of task t to workshift w, sourced from `shift_rule.rule_mapping.relevance`. A value of 1.0 denotes a perfect match; lower values indicate decreasing preference. |
| N_g | Maximum number of simultaneously active workshifts in group g, sourced from `shift_rule.max_simultaneous_shifts`. When a group contains multiple shift types, N_g is the minimum across all types (conservative bound). |
| c_w | Cost weight of workshift w, sourced from `shift_rule.cost` (default 1). Used only in `workshift_count` objective. |

### Penalty Coefficients

| Symbol | Value | Definition |
|--------|-------|-----------|
| M | 1000 · Δ = 900000 s | Penalty per unallocated task (in `total_time` mode) |
| M' | 20 | Penalty per unallocated task (in `workshift_count` mode) |
| α | Δ / max(Σ_w S_max, 1) | Small normalizing coefficient for the late-start bonus term |

---

## Decision Variables

### Assignment Variables (always present)

```
x_{t,w} ∈ {0, 1}     ∀ t ∈ T,  ∀ w ∈ W  s.t. task t is type- and airline-compatible with shift w
                                            (or w ∈ W_U — unallocated sink)
```

Binary: equals 1 if and only if task t is assigned to workshift w. The set of valid (t, w) pairs
is determined by `shift_rule.rule_mappings` — a task is only offered to shifts whose rule mappings
match both the task's type and its operating airline. Tasks that match no shift are only offered to
W_U. Source: [`variables.py:44–59`](../optimization/model/variables.py#L44).

---

### Shift Timing Variables

```
s_w ∈ ℤ_≥0,  s_w ∈ D     ∀ w ∈ W \ W_O
```

Integer index into the 15-minute time scale representing the **start** of workshift w. Fixed to a
constant for open workshifts. The domain D excludes configured peak-hour slots.
Source: [`variables.py:131`](../optimization/model/variables.py#L131).

```
e_w ∈ ℤ_≥0,  e_w ∈ D     ∀ w ∈ W \ W_F
```

Integer index into the 15-minute time scale representing the **end** of workshift w. Fixed to a
constant for fully fixed workshifts. Source: [`variables.py:155`](../optimization/model/variables.py#L155).

---

### Presence Variable (mode-dependent)

```
p_w ∈ {0, 1}     ∀ w ∈ W \ W_U
```

Binary: equals 1 if workshift w is activated. **In `total_time` mode this is a constant 1** — all
candidate workshifts are always considered present, and idle shifts still contribute their full span
to the objective. In `workshift_count` mode it is a genuine binary decision variable.
Source: [`variables.py:113–116`](../optimization/model/variables.py#L113).

---

### Split Shift Variables (when `config.include_split_shift = True`)

```
sp_w ∈ {0, 1}     ∀ w ∈ W \ W_U
```

Binary: equals 1 if workshift w contains a mid-shift off-clock gap (split).
Source: [`split_shift.py:49`](../optimization/model/split_shift.py#L49).

```
sp_s_w ∈ ℤ   (Unix seconds, on Δ-grid)     ∀ w ∈ W \ W_U
sp_e_w ∈ ℤ   (Unix seconds, on Δ-grid)     ∀ w ∈ W \ W_U
```

Start and end of the off-clock gap in absolute epoch seconds, snapped to the Δ-grid. When
`sp_w = 0`, both are forced to 0. **Critically, the OR-Tools interval constraint
`size = config.split_min_length_in_seconds` is a constant**, so the model implicitly enforces
`sp_e_w − sp_s_w = L_split` exactly — see Issue 1.
Source: [`split_shift.py:88–93`](../optimization/model/split_shift.py#L88).

---

### Break Variables (when `config.include_break = True` — disabled by default)

```
b_w ∈ {0, 1},  b_s_w ∈ ℤ,  b_e_w ∈ ℤ     ∀ w ∈ W \ W_U
```

Break presence and its window. Default configuration disables breaks entirely
(`include_break = False`), so these variables are not created in standard runs.
Source: [`model/breaks.py`](../optimization/model/breaks.py).

---

## Objective Functions

### Mode A — `total_time` (primary: minimize total paid labor)

```
Minimize  Z_A  =  Z_work  +  Z_split  +  Z_lateness  +  Z_relevance  +  Z_unalloc
```

**Term 1 — Total shift span**

```
Z_work  =  Δ · Σ_{w ∈ W \ W_U} ( e_w − s_w )
```

Sum of all shift durations in seconds (index difference × 15 min). This is the dominant term.
Source: [`objectives.py:47–56`](../optimization/model/objectives.py#L47).

---

**Term 2 — Split shift credit**

```
Z_split  =  − Σ_{w ∈ W \ W_U} (sp_e_w − sp_s_w)  +  2·3600 · Σ_{w ∈ W \ W_U} sp_w
```

Because `sp_e_w − sp_s_w = L_split` exactly (5 h) when `sp_w = 1`, this simplifies to:

```
Z_split  =  ( −L_split + 2·3600 ) · Σ_{w ∈ W \ W_U} sp_w
          =  −3·3600 · Σ_{w ∈ W \ W_U} sp_w         [at default L_split = 5 h]
```

**Interpretation:** A 5-hour off-clock gap is treated as only 2 hours of non-working time under the
labor contract. The net effect is that each activated split **reduces** the objective by 3 h worth
of time units, incentivizing the solver to use split shifts. This is a deliberate business rule
encoding a labor agreement, not a bug. Source: [`objectives.py:58–71`](../optimization/model/objectives.py#L58).

---

**Term 3 — Late-start bonus**

```
Z_lateness  =  − α · Σ_{w ∈ W \ ( W_O ∪ W_U )} s_w
```

Weakly encourages new shifts to start later in the day (saving early-morning staffing slots). The
normalizing coefficient α is very small, keeping this term strictly secondary to Z_work.
Source: [`objectives.py:75–104`](../optimization/model/objectives.py#L75).

---

**Term 4 — Task-to-shift relevance mismatch penalty**

```
Z_relevance  =  Σ_{w ∈ W \ W_U}  Σ_{t}  ( 1 − ρ_{t,w} ) · x_{t,w}
```

Penalizes assigning tasks to shifts with lower rule-affinity (e.g., wrong airline specialty).
When ρ_{t,w} = 1 (perfect match) the penalty is zero. Source: [`objectives.py:107–136`](../optimization/model/objectives.py#L107).

---

**Term 5 — Unallocated task penalty**

```
Z_unalloc  =  M · Σ_{w ∈ W_U}  Σ_{t}  x_{t,w}       where M = 1000·Δ
```

Strongly discourages leaving tasks unscheduled by assigning a 1000× multiplied cost per task
routed to a dummy unallocated shift. This term dominates all others when any task is unallocated.
Source: [`objectives.py:32–37`](../optimization/model/objectives.py#L32).

---

### Mode B — `workshift_count` (pre-optimization: minimize shift count)

```
Minimize  Z_B  =  Σ_{w ∈ W \ W_U} c_w · p_w  +  20 · Σ_{w ∈ W_U} Σ_{t} x_{t,w}
```

Minimizes the weighted count of activated workshifts. The factor 20 weakly penalizes unallocated
tasks (weaker than Mode A's 1000× so that near-infeasible tasks do not force shift creation at
unreasonable cost). The result — minimum shift counts per type — is carried forward to constrain
Mode A. Source: [`objectives.py:38–42`](../optimization/model/objectives.py#L38).

---

## Constraints

### C1 — Complete Task Coverage

```
Σ_{w : x_{t,w} defined}  x_{t,w}  =  1       ∀ t ∈ T
```

Every task must be assigned to exactly one workshift. The unallocated sinks W_U are always
included in the sum, so this constraint is always feasible. Source: [`constraints.py:293–307`](../optimization/constraints.py#L293).

---

### C2 — Shift Length Bounds

```
L_min   ≤  e_w − s_w  ≤  L_max       if p_w = 1  and  sp_w = 0
L_min^sp ≤  e_w − s_w  ≤  L_max^sp    if p_w = 1  and  sp_w = 1
                                        ∀ w ∈ W \ ( W_F ∪ W_U )
```

Enforces labor-law minimum and maximum shift lengths. The bounds differ depending on whether a
split is present (different parameter pair from `OptimizationConfiguration`).
Source: [`constraints.py:95–154`](../optimization/model/constraints.py#L95).

---

### C3 — No Task Overlap Within a Shift (Cumulative Resource)

For each workshift w, a resource of effective capacity 1.1 is defined. At every time slot τ:

```
Σ_{t : τ_t^s ≤ τ < τ_t^e}  κ_t · x_{t,w}
  +  1.1 · 𝟙[break interval covers τ] · b_w
  +  1.1 · 𝟙[split interval covers τ] · sp_w
  ≤  1.1                                          ∀ w ∈ W \ W_U
```

The capacity of 1.1 (rather than 1.0) intentionally permits two simultaneously active tasks whose
combined demand does not exceed 1.1 — for example, two half-staffing tasks each with κ = 0.5.
Breaks and splits consume the full 1.1, which prevents any task work during those intervals.
OR-Tools requires integer inputs; the helper `multiply_decimals_to_integers` scales all demands
and the capacity to integers before calling `AddCumulative`.
Source: [`constraints.py:157–184`](../optimization/model/constraints.py#L157).

---

### C4 — Maximum Simultaneous Shifts per Group (Staffing Cap)

At every time slot τ:

```
Σ_{w ∈ W_g : shift w is active at τ}  1  ≤  N_g       ∀ g ∈ G
```

Limits the number of concurrently active workshifts of the same group (e.g., at most N_g
loadmasters on the floor at any one time). Implemented as an OR-Tools `AddCumulative` over the
optional workshift intervals. Source: [`constraints.py:56–92`](../optimization/model/constraints.py#L56).

---

### C5 — Shift Must Bracket Its Assigned Tasks

```
s_w  ≤  ⌊ (τ_t^s − η_before) / Δ ⌋       if x_{t,w} = 1
e_w  >  ⌊ (τ_t^e + η_after)  / Δ ⌋       if x_{t,w} = 1
                                            ∀ t ∈ T,  ∀ w ∈ W
```

The shift must begin at least η_before = 15 min before any assigned task starts (preparation
time), and end at least η_after = 15 min after any assigned task ends (wind-down time). Both are
conditional on the assignment variable via `OnlyEnforceIf`.
Source: [`constraints.py:187–240`](../optimization/model/constraints.py#L187).

---

### C6 — Inactive Shift Holds No Tasks

```
p_w = 0  ⟹  x_{t,w} = 0       ∀ t ∈ T,  ∀ w ∈ W \ W_O
```

If a workshift is not activated, no task may be assigned to it. Implemented via
`AddBoolAnd([x.Not() for all t]).OnlyEnforceIf(p_w.Not())`.
Source: [`constraints.py:223–227`](../optimization/model/constraints.py#L223).

---

### C7 — Split Shift Feasibility (eight sub-conditions, active when sp_w = 1)

Let t_0 = epoch of the first time-scale entry. The split start/end are in absolute Unix seconds;
shift start/end are indices scaled back by: `Δ · s_w + t_0`.

```
(a)  sp_w ≤ p_w
     [split only if shift is present]

(b)  Δ·(e_w − s_w)  −  (sp_e_w − sp_s_w)  ≥  L_combined     (= 7 h)
     [minimum 7 h of on-clock work after subtracting the gap]

(c)  sp_s_w  ≥  Δ·s_w + t_0
     [split starts no earlier than shift start]

(d)  sp_e_w  ≤  Δ·e_w + t_0
     [split ends no later than shift end]

(e)  sp_e_w  ≤  end_of_calendar_day( s_w )
     [split must end within the same calendar day the shift starts]

(f)  ∃ t assigned to w :  τ_t^e + η_after  ≤  sp_s_w
     [at least one task must complete before the split begins]

(g)  ∃ t assigned to w :  sp_e_w  ≤  τ_t^s − η_before
     [at least one task must start after the split ends]

(h)  Σ tasks_before_split[t]  +  Σ tasks_after_split[t]  =  Σ_{t} x_{t,w}
     [every assigned task is entirely before or entirely after the split; none straddle it]
```

Source: [`split_shift.py:100–210`](../optimization/model/split_shift.py#L100).

---

### C8 — No Night Shifts (when `config.allow_nightshifts = False`)

```
e_w  ≤  NightLimit( s_w )       ∀ w ∈ W \ ( W_F ∪ W_U )
```

NightLimit maps the calendar day of s_w to the 03:00 next-day boundary for that day. Prevents
shifts from crossing into the early-morning hours. The day determination uses a set of binary
indicator variables `workshift_start_day[i]` that identify which day group s_w falls into, then
constrains e_w to the maximum index of that day group.
Source: [`constraints.py:310–349`](../optimization/model/constraints.py#L310).

---

### C9 — Loadmaster / Ramp Loader Pairing

For each pair (w_LM, w_RL) ∈ L:

```
p_{w_LM}  =  p_{w_RL}
[paired shifts must be activated together or not at all]

x_{t_LM, w_LM}  ≤  Σ_{t_RL : flights(t_RL) ∩ flights(t_LM) ≠ ∅}  x_{t_RL, w_RL}
[if a loadmaster task is assigned, a matching ramp-loader task for the same flight(s)
 must also be assigned to the paired shift]
                                        ∀ t_LM ∈ T compatible with w_LM
```

Ensures that loadmaster and ramp-loader shifts co-exist and handle the same set of flights as a
coordinated pair. Source: [`constraints.py:243–290`](../optimization/model/constraints.py#L243).

---

### C10 — Peak-Time Exclusion (domain constraint)

```
s_w  ∉  peak_time_indices       ∀ w ∈ W \ W_O
e_w  ∉  peak_time_indices       ∀ w ∈ W \ W_O
```

Prevents new shifts from starting or ending during configured peak periods (default 14:30–17:00).
Implemented by constructing `start_time_domain` and `end_time_domain` via `Domain.FromValues`
that exclude those indices, rather than as an explicit model constraint.
Source: [`variables.py:27–43`](../optimization/model/variables.py#L27).

---

## Compact Formulation (primary mode, `total_time`)

```
Minimize  Z_A  =

    Δ · Σ_{w ∉ W_U} (e_w − s_w)                            (shift span)
  − 3·3600 · Σ_{w ∉ W_U} sp_w                              (split credit, −3 h each)
  − α · Σ_{w ∉ W_O ∪ W_U} s_w                              (late-start bonus)
  + Σ_{w ∉ W_U} Σ_t (1 − ρ_{t,w}) · x_{t,w}               (relevance mismatch)
  + 1000Δ · Σ_{w ∈ W_U} Σ_t x_{t,w}                        (unallocated penalty)

Subject to:

  [C1]  Σ_w x_{t,w} = 1                                      ∀ t ∈ T
  [C2]  L_min ≤ e_w − s_w ≤ L_max                            ∀ w ∉ W_F ∪ W_U,  conditional on sp_w
  [C3]  Cumulative task demands ≤ 1.1 per workshift           ∀ w ∉ W_U
  [C4]  Σ active shifts in group g ≤ N_g                      ∀ g ∈ G, at every time slot
  [C5]  s_w ≤ ⌊(τ_t^s − η_before)/Δ⌋,  e_w > ⌊(τ_t^e + η_after)/Δ⌋   if x_{t,w} = 1
  [C6]  p_w = 0  ⟹  x_{t,w} = 0                             ∀ w ∉ W_O
  [C7]  Split feasibility conditions (a)–(h)                  if sp_w = 1
  [C8]  e_w ≤ NightLimit(s_w)                                 if ¬allow_nightshifts
  [C9]  LM–RL pairing                                         ∀ (w_LM, w_RL) ∈ L
  [C10] s_w, e_w ∉ peak_time_indices                          ∀ w ∉ W_O

  x_{t,w} ∈ {0, 1},   s_w, e_w ∈ ℤ_≥0 ∩ D,   sp_w ∈ {0, 1}
```

---

## Issues, Anomalies, and Open Problems

The following issues were identified purely from code inspection. They represent gaps between the
apparent intent of the code (variable names, comments, config field names) and the actual
mathematical behavior.

---

### Issue 1 — Split gap length is fixed, not a minimum (design flaw or undocumented intent)

**Location:** [`split_shift.py:88–93`](../optimization/model/split_shift.py#L88)

```python
assigned_splits[w_id] = model.NewOptionalIntervalVar(
    start=start,
    size=config.split_min_length_in_seconds,   # ← constant, not a lower bound
    end=end,
    is_present=has_split,
)
```

The `size` argument to `NewOptionalIntervalVar` is a **constant integer**, not a variable. OR-Tools
therefore enforces `sp_e_w − sp_s_w = L_split` exactly — always 5 h. The config field name
`split_min_length_in_seconds` strongly implies a minimum, but the implementation makes it an
equality.

As a consequence, the objective term `split_size = end − start` in `split_variables` is always
exactly `L_split` when `sp_w = 1`. The split credit in the objective is therefore a fixed constant
per activated split: `−5h + 2h = −3h`. There is no flexibility in split duration.

**Consequence:** If the labor agreement intended "gap of at least 5 h," the model is more
restrictive than required and may reject feasible schedules that use gaps of, say, 6 h.

**Suggested fix:** Replace the constant `size` with an integer variable bounded below by
`split_min_length_in_seconds` and above by the shift span. Adjust the objective's split_size term
to use this variable.

---

### Issue 2 — Capacity threshold of 1.1 is a magic number (fragile design)

**Location:** [`constraints.py:171–178`](../optimization/model/constraints.py#L171)

The cumulative capacity is hardcoded to 1.1 with demands scaled by `multiply_decimals_to_integers`.
The rationale:

- Two half-staffing tasks (κ = 0.5 each): demand 0.5 + 0.5 = 1.0 ≤ 1.1 → allowed ✓
- Any task + break: κ + 1.1 > 1.1 → blocked ✓
- Any task + split: κ + 1.1 > 1.1 → blocked ✓

This works only if **all** task capacities satisfy κ > 0 and κ ≤ 1.0. The logic breaks if:
- A task with κ < 0.1 is introduced: it could co-exist with a break (κ + 1.1 = 1.1 + ε ≤ 1.1
  could pass with rounding).
- More than two fractional tasks with combined demand > 1.1 are expected to be blocked.

There is no documentation explaining why 1.1 was chosen. A safer design would make the capacity
configurable or derive it from the maximum task count permitted per shift.

---

### Issue 3 — Acknowledged bug: LM–RL pairing fails for multi-flight tasks

**Location:** [`constraints.py:270–273`](../optimization/model/constraints.py#L270)

```python
# TODO: possible issue with flight_id if we have task with multiple flights
if len(
    set(f.id for f in task.flights).intersection(
        set(f.id for f in task_dict[task_id1].flights)
    )
) > 0
```

Tasks generated from grouped flights (e.g., airline SK groups 2 flights per loadmaster task —
see `flight_grouping/grouping.py`) contain multiple `Flight` objects. The pairing constraint
matches tasks by set intersection of `flight.id`. If the same physical flight appears in different
task groupings for the LM and RL sides, the intersection may be empty even when the tasks should
be paired, causing the pairing constraint to be silently skipped.

**Impact:** Loadmaster and ramp-loader tasks for the same flight may end up on shifts that are
not paired, violating the operational requirement that both roles service the same aircraft
together. This is an open acknowledged bug with no fix in the codebase.

---

### Issue 4 — Objective terms have inconsistent units and undocumented relative scaling

**Location:** [`objectives.py:19–43`](../optimization/model/objectives.py#L19)

The five terms of Z_A have different units:

| Term | Units |
|------|-------|
| Z_work | seconds (Δ × index) |
| Z_split | seconds (same) |
| Z_lateness | approximately dimensionless (very small fractional value) |
| Z_relevance | task-count (pure integer count of mismatched assignments × (1−ρ)) |
| Z_unalloc | seconds (1000 × Δ per task) |

Because CP-SAT operates on integers, all terms are in practice scaled by OR-Tools' internal
integer conversion — but the *relative weights* between seconds-valued terms and the
relevance count term are unexamined. A single relevance-mismatched assignment contributes
`(1 − ρ) ≈ O(1)` to the objective, which is equal to one second of additional shift time.
A 30-minute over-run (1800 s) is therefore 1800× more expensive than one relevance mismatch.
This is almost certainly not the intended weighting, and there is no comment documenting it.

---

### Issue 5 — Rolling-horizon windowing destroys global optimality

**Location:** `optimization.py` (time-window chunking logic)

Tasks are processed in sequential chunks of approximately 70 tasks per time window. The solver
finds a locally optimal solution within each window, then workshifts from that window are passed
forward as open workshifts with fixed start times. **The combined solution is not globally
optimal** — it is a rolling-horizon greedy heuristic. The 10-second solver time limit per window
(from `solver_time_limit_in_seconds`) further limits within-window quality.

The formulation described in this document applies to a single time window only. The true
multi-window problem is not formulated anywhere in the codebase as a unified model.

---

### Issue 6 — In `total_time` mode, idle shifts are never eliminated

**Location:** [`variables.py:113–116`](../optimization/model/variables.py#L113)

```python
if config.objective == "total_time" or w_id in {w.id for w in open_work_shifts}:
    workshift_is_present = model.NewConstant(True)
else:
    workshift_is_present = model.NewBoolVar(...)
```

In `total_time` mode, `p_w` is forced to constant `True` for all candidate workshifts. The solver
cannot choose to deactivate an empty shift. If the workshift pool contains a shift that receives
no tasks, it still contributes its minimum span (L_min = 6 h) to the objective. Shift pool sizing
is entirely controlled by the pre-optimization phase; the primary optimizer has no recourse if the
pool is over-provisioned.

---

### Issue 7 — No inter-shift, inter-day, or fairness constraints

The model contains no constraints on:
- Minimum rest time between an employee's consecutive shifts on the same or subsequent days
- Maximum cumulative hours per employee per week
- Balanced task load distribution between workers of the same role

This is a pure cost-minimization model with a single aggregate objective. In operational
deployments subject to labor law or collective agreements, additional constraints of this type
would be required.

---

### Issue 8 — Peak-time exclusion is one-directional (starts/ends only)

**Location:** [`variables.py:27–43`](../optimization/model/variables.py#L27)

The peak-time domain excludes shift **start times and end times** from the peak window. However,
a shift starting at 14:00 and ending at 18:00 passes directly through the 14:30–17:00 peak period
and is not blocked. The constraint prevents *creating* new shifts during peak hours but does not
limit the number of shifts *active* during peak. Whether the business intent was to prevent all
peak-hour shift boundaries or to cap active staffing during peak is not documented.

---

*All formulation elements verified against source code. File and line references are to the
`/work-shift-optimization/optimization/` directory.*
