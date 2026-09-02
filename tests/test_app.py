import time

import pytest
from textual.widgets import Button, Input, Static

import t1_bootstrap.app as tui
from t1_bootstrap import uv_setup
from t1_bootstrap.app import (
    BootstrapApp,
    BuildScreen,
    Outcome,
    Radio,
    Toggle,
    UvPrompt,
    WelcomeScreen,
    WizardScreen,
)
from t1_bootstrap.scaffold import Event


async def settle(pilot, condition, what: str, timeout: float = 15.0) -> None:
    """Pause the pilot until `condition()` holds - builds run on a real thread."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        await pilot.pause()
        if condition():
            return
    pytest.fail(f"{what} did not happen within {timeout:.0f}s")


async def test_the_welcome_screen_offers_one_door_in():
    async with BootstrapApp().run_test(size=(120, 46)) as pilot:
        screen = pilot.app.screen
        assert isinstance(screen, WelcomeScreen)
        start = screen.query_one("#start", Button)
        assert pilot.app.focused is start
        assert "Create new project" in str(start.label)
        assert "p.formanek" in str(screen.query_one("#welcome-credit", Static).content)


async def test_enter_on_the_welcome_screen_opens_the_wizard():
    async with BootstrapApp().run_test(size=(120, 46)) as pilot:
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(pilot.app.screen, WizardScreen)
        assert pilot.app.focused is pilot.app.screen.query_one("#name", Input)


async def test_the_welcome_screen_can_be_skipped():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        assert isinstance(pilot.app.screen, WizardScreen)
        assert pilot.app.theme == "tabelle1"
        assert pilot.app.focused is pilot.app.query_one("#name", Input)


async def test_create_stays_disabled_until_the_name_is_usable():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        create = pilot.app.query_one("#create", Button)
        assert create.disabled

        await pilot.press(*"demo")
        assert not create.disabled

        pilot.app.query_one("#name", Input).value = "class"
        await pilot.pause()
        assert create.disabled
        assert pilot.app.query_one("#problems", Static).has_class("visible")


async def test_preview_follows_the_toggles():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")
        screen = pilot.app.screen

        assert "notebooks" not in screen.spec.directories
        pilot.app.query_one("#dir-notebooks", Toggle).value = True
        await pilot.pause()

        assert "notebooks" in screen.spec.directories
        assert "notebooks" in str(screen.render_tree(screen.spec, screen.spec.tree()))


async def test_flat_layout_changes_the_package_path():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")
        pilot.app.query(Radio)[1].value = True  # flat
        await pilot.pause()
        assert pilot.app.screen.spec.layout == "flat"
        assert "src" not in str(
            pilot.app.screen.render_tree(pilot.app.screen.spec, pilot.app.screen.spec.tree())
        )


async def test_selecting_logging_turns_on_the_logs_directory():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")
        pilot.app.query_one("#dir-logs", Toggle).value = False
        pilot.app.query_one("#extra-logging", Toggle).value = True
        await pilot.pause()
        assert "logs" in pilot.app.screen.spec.directories


async def test_create_is_refused_while_the_name_is_invalid():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert isinstance(pilot.app.screen, WizardScreen)


async def build_demo(pilot, tmp_path) -> BuildScreen:
    """Run a scaffold to completion and hand back the build screen."""
    await pilot.press(*"demo")
    pilot.app.query_one("#location", Input).value = str(tmp_path)
    pilot.app.query_one("#extra-venv", Toggle).value = False
    pilot.app.query_one("#extra-git", Toggle).value = False
    await pilot.pause()

    await pilot.press("ctrl+n")
    await settle(pilot, lambda: getattr(pilot.app.screen, "finished", False), "the build")
    return pilot.app.screen


async def test_a_full_run_reaches_the_outcome_panel(tmp_path):
    async with BootstrapApp(welcome=False).run_test(size=(120, 40)) as pilot:
        screen = await build_demo(pilot, tmp_path)
        assert isinstance(screen, BuildScreen)
        assert screen.finished
        # query from the screen: App.query_one resolves against the base screen
        assert screen.query_one("#outcome", Static).has_class("visible")
        assert (tmp_path / "demo" / "pyproject.toml").is_file()


async def test_the_shell_button_asks_to_be_dropped_into_the_project(tmp_path):
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await build_demo(pilot, tmp_path)
        assert screen.query_one("#actions").has_class("visible")
        assert app.focused is screen.query_one("#shell", Button)

        await pilot.press("enter")  # presses the focused button
        await pilot.pause()
    assert app.return_value == Outcome(tmp_path / "demo", enter=True)


async def test_done_leaves_the_terminal_where_it_was(tmp_path):
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(120, 40)) as pilot:
        await build_demo(pilot, tmp_path)
        await pilot.click("#done")
        await pilot.pause()
    assert app.return_value == Outcome(tmp_path / "demo", enter=False)


async def test_neither_way_out_fires_before_the_build_finishes(tmp_path):
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(120, 40)) as pilot:
        screen = await build_demo(pilot, tmp_path)
        screen.finished = False  # as it is for the whole run
        await pilot.press("o")
        await pilot.press("d")
        await pilot.pause()
        assert app.is_running


async def test_narrow_terminal_collapses_the_choice_grid():
    async with BootstrapApp(welcome=False).run_test(size=(80, 40)) as pilot:
        await pilot.pause()
        assert all(group.has_class("narrow") for group in pilot.app.query(".choices"))


async def quits_on(key: str, *, focus_input: bool) -> bool:
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(110, 40)) as pilot:
        if not focus_input:
            pilot.app.query_one("#dir-data", Toggle).focus()
        await pilot.pause()
        await pilot.press(key)
        await pilot.pause()
        return not app.is_running  # checked while the app is still up


async def test_every_quit_route_works_from_a_toggle():
    # ctrl+q is XOFF on some terminals, so it must not be the only way out.
    for key in ("ctrl+q", "ctrl+c", "escape", "q"):
        assert await quits_on(key, focus_input=False), f"{key} did not quit"


async def test_escape_and_ctrl_c_quit_from_a_text_field():
    for key in ("escape", "ctrl+c", "ctrl+q"):
        assert await quits_on(key, focus_input=True), f"{key} did not quit from an Input"


async def test_typing_q_into_the_name_field_is_still_just_text():
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.press(*"qq")
        await pilot.pause()
        assert app.is_running
        assert pilot.app.query_one("#name", Input).value == "qq"


# -- arrow keys ------------------------------------------------------------


async def focus_after(keys: list[str], start: str = "#name", size=(120, 46)) -> str:
    """Focus the widget at `start`, press the keys, report where focus landed."""
    async with BootstrapApp(welcome=False).run_test(size=size) as pilot:
        pilot.app.query_one(start).focus()
        await pilot.pause()
        for key in keys:
            await pilot.press(key)
        await pilot.pause()
        return pilot.app.focused.id or ""


async def test_down_walks_the_fields_in_order():
    assert await focus_after(["down"]) == "location"
    assert await focus_after(["down", "down"]) == "python"
    assert await focus_after(["down", "down", "down"]) == "layout"
    assert await focus_after(["down", "down", "down", "down"]) == "dir-tests"


async def test_up_walks_back():
    assert await focus_after(["up"], start="#python") == "location"


async def test_the_arrows_never_scroll_the_form_out_from_under_the_focus():
    """The form used to eat up/down as a scroll; nothing may scroll unfocused."""
    async with BootstrapApp(welcome=False).run_test(size=(120, 30)) as pilot:
        form = pilot.app.query_one("#form")
        assert not form.can_focus
        pilot.app.query_one("#name").focus()
        await pilot.pause()
        for _ in range(6):
            await pilot.press("down")
        await pilot.pause()
        assert pilot.app.focused.id == "dir-notebooks"
        assert form.scroll_offset.y > 0  # it followed the focus instead


async def test_the_toggle_grid_moves_like_a_grid():
    # Two columns: right crosses the row, down drops to the row below.
    assert await focus_after(["right"], start="#dir-tests") == "dir-data"
    assert await focus_after(["down"], start="#dir-tests") == "dir-logs"
    assert await focus_after(["down"], start="#dir-data") == "dir-scripts"
    assert await focus_after(["left"], start="#dir-data") == "dir-tests"


async def test_a_one_column_grid_still_walks_top_to_bottom():
    assert await focus_after(["down"], start="#dir-tests", size=(80, 46)) == "dir-data"


async def test_down_off_the_last_field_reaches_the_create_button():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")  # enables the button
        pilot.app.query_one("#extra-cli").focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert pilot.app.focused.id == "create"


async def test_up_and_down_leave_the_python_menu_closed():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        picker = pilot.app.query_one("#python")
        picker.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert not picker.expanded
        assert pilot.app.focused.id == "layout"


async def test_left_and_right_still_pick_the_layout():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        pilot.app.query_one("#layout").focus()
        await pilot.pause()
        await pilot.press("right")
        await pilot.press("enter")
        await pilot.pause()
        assert pilot.app.screen.spec.layout == "flat"


async def test_left_and_right_still_move_the_cursor_in_a_text_field():
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")
        await pilot.press("left", "left")
        await pilot.pause()
        name = pilot.app.query_one("#name", Input)
        assert pilot.app.focused is name
        assert name.cursor_position == 2


async def test_the_python_menu_still_opens_and_picks_with_the_keyboard():
    """Overriding up/down on the Select must not cost us the menu itself."""
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        picker = pilot.app.query_one("#python")
        picker.focus()
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()
        assert picker.expanded

        before = picker.value
        await pilot.press("down")  # inside the menu, this moves the highlight
        await pilot.pause()
        assert picker.expanded

        await pilot.press("enter")
        await pilot.pause()
        assert not picker.expanded
        assert picker.value != before
        assert pilot.app.screen.spec.python == picker.value


async def test_tab_still_walks_the_form():
    assert await focus_after(["tab"]) == "location"
    assert await focus_after(["tab", "shift+tab"]) == "name"


async def test_off_the_end_of_a_row_carries_on_in_reading_order():
    assert await focus_after(["right"], start="#dir-data") == "dir-logs"


# -- the uv prompt ---------------------------------------------------------


async def test_create_stops_to_ask_when_uv_is_missing(monkeypatch, tmp_path):
    """A venv was asked for and uv is gone: the build waits behind the question."""
    monkeypatch.setattr(uv_setup, "should_offer_ui", lambda: True)
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("installed without being asked")
    )
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        await pilot.press(*"demo")
        pilot.app.query_one("#location", Input).value = str(tmp_path)
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        assert isinstance(pilot.app.screen, UvPrompt)
        assert not (tmp_path / "demo").exists()


async def test_no_question_when_a_venv_was_not_asked_for(monkeypatch, tmp_path):
    monkeypatch.setattr(uv_setup, "should_offer_ui", lambda: True)
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        screen = await build_demo(pilot, tmp_path)
        assert isinstance(screen, BuildScreen)


async def test_escape_on_the_prompt_installs_nothing(monkeypatch):
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("installed after declining")
    )
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        answers: list[bool] = []
        pilot.app.push_screen(UvPrompt(), answers.append)
        await pilot.pause()
        assert isinstance(pilot.app.screen, UvPrompt)
        await pilot.press("escape")
        await pilot.pause()
        assert answers == [False]


async def test_the_no_button_installs_nothing(monkeypatch):
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("installed after declining")
    )
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        answers: list[bool] = []
        pilot.app.push_screen(UvPrompt(), answers.append)
        await pilot.pause()
        await pilot.click("#uv-no")
        await pilot.pause()
        assert answers == [False]


async def test_the_prompt_shows_the_official_command(monkeypatch):
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        pilot.app.push_screen(UvPrompt())
        await pilot.pause()
        screen = pilot.app.screen
        command = str(screen.query_one("#uv-command", Static).content)
        assert "astral.sh/uv/install" in command  # .sh or .ps1, whichever this box gets
        assert pilot.app.focused is screen.query_one("#uv-yes", Button)


async def test_saying_yes_on_the_prompt_installs(monkeypatch):
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: (True, "/home/me/.local/bin/uv"))
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        pilot.app.push_screen(UvPrompt())
        await pilot.pause()
        screen = pilot.app.screen
        await pilot.press("y")
        status = screen.query_one("#uv-status", Static)
        await settle(pilot, lambda: "installed" in str(status.content), "the install")
        assert "uv installed" in str(status.content)


async def test_a_failed_install_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: (False, "network unreachable"))
    async with BootstrapApp(welcome=False).run_test(size=(120, 46)) as pilot:
        pilot.app.push_screen(UvPrompt())
        await pilot.pause()
        screen = pilot.app.screen
        await pilot.click("#uv-yes")
        status = screen.query_one("#uv-status", Static)
        await settle(pilot, lambda: "unreachable" in str(status.content), "the failure report")
        assert "network unreachable" in str(status.content)


# -- when the scaffold itself breaks -----------------------------------------


async def test_a_crashing_build_still_lets_you_leave(monkeypatch, tmp_path):
    """A bug in the scaffold must show up as a failed outcome, not a stranded screen."""

    def crashing_build(spec):
        yield Event("start", "Create demo/")
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(tui, "build", crashing_build)
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press(*"demo")
        pilot.app.query_one("#location", Input).value = str(tmp_path)
        await pilot.pause()
        await pilot.press("ctrl+n")
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, BuildScreen)
        await settle(pilot, lambda: screen.finished, "the crash report")
        outcome = str(screen.query_one("#outcome", Static).content)
        assert "crashed" in outcome
        assert "disk on fire" in outcome
        await pilot.press("d")
        await pilot.pause()
    assert app.return_value == Outcome(tmp_path / "demo", enter=False)


async def test_a_partial_build_is_shown_as_such(tmp_path):
    """Files that cannot be written: the outcome says so and the tree is still there."""
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "pyproject.toml").mkdir()
    app = BootstrapApp(welcome=False)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press(*"demo")
        pilot.app.query_one("#location", Input).value = str(tmp_path)
        pilot.app.query_one("#extra-venv", Toggle).value = False
        pilot.app.query_one("#extra-git", Toggle).value = False
        await pilot.pause()
        # The wizard refuses a non-empty target; drive the build screen directly.
        pilot.app.push_screen(BuildScreen(pilot.app.screen.spec))
        await pilot.pause()
        screen = pilot.app.screen
        await settle(pilot, lambda: screen.finished, "the aborted build")
        assert "incomplete" in str(screen.query_one("#outcome", Static).content)
        assert screen.query_one("#actions").has_class("visible")
