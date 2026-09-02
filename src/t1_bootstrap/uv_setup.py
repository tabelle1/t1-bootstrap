"""Finding uv, and offering to install it from Astral's official installer.

Everything here is opt-in: nothing installs without an explicit yes from the
person at the keyboard. The scaffold still works without uv - it falls back to
`python -m venv` - so declining is a real choice, not a dead end.

Every platform branch keys off ``WINDOWS`` so the tests can drive both paths on
any machine; the Windows CI leg runs the real thing.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

WINDOWS = os.name == "nt"

INSTALL_URL = "https://astral.sh/uv/install.sh"
INSTALL_URL_WINDOWS = "https://astral.sh/uv/install.ps1"
DOCS_URL = "https://docs.astral.sh/uv/getting-started/installation/"

WHY = "uv builds the venv and installs dependencies. Without it: venv only, no install."


def install_url() -> str:
    """The official installer script for this platform."""
    return INSTALL_URL_WINDOWS if WINDOWS else INSTALL_URL


def install_command() -> str:
    """Astral's documented one-liner for this platform: what we show, and what we do.

    The script is fetched and run as two steps so it can be inspected, but the
    effect is the one-liner from Astral's docs.
    """
    if WINDOWS:
        return f'powershell -ExecutionPolicy ByPass -c "irm {INSTALL_URL_WINDOWS} | iex"'
    return f"curl -LsSf {INSTALL_URL} | sh"


def needs() -> str:
    """What the installer needs on this machine, for the 'cannot install' message."""
    return "PowerShell" if WINDOWS else "curl and sh"


def binary_name() -> str:
    return "uv.exe" if WINDOWS else "uv"


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
        candidate = directory / binary_name()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def missing() -> bool:
    return uv_path() is None


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def can_install() -> bool:
    """POSIX: a shell script fetched with curl. Windows: a PowerShell script."""
    if WINDOWS:
        return _powershell() is not None
    return bool(shutil.which("curl")) and bool(shutil.which("sh"))


def is_interactive() -> bool:
    """Never ask a question nobody is there to answer."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def should_offer() -> bool:
    """For the CLI, where a tty is what makes the question answerable."""
    return missing() and can_install() and is_interactive()


def should_offer_ui() -> bool:
    """For the TUI, where the screen itself is the interaction."""
    return missing() and can_install()


def _fetch_command(script: Path) -> list[str]:
    """Download the installer to ``script`` - an argument list, never a shell string."""
    if WINDOWS:
        shell = _powershell() or "powershell"
        return [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "ByPass",
            "-Command",
            f"Invoke-RestMethod -Uri '{INSTALL_URL_WINDOWS}' -OutFile '{script}'",
        ]
    return ["curl", "-LsSf", INSTALL_URL, "-o", str(script)]


def _run_command(script: Path) -> list[str]:
    """Run the downloaded installer with the interpreter it was written for."""
    if WINDOWS:
        shell = _powershell() or "powershell"
        return [shell, "-NoProfile", "-ExecutionPolicy", "ByPass", "-File", str(script)]
    return ["sh", str(script)]


def install(on_line: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """Fetch and run the official installer. Returns success and a short detail.

    The script is downloaded to a temp file and then run from there, rather than
    piped through a shell, so nothing runs through a shell we build by hand.
    """
    if not can_install():
        return False, f"needs {needs()}"

    with tempfile.TemporaryDirectory(prefix="t1-uv-") as tmp:
        script = Path(tmp) / ("install.ps1" if WINDOWS else "install.sh")
        try:
            fetch = subprocess.run(
                _fetch_command(script),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
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
                _run_command(script),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
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
        f"Install it now from Astral's official installer?  {install_command()}",
    ]
