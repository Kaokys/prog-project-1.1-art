"""Static evidence of the Python rubric; runtime rules covered by unittest."""
import ast
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    files = [root / name for name in ("main.py", "server.py", "marketplace.py", "storage.py", "validation.py", "auth.py", "seed.py", "console.py", "user_files.py", "social.py", "digital.py", "earnings.py", "api/index.py")]
    trees = []
    try:
        for path in files:
            trees.append(ast.parse(path.read_text(encoding="utf-8")))
    except (OSError, SyntaxError, UnicodeError):
        print("FAIL: cannot read or parse source files")
        return 1
    nodes = [node for tree in trees for node in ast.walk(tree)]
    imports = {node.module.split(".")[0] for node in nodes if isinstance(node, ast.ImportFrom) and node.module}
    imports |= {alias.name.split(".")[0] for node in nodes if isinstance(node, ast.Import) for alias in node.names}
    local = {path.stem for path in files} | {"api"}
    external = imports - sys.stdlib_module_names - local
    functions = [node for node in nodes if isinstance(node, ast.FunctionDef) and node.args.args and any(isinstance(child, ast.Return) for child in ast.walk(node))]
    calls = {node.func.id for node in nodes if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    checks = {
        "Python modules >= 2": len(files) >= 2,
        "Functions with parameters and returns >= 6": len(functions) >= 6,
        "int float str bool conversion/validation": {"int", "float", "str", "bool"}.issubset(calls),
        "if + for + while + try/except": all(any(isinstance(n, kind) for n in nodes) for kind in (ast.If, ast.For, ast.While, ast.Try)),
        "and or not conditions": all(any(isinstance(n, kind) for n in nodes) for kind in (ast.And, ast.Or, ast.Not)),
        "list dict tuple set structures": all(any(isinstance(n, kind) for n in nodes) for kind in (ast.List, ast.Dict, ast.Tuple, ast.Set)),
        "Standard Library only": not external,
    }
    for label, passed in checks.items():
        print(("PASS " if passed else "FAIL ") + label)
    print(f"Evidence: {len(functions)} functions in {len(files)} Python files")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
