"""Leaving the wizard inside the project it just created, venv and all.

A process cannot change its parent's working directory, so there are two ways to
end up in the new project. If the shell wrapper from ``t1 shell-init`` is
installed it hands us a file to write the path into and does the ``cd`` (and the
activation) itself; otherwise we start a fresh interactive shell in the
directory with the venv already on PATH - replacing this process on POSIX, as a
child on Windows.
"""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

WINDOWS = os.name == "nt"

CD_FILE = "T1_CD_FILE"
"""Set by the shell wrapper: the file to write the directory to change into."""

POSIX_WRAPPER = """\
# t1 bootstrap - leave the shell in the project the wizard just created.
# Add to ~/.zshrc or ~/.bashrc:   eval "$(t1 shell-init)"
t1() {
    local cd_file target t1_status
    cd_file="$(mktemp -t t1cd.XXXXXX)" || { command t1 "$@"; return $?; }
    T1_CD_FILE="$cd_file" command t1 "$@"
    t1_status=$?
    target="$(cat "$cd_file" 2>/dev/null)"
    rm -f "$cd_file"
    if [ -n "$target" ] && [ -d "$target" ]; then
        cd "$target" || return $t1_status
        if [ -f .venv/bin/activate ]; then
            . .venv/bin/activate
        elif [ -f .venv/Scripts/activate ]; then
            . .venv/Scripts/activate    # Git Bash on Windows
        fi
    fi
    return $t1_status
}
"""

FISH_WRAPPER = """\
# t1 bootstrap - leave the shell in the project the wizard just created.
# Add to ~/.config/fish/config.fish:   t1 shell-init fish | source
function t1
    set -l cd_file (mktemp -t t1cd.XXXXXX)
    T1_CD_FILE=$cd_file command t1 $argv
    set -l t1_status $status
    set -l target (cat $cd_file 2>/dev/null)
    rm -f $cd_file
    if test -n "$target"; and test -d "$target"
        cd $target
        test -f .venv/bin/activate.fish; and source .venv/bin/activate.fish
    end
    return $t1_status
end
"""

POWERSHELL_WRAPPER = """\
# t1 bootstrap - leave the shell in the project the wizard just created.
# Add to $PROFILE:   Invoke-Expression (t1 shell-init powershell | Out-String)
function t1 {
    $cdFile = [System.IO.Path]::GetTempFileName()
    $env:T1_CD_FILE = $cdFile
    try {
        # The real executable, not this function.
        & (Get-Command t1 -CommandType Application | Select-Object -First 1) @args
        $t1Status = $LASTEXITCODE
    } finally {
        Remove-Item Env:T1_CD_FILE -ErrorAction SilentlyContinue
    }
    $target = if (Test-Path $cdFile) { (Get-Content $cdFile -Raw).Trim() } else { "" }
    Remove-Item $cdFile -ErrorAction SilentlyContinue
    if ($target -and (Test-Path $target -PathType Container)) {
        Set-Location $target
        if (Test-Path .venv/Scripts/Activate.ps1) { . .venv/Scripts/Activate.ps1 }
    }
    $global:LASTEXITCODE = $t1Status
}
"""

POWERSHELL_FAMILIES = frozenset({"pwsh", "powershell"})


def user_shell() -> str:
    """The shell to hand the terminal to."""
    if WINDOWS:
        return (
            os.environ.get("SHELL")  # Git Bash and MSYS set it
            or shutil.which("pwsh")
            or shutil.which("powershell")
            or os.environ.get("COMSPEC")
            or "cmd.exe"
        )
    return os.environ.get("SHELL") or shutil.which("zsh") or shutil.which("bash") or "/bin/sh"


def shell_family(shell: str | None = None) -> str:
    """`/opt/homebrew/bin/fish` -> `fish`; `C:/Program Files/PowerShell/7/pwsh.exe` -> `pwsh`."""
    return Path(shell or user_shell()).name.lower().removesuffix(".exe")


def wrapper(family: str | None = None) -> str:
    """The shell function that makes the parent shell follow us into the project."""
    family = family or shell_family()
    if family == "fish":
        return FISH_WRAPPER
    if family in POWERSHELL_FAMILIES:
        return POWERSHELL_WRAPPER
    return POSIX_WRAPPER


def quote_path(path: Path | str) -> str:
    """A path as a single shell argument: POSIX quoting, or double quotes on Windows."""
    text = str(path)
    if WINDOWS:
        return f'"{text}"' if any(ch in text for ch in " \t&()^") else text
    return shlex.quote(text)


def venv_bin(root: Path) -> Path | None:
    """The venv's script directory, if the project has one."""
    bin_dir = root / ".venv" / ("Scripts" if WINDOWS else "bin")
    return bin_dir if bin_dir.is_dir() else None


def activated(root: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """``env`` with ``root/.venv`` active - what the activate script exports."""
    env = dict(os.environ if env is None else env)
    bin_dir = venv_bin(root)
    if bin_dir is None:
        return env

    # Take the venv we were started from back off PATH, so the new shell has
    # exactly one active environment rather than two stacked ones.
    outgoing = env.get("VIRTUAL_ENV")
    entries = [
        entry
        for entry in env.get("PATH", "").split(os.pathsep)
        if entry and (not outgoing or Path(entry).parent != Path(outgoing))
    ]
    env["VIRTUAL_ENV"] = str(bin_dir.parent)
    env["VIRTUAL_ENV_PROMPT"] = root.name
    env.pop("PYTHONHOME", None)
    env["PATH"] = os.pathsep.join([str(bin_dir), *entries])
    return env


def hand_back(root: Path) -> bool:
    """Tell the ``shell-init`` wrapper where to cd; False when there isn't one."""
    target = os.environ.get(CD_FILE)
    if not target:
        return False
    try:
        Path(target).write_text(f"{root}\n", encoding="utf-8", newline="\n")
    except OSError:
        return False
    return True


def open_shell(root: Path, shell: str | None = None) -> int:
    """Put an interactive shell inside ``root`` and hand it the terminal.

    On POSIX this replaces the process and never returns: leaving the shell
    drops the user back where they started. On Windows the shell runs as a
    child and its exit code is returned. Raises OSError if it cannot start.
    """
    shell = shell or user_shell()
    env = activated(root)
    env["PWD"] = str(root)  # shells trust $PWD over getcwd() for the prompt
    os.chdir(root)
    sys.stdout.flush()
    sys.stderr.flush()
    if WINDOWS:
        command = [shell]
        if shell_family(shell) in POWERSHELL_FAMILIES:
            command.append("-NoLogo")
        return subprocess.run(command, cwd=root, env=env, check=False).returncode
    os.execve(shell, [shell], env)
    return 0  # unreachable: execve has replaced this process
