"""Leaving the wizard inside the project it just created, venv and all.

A process cannot change its parent's working directory, so there are two ways to
end up in the new project. If the shell wrapper from ``t1 shell-init`` is
installed it hands us a file to write the path into and does the ``cd`` (and the
activation) itself; otherwise we exec a fresh interactive shell in the directory
with the venv already on PATH.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

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
        [ -f .venv/bin/activate ] && . .venv/bin/activate
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


def user_shell() -> str:
    """The shell to hand the terminal to."""
    if os.name == "nt":
        return os.environ.get("COMSPEC") or "cmd.exe"
    return os.environ.get("SHELL") or shutil.which("zsh") or shutil.which("bash") or "/bin/sh"


def shell_family(shell: str | None = None) -> str:
    """`/opt/homebrew/bin/fish` -> `fish`."""
    return Path(shell or user_shell()).name.lower().removesuffix(".exe")


def wrapper(family: str | None = None) -> str:
    """The shell function that makes the parent shell follow us into the project."""
    return FISH_WRAPPER if (family or shell_family()) == "fish" else POSIX_WRAPPER


def venv_bin(root: Path) -> Path | None:
    """The venv's script directory, if the project has one."""
    bin_dir = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
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
        Path(target).write_text(f"{root}\n", encoding="utf-8")
    except OSError:
        return False
    return True


def open_shell(root: Path, shell: str | None = None) -> int:
    """Replace this process with an interactive shell inside ``root``.

    On POSIX this never returns: the shell inherits the terminal, and leaving it
    drops the user back where they started. Raises OSError if it cannot start.
    """
    shell = shell or user_shell()
    env = activated(root)
    env["PWD"] = str(root)  # shells trust $PWD over getcwd() for the prompt
    os.chdir(root)
    sys.stdout.flush()
    sys.stderr.flush()
    if os.name == "nt":
        return subprocess.run([shell], cwd=root, env=env, check=False).returncode
    os.execve(shell, [shell], env)
    return 0  # unreachable: execve has replaced this process
