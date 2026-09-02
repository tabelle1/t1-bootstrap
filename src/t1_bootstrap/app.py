"""The t1 bootstrap TUI."""

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen, Screen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Rule,
    Select,
    Static,
)

from t1_bootstrap import __version__, handoff, uv_setup
from t1_bootstrap.branding import (
    AUTHOR,
    FLAME,
    ICON,
    MUTED,
    PITCH,
    SITE,
    TAGLINE,
    TAGLINE_SHORT,
    logo_text,
    mark_text,
    wordmark,
)
from t1_bootstrap.options import DEFAULT_DIRECTORIES, DEFAULT_EXTRAS, DIRECTORIES, EXTRAS
from t1_bootstrap.pythons import available_pythons, default_python
from t1_bootstrap.scaffold import Event, build, next_steps, step_count
from t1_bootstrap.spec import ProjectSpec

TABELLE1 = Theme(
    name="tabelle1",
    primary="#f18d4f",
    secondary="#f0b27a",
    accent="#f18d4f",
    foreground="#e6e9ef",
    background="#0f1216",
    surface="#161a20",
    panel="#242a33",
    success="#7fd18b",
    warning="#f0c674",
    error="#e06c75",
    dark=True,
    variables={
        "block-cursor-background": "#f18d4f",
        "block-cursor-foreground": "#0f1216",
        "block-cursor-text-style": "none",
        "input-selection-background": "#f18d4f 35%",
        "text-muted": "#8b93a1",
        "scrollbar": "#242a33",
        "scrollbar-hover": "#f18d4f",
        "scrollbar-active": "#f18d4f",
        "footer-key-foreground": "#f18d4f",
    },
)


@dataclass(frozen=True)
class Outcome:
    """What the wizard hands back: the project, and whether to step into it."""

    root: Path
    enter: bool = False


STATUS_MARKS = {
    "ok": ("✓", "success"),
    "skip": ("–", "$text-muted"),
    "warn": ("!", "warning"),
    "fail": ("✗", "error"),
}


def short_path(path: str) -> str:
    """Collapse $HOME so paths stay on one line."""
    home = str(Path.home())
    return f"~{path[len(home) :]}" if path.startswith(home) else path


def hint_bar(pairs: list[tuple[str, str]]) -> Text:
    """`key label  ·  key label` in the brand accent."""
    text = Text(no_wrap=True, overflow="ellipsis")
    for index, (key, label) in enumerate(pairs):
        if index:
            text.append("   ")
        text.append(key, style=f"bold {FLAME}")
        text.append(f" {label}", style=MUTED)
    return text


def head(icon: str, title: str, hint: str = "") -> Text:
    """`✎  PROJECT NAME   spaces become dashes`."""
    text = Text(no_wrap=True, overflow="ellipsis")
    text.append(f"{ICON[icon]}  ", style=f"bold {FLAME}")
    text.append(title.upper(), style="bold #e6e9ef")
    if hint:
        text.append(f"   {hint}", style=MUTED)
    return text


def one_line(body: str, style: str) -> Text:
    """A single line that ellipsises rather than wraps. CSS does the aligning."""
    return Text(body, style=style, no_wrap=True, overflow="ellipsis")


def choice_label(label: str, hint: str, width: int = 14) -> Text:
    text = Text(no_wrap=True, overflow="ellipsis")
    text.append(f"{label:<{width}}", style="bold")
    text.append(hint, style=MUTED)
    return text


class Toggle(Checkbox):
    """A checkbox that shows its state through its glyph, not only its colour."""

    BUTTON_LEFT = ""
    BUTTON_RIGHT = ""
    ON = "■"
    OFF = "□"

    @property
    def _button(self) -> Content:
        style = self.get_visual_style("toggle--button")
        return Content.assemble((self.ON if self.value else self.OFF, style))


class Radio(RadioButton):
    """RadioButton, same treatment."""

    BUTTON_LEFT = ""
    BUTTON_RIGHT = ""
    ON = "●"
    OFF = "○"

    @property
    def _button(self) -> Content:
        style = self.get_visual_style("toggle--button")
        return Content.assemble((self.ON if self.value else self.OFF, style))


# Widgets that would otherwise eat an arrow key hand it back to the screen, so
# up/down always means "next field" and never "scroll" or "open a menu".

