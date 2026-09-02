"""`t1` - open the wizard, or scaffold straight from the command line."""

import argparse
import shlex
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm
from rich.text import Text

from t1_bootstrap import __version__, handoff, uv_setup
from t1_bootstrap.branding import FLAME, logo_text
from t1_bootstrap.options import (
    DEFAULT_DIRECTORIES,
    DEFAULT_EXTRAS,
    DIRECTORIES,
    DIRECTORIES_BY_KEY,
    EXTRAS,
    EXTRAS_BY_KEY,
)
from t1_bootstrap.pythons import available_pythons, default_python
from t1_bootstrap.scaffold import build, next_steps
from t1_bootstrap.spec import ProjectSpec

console = Console()

MARKS = {"ok": ("✓", "green"), "warn": ("!", "yellow"), "fail": ("✗", "red"), "skip": ("–", "dim")}


def _keys(raw: str | None, catalogue: dict, default: frozenset[str]) -> set[str] | None:
    """Parse a comma-separated selection; returns None if a key is unknown."""
    if raw is None:
        return set(default)
    if raw.strip().lower() in {"none", ""}:
        return set()
    if raw.strip().lower() == "all":
        return set(catalogue)
    chosen = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = chosen - set(catalogue)
    if unknown:
        console.print(f"[red]Unknown: {', '.join(sorted(unknown))}[/]")
        console.print(f"[dim]Available: {', '.join(catalogue)}[/]")
        return None
    return chosen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="t1",
        description="Start a Python project: venv, src layout, and the directories you always create anyway.",
    )
    parser.add_argument("--version", action="version", version=f"t1 bootstrap {__version__}")
    sub = parser.add_subparsers(dest="command")

    new = sub.add_parser("new", help="scaffold without opening the TUI")
    new.add_argument("name", help="project name; spaces become dashes")
    new.add_argument(
        "-p", "--python", default=None, help=f"version series (default {default_python()})"
    )
    new.add_argument("-C", "--into", default=".", help="parent directory (default: here)")
    new.add_argument("--flat", action="store_true", help="package at the root instead of src/")
    new.add_argument("--dirs", default=None, help="comma list, or 'none' / 'all'")
    new.add_argument("--extras", default=None, help="comma list, or 'none' / 'all'")
    new.add_argument("--no-venv", action="store_true", help="skip uv venv / uv sync")
    new.add_argument("--no-git", action="store_true", help="skip git init")
    new.add_argument("-n", "--dry-run", action="store_true", help="show the plan, write nothing")

    sub.add_parser("install-uv", help="install uv from Astral's official installer")
    sub.add_parser("options", help="list the available directories and extras")
    sub.add_parser("pythons", help="list the interpreters you can build on")

    shell = sub.add_parser(
        "shell-init", help="print the shell function that cd's you into a new project"
    )
    shell.add_argument(
        "shell",
        nargs="?",
        choices=["zsh", "bash", "sh", "fish"],
        help=f"default: your $SHELL ({handoff.shell_family()})",
    )
    return parser


def cmd_new(args: argparse.Namespace) -> int:
    directories = _keys(args.dirs, DIRECTORIES_BY_KEY, DEFAULT_DIRECTORIES)
    extras = _keys(args.extras, EXTRAS_BY_KEY, DEFAULT_EXTRAS)
    if directories is None or extras is None:
        return 2
    if args.no_venv:
        extras.discard("venv")
    if args.no_git:
        extras.discard("git")

    spec = ProjectSpec(
        name=args.name,
        parent=Path(args.into).expanduser().resolve(),
        python=args.python or default_python(),
        layout="flat" if args.flat else "src",
        directories=directories,
        extras=extras,
    )
    spec.resolve_implications()

    problems = spec.problems()
    if problems:
        for problem in problems:
            console.print(f"[red]⚠[/] {problem}")
        return 1

    if args.dry_run:
        console.print(Text(f"\n{spec.slug}/", style=f"bold {FLAME}"))
        for prefix, name, kind in spec.tree():
            suffix = "/" if kind in {"dir", "venv"} else ""
            style = FLAME if kind == "dir" else "dim" if kind == "venv" else "default"
            console.print(Text(prefix, style="grey30") + Text(f"{name}{suffix}", style=style))
        console.print()
        for step in spec.plan():
            console.print(f"[{FLAME}]·[/] [dim]{step}[/]")
        return 0

    if spec.has("venv"):
        offer_uv()

    console.print(Text(f"\nBuilding {spec.slug}", style=f"bold {FLAME}"))
    failed = False
    for event in build(spec):
        if event.status == "start":
            continue
        if event.status == "done":
            console.print()
            console.print(Text(f"✓ {event.label}", style="bold green"))
            for command in next_steps(spec):
                console.print(Text("  $ ", style=FLAME) + Text(command))
            continue
        mark, colour = MARKS.get(event.status, ("·", "dim"))
        line = Text(f"  {mark} ", style=colour) + Text(event.label)
        if event.detail:
            line += Text(f"   {event.detail}", style="dim")
        console.print(line)
        failed = failed or event.status == "fail"
    return 1 if failed else 0


