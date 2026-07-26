"""Language key usage: keys referenced in code must exist in EN.json."""

import ast
import os

from helpers import ROOT, detail, fail, flatten, load_json, ok

NAME = "Language Key Usage"
DESCRIPTION = (
    "Scan cogs/ and voicelink/ for send_localized_message, get_lang, _get_lang, "
    "and get_msg calls. Fails if any key is missing from langs/EN.json."
)

SCAN_DIRS = ("cogs", "voicelink")
BASE = os.path.join(ROOT, "langs", "EN.json")

# How to pick lang-key string args from each call
#   int tuple -> those positional indexes
#   "rest"    -> every string arg after the first
#   "all"     -> every string arg
CALLS = {
    "send_localized_message": (1,),
    "get_lang": "rest",
    "_get_lang": "rest",
    "get_msg": "all",
}


def _strings_from(node: ast.AST) -> list[str]:
    """Collect constant strings from a node (handles IfExp / BoolOp)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _strings_from(node.body) + _strings_from(node.orelse)
    if isinstance(node, ast.BoolOp):
        return [s for v in node.values for s in _strings_from(v)]
    return []


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def extract_keys(path: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except SyntaxError:
            return set()

    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        rule = CALLS.get(_call_name(node))
        if rule is None:
            continue

        if rule == "all":
            args = node.args
        elif rule == "rest":
            args = node.args[1:]
        else:
            args = [node.args[i] for i in rule if i < len(node.args)]

        for arg in args:
            for s in _strings_from(arg):
                # Lang keys are dotted paths like "player.errors.noPlayer"
                if "." in s and s.replace(".", "").replace("_", "").isalnum():
                    keys.add(s)
    return keys


def iter_py_files() -> list[tuple[str, str]]:
    files = []
    for folder in SCAN_DIRS:
        root = os.path.join(ROOT, folder)
        for dirpath, _, filenames in os.walk(root):
            for name in filenames:
                if name.endswith(".py"):
                    path = os.path.join(dirpath, name)
                    files.append((os.path.relpath(path, ROOT), path))
    return files


def run() -> bool:
    if not os.path.isfile(BASE):
        fail(f"Base language file not found: {BASE}")
        return False

    known = set(flatten(load_json(BASE)))
    files = iter_py_files()
    missing: dict[str, list[str]] = {}
    total_keys: set[str] = set()

    for rel, path in files:
        used = extract_keys(path)
        total_keys |= used
        bad = sorted(used - known)
        if bad:
            missing[rel] = bad

    print(f"Scanned {len(files)} file(s), found {len(total_keys)} unique lang key(s)...")

    if not missing:
        ok("All language keys used in code exist in EN.json")
        return True

    fail(f"{sum(len(v) for v in missing.values())} invalid language key reference(s):")
    for rel, keys in sorted(missing.items()):
        detail(rel)
        for key in keys:
            detail(f"  {key}")
    return False