MOVE_UP = Binding("up", "screen.move_focus(0, -1)", "Previous field", show=False)
MOVE_DOWN = Binding("down", "screen.move_focus(0, 1)", "Next field", show=False)
MOVE_LEFT = Binding("left", "screen.move_focus(-1, 0)", "Left", show=False)
MOVE_RIGHT = Binding("right", "screen.move_focus(1, 0)", "Right", show=False)


class Form(VerticalScroll, can_focus=False):
    """The scrolling form body. It follows the focus instead of the arrow keys."""

    BINDINGS: ClassVar[list[Binding]] = [MOVE_UP, MOVE_DOWN, MOVE_LEFT, MOVE_RIGHT]


class Picker(Select):
    """Select, but up/down leave the field; enter and space open the menu."""

    BINDINGS: ClassVar[list[Binding]] = [MOVE_UP, MOVE_DOWN]


class Choice(RadioSet):
    """RadioSet laid out in a row: left/right pick, up/down leave the field."""

    BINDINGS: ClassVar[list[Binding]] = [MOVE_UP, MOVE_DOWN]


class Brandbar(Horizontal):
    """The short t1 mark, dropping to a one-line lockup on a cramped terminal."""

    def compose(self) -> ComposeResult:
        yield Static(mark_text(), id="logo")
        tagline = Text(no_wrap=True)
        tagline.append("bootstrap", style="bold #e6e9ef")
        tagline.append(f"  v{__version__}", style=MUTED)
        yield Static(tagline, id="tagline")

    def on_resize(self) -> None:
        self.query_one("#logo", Static).update(mark_text(tall=self.app.size.height >= 34))


