import re
from pathlib import Path

BASE = Path(r"C:\Users\BYCLADM\advanced-analytics-ai")

# ── Fix 1: src/csp/csp.py ──────────────────────────────────────────────────
f = BASE / "src/csp/csp.py"
txt = f.read_text(encoding="utf-8")
txt = re.sub(
    r'from \.\.search\.search import \*\s+# rewritten from: import search\n',
    'from ..search import search  # rewritten: module alias\n',
    txt
)
f.write_text(txt, encoding="utf-8")
print("Fixed: src/csp/csp.py — search module alias")

# ── Fix 2: src/logic/logic.py ─────────────────────────────────────────────
f = BASE / "src/logic/logic.py"
txt = f.read_text(encoding="utf-8")
txt = re.sub(r'# DROPPED: (import agents.*|from agents import.*)\s*\n', '', txt)
txt = re.sub(r'from agents import \S+.*\n', '', txt)
txt = re.sub(r'import agents.*\n', '', txt)
f.write_text(txt, encoding="utf-8")
print("Fixed: src/logic/logic.py — dropped agents import")

# ── Fix 3: src/probability/probability.py ─────────────────────────────────
f = BASE / "src/probability/probability.py"
txt = f.read_text(encoding="utf-8")
txt = re.sub(r'# DROPPED: (import agents.*|from agents import.*)\s*\n', '', txt)
txt = re.sub(r'from agents import \S+.*\n', '', txt)
txt = re.sub(r'import agents.*\n', '', txt)
f.write_text(txt, encoding="utf-8")
print("Fixed: src/probability/probability.py — dropped agents import")

# ── Fix 4: src/planning/planning.py ───────────────────────────────────────
f = BASE / "src/planning/planning.py"
txt = f.read_text(encoding="utf-8")
txt = re.sub(r'from \.\.search\.search import \*\s+# rewritten from: import search\n',
             'from ..search import search  # rewritten: module alias\n', txt)
txt = re.sub(r'from \.\.csp\.csp import \*\s+# rewritten from: import csp\n',
             'from ..csp import csp  # rewritten: module alias\n', txt)
txt = re.sub(r'from \.\.logic\.logic import \*\s+# rewritten from: import logic\n',
             'from ..logic import logic  # rewritten: module alias\n', txt)
txt = re.sub(r'# DROPPED: (import agents.*|from agents import.*)\s*\n', '', txt)
txt = re.sub(r'from agents import \S+.*\n', '', txt)
txt = re.sub(r'import agents.*\n', '', txt)
f.write_text(txt, encoding="utf-8")
print("Fixed: src/planning/planning.py — search/csp/logic module aliases, dropped agents")

# ── Fix 5: src/nlp/__init__.py ────────────────────────────────────────────
f = BASE / "src/nlp/__init__.py"
txt = '"""Natural language processing: grammars, parsing, n-grams, text classification."""\nfrom .nlp import Grammar, Chart  # noqa: F401\n'
f.write_text(txt, encoding="utf-8")
print("Fixed: src/nlp/__init__.py — removed CYKParse (not defined in nlp.py)")

# ── Fix 6: src/nlp/text.py ────────────────────────────────────────────────
f = BASE / "src/nlp/text.py"
txt = f.read_text(encoding="utf-8")
txt = re.sub(r'from \.\.search\.search import \*\s+# rewritten from: import search\n',
             'from ..search import search  # rewritten: module alias\n', txt)
f.write_text(txt, encoding="utf-8")
print("Fixed: src/nlp/text.py — search module alias")

print("\nAll fixes applied.")
