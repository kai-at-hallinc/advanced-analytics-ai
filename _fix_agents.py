import re
from pathlib import Path

BASE = Path(r"C:\Users\BYCLADM\advanced-analytics-ai")

# ── 1. src/shared/agents.py — no internal imports, nothing to rewrite
print("src/shared/agents.py: no import changes needed (self-contained)")

# ── 2. src/logic/logic.py — replace the stub Agent class + fix the import
f = BASE / "src/logic/logic.py"
txt = f.read_text(encoding="utf-8")

# Remove the hand-written Agent stub that was injected earlier
stub = '''\nclass Agent:
    """Minimal stub for Agent base class (original agents module was removed)."""
    def __init__(self, program=None):
        self.program = program
        self.alive = True

    def __call__(self, percept):
        if self.program:
            return self.program(percept)
        raise NotImplementedError\n'''
txt = txt.replace(stub, '\n')

# The original `from agents import Agent, Glitter, ...` was DROPPED — restore it as a proper relative import
# Check if still dropped
if '# DROPPED: from agents import Agent' in txt:
    txt = txt.replace(
        '# DROPPED: from agents import Agent, Glitter, Bump, Stench, Breeze, Scream  (not in scope)\n',
        'from ..shared.agents import Agent, Glitter, Bump, Stench, Breeze, Scream  # rewritten\n'
    )
elif 'from ..shared.agents import Agent' not in txt:
    # Add it near the top after the first import block
    txt = 'from ..shared.agents import Agent, Glitter, Bump, Stench, Breeze, Scream  # rewritten\n' + txt

f.write_text(txt, encoding="utf-8")
print("Fixed: src/logic/logic.py — proper agents import from shared")

# ── 3. src/logic/logic4e.py — same pattern
f = BASE / "src/logic/logic4e.py"
if f.exists():
    txt = f.read_text(encoding="utf-8")
    if '# DROPPED: from agents import Agent' in txt:
        txt = txt.replace(
            '# DROPPED: from agents import Agent, Glitter, Bump, Stench, Breeze, Scream  (not in scope)\n',
            'from ..shared.agents import Agent, Glitter, Bump, Stench, Breeze, Scream  # rewritten\n'
        )
    f.write_text(txt, encoding="utf-8")
    print("Fixed: src/logic/logic4e.py — proper agents import from shared")

# ── 4. src/probability/probability.py
f = BASE / "src/probability/probability.py"
txt = f.read_text(encoding="utf-8")
if '# DROPPED: from agents import Agent' in txt or '# DROPPED: import agents' in txt:
    txt = re.sub(
        r'# DROPPED: from agents import Agent.*\n',
        'from ..shared.agents import Agent  # rewritten\n',
        txt
    )
    txt = re.sub(
        r'# DROPPED: import agents.*\n',
        'from ..shared import agents  # rewritten\n',
        txt
    )
elif 'from ..shared.agents import Agent' not in txt:
    txt = 'from ..shared.agents import Agent  # rewritten\n' + txt
f.write_text(txt, encoding="utf-8")
print("Fixed: src/probability/probability.py — proper agents import from shared")

# ── 5. src/planning/making_simple_decision4e.py
f = BASE / "src/planning/making_simple_decision4e.py"
if f.exists():
    txt = f.read_text(encoding="utf-8")
    txt = re.sub(
        r'# DROPPED: from agents import Agent.*\n',
        'from ..shared.agents import Agent  # rewritten\n',
        txt
    )
    txt = re.sub(
        r'# DROPPED: import agents.*\n',
        'from ..shared import agents  # rewritten\n',
        txt
    )
    f.write_text(txt, encoding="utf-8")
    print("Fixed: src/planning/making_simple_decision4e.py — proper agents import")

# ── 6. src/shared/ipyviews.py — uses `from agents import PolygonObstacle`
f = BASE / "src/shared/ipyviews.py"
if f.exists():
    txt = f.read_text(encoding="utf-8")
    txt = txt.replace(
        'from agents import PolygonObstacle',
        'from .agents import PolygonObstacle  # rewritten'
    )
    f.write_text(txt, encoding="utf-8")
    print("Fixed: src/shared/ipyviews.py — agents import to .agents")

print("\nAll agent import fixes applied.")
