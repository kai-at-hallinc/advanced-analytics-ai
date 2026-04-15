import re
from pathlib import Path

SRC = Path(r"C:\Users\BYCLADM\advanced-analytics-ai\src")

# Mapping: module_name -> (package_relative_to_src, module_filename_stem)
# e.g. "utils" lives in src/shared/utils.py => ("shared", "utils")
MODULE_MAP = {
    "utils":                  ("shared", "utils"),
    "utils4e":                ("shared", "utils4e"),
    "notebook":               ("shared", "notebook"),
    "notebook4e":             ("shared", "notebook4e"),
    "ipyviews":               ("shared", "ipyviews"),
    "search":                 ("search", "search"),
    "search4e":               ("search", "search4e"),
    "csp":                    ("csp",    "csp"),
    "logic":                  ("logic",  "logic"),
    "logic4e":                ("logic",  "logic4e"),
    "knowledge":              ("logic",  "knowledge"),
    "planning":               ("planning","planning"),
    "probability":            ("probability","probability"),
    "probability4e":          ("probability","probability4e"),
    "probabilistic_learning": ("probability","probabilistic_learning"),
    "learning":               ("ml",     "learning"),
    "learning4e":             ("ml",     "learning4e"),
    "deep_learning4e":        ("neural_nets","deep_learning4e"),
    "perception4e":           ("neural_nets","perception4e"),
    "mdp":                    ("rl",     "mdp"),
    "mdp4e":                  ("rl",     "mdp4e"),
    "reinforcement_learning": ("rl",     "reinforcement_learning"),
    "reinforcement_learning4e":("rl",    "reinforcement_learning4e"),
    "nlp":                    ("nlp",    "nlp"),
    "nlp4e":                  ("nlp",    "nlp4e"),
    "text":                   ("nlp",    "text"),
}

def relative_import(from_pkg: str, target_pkg: str, target_mod: str) -> str:
    """Return relative import prefix. Same package = '.' else '..'"""
    if from_pkg == target_pkg:
        return f"from .{target_mod}"
    else:
        return f"from ..{target_pkg}.{target_mod}"

def rewrite_file(py_file: Path):
    # Determine which package this file lives in (the immediate parent dir name)
    pkg = py_file.parent.name  # e.g. "search", "csp", etc.
    
    lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    new_lines = []
    changed = False

    for line in lines:
        new_line = line

        # Pattern 1: `import MODULE` (standalone, not already relative)
        m = re.match(r'^(\s*)import\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$', line)
        if m:
            indent, mod = m.group(1), m.group(2)
            if mod in MODULE_MAP:
                tpkg, tmod = MODULE_MAP[mod]
                prefix = relative_import(pkg, tpkg, tmod)
                new_line = f"{indent}{prefix} import *  # rewritten from: import {mod}\n"
                changed = True

        # Pattern 2: `from MODULE import ...`
        m2 = re.match(r'^(\s*)from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import\s+(.+)$', line)
        if m2:
            indent, mod, names = m2.group(1), m2.group(2), m2.group(3)
            if mod in MODULE_MAP:
                tpkg, tmod = MODULE_MAP[mod]
                prefix = relative_import(pkg, tpkg, tmod)
                new_line = f"{indent}{prefix} import {names}\n"
                changed = True

        # Pattern 3: `import MODULE as alias`
        m3 = re.match(r'^(\s*)import\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+as\s+(\w+)\s*$', line)
        if m3:
            indent, mod, alias = m3.group(1), m3.group(2), m3.group(3)
            if mod in MODULE_MAP:
                tpkg, tmod = MODULE_MAP[mod]
                prefix = relative_import(pkg, tpkg, tmod)
                new_line = f"{indent}{prefix} import {tmod} as {alias}  # rewritten\n"
                changed = True

        new_lines.append(new_line)

    if changed:
        py_file.write_text("".join(new_lines), encoding="utf-8")
        print(f"  Rewrote: {py_file.relative_to(SRC)}")
    else:
        print(f"  No changes: {py_file.relative_to(SRC)}")

# Process all .py files in src/ except __init__.py
total = 0
for py_file in sorted(SRC.rglob("*.py")):
    if py_file.name == "__init__.py":
        continue
    rewrite_file(py_file)
    total += 1

print(f"\nDone. Processed {total} files.")
