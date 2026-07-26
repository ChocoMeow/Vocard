"""Shared test helpers (stdlib only)."""

import json
import os
import sys

if sys.platform == "win32":
    os.system("")  # enable ANSI on Windows

_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and "NO_COLOR" not in os.environ
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _c(text: str, code: int) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def green(text: str) -> str:
    return _c(text, 92)


def red(text: str) -> str:
    return _c(text, 91)


def ok(msg: str) -> None:
    print(f"{green('[PASS]')} {msg}")


def fail(msg: str) -> None:
    print(f"{red('[FAIL]')} {msg}")


def detail(msg: str) -> None:
    print(red(f"  {msg}"))


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dicts into dotted keys."""
    out = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, path))
        else:
            out[path] = value if isinstance(value, str) else str(value)
    return out


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
