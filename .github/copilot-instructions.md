# advanced-analytics-ai Development Guidelines

   Repository for prototyping optimization and machine learning methods in agentic workflows, based on AIMA (Artificial Intelligence: A Modern Approach)
  implementations.

   ## Build, Test, and Lint

   ### Environment Setup
   ```bash
   # Python 3.10+ required
   pip install -e .                    # Install base dependencies
   pip install -e ".[dev]"              # Install with test dependencies
   pip install -e ".[lp]"               # Install linear programming (ortools)
   pip install -e ".[ml]"               # Install ML dependencies (qpsolvers)
   pip install -e ".[deep_learning]"    # Install deep learning (keras, tensorflow)

  Testing

   # Run all tests
   cd src && pytest

   # Run specific module tests
   pytest tests/lp/test_demand.py
   pytest tests/search/test_search.py
   pytest tests/ml/test_learning.py

   # Run single test function
   pytest tests/lp/test_demand.py::test_single_narrow_body_single_slot
   pytest tests/search/test_search.py::test_breadth_first_tree_search

   # Alternative: Direct execution (calls pytest.main())
   python tests/lp/test_demand.py

  Linting

   cd src && ruff check .

  Architecture

  Module Organization

  The codebase follows a topic-based structure mirroring AI/ML domains:

   src/
   ├── csp/                   # Constraint Satisfaction Problems
   ├── logic/                 # Logic and knowledge representation
   ├── lp/                    # Linear Programming (optimization)
   │   ├── types.py          # Core data classes (FlightSlotInput, DemandConfig, etc.)
   │   └── demand.py         # Demand computation algorithms
   ├── ml/                    # Machine Learning
   ├── neural_nets/           # Neural network implementations
   ├── nlp/                   # Natural Language Processing
   ├── planning/              # Planning algorithms
   ├── probability/           # Probabilistic models and inference
   ├── rl/                    # Reinforcement Learning
   ├── search/                # Search algorithms
   ├── shared/                # Shared utilities across modules
   │   ├── utils_aima.py     # AIMA-specific utilities
   │   ├── utils4e.py        # 4th edition utilities
   │   ├── utils.py          # General utilities (sequences, graphs, etc.)
   │   └── agents.py         # Agent frameworks
   └── utils/                 # Data loading utilities
       └── efhk_loader.py    # EFHK (Helsinki airport) data loader

   tests/                     # Mirrors src/ structure
   └── {module}/test_*.py    # Test files mirror source structure

  Dual Implementation Pattern

  Many modules have both base and "4e" (4th edition) versions:

   - {module}.py - Base/3rd edition implementation
   - {module}4e.py - 4th edition implementation

  Examples: learning.py/learning4e.py, probability.py/probability4e.py, search.py/search4e.py

  Business Problems

  The business_problems/ directory contains specifications for real-world optimization problems:

   - ramp_resource_minimization_spec.md - Aviation ground handling worker scheduling (LP)
   - Specs follow Gherkin-style user stories with formal mathematical formulations

  Feature Development

  Features follow the Spec Kit workflow in specs/{feature-id}/:

   - spec.md - Feature specification
   - plan.md - Implementation plan
   - tasks.md - Task breakdown
   - data-model.md - Data model documentation

  Key Conventions

  Import Patterns

   - Tests use wildcard imports: from src.{module}.{file} import
    *
   - Test files import from src/ directory (using pytest pythonpath configuration)

  Test Data and Reproducibility

   - All test files seed randomness: random.seed("aima-python") at module level
   - Specific tests may use additional seeds for reproducibility
   - Tests define reusable problem instances at module level (e.g., romania_problem, burglary network)

  Data Classes and Type Safety

   - Heavy use of @dataclass with __post_init__ validation (see src/lp/types.py)
   - Type hints throughout: dict[AircraftType, int], Literal["A", "D"], etc.
   - Enums for constrained values: class AircraftType(str, Enum)

  Linear Programming Module (src/lp/)

   - Domain-specific types for aviation optimization problems
   - Validation in __post_init__ methods (negative counts, time ranges, enum values)
   - Structured input types (e.g., FlightSlotInput, FlightMovementInput)
   - Configuration objects with factory defaults (e.g., DemandConfig)

  Databricks Integration

   - Repository supports Databricks asset bundles (databricks.yml)
   - Development target configured for Azure Databricks workspace
   - Optional dependency group: pip install -e ".[mcp]" for MCP server features

  Documentation

   - CLAUDE.md contains auto-generated guidelines from feature plans
   - README.md provides high-level project description
   - Business problem specs in business_problems/ contain detailed requirements and mathematical formulations

  AIMA Context

  This codebase implements algorithms and techniques from "Artificial Intelligence: A Modern Approach" (Russell & Norvig), enabling rapid prototyping of
  AI/optimization solutions for business problems