def offer_uv() -> None:
    """If uv is missing, ask once - and only when someone is there to answer."""
    if not uv_setup.should_offer():
        return
    console.print()
    console.print(Text("uv was not found on your PATH.", style="bold"))
    console.print(f"[dim]{uv_setup.WHY}[/]")
    console.print(f"[dim]Official installer:[/] {uv_setup.INSTALL_COMMAND}")
    try:
        yes = Confirm.ask(f"[{FLAME}]Install uv now?[/]", default=False)
    except (EOFError, KeyboardInterrupt):
        console.print()
        return
    if not yes:
        console.print(f"[dim]Carrying on without uv - venv only. {uv_setup.DOCS_URL}[/]")
        return
    console.print("[dim]  ⋯ installing uv[/]")
    ok, detail = uv_setup.install()
    if ok:
        console.print(f"[green]✓[/] uv installed   [dim]{detail}[/]")
    else:
        console.print(f"[red]✗[/] uv install failed   [dim]{detail}[/]")
        console.print(f"[dim]  Install it yourself: {uv_setup.INSTALL_COMMAND}[/]")


def cmd_install_uv() -> int:
    """Explicit install: running the command is the consent, so no second question."""
    existing = uv_setup.uv_path()
    if existing:
        console.print(f"[green]✓[/] uv is already installed   [dim]{existing}[/]")
        return 0
    if not uv_setup.can_install():
        console.print(f"[red]✗[/] Needs curl and sh. See {uv_setup.DOCS_URL}")
        return 1
    console.print(f"[dim]Astral's official installer:[/] {uv_setup.INSTALL_COMMAND}\n")
    ok, detail = uv_setup.install(on_line=lambda line: console.print(f"[dim]  {line}[/]"))
    if ok:
        console.print(f"\n[green]✓[/] uv installed   [dim]{detail}[/]")
        return 0
    console.print(f"\n[red]✗[/] uv install failed   [dim]{detail}[/]")
    return 1


def cmd_options() -> int:
    console.print(Text("\nDIRECTORIES", style="bold"))
    for choice in DIRECTORIES:
        star = f"[{FLAME}]*[/]" if choice.default else " "
        console.print(f" {star} [bold]{choice.key:<14}[/]{choice.label:<10} [dim]{choice.hint}[/]")
    console.print(Text("\nEXTRAS", style="bold"))
    for extra in EXTRAS:
        star = f"[{FLAME}]*[/]" if extra.default else " "
        console.print(f" {star} [bold]{extra.key:<14}[/]{extra.label:<10} [dim]{extra.hint}[/]")
    console.print(
        "\n[dim]* on by default. Use --dirs / --extras with a comma list, 'all' or 'none'.[/]"
    )
    return 0


def cmd_pythons() -> int:
    console.print()
    for option in available_pythons():
        tag = f"[{FLAME}]installed[/]" if option.installed else "[dim]download[/]"
        marker = f"[{FLAME}]›[/]" if option.series == default_python() else " "
        console.print(f" {marker} [bold]{option.series:<6}[/] [dim]{option.patch:<10}[/] {tag}")
    return 0


def cmd_shell_init(args: argparse.Namespace) -> int:
    # Plain print, not the console: this is meant to be eval'd, not read.
    print(handoff.wrapper(args.shell), end="")
    return 0


def farewell(root: Path, enter: bool) -> int:
    """The last thing the terminal shows: what was built, and where you now are."""
    console.print()
    console.print(
        Text("✓ ", style="bold green") + Text(f"{root.name} is ready. Have fun.", style="bold")
    )
    console.print(Text(f"  {root}", style=FLAME))
    if not enter:
        return 0
    if handoff.hand_back(root):
        return 0  # the shell-init wrapper does the cd - and the activation

    shell = handoff.user_shell()
    note = [f"{Path(shell).name} here"]
    if handoff.venv_bin(root):
        note.append(".venv active")
    note.append("exit returns you to this shell")
    console.print(Text("  " + " · ".join(note), style="dim"))
    try:
        return handoff.open_shell(root, shell)
    except OSError as error:
        console.print(f"[red]✗[/] Could not open a shell: {error}")
        console.print(f"[dim]  cd {shlex.quote(str(root))}[/]")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "new":
        return cmd_new(args)
    if args.command == "install-uv":
        return cmd_install_uv()
    if args.command == "options":
        return cmd_options()
    if args.command == "pythons":
        return cmd_pythons()
    if args.command == "shell-init":
        return cmd_shell_init(args)

    if not console.is_terminal:
        console.print(logo_text())
        console.print("\n[dim]Not a terminal - use[/] t1 new NAME [dim]or run t1 from a TTY.[/]")
        return 1

    from t1_bootstrap.app import run

    created = run()
    if created is None:
        return 0
    return farewell(created.root, created.enter)
