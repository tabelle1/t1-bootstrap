"""Discovery of the Python interpreters a new project can be built on."""

import json
import os
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from t1_bootstrap.uv_setup import uv_path

_PRERELEASE = re.compile(r"[a-zA-Z]")


@dataclass(frozen=True, order=True)
class PythonOption:
    """A selectable interpreter, keyed on its ``major.minor`` series."""

    sort_key: tuple[int, int]
    series: str
    """e.g. "3.13" - what lands in .python-version."""
    patch: str
    """Fullest version string we know about, e.g. "3.13.5"."""
    installed: bool

    @property
    def label(self) -> str:
        suffix = "installed" if self.installed else "download"
        return f"Python {self.series}  ·  {suffix}"


def _from_uv() -> list[PythonOption]:
    uv = uv_path()
    if not uv:
        return []
    try:
        raw = subprocess.run(
            [uv, "python", "list", "--output-format", "json"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
        entries = json.loads(raw)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return []

    best: dict[tuple[int, int], PythonOption] = {}
    for entry in entries:
        if entry.get("implementation") != "cpython" or entry.get("variant") != "default":
            continue
        parts = entry.get("version_parts") or {}
        major, minor = parts.get("major"), parts.get("minor")
        version = entry.get("version") or ""
        if major is None or minor is None:
            continue
        installed = bool(entry.get("path"))
        if _PRERELEASE.search(version) and not installed:
            continue  # don't offer alphas as a default choice
        key = (major, minor)
        option = PythonOption((major, minor), f"{major}.{minor}", version, installed)
        current = best.get(key)
        # An installed interpreter always wins over a downloadable one.
        if current is None or (option.installed and not current.installed):
            best[key] = option
    return sorted(best.values(), reverse=True)


def _from_path() -> list[PythonOption]:
    """Fallback for machines without uv: scan PATH for pythonX.Y binaries."""
    found: dict[tuple[int, int], PythonOption] = {}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            names = [entry.name for entry in Path(directory).iterdir()]
        except OSError:
            continue
        for name in names:
            match = re.fullmatch(r"python(\d+)\.(\d+)", name)
            if not match:
                continue
            major, minor = int(match[1]), int(match[2])
            key = (major, minor)
            found.setdefault(
                key, PythonOption(key, f"{major}.{minor}", f"{major}.{minor}", installed=True)
            )
    return sorted(found.values(), reverse=True)


@lru_cache(maxsize=1)
def available_pythons() -> tuple[PythonOption, ...]:
    """Every interpreter series we can offer, newest first."""
    options = _from_uv() or _from_path()
    if not options:  # last resort: whatever is running us
        import sys

        major, minor = sys.version_info[:2]
        options = [PythonOption((major, minor), f"{major}.{minor}", f"{major}.{minor}", True)]
    return tuple(options)


def default_python() -> str:
    """Newest stable interpreter already on the machine, else the newest available."""
    options = available_pythons()
    installed = [o for o in options if o.installed]
    return (installed or list(options))[0].series
