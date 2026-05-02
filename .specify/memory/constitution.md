<!--
SYNC IMPACT REPORT
Version change: template (unversioned) → 1.0.0
Bump type: MAJOR — initial formal ratification from blank template.

Principles resolved:
- [PRINCIPLE_1_NAME] → I. Module-First (new)
- [PRINCIPLE_2_NAME] → II. Notebook-Driven Validation (amended 2026-04-19)
- [PRINCIPLE_3_NAME] → III. Test Coverage Required (new)
- [PRINCIPLE_4_NAME] → IV. Reproducibility (new)
- [PRINCIPLE_5_NAME] → V. Simplicity & Educational Clarity (new)

Version change: 1.1.0 → 1.2.0
Bump type: MINOR — new workflow rule added (rule 5: src/utils/ for data-loading utilities).
Changes: Development Workflow rule 4 clarified (business_problems/ scope); rule 5 added (src/utils/).

Sections added:
- Technology Stack & Constraints (formerly [SECTION_2_NAME])
- Development Workflow (formerly [SECTION_3_NAME])
- Governance (populated)

Sections removed: None

Templates requiring updates:
✅ .specify/memory/constitution.md — updated (this file)
✅ .specify/templates/plan-template.md — no changes required; Constitution Check gate is generic
✅ .specify/templates/spec-template.md — no changes required
✅ .specify/templates/tasks-template.md — no changes required
✅ .specify/templates/agent-file-template.md — no changes required
✅ .specify/templates/checklist-template.md — no changes required
⚠ .specify/templates/commands/ — directory absent; skipped

Deferred TODOs: None. All placeholders resolved.
-->

# Advanced Analytics AI Constitution

## Core Principles

### I. Module-First

Every feature MUST start as a standalone topic module under `src/`.
Modules MUST be self-contained, independently importable, and independently
testable without requiring other `src/` modules unless an explicit interface
contract exists. Each module MUST address one clearly-defined AI/ML or
analytics domain (e.g., `csp`, `ml`, `planning`, `rl`). Organizational-only
modules with no substantive logic are not permitted.

**Rationale**: Modular boundaries prevent entanglement, enable incremental
delivery, and keep the codebase navigable as the domain surface grows.

### II. Notebook-Driven Validation

All algorithms implemented in `src/` MUST have a corresponding Jupyter
notebook under `notebooks/` that demonstrates and validates the implementation
against realistic inputs. The notebook serves as living documentation and a
test-run record; it MUST import from `src/` rather than re-implementing logic
inline. Notebooks MAY be created concurrently with or after `src/`
implementation.

**Rationale**: Notebooks provide a human-readable validation layer and
experimentation record; the import rule keeps `src/` as the single
authoritative implementation.

### III. Test Coverage Required

Every public function or class added to `src/` MUST have a corresponding
test in `tests/`, mirroring the `src/` directory hierarchy. The test runner
is `pytest`; no alternative runner is permitted. Tests for a module MUST pass
independently before that module is considered mergeable. Tests MUST be
written before or alongside implementation — never solely after PR review.

**Rationale**: Untested prototype code accumulates silent regressions;
mandatory coverage enforces confidence at the module boundary.

### IV. Reproducibility

All experiments and optimization runs MUST be reproducible. Random seeds MUST
be set explicitly where stochastic behaviour is involved. All runtime
dependencies MUST be declared in `pyproject.toml`; undeclared transitive
dependencies are not acceptable in `src/` code. Data preprocessing steps
that affect results MUST be documented in the relevant notebook or a
dedicated README section.

**Rationale**: Reproducibility is the foundation of valid scientific
prototyping; it enables colleagues to replicate, audit, and extend results.

### V. Simplicity & Educational Clarity

Implementations MUST be explainable and educationally clear. YAGNI applies:
no premature abstractions, no speculative generalisations. Complexity beyond
the minimum needed MUST be justified with a written rationale. Where an AIMA
textbook algorithm exists, the implementation MUST follow its conventions and
naming unless a documented reason overrides them. Prefer readable code over
micro-optimised-but-opaque code.

**Rationale**: The project serves as a learning and prototyping environment;
clarity is a first-class quality attribute alongside correctness.

## Technology Stack & Constraints

- **Language**: Python 3.10 or higher (required).
- **Core dependencies**: `numpy`, `scipy`, `ipywidgets`, `jupyter` — always
  available; MUST NOT be removed from base dependencies.
- **Optional groups** (declared in `pyproject.toml`):
  - `ml` — `qpsolvers` for linear/quadratic programming formulations.
  - `deep_learning` — `keras`, `tensorflow` for neural network experiments.
  - `mcp` — `mcp` package for Model Context Protocol agentic tool integration.
  - `dev` — `pytest`, `pytest-cov` for development and CI.
- No unlisted runtime dependency MAY be introduced without a corresponding
  `pyproject.toml` update and PR review.
- All optional dependency groups MUST be installable in isolation without
  side effects on other groups.

## Development Workflow

1. All new work MUST be developed on a feature branch from `main`.
2. The standard delivery flow is: `src/` extraction → `tests/` coverage →
   notebook validation → PR review → merge to `main`.
3. `pytest` MUST pass with zero failures before a PR is opened.
4. Business problem formulations (mathematical specs, notebooks, and
   domain-level documentation) belong under `business_problems/`. A formulation
   MUST reference the relevant `src/` solver module rather than re-implementing
   solver logic inline.
5. Data loading and integration utilities (e.g., CSV loaders, timezone
   converters, external data mappers) belong under `src/utils/` as a standalone
   module. Each utility file MUST have corresponding tests in `tests/utils/`
   mirroring the `src/utils/` hierarchy. `src/utils/` MUST NOT contain
   solver logic; it is strictly a data-preparation layer that calls into
   solver modules.
5. MCP tool implementations belong under `mcp/` and MUST be independently
   runnable and testable.
6. Commit messages MUST be descriptive; each commit SHOULD correspond to one
   logical unit of change (a module, a notebook, or a test suite).

## Governance

This constitution supersedes all other development practices for this
repository. Any practice not addressed here defaults to Python community
standards (PEP 8, PEP 20).

**Amendment procedure**: Amendments require a dedicated PR that (1) updates
this file, (2) increments the version per the versioning policy below,
(3) lists changed principles or sections in the PR description, and
(4) receives at least one approval before merge.

**Versioning policy**:

- MAJOR: backward-incompatible governance changes, principle removals, or
  redefinitions that invalidate existing practice.
- MINOR: new principle or section added, or materially expanded guidance.
- PATCH: clarifications, wording fixes, or non-semantic refinements.

**Compliance review**: All PRs MUST be reviewed against the Core Principles
before merge. Violations MUST either be resolved or documented in a
Complexity Tracking table in the relevant implementation plan. Use `README.md`
for runtime development guidance that supplements this constitution.

**Version**: 1.2.0 | **Ratified**: 2026-04-15 | **Last Amended**: 2026-05-02
