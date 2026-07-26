"""Language pack consistency: langs/*.json vs EN.json."""

import os
import re

from helpers import detail, fail, flatten, load_json, ok

NAME = "Language Packs"
DESCRIPTION = (
    "Compare every langs/*.json against langs/EN.json. "
    "Fails on missing/extra keys or missing/extra placeholders ({0}, {1}, ...)."
)

LANGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "langs")
BASE = "EN.json"
PLACEHOLDER = re.compile(r"\{(\d+)(?::[^}]*)?\}")


def placeholders(text: str) -> set[int]:
    return {int(m.group(1)) for m in PLACEHOLDER.finditer(text)}


def check(base: dict[str, str], other: dict[str, str]) -> list[str]:
    errors = []
    for key, value in base.items():
        if key not in other:
            errors.append(f"missing key: {key}")
            continue
        expected, actual = placeholders(value), placeholders(other[key])
        if missing := expected - actual:
            errors.append(f"missing placeholder(s) {', '.join(f'{{{i}}}' for i in sorted(missing))} in key: {key}")
        if extra := actual - expected:
            errors.append(f"extra placeholder(s) {', '.join(f'{{{i}}}' for i in sorted(extra))} in key: {key}")
    for key in other:
        if key not in base:
            errors.append(f"extra key: {key}")
    return errors


def run() -> bool:
    base_path = os.path.join(LANGS, BASE)
    if not os.path.isfile(base_path):
        fail(f"Base language file not found: {base_path}")
        return False

    base = flatten(load_json(base_path))
    files = sorted(f for f in os.listdir(LANGS) if f.endswith(".json") and f != BASE)
    if not files:
        fail(f"No language files found to compare against {BASE}")
        return False

    print(f"Checking {len(files)} language file(s) against {BASE} ({len(base)} keys)...")
    passed = True

    for name in files:
        try:
            errors = check(base, flatten(load_json(os.path.join(LANGS, name))))
        except (OSError, ValueError) as exc:
            fail(f"{name}: could not load ({exc})")
            passed = False
            continue

        if errors:
            passed = False
            fail(f"{name} ({len(errors)} issue(s)):")
            for error in errors:
                detail(error)
        else:
            ok(name)

    return passed
