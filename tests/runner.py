"""Discover and run every tests/test_*.py that exposes run() -> bool.

Each test module may define:
  NAME        - short display name
  DESCRIPTION - what the test checks
"""

import importlib.util
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS_DIR)

from helpers import fail, green, red


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover() -> list:
    """Return (file, name, description, run) for each test module."""
    tests = []
    for file in sorted(os.listdir(TESTS_DIR)):
        if not file.startswith("test_") or not file.endswith(".py"):
            continue
        module = _load(file[:-3], os.path.join(TESTS_DIR, file))
        run = getattr(module, "run", None)
        if not callable(run):
            continue
        name = getattr(module, "NAME", file[:-3])
        description = getattr(module, "DESCRIPTION", "").strip()
        tests.append((file, name, description, run))
    return tests


def run_all() -> int:
    tests = discover()
    if not tests:
        fail("No tests found.")
        return 1

    print(f"Running {len(tests)} test(s)...\n")
    failed = 0

    for i, (file, name, description, run) in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {name}")
        if description:
            print(f"  {description}")
        print(f"  ({file})")
        try:
            if not run():
                failed += 1
        except Exception as exc:
            fail(f"{name} raised: {exc}")
            failed += 1
        print()

    print(f"Results: {len(tests) - failed}/{len(tests)} passed")
    if failed:
        print(red(f"{failed} test(s) failed."))
        return 1

    print(green("All tests passed."))
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