class ArrowScreen(Screen):
    """A screen where the arrow keys walk the controls the way they look."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("up", "move_focus(0, -1)", "Previous field", show=False),
        Binding("down", "move_focus(0, 1)", "Next field", show=False),
        Binding("left", "move_focus(-1, 0)", "Left", show=False),
        Binding("right", "move_focus(1, 0)", "Right", show=False),
    ]

    def action_move_focus(self, dx: int, dy: int) -> None:
        """Move focus one step in the given direction, by geometry."""
        if any(select.expanded for select in self.query(Select)):
            return  # an open menu owns its own arrow keys
        chain = self.focus_chain
        if not chain:
            return
        current = self.focused
        if current is None or current not in chain:
            self.set_focus(chain[0])
            return
        target = self.nearest(current, chain, dx, dy)
        if target is not None:
            self.set_focus(target)
        elif dx + dy > 0:
            self.focus_next()
        else:
            self.focus_previous()

    @staticmethod
    def pane(widget: Widget) -> Widget | None:
        """The scroller a widget lives in; positions only compare within one."""
        return next(
            (node for node in widget.ancestors if isinstance(node, ScrollableContainer)), None
        )

    def nearest(self, current: Widget, chain: list[Widget], dx: int, dy: int) -> Widget | None:
        """The closest control in that direction: same row or column wins first."""
        here = current.region
        pane = self.pane(current)
        best: tuple[int, int, int] | None = None
        winner: Widget | None = None
        for widget in chain:
            if widget is current or self.pane(widget) is not pane:
                continue
            there = widget.region
            step = (there.x - here.x) * dx + (there.y - here.y) * dy
            if step <= 0:
                continue
            if dy:
                aligned = there.x < here.right and here.x < there.right
                drift = abs(there.x - here.x)
            else:
                aligned = there.y < here.bottom and here.y < there.bottom
                drift = abs(there.y - here.y)
            score = (0 if aligned else 1, step, drift)
            if best is None or score < best:
                best, winner = score, widget
        return winner


class WelcomeScreen(ArrowScreen):
    """One door in, and who built it."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "start", "Create new project"),
        Binding("n", "start", "Create new project", show=False),
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
        Binding("ctrl+c", "app.quit", "Quit", priority=True, show=False),
        Binding("escape", "app.quit", "Quit", show=False),
        Binding("q", "app.quit", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome"):
            yield Static(logo_text(), id="welcome-logo")
            name = Text(no_wrap=True, overflow="ellipsis")
            name.append("bootstrap", style="bold #e6e9ef")
            name.append(f"  v{__version__}", style=MUTED)
            yield Static(name, id="welcome-name")
            yield Static(one_line(TAGLINE, MUTED), id="welcome-tagline")
            yield Static(one_line(PITCH, "#5c6472"), id="welcome-pitch")
            yield Button(f"{ICON['create']}  Create new project", id="start")
            yield Static(hint_bar([("⏎", "start"), ("esc", "quit")]), id="welcome-keys")
        credit = Text(no_wrap=True, overflow="ellipsis")
        credit.append(f"by {AUTHOR}", style=MUTED)
        credit.append("   ·   ", style="#3a424e")
        credit.append(SITE, style=MUTED)
        yield Static(credit, id="welcome-credit")

    def on_mount(self) -> None:
        self.query_one("#start", Button).focus()

    def on_resize(self) -> None:
        width = self.size.width
        self.query_one("#welcome-logo", Static).update(wordmark(width=width))
        # A cropped sales pitch is worse than none; the tagline gets a short form.
        self.query_one("#welcome-pitch").display = width >= 68
        self.query_one("#welcome-tagline", Static).update(
            one_line(TAGLINE if width >= 66 else TAGLINE_SHORT, MUTED)
        )

    @on(Button.Pressed, "#start")
    def start_pressed(self) -> None:
        self.action_start()

    def action_start(self) -> None:
        self.app.push_screen(WizardScreen())


class WizardScreen(ArrowScreen):
    """One screen, every decision visible, live preview on the right."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+n", "create", "Create", priority=True),
        Binding("ctrl+r", "reset", "Reset", show=False),
        # Several ways out: ctrl+q is XOFF on some terminals and never reaches us.
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
        Binding("ctrl+c", "app.quit", "Quit", priority=True, show=False),
        Binding("escape", "app.quit", "Quit", show=False),
        Binding("q", "app.quit", "Quit", show=False),
    ]
    HINTS: ClassVar[list[tuple[str, str]]] = [
        ("↑↓", "field"),
        ("←→", "across"),
        ("space", "toggle"),
        ("^n", "create"),
        ("^p", "palette"),
        ("esc", "quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.spec = ProjectSpec(
            name="",
            parent=Path.cwd(),
            python=default_python(),
            layout="src",
            directories=set(DEFAULT_DIRECTORIES),
            extras=set(DEFAULT_EXTRAS),
        )

    def compose(self) -> ComposeResult:
        yield Brandbar(id="brandbar")
        yield Rule(line_style="solid", id="brandrule")

        with Horizontal(id="body"):
            with Vertical(id="left"):
                with Form(id="form"):
                    with Vertical(classes="field"):
                        yield Static(
                            head("name", "Project name", "spaces become dashes"),
                            classes="field-head",
                        )
                        yield Input(placeholder="my-new-project", id="name")
                        yield Static("", id="problems")

                    with Vertical(classes="field"):
                        yield Static(
                            head("location", "Location", "where the folder is created"),
                            classes="field-head",
                        )
                        yield Input(value=str(Path.cwd()), id="location")
                        yield Static("", id="resolved")

                    with Vertical(classes="field"):
                        yield Static(
                            head("python", "Python", "pins .python-version and the venv"),
                            classes="field-head",
                        )
                        yield Picker(
                            [(option.label, option.series) for option in available_pythons()],
                            value=self.spec.python,
                            allow_blank=False,
                            id="python",
                        )

                    with Vertical(classes="field"):
                        yield Static(head("layout", "Layout"), classes="field-head")
                        with Choice(id="layout"):
                            yield Radio("src/ layout", value=True)
                            yield Radio("flat layout")

                    with Vertical(classes="field"):
                        yield Static("", classes="field-head-tight", id="head-dirs")
                        with Vertical(classes="choices"):
                            for choice in DIRECTORIES:
                                yield Toggle(
                                    choice_label(choice.label, choice.hint, 12),
                                    value=choice.default,
                                    id=f"dir-{choice.key}",
                                )

                    with Vertical(classes="field"):
                        yield Static("", classes="field-head-tight", id="head-extras")
                        with Vertical(classes="choices"):
                            for extra in EXTRAS:
                                yield Toggle(
                                    choice_label(extra.label, extra.hint, 16),
                                    value=extra.default,
                                    id=f"extra-{extra.key}",
                                )

                yield Button(f"{ICON['create']}  Create project", id="create", disabled=True)

            with Vertical(id="side"):
                with Horizontal(id="side-head"):
                    yield Static(Text("PREVIEW", style=f"bold {MUTED}"), id="side-title")
                    yield Static("", id="counts")
                with VerticalScroll(id="tree-scroll", can_focus=False):
                    yield Static("", id="tree")
                yield Static("", id="plan")

        yield Static(hint_bar(self.HINTS), id="hints")

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()
        self.refresh_preview()

    def on_resize(self) -> None:
        width = self.size.width
        for group in self.query(".choices"):
            group.set_class(width < 104, "narrow")
        # Below ~72 columns the preview costs more space than it earns.
        self.query_one("#side").display = width >= 72
        self.query_one("#counts").display = width >= 100
        keep = len(self.HINTS) if width >= 84 else 4 if width >= 62 else 2
        self.query_one("#hints", Static).update(hint_bar(self.HINTS[:keep]))

    # -- state ------------------------------------------------------------

    def collect(self) -> None:
        """Read every widget back into the spec."""
        self.spec.name = self.query_one("#name", Input).value
        location = self.query_one("#location", Input).value.strip() or "."
        self.spec.parent = Path(location).expanduser()
        select = self.query_one("#python", Picker)
        if select.value is not Select.BLANK:
            self.spec.python = str(select.value)
        self.spec.layout = "src" if self.query_one("#layout", Choice).pressed_index == 0 else "flat"
        self.spec.directories = {
            choice.key
            for choice in DIRECTORIES
            if self.query_one(f"#dir-{choice.key}", Toggle).value
        }
        self.spec.extras = {
            extra.key for extra in EXTRAS if self.query_one(f"#extra-{extra.key}", Toggle).value
        }
        self.spec.resolve_implications()

    def refresh_preview(self) -> None:
        self.collect()
        spec = self.spec
        problems = spec.problems()

        problems_widget = self.query_one("#problems", Static)
        if problems and spec.name.strip():
            problems_widget.update(Text("\n".join(f"⚠ {p}" for p in problems)))
            problems_widget.add_class("visible")
        else:
            problems_widget.remove_class("visible")

        resolved = Text(no_wrap=True, overflow="ellipsis")
        if spec.slug:
            resolved.append("→ ", style=MUTED)
            resolved.append(str(spec.root), style=FLAME)
        self.query_one("#resolved", Static).update(resolved)

        self.query_one("#head-dirs", Static).update(
            head("dirs", "Directories", f"{len(spec.directories)} of {len(DIRECTORIES)}")
        )
        self.query_one("#head-extras", Static).update(
            head("extras", "Extras", f"{len(spec.extras)} of {len(EXTRAS)}")
        )

        # Before a name is typed, preview a stand-in so the tree still reads.
        preview = spec if spec.slug else replace(spec, name="project")
        rows = preview.tree()
        self.query_one("#create", Button).disabled = not spec.is_valid
        self.query_one("#tree", Static).update(self.render_tree(preview, rows))
        self.query_one("#counts", Static).update(self.render_counts(rows))
        self.query_one("#plan", Static).update(self.render_plan(preview))

    def render_tree(self, spec: ProjectSpec, rows: list[tuple[str, str, str]]) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(f"{spec.slug}/\n", style=f"bold {FLAME}")
        styles = {"dir": FLAME, "venv": f"{MUTED} italic", "file": "#c8cdd6"}
        for prefix, name, kind in rows:
            text.append(prefix, style="#3a424e")
            suffix = "/" if kind in {"dir", "venv"} else ""
            text.append(f"{name}{suffix}\n", style=styles.get(kind, "#c8cdd6"))
        return text

    def render_counts(self, rows: list[tuple[str, str, str]]) -> Text:
        directories = sum(1 for _, _, kind in rows if kind == "dir")
        files = sum(1 for _, _, kind in rows if kind == "file")
        return Text(
            f"{directories} dirs · {files} files", style=MUTED, no_wrap=True, overflow="ellipsis"
        )

    def render_plan(self, spec: ProjectSpec) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append("PLAN\n\n", style=f"bold {MUTED}")
        for step in spec.plan():
            text.append("· ", style=FLAME)
            text.append(f"{step}\n", style=MUTED)
        return text

    # -- events -----------------------------------------------------------

    @on(Input.Changed)
    @on(Checkbox.Changed)
    @on(Select.Changed)
    @on(RadioSet.Changed)
    def anything_changed(self) -> None:
        self.refresh_preview()

    @on(Input.Submitted, "#name")
    def name_submitted(self) -> None:
        self.query_one("#location", Input).focus()

    @on(Input.Submitted, "#location")
    def location_submitted(self) -> None:
        self.action_create()

    @on(Button.Pressed, "#create")
    def create_pressed(self) -> None:
        self.action_create()

    # -- actions ----------------------------------------------------------

    def action_create(self) -> None:
        self.refresh_preview()
        if not self.spec.is_valid:
            self.query_one("#name", Input).focus()
            self.app.bell()
            return
        frozen = replace(
            self.spec, directories=set(self.spec.directories), extras=set(self.spec.extras)
        )
        if frozen.has("venv") and uv_setup.should_offer_ui():
            self.app.push_screen(UvPrompt(), lambda _: self.app.push_screen(BuildScreen(frozen)))
            return
        self.app.push_screen(BuildScreen(frozen))

    def action_reset(self) -> None:
        self.query_one("#name", Input).value = ""
        self.query_one("#location", Input).value = str(Path.cwd())
        self.query_one("#python", Picker).value = default_python()
        for choice in DIRECTORIES:
            self.query_one(f"#dir-{choice.key}", Toggle).value = choice.default
        for extra in EXTRAS:
            self.query_one(f"#extra-{extra.key}", Toggle).value = extra.default
        self.query_one("#name", Input).focus()


class UvPrompt(ModalScreen[bool]):
    """uv is missing. Ask - and only install on a yes."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("y", "accept", "Install uv", show=False),
        Binding("n", "decline", "Continue without", show=False),
        Binding("escape", "decline", "Continue without", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="uv-dialog"):
            yield Static(head("extras", "uv was not found"), id="uv-title")
            yield Static(Text(uv_setup.WHY, style=MUTED), id="uv-why")
            yield Static(one_line(uv_setup.INSTALL_COMMAND, FLAME), id="uv-command")
            yield Static("", id="uv-status")
            with Horizontal(id="uv-actions"):
                yield Button("Install uv", id="uv-yes")
                yield Button("Continue without", id="uv-no")

    def on_mount(self) -> None:
        self.query_one("#uv-yes", Button).focus()

    @on(Button.Pressed, "#uv-yes")
    def yes_pressed(self) -> None:
        self.action_accept()

    @on(Button.Pressed, "#uv-no")
    def no_pressed(self) -> None:
        self.action_decline()

    # -- actions ----------------------------------------------------------

    def action_decline(self) -> None:
        self.dismiss(False)

    def action_accept(self) -> None:
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#uv-status", Static).update(one_line("\u22ef  installing uv", MUTED))
        self.install_uv()

    @work(thread=True, exclusive=True)
    def install_uv(self) -> None:
        ok, detail = uv_setup.install()
        self.app.call_from_thread(self.installed, ok=ok, detail=detail)

    def installed(self, *, ok: bool, detail: str) -> None:
        mark = "\u2713  uv installed" if ok else f"\u2717  {detail}"
        style = "green" if ok else "red"
        self.query_one("#uv-status", Static).update(one_line(mark, style))
        self.set_timer(1.2, lambda: self.dismiss(ok))


class BuildScreen(ArrowScreen):
    """Live log of the scaffold run, then what to do next."""

    BINDINGS: ClassVar[list[Binding]] = [
        # No binding on enter: once the buttons appear it presses the focused one.
        Binding("o", "enter_shell", "Shell here", show=False),
        Binding("d", "finish", "Done", show=False),
        Binding("escape", "finish", "Done", show=False),
        Binding("q", "finish", "Done", show=False),
        Binding("ctrl+q", "app.quit", "Quit", priority=True),
        Binding("ctrl+c", "app.quit", "Quit", priority=True, show=False),
    ]

    def __init__(self, spec: ProjectSpec) -> None:
        super().__init__()
        self.spec = spec
        self.finished = False
        self.started_at: float | None = None

    def compose(self) -> ComposeResult:
        yield Brandbar(id="brandbar")
        yield Rule(line_style="solid", id="brandrule")
        with Vertical(id="build-body"):
            yield ProgressBar(
                total=step_count(self.spec),
                show_eta=False,
                show_percentage=False,
                id="build-progress",
            )
            yield Static("", id="current")
            yield RichLog(markup=True, id="build-log", wrap=True)
            yield Static("", id="outcome")
            with Horizontal(id="actions"):
                yield Button(f"{ICON['shell']}  Open a shell here", id="shell")
                yield Button("Done", id="done")
        yield Static(hint_bar([("esc", "quit")]), id="hints")

    def on_mount(self) -> None:
        log = self.query_one("#build-log", RichLog)
        log.write(Text(f"Building {self.spec.slug}\n", style=f"bold {FLAME}"))
        self.run_build()

    @work(thread=True, exclusive=True)
    def run_build(self) -> None:
        for event in build(self.spec):
            self.app.call_from_thread(self.handle_event, event)

    def handle_event(self, event: Event) -> None:
        log = self.query_one("#build-log", RichLog)
        current = self.query_one("#current", Static)

        if event.status == "start":
            self.started_at = time.monotonic()
            pending = Text()
            pending.append("  ⋯ ", style=FLAME)
            pending.append(event.label, style=MUTED)
            current.update(pending)
            return

        current.update("")

        if event.status == "done":
            progress = self.query_one("#build-progress", ProgressBar)
            progress.update(total=1, progress=1)
            self.show_outcome(event)
            log.scroll_end(animate=False)
            return

        mark, colour = STATUS_MARKS.get(event.status, ("·", MUTED))
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(f"  {mark} ", style=colour)
        line.append(event.label, style="#e6e9ef")
        if event.detail:
            line.append(f"   {short_path(event.detail)}", style=MUTED)
        if self.started_at is not None:
            elapsed = time.monotonic() - self.started_at
            if elapsed >= 0.15:
                line.append(f"   {elapsed:.1f}s", style="#5c6472")
        log.write(line)
        log.scroll_end(animate=False)
        self.query_one("#build-progress", ProgressBar).advance(1)

    def show_outcome(self, event: Event) -> None:
        self.finished = True
        text = Text()
        text.append("✓  ", style="bold #7fd18b")
        text.append(f"{event.label}\n", style="bold #e6e9ef")
        text.append(f"   {event.detail}\n\n", style=MUTED)
        text.append("   NEXT\n", style=f"bold {MUTED}")
        commands = next_steps(self.spec)
        for index, command in enumerate(commands):
            text.append("   $ ", style=FLAME)
            text.append(command, style="#c8cdd6")
            if index < len(commands) - 1:
                text.append("\n")
        outcome = self.query_one("#outcome", Static)
        outcome.update(text)
        outcome.add_class("visible")
        shell = self.query_one("#shell", Button)
        # Nothing to step into if the directory never got made.
        shell.display = self.spec.root.is_dir()
        if handoff.venv_bin(self.spec.root):
            shell.label = f"{ICON['shell']}  Open a shell here · .venv active"
        self.query_one("#actions").add_class("visible")
        (shell if shell.display else self.query_one("#done", Button)).focus()
        self.query_one("#hints", Static).update(
            hint_bar([("⏎", "shell here"), ("d", "done"), ("esc", "quit")])
        )

    @on(Button.Pressed, "#shell")
    def shell_pressed(self) -> None:
        self.action_enter_shell()

    @on(Button.Pressed, "#done")
    def done_pressed(self) -> None:
        self.action_finish()

    def action_enter_shell(self) -> None:
        """Quit, and leave the terminal inside the new project."""
        if self.finished and self.spec.root.is_dir():
            self.app.exit(Outcome(self.spec.root, enter=True))

    def action_finish(self) -> None:
        if self.finished:
            self.app.exit(Outcome(self.spec.root))


class BootstrapApp(App):
    """`t1` - start a Python project without thinking about the boilerplate."""

    CSS_PATH = "app.tcss"
    TITLE = "t1 bootstrap"
    ENABLE_COMMAND_PALETTE = True

    def __init__(self, *, welcome: bool = True) -> None:
        super().__init__()
        self.welcome = welcome
        self.register_theme(TABELLE1)
        self.theme = "tabelle1"

    def get_default_screen(self) -> Screen:
        return WelcomeScreen() if self.welcome else WizardScreen()


def run() -> Outcome | None:
    """Run the wizard; returns what was created, or None if it was cancelled."""
    return BootstrapApp().run()
