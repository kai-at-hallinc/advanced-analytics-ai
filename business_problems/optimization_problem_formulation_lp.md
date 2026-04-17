# Airport Ground Handling — Workforce LP Formulation

> **Solver:** Any LP solver (HiGHS, GLPK, Gurobi, …). No integer declarations required
> under normal operating conditions (see Section 12, Claim 1).
> **Scope:** One operational day per solve. Split shifts and breaks omitted for clarity;
> add in a subsequent iteration once the core LP is validated.

---

## 1. Problem Description

### 1.1 Two-Role Decomposition

This formulation deliberately separates two decisions that belong to different
organizational roles:

| Role | Decision | When | Model |
| --- | --- | --- | --- |
| **Resource Planner** | How many shifts of each crew type, starting at which time? | Day before operations | **This LP** |
| **Ops Coordinator** | Which specific task goes to which open shift? | Day of operations | Downstream — see Section 13 |

The **Resource Planner LP** produces a shift count schedule: for each crew type k and
shift template j, the LP returns x_{k,j} — the number of shifts of that type that should
start at start_j and end at end_j. The Ops Coordinator then assigns individual tasks to
those shifts on the day. This separation is correct because:

- The two decisions have different timescales (day-before vs. real-time).
- The resource planner does not know which specific aircraft will arrive late; they only
  know the scheduled demand profile.
- The ops coordinator does not re-optimize the total number of shifts; they work with
  what the planner has opened.

The original CP-SAT model solved both decisions simultaneously. This LP formalises only
the resource planner's problem.

### 1.2 Ground Handling Context

An airport ground handling operator (ramp, loadmaster, check-in) receives a daily flight
schedule. Each flight triggers one or more **tasks** — bounded work intervals with a fixed
start and end time. Tasks are grouped by **crew type** k (e.g., Loadmaster = LM, Ramp
Loader = RL, Check-in = CI).

The planner must decide how many shifts of each type to open, and when each shift should
start and end, such that enough workers are present at every moment to service all
concurrent tasks. The objective is to minimize total paid shift-hours.

---

## 2. Computing Demand Parameters

Before the LP is built, the concurrent task demand d_{k,θ} is computed from the flight
schedule. This is a preprocessing step — not part of the LP.

### 2.1 Definition

```
d_{k,θ}  =  |{ t ∈ T_k : τ_t^s ≤ θ < τ_t^e }|     ∀ k ∈ K, θ ∈ Θ
```

The number of tasks of crew type k whose service window contains time slot θ. This is
always a non-negative integer.

### 2.2 Example

Three LM tasks on a morning:

| Task | Window |
| --- | --- |
| LM-1 | 06:00 – 07:00 |
| LM-2 | 06:30 – 07:30 |
| LM-3 | 07:00 – 08:00 |

Resulting demand profile (Δ = 15 min):

| Slot θ | d_{LM,θ} |
| --- | --- |
| 06:00 | 1 |
| 06:15 | 1 |
| 06:30 | 2 |
| 06:45 | 2 |
| 07:00 | 2 |
| 07:15 | 1 |
| 07:30 | 1 |
| 07:45 | 0 |

The LP must open enough LM shifts to have at least 2 active workers during 06:30–07:15.

---

## 3. LP Assumptions (Winston Section 3.1)

Any LP model requires four assumptions. Their status in this formulation:

| Assumption | Requirement | Status |
| --- | --- | --- |
| **Proportionality** | Each variable contributes linearly to the objective and constraints | ✓ Satisfied — duration_j · x_{k,j} is linear; no squared or product terms |
| **Additivity** | Total objective = sum of individual variable contributions; no cross-product terms | ✓ Satisfied |
| **Divisibility** | Variables may take any non-negative real value (fractions allowed) | ✓ Satisfied at LP extreme points due to Total Unimodularity — see Section 12, Claim 1 |
| **Certainty** | All parameters are known with certainty | ⚠ Approximate — d_{k,θ} is derived from scheduled times; actual flight delays introduce uncertainty |

