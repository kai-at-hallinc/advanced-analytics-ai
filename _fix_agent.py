from pathlib import Path

f = Path(r"C:\Users\BYCLADM\advanced-analytics-ai\src\logic\logic.py")
txt = f.read_text(encoding="utf-8")

stub = (
    "class Agent:\n"
    '    """Minimal stub for Agent base class (original agents module was removed)."""\n'
    "    def __init__(self, program=None):\n"
    "        self.program = program\n"
    "        self.alive = True\n"
    "\n"
    "    def __call__(self, percept):\n"
    "        if self.program:\n"
    "            return self.program(percept)\n"
    "        raise NotImplementedError\n"
    "\n"
    "\n"
)

if "class Agent:" not in txt:
    txt = txt.replace(
        "class HybridWumpusAgent(Agent):",
        stub + "class HybridWumpusAgent(Agent):"
    )
    f.write_text(txt, encoding="utf-8")
    print("Added Agent stub to logic.py")
else:
    print("Agent class already present - no change")
