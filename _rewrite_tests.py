import re
from pathlib import Path

TESTS = Path(r"C:\Users\BYCLADM\advanced-analytics-ai\tests")

# Same module map as before — maps old flat module name to src.pkg.module path
MODULE_MAP = {
    "utils":                   "src.shared.utils",
    "utils4e":                 "src.shared.utils4e",
    "notebook":                "src.shared.notebook",
    "notebook4e":              "src.shared.notebook4e",
    "ipyviews":                "src.shared.ipyviews",
    "search":                  "src.search.search",
    "search4e":                "src.search.search4e",
    "csp":                     "src.csp.csp",
    "logic":                   "src.logic.logic",
    "logic4e":                 "src.logic.logic4e",
    "knowledge":               "src.logic.knowledge",
    "planning":                "src.planning.planning",
    "probability":             "src.probability.probability",
    "probability4e":           "src.probability.probability4e",
    "probabilistic_learning":  "src.probability.probabilistic_learning",
    "learning":                "src.ml.learning",
    "learning4e":              "src.ml.learning4e",
    "deep_learning4e":         "src.neural_nets.deep_learning4e",
    "perception4e":            "src.neural_nets.perception4e",
    "mdp":                     "src.rl.mdp",
    "mdp4e":                   "src.rl.mdp4e",
    "reinforcement_learning":  "src.rl.reinforcement_learning",
    "reinforcement_learning4e":"src.rl.reinforcement_learning4e",
    "nlp":                     "src.nlp.nlp",
    "nlp4e":                   "src.nlp.nlp4e",
    "text":                    "src.nlp.text",
    "agents":                  None,  # drop — not migrated
    "games":                   None,  # drop — not in scope
    "games4e":                 None,
}

def rewrite_file(py_file: Path):
    lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    new_lines = []
    changed = False

    for line in lines:
        new_line = line

        # `import MODULE`
        m = re.match(r'^(\s*)import\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$', line)
        if m:
            indent, mod = m.group(1), m.group(2)
            if mod in MODULE_MAP:
                target = MODULE_MAP[mod]
                if target is None:
                    new_line = f"# DROPPED: import {mod}  (not in scope)\n"
                else:
                    new_line = f"{indent}import {target} as {mod}  # rewritten\n"
                changed = True

        # `from MODULE import ...`
        m2 = re.match(r'^(\s*)from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import\s+(.+)$', line)
        if m2:
            indent, mod, names = m2.group(1), m2.group(2), m2.group(3)
            if mod in MODULE_MAP:
                target = MODULE_MAP[mod]
                if target is None:
                    new_line = f"# DROPPED: from {mod} import {names}  (not in scope)\n"
                else:
                    new_line = f"{indent}from {target} import {names}\n"
                changed = True

        # `import MODULE as alias`
        m3 = re.match(r'^(\s*)import\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s+(\w+)\s*$', line)
        if m3:
            indent, mod, alias = m3.group(1), m3.group(2), m3.group(3)
            if mod in MODULE_MAP:
                target = MODULE_MAP[mod]
                if target is None:
                    new_line = f"# DROPPED: import {mod} as {alias}  (not in scope)\n"
                else:
                    new_line = f"{indent}import {target} as {alias}  # rewritten\n"
                changed = True

        new_lines.append(new_line)

    if changed:
        py_file.write_text("".join(new_lines), encoding="utf-8")
        print(f"  Rewrote: {py_file.relative_to(TESTS)}")
    else:
        print(f"  No changes: {py_file.relative_to(TESTS)}")

total = 0
for py_file in sorted(TESTS.rglob("*.py")):
    if py_file.name in ("__init__.py", "conftest.py"):
        continue
    rewrite_file(py_file)
    total += 1

print(f"\nDone. Processed {total} test files.")