**Divisibility in detail.** Workforce planning requires integer shift counts (you cannot
open 1.7 shifts). This is the same tension noted by Winston (Section 3.5) for the Post
Office Problem, where the LP optimum had x_1 = 15.67 employees. The resolution here is
different: the constraint matrix of the coverage LP is an **interval matrix**, which is
totally unimodular (TU). Combined with integer demand d_{k,θ}, this guarantees that every
LP extreme point is integer-valued. The LP relaxation therefore returns integer x_{k,j}
without any integer declaration. See Section 12, Claim 1 for the formal argument.

---

## 4. Candidate Shift Templates

The LP variables are indexed over pre-generated shift **templates** — (type, start, end)
triples that define a valid shift window before the LP is built.

### 4.1 Generation

For each crew type k, the set of candidate templates is:

```text
J_k  =  { j = (k, start_j, end_j) :
            start_j ∈ D,
            end_j ∈ D,
            L_min ≤ end_j − start_j ≤ L_max }
```

where D is the set of allowed Δ-grid time points (excluding peak hours — see Filter F2
below). There is no task-compatibility filter: templates are pure time windows, not tied
to individual tasks. Whether enough templates are active at a given slot is enforced by
the LP coverage constraint C1.

### 4.2 Parameter Filters (no LP rows generated)

These filters are applied during template generation and do not add LP constraint rows:

- **[F1] Duration bounds.** L_min ≤ end_j − start_j ≤ L_max. Templates outside this
  range are excluded from J_k.
- **[F2] Peak-time exclusion.** start_j ∉ peak_slots, end_j ∉ peak_slots. Templates
  whose start or end falls in a configured peak window (default 14:30–17:00) are excluded.
  Shifts may be *active* during peak hours; only shift starts and ends are restricted.

### 4.3 Size

With Δ = 15 min and a 24-hour day, |D| ≤ 96 slots. After applying F1 (6 h ≤ duration ≤
14 h) and F2 (peak exclusion), the number of templates per type is typically 500–1 500.
Total variable count across all types: |K| × 1 000 ≈ 3 000–5 000.

---

## 5. Sets, Indices, and Parameters

### Sets

| Symbol | Definition |
| --- | --- |
| K | Crew/shift types (LM, RL, CI, …) |
| T | All tasks for the day |
| T_k ⊆ T | Tasks of type k |
| J | All candidate templates: J = ∪_k J_k |
| J_k ⊆ J | Candidate templates for type k |
| G | Shift groups — each group g covers one or more types k |
| J_g ⊆ J | Templates belonging to group g |
| Θ | Discrete time slots: {0, Δ, 2Δ, …, T_day − Δ} |

### Parameters

| Symbol | Default | Definition |
| --- | --- | --- |
| Δ | 900 s (15 min) | Discretization timestep |
| T_day | 86 400 s | Seconds in a day |
| τ_t^s | — | Start time of task t (seconds from midnight) |
| τ_t^e | — | End time of task t (seconds from midnight) |
| d_{k,θ} | — | Concurrent task demand of type k at slot θ (integer ≥ 0, precomputed) |
| start_j | — | Pre-computed start time of template j |
| end_j | — | Pre-computed end time of template j |
| duration_j | end_j − start_j | Paid duration of template j (seconds) |
| L_min | 21 600 s = 6 h | Minimum shift length (filter F1) |
| L_max | 50 400 s = 14 h | Maximum shift length (filter F1) |
| N_g | — | Maximum simultaneously active shifts in group g |
| α | Δ / max(Σ_j start_j, 1) | Small coefficient for optional late-start bonus |

---

## 6. Decision Variable

There is a single class of decision variables:

```
x_{k,j} ≥ 0     ∀ k ∈ K,  j ∈ J_k
```

**x_{k,j}** = number of shifts of crew type k using template j that the planner opens.

Sign restriction: x_{k,j} ≥ 0 (non-negativity).
Upper bound: none imposed explicitly; bounded implicitly by coverage constraints and
the solver's minimization of cost.

At LP optimum, x_{k,j} is integer-valued (see Section 12, Claim 1). No binary or integer
declaration is needed.

---

## 7. Objective Function

