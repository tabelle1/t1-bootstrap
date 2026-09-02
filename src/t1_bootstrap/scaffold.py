"""Turning a ProjectSpec into files on disk."""

import shlex
import shutil
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from t1_bootstrap import templates
from t1_bootstrap.options import DIRECTORIES
from t1_bootstrap.spec import ProjectSpec
from t1_bootstrap.uv_setup import uv_path

Status = Literal["start", "ok", "skip", "warn", "fail", "done"]


@dataclass
class Event:
    """A single beat of progress, consumed by both the TUI and the CLI."""

    status: Status
    label: str
    detail: str = ""


def _run(command: list[str], cwd: Path, timeout: int = 300) -> tuple[bool, str]:
    """Run a command, returning success and the most useful line of output."""
    try:
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except FileNotFoundError:
        return False, f"{command[0]} not found on PATH"
    except subprocess.TimeoutExpired:
        return False, f"{command[0]} timed out"
    if result.returncode == 0:
        return True, ""
    output = (result.stderr or result.stdout or "").strip().splitlines()
    return False, output[-1] if output else f"exit code {result.returncode}"


def _interpreter(series: str) -> str | None:
    return shutil.which(f"python{series}") or shutil.which("python3")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(spec: ProjectSpec) -> Iterator[Event]:
    """Create the project, yielding an Event for every step.

    Never raises for expected failures - a failing step yields ``fail`` or ``warn``
    and the run carries on with whatever is still possible.
    """
    root = spec.root
    failures = 0

    yield Event("start", f"Create {spec.slug}/")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        yield Event("fail", f"Create {spec.slug}/", str(error))
        yield Event("done", "Nothing was created", "could not make the project directory")
        return
    yield Event("ok", f"Create {spec.slug}/", str(root))

    # -- directories ------------------------------------------------------
    directories = spec.planned_dirs()
    yield Event("start", "Lay out directories")
    for relative in directories:
        (root / relative).mkdir(parents=True, exist_ok=True)
    for choice in DIRECTORIES:
        if choice.key in spec.directories and choice.keep:
            for relative in choice.paths:
                (root / relative / ".gitkeep").touch()
    yield Event("ok", "Lay out directories", f"{len(directories)} directories")

    # -- files ------------------------------------------------------------
    package = root / spec.package_dir
    yield Event("start", "Write project files")
    written = 0

    _write(root / "pyproject.toml", templates.pyproject(spec))
    _write(root / ".python-version", f"{spec.python}\n")
    _write(package / "__init__.py", templates.package_init(spec))
    (package / "py.typed").touch()
    written += 4

    if spec.has("readme"):
        _write(root / "README.md", templates.readme(spec))
        written += 1
    if spec.has("git"):
        _write(root / ".gitignore", templates.gitignore(spec))
        written += 1
    if spec.has("env"):
        _write(root / ".env.example", templates.env_example(spec))
        _write(root / ".env", templates.env_example(spec))
        written += 2
    if spec.has("editorconfig"):
        _write(root / ".editorconfig", templates.EDITORCONFIG)
        written += 1
    if spec.has("cli"):
        _write(package / "cli.py", templates.cli_module(spec))
        _write(package / "__main__.py", templates.dunder_main(spec))
        written += 2
    if spec.has("logging"):
        _write(package / "logging_setup.py", templates.logging_module(spec))
        written += 1
    if "tests" in spec.directories:
        _write(root / "tests" / "test_smoke.py", templates.smoke_test(spec))
        written += 1

    yield Event("ok", "Write project files", f"{written} files")

    # -- environment ------------------------------------------------------
    if spec.has("venv"):
        uv = uv_path()
        if uv:
            # uv sync creates .venv on the interpreter in .python-version, so a
            # separate `uv venv` call is redundant - one subprocess, not two.
            yield Event("start", "uv sync")
            ok, detail = _run([uv, "sync"], cwd=root, timeout=600)
            if ok:
                yield Event("ok", "uv sync", f".venv on {spec.python} + dependencies")
            else:
                failures += 1
                yield Event("fail", "uv sync", detail)
        else:
            yield Event("start", "Create .venv")
            interpreter = _interpreter(spec.python)
            if not interpreter:
                failures += 1
                yield Event("fail", "Create .venv", f"no python{spec.python} on PATH")
            else:
                ok, detail = _run([interpreter, "-m", "venv", ".venv"], cwd=root)
                if ok:
                    yield Event("ok", "Create .venv", "uv not found - venv only, no install")
                else:
                    failures += 1
                    yield Event("fail", "Create .venv", detail)

    # -- git --------------------------------------------------------------
    if spec.has("git"):
        yield Event("start", "Initialise git")
        ok, detail = _run(["git", "init", "--quiet", "--initial-branch=main"], cwd=root)
        if not ok:
            failures += 1
            yield Event("warn", "Initialise git", detail)
        else:
            staged, detail = _run(["git", "add", "-A"], cwd=root)
            if staged:
                # --no-gpg-sign / --no-verify: a global signing or hook setting must
                # never make a scaffold hang waiting on a passphrase prompt.
                commit = ["git", "commit", "--quiet", "--no-verify", "--no-gpg-sign"]
                committed, _ = _run([*commit, "-m", "Initial commit"], cwd=root, timeout=30)
                if committed:
                    yield Event("ok", "Initialise git", "initial commit created")
                else:
                    yield Event("ok", "Initialise git", "files staged (commit skipped)")
            else:
                yield Event("ok", "Initialise git", detail or "repository created")

    if failures:
        yield Event("done", f"{spec.slug} created with {failures} warning(s)", str(root))
    else:
        yield Event("done", f"{spec.slug} is ready", str(root))


def next_steps(spec: ProjectSpec) -> list[str]:
    """Commands worth running once the project exists."""
    steps = [f"cd {shlex.quote(str(spec.root))}"]
    if not spec.has("venv"):
        steps.append("uv sync")
    if spec.has("cli"):
        steps.append(f"uv run {spec.slug}")
    if "tests" in spec.directories:
        steps.append("uv run pytest")
    return steps


def step_count(spec: ProjectSpec) -> int:
    """How many steps ``build`` will report, for the progress bar."""
    total = 3  # root, directories, files
    if spec.has("git"):
        total += 1
    if spec.has("venv"):
        total += 1
    return total
