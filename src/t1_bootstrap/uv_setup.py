"""Finding uv, and offering to install it from Astral's official installer.

Everything here is opt-in: nothing installs without an explicit yes from the
person at the keyboard. The scaffold still works without uv - it falls back to
`python -m venv` - so declining is a real choice, not a dead end.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

INSTALL_URL = "https://astral.sh/uv/install.sh"
DOCS_URL = "https://docs.astral.sh/uv/getting-started/installation/"

#: What we tell the user we are about to do, and what we actually do - the
#: script is fetched and run as two steps so it can be inspected, but the
#: effect is the one-liner from Astral's docs.
INSTALL_COMMAND = f"curl -LsSf {INSTALL_URL} | sh"

WHY = "uv builds the venv and installs dependencies. Without it: venv only, no install."


def _candidate_dirs() -> list[Path]:
    """Where the official installer puts uv, newest-installer conventions first."""
    home = Path.home()
    raw = [
        os.environ.get("UV_INSTALL_DIR"),
        os.environ.get("XDG_BIN_HOME"),
        f"{os.environ['CARGO_HOME']}/bin" if os.environ.get("CARGO_HOME") else None,
    ]
    dirs = [Path(value).expanduser() for value in raw if value]
    dirs.extend([home / ".local" / "bin", home / ".cargo" / "bin"])
    return dirs


def uv_path() -> str | None:
    """uv on PATH - or where the installer just put it, before a new shell exists."""
    found = shutil.which("uv")
    if found:
        return found
    for directory in _candidate_dirs():
        candidate = directory / "uv"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def missing() -> bool:
    return uv_path() is None


def can_install() -> bool:
    """The installer is a POSIX shell script fetched with curl. Both must exist."""
    return os.name != "nt" and bool(shutil.which("curl")) and bool(shutil.which("sh"))


def is_interactive() -> bool:
    """Never ask a question nobody is there to answer."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def should_offer() -> bool:
    """For the CLI, where a tty is what makes the question answerable."""
    return missing() and can_install() and is_interactive()


def should_offer_ui() -> bool:
    """For the TUI, where the screen itself is the interaction."""
    return missing() and can_install()


def install(on_line: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """Fetch and run the official installer. Returns success and a short detail.

    The script is downloaded to a temp file and handed to `sh` rather than piped
    through a shell, so nothing runs through a shell we build by hand.
    """
    if not can_install():
        return False, "needs curl and sh"

    with tempfile.TemporaryDirectory(prefix="t1-uv-") as tmp:
        script = Path(tmp) / "install.sh"
        try:
            fetch = subprocess.run(
                ["curl", "-LsSf", INSTALL_URL, "-o", str(script)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as error:
            return False, f"could not reach astral.sh ({error})"
        if fetch.returncode != 0:
            detail = (fetch.stderr or "").strip().splitlines()
            return False, detail[-1] if detail else "download failed"
        if not script.is_file() or script.stat().st_size == 0:
            return False, "installer came back empty"

        try:
            run = subprocess.run(
                ["sh", str(script)],
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as error:
            return False, f"installer did not run ({error})"

    if on_line:
        for line in (run.stdout or "").splitlines():
            if line.strip():
                on_line(line.rstrip())

    if run.returncode != 0:
        detail = (run.stderr or run.stdout or "").strip().splitlines()
        return False, detail[-1] if detail else f"exit code {run.returncode}"

    forget_uv()
    path = uv_path()
    if not path:
        return False, "installed, but uv is not on PATH - open a new shell"
    return True, path


def forget_uv() -> None:
    """Drop the caches that were built while uv was missing."""
    from t1_bootstrap.pythons import available_pythons
    from t1_bootstrap.templates import uv_build_requirement

    available_pythons.cache_clear()
    uv_build_requirement.cache_clear()


def offer_lines() -> list[str]:
    """The question, as plain strings - the CLI and the TUI dress it differently."""
    return [
        "uv was not found on your PATH.",
        WHY,
        f"Install it now from Astral's official installer?  {INSTALL_COMMAND}",
    ]