```
Minimize  Z  =    Σ_{k ∈ K}  Σ_{j ∈ J_k}  duration_j · x_{k,j}         (1)

                − α · Σ_{k ∈ K}  Σ_{j ∈ J_k}  start_j · x_{k,j}        (2)
```

**Term (1) — Total paid shift-hours.** The dominant term. Each shift opened costs its
full duration regardless of how many tasks it covers.

**Term (2) — Late-start bonus (optional).** Weakly discourages opening shifts earlier
than necessary by crediting later start times. The coefficient α is deliberately tiny
(α ≈ 0.018 for typical inputs) so this term never overrides span minimization. It serves
as a tie-breaker between templates of equal duration. Set α = 0 to disable.

No task-level summation appears in the objective. The LP minimizes aggregate shift cost,
not individual task cost.

---

## 8. Constraints

### C1 — Coverage

```
Σ_{j ∈ J_k : start_j ≤ θ < end_j}  x_{k,j}  ≥  d_{k,θ}     ∀ k ∈ K, θ ∈ Θ
```

At every time slot θ, the total number of active shifts of type k must be at least the
concurrent task demand d_{k,θ}. This is the direct LP analogue of the Post Office Problem
coverage constraint (Winston Section 3.5).

**Row count.** |K| × |Θ| = 3 × 96 = 288 rows for a typical three-type, 15-min-grid
setup. Slots with d_{k,θ} = 0 can be dropped (never binding); in practice the active row
count is determined by the operational hours of each type.

---

### C2 — Staffing Cap

```
Σ_{j ∈ J_g : start_j ≤ θ < end_j}  x_{k,j}  ≤  N_g     ∀ g ∈ G, θ ∈ Θ
```

The number of simultaneously active shifts in crew group g cannot exceed N_g at any time
slot (floor space, equipment, or regulatory headcount limit). This is the only constraint
that can cause LP infeasibility — see Section 11.

---

### Sign Restrictions

Per textbook LP convention (Winston Section 3.2), the sign restrictions are listed
separately from the structural constraints:

```
x_{k,j} ≥ 0     ∀ k ∈ K,  j ∈ J_k
```

---

## 9. Full LP (Compact Form)

```
Minimize  Z  =  Σ_{k,j}  duration_j · x_{k,j}  −  α · Σ_{k,j}  start_j · x_{k,j}

Subject to:

  [C1]  Σ_{j : start_j ≤ θ < end_j}  x_{k,j}  ≥  d_{k,θ}     ∀ k ∈ K, θ ∈ Θ

  [C2]  Σ_{j ∈ J_g : start_j ≤ θ < end_j}  x_{k,j}  ≤  N_g   ∀ g ∈ G, θ ∈ Θ

        x_{k,j} ≥ 0   [sign restrictions]

        [F1, F2: duration bounds and peak exclusion enforced by construction of J_k]
```

Variable count: |K| × avg|J_k| ≈ 3–5 × 10³.
Constraint rows: |K||Θ| + |G||Θ| ≈ 400–500 (excluding trivially non-binding rows).
Expected solve time: < 1 second on any modern LP solver.

---

## 10. Relationship to the Classical Work Scheduling LP (Winston Section 3.5)

The standard textbook workforce scheduling LP (Post Office Problem, Winston Section 3.5)
uses variables x_i = number of employees starting work on day i, with coverage constraints
ensuring enough workers are present on each day. Our formulation is a direct generalization
of that model:

| Element | Post Office (Winston §3.5) | This LP |
| --- | --- | --- |
| Index set | Days of the week (7 templates) | (type, start, end) triples (\|J_k\| templates) |
| Variable | x_i = workers starting on day i | x_{k,j} = shifts of type k using template j |
| Coverage constraint | Σ_{i covering day d} x_i ≥ r_d | Σ_{j active at θ} x_{k,j} ≥ d_{k,θ} |
| Objective | Minimize Σ x_i (worker count) | Minimize Σ duration_j · x_{k,j} (shift-hours) |
| Templates | Fixed (5-day shifts) | Flexible — any (start, end) on Δ-grid within [L_min, L_max] |
| TU / integrality | Not argued; textbook notes IP is needed | ✓ Interval matrix TU guarantees integer optimum |

