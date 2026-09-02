#!/usr/bin/env python3
"""Render docs/wizard.svg - the README screenshot - from the real app, headless.

    uv run python scripts/screenshot.py

Deterministic on purpose: a fixed interpreter list and a stand-in home directory,
so the picture never depends on, or leaks, the machine it was taken on.
"""

import asyncio
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Input

from t1_bootstrap import pythons
from t1_bootstrap.app import BootstrapApp
from t1_bootstrap.pythons import PythonOption

OUT = Path(__file__).resolve().parents[1] / "docs" / "wizard.svg"
SIZE = (116, 48)
PYTHONS = (
    PythonOption((3, 14), "3.14", "3.14.2", installed=True),
    PythonOption((3, 13), "3.13", "3.13.7", installed=True),
    PythonOption((3, 12), "3.12", "3.12.11", installed=False),
)


@lru_cache(maxsize=1)
def known_pythons() -> tuple[PythonOption, ...]:
    return PYTHONS


async def render() -> str:
    with patch.object(pythons, "available_pythons", known_pythons):
        app = BootstrapApp(welcome=False)
        async with app.run_test(size=SIZE) as pilot:
            pilot.app.query_one("#location", Input).value = "~/projects"
            await pilot.press(*"sales pipeline")
            await pilot.pause()
            return pilot.app.export_screenshot(title="t1 bootstrap")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        # Resolved, so that `~/projects` and Path.home() agree and collapse to `~`.
        home = Path(tmp).resolve() / "home" / "dev"
        (home / "projects").mkdir(parents=True)
        os.environ["HOME"] = str(home)  # Path.home() and expanduser() follow this ...
        os.environ["USERPROFILE"] = str(home)  # ... and this, on Windows
        svg = asyncio.run(render())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(svg, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({len(svg) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
