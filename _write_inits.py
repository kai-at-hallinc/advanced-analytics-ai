from pathlib import Path

BASE = Path(r"C:\Users\BYCLADM\advanced-analytics-ai")

inits = {
    BASE / "src" / "__init__.py": '''\
"""
src — Advanced Analytics AI source package.

Topic packages:
  src.shared       — shared utilities and helpers
  src.search       — search algorithms (BFS, DFS, A*, etc.)
  src.csp          — constraint satisfaction problems
  src.logic        — propositional and first-order logic
  src.planning     — classical planning (STRIPS, GraphPlan)
  src.probability  — Bayesian networks, HMMs, probabilistic learning
  src.ml           — machine learning (decision trees, SVM, k-NN)
  src.neural_nets  — deep learning and perception
  src.rl           — MDPs and reinforcement learning
  src.nlp          — natural language processing
"""
''',
    BASE / "src" / "shared" / "__init__.py": '''\
"""Shared utilities used across all src topic packages."""
from .utils import *  # noqa: F401, F403
''',
    BASE / "src" / "search" / "__init__.py": '''\
"""Search algorithms: BFS, DFS, UCS, A*, hill-climbing, simulated annealing."""
from .search import (  # noqa: F401
    Problem, Node, SimpleProblemSolvingAgentProgram,
    breadth_first_graph_search, depth_first_graph_search,
    best_first_graph_search, astar_search,
)
''',
    BASE / "src" / "csp" / "__init__.py": '''\
"""Constraint Satisfaction Problems: backtracking, AC-3, min-conflicts."""
from .csp import CSP, backtracking_search, min_conflicts  # noqa: F401
''',
    BASE / "src" / "logic" / "__init__.py": '''\
"""Logic: propositional and first-order logic, knowledge bases, inference."""
from .logic import KB, PropKB, FolKB, tt_entails, pl_resolution  # noqa: F401
''',
    BASE / "src" / "planning" / "__init__.py": '''\
"""Classical planning: STRIPS, GraphPlan, partial-order and hierarchical planners."""
from .planning import PDDL, Action, PlanningKB  # noqa: F401
''',
    BASE / "src" / "probability" / "__init__.py": '''\
"""Probability: Bayesian networks, HMMs, Kalman filter, probabilistic learning."""
from .probability import BayesNet, enumeration_ask, elimination_ask  # noqa: F401
''',
    BASE / "src" / "ml" / "__init__.py": '''\
"""Machine learning: decision trees, naive Bayes, SVM, k-NN, ensembles."""
from .learning import DecisionTreeLearner, NaiveBayesLearner, NearestNeighborLearner  # noqa: F401
''',
    BASE / "src" / "neural_nets" / "__init__.py": '''\
"""Neural networks and deep learning (Keras/TensorFlow based)."""
''',
    BASE / "src" / "rl" / "__init__.py": '''\
"""Reinforcement learning: MDPs, Q-learning, TD-learning, policy iteration."""
from .mdp import MDP, GridMDP, value_iteration, best_policy  # noqa: F401
from .reinforcement_learning import QLearningAgent, PassiveTDAgent  # noqa: F401
''',
    BASE / "src" / "nlp" / "__init__.py": '''\
"""Natural language processing: grammars, parsing, n-grams, text classification."""
from .nlp import Grammar, Chart, CYKParse  # noqa: F401
''',
    BASE / "agents" / "__init__.py": '''\
"""
agents — AI agent scaffolding for advanced-analytics-ai.

TODO: Implement agent patterns here using src.* packages.
Example structure:
  agents/
    planner_agent.py   — goal-directed agent using src.planning
    rl_agent.py        — RL-based agent using src.rl
    nlp_agent.py       — NLP pipeline agent using src.nlp
"""
''',
    BASE / "mcp" / "__init__.py": '''\
"""
mcp — Model Context Protocol (MCP) server scaffolding.

TODO: Define MCP tools that expose src.* functionality.
Example structure:
  mcp/
    server.py          — MCP server entry point
    tools/
      search_tools.py  — expose src.search algorithms as MCP tools
      csp_tools.py     — expose src.csp solvers as MCP tools
      nlp_tools.py     — expose src.nlp as MCP tools

Install the MCP SDK: pip install mcp
"""
''',
    BASE / "tests" / "conftest.py": '''\
# conftest.py — pytest root configuration
# Python path is resolved via pyproject.toml: pythonpath = ["."]
# Run tests with: pytest tests/
# Install package first: pip install -e .
''',
}

for path, content in inits.items():
    path.write_text(content, encoding="utf-8")
    print(f"Written: {path.relative_to(BASE)}")

print("\nAll __init__.py files and conftest.py written.")