**Key extension beyond the textbook.** The post office model assumes fixed 5-day shift
templates, so timing is a given. In our model, shift timing is a design decision: any
(start, end) pair on the Δ-grid within the allowed domain is a valid template. This
multiplies the variable count by roughly 1 000× compared to the textbook, but the LP
structure is identical and the TU property still holds.

**Why not the aggregate count approach alone?** The post office model answers "how many
workers per shift template" but cannot track individual task-to-shift assignments. For the
Resource Planner, this is sufficient — they need headcounts, not rosters. The Ops
Coordinator handles individual assignment downstream (Section 13).

---

## 11. LP Feasibility and Boundedness (Winston Section 3.3)

**Feasibility.** The LP is always feasible when N_g is not binding. Setting x_{k,j} large
enough for the single widest template j^* (start_{j^*} = min D, end_{j^*} = max D) satisfies
C1 at all slots. The LP is always feasible in the absence of C2.

**Potential infeasibility from C2.** If peak demand max_θ d_{k,θ} > N_g for any group g,
the coverage requirement C1 and the cap C2 are simultaneously infeasible. Remedies:
raise N_g, reduce demand (reject some tasks), or add a slack variable to C1 with a large
penalty (making it a soft constraint).

**Boundedness.** The objective is bounded below:

- Term (1): duration_j ≥ 0 and x_{k,j} ≥ 0, so Σ duration_j · x_{k,j} ≥ 0.
- Term (2): −α · Σ start_j · x_{k,j} ≥ −α · Σ start_j ≥ −Δ (by construction of α).
- Therefore Z ≥ −Δ > −∞. The LP cannot be unbounded.

**Alternative optima.** When two templates j, j' have equal duration and cover the same
demand slots, the solver is indifferent. Term (2) breaks this tie by preferring the
later-starting template. If start times also match, any convex combination is optimal and
the simplex may return a degenerate basis — this is harmless given Claim 1.

---

## 12. Claims and Rebuttals

### Claim 1 — The LP Returns Integer x_{k,j} at Optimum

