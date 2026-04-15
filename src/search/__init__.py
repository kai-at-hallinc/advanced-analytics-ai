"""Search algorithms: BFS, DFS, UCS, A*, hill-climbing, simulated annealing."""
from .search import (  # noqa: F401
    Problem, Node, SimpleProblemSolvingAgentProgram,
    breadth_first_graph_search, depth_first_graph_search,
    best_first_graph_search, astar_search,
)