**Argument.** The constraint matrix A of C1 is a 0-1 matrix: entry A_{(k,θ), (k',j)} = 1
if and only if k' = k and start_j ≤ θ < end_j, and 0 otherwise. For a fixed type k, the
sub-matrix has one column per template j, and each column's 1s occupy a contiguous block
of rows (those θ ∈ [start_j, end_j)). A matrix in which every column has a contiguous
block of 1s is an **interval matrix** — a well-known subclass of totally unimodular (TU)
matrices.

By the TU theorem: with a TU constraint matrix and integer right-hand side d_{k,θ} (which
is always an integer since it counts tasks), every extreme point of the LP feasible region
is integer-valued. The simplex method always terminates at an extreme point, so the LP
optimum is integer without any branch-and-bound.

This means the **Divisibility Assumption** (LP variables may be fractional) does not lead
to fractional solutions in practice: the LP relaxation and the integer program have the
same optimal value and the same optimal solution.

**Rebuttal.** TU holds for C1 alone. If C2 (staffing cap) is binding at some slot θ, the
combined constraint matrix [C1; C2] may not be TU, and fractional solutions can appear.
In practice, N_g is rarely tight; empirical rounding (x_{k,j} → round(x_{k,j})) produces
feasible integer solutions in the vast majority of cases.

---

### Claim 2 — C2 Is the Only Source of Infeasibility

**Argument.** Without C2, coverage C1 is always satisfiable (set x_{k,j^*} = max_θ d_{k,θ}
for a single all-day template). Therefore the LP is always feasible in the absence of a
binding staffing cap.

**Rebuttal.** If the domain D (after peak exclusion) excludes time slots where demand
d_{k,θ} > 0 and no template in J_k covers those slots, C1 cannot be satisfied even without
C2. Verify that for each type k, every slot θ with d_{k,θ} > 0 is covered by at least one
template in J_k.

---

### Claim 3 — The Late-Start Bonus (Term 2) Can Be Dropped Without Meaningful Impact

**Argument.** The coefficient α = Δ / max(Σ_j start_j, 1) is deliberately tiny. On a
24-hour day with ~1 000 templates, α ≈ 900 / (1 000 × 50 000) ≈ 0.000018. The maximum
contribution of Term (2) is at most Δ = 900 s = 15 min equivalent — smaller than L_min
(6 h). It is a tie-breaking device, not an objective driver.

**Rebuttal.** Without Term (2), the LP is indifferent between two templates of identical
duration starting at 04:00 vs. 10:00. This degeneracy produces unnecessarily early shift
starts on some days. Keep Term (2); it adds no computational cost and prevents this
degeneracy. Set α = 0 only when comparing against a pure shift-count objective to simplify
the formulation for analysis.

---

## 13. Ops Coordinator — Downstream Task Assignment

The LP output is a list of opened shifts: for each (k, j) pair, x_{k,j}* shifts of type
k starting at start_j and ending at end_j.

**What the Ops Coordinator receives:**
> "Open 2 LM shifts 06:00–14:00, 1 LM shift 07:00–15:00, 3 RL shifts 06:30–14:30, …"

**Task assignment (day of operations):**
For each task t of type k, assign it to any open shift j of type k that covers [τ_t^s, τ_t^e)
with at least η_before = 15 min prep before τ_t^s and η_after = 15 min wind-down after
τ_t^e. Constraints at this stage:

- A single shift covers at most one full-demand task per time slot (no double-booking).
- Tasks for the same flight should be assigned to shifts of the correct paired type
  (LM and RL together).

This assignment can be done manually using a roster board, or with a simple greedy
matching algorithm (earliest-deadline-first is sufficient for most days). If automated
assignment is required, it is a separate **minimum-cost bipartite matching LP** — much
smaller than the Resource Planner LP, since it operates on the fixed set of opened
shifts rather than all templates.

**No-overlap is not a Resource Planner concern.** The Resource Planner LP guarantees that
enough shifts are open at every slot. Whether two specific tasks can fit in the same shift
without overlapping is determined by the Ops Coordinator during assignment.

---

## 14. Simplification Suggestions (Priority Order)

| Priority | Suggestion | Benefit | When to add back |
| --- | --- | --- | --- |
| 1 | Solve one crew type at a time | Decouples C2 across types; removes cross-type cap coupling | When group caps N_g span multiple types |
| 2 | Drop Term (2) late-start bonus | Simpler one-term objective; easier to explain | After validating core LP; re-add as tie-breaker |
| 3 | Set N_g = ∞ (drop C2) | Guaranteed TU; always feasible; single constraint class | Add C2 back if floor-space limits are operationally binding |
| 4 | Coarsen time grid to Δ = 30 min | Halves \|J_k\| and \|Θ\|; 4× fewer LP rows | If any task window is ≤ 15 min, keep Δ = 15 min |
| 5 | Fix shift templates | Reduces \|J_k\| from ~1 000 to ~5–10 per type | Only if labor contracts mandate fixed hours |

---

## 15. Open Questions for the Domain Expert

1. **What is the concrete value of N_g per group?** If N_g ≥ max_θ d_{k,θ} for all groups,
   C2 is never binding and can be dropped entirely, giving a guaranteed-TU pure coverage LP.

2. **Are there contractually fixed shift templates** (e.g., morning 06:00–14:00, afternoon
   14:00–22:00)? Templates shrink |J_k| dramatically and simplify the formulation.

3. **What is an acceptable Δ for the LP prototype?** A 30-minute grid halves |J_k| and |Θ|.
   If task windows are never shorter than 30 min, no information is lost.

4. **Should the late-start bonus (Term 2) be retained?** It prevents degeneracy at the cost
   of a slightly more complex objective. Confirm whether early-shift bias is a real issue in
   practice.

5. **Is automated task assignment required, or will the Ops Coordinator assign manually?**
   If automated, the bipartite matching LP (Section 13) should be specified next.

---

*Formulation derived by decomposing the original CP-SAT model in `/optimization/` into
a Resource Planner LP (this document) and a downstream Ops Coordinator assignment step.
The LP structure corresponds directly to the classical workforce scheduling LP of Winston
(2004), Section 3.5, generalized to flexible shift timing and multiple crew types.*
