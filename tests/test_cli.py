from pathlib import Path

import pytest

from t1_bootstrap import __version__, cli, handoff, pythons
from t1_bootstrap.cli import build_parser, farewell, main


def test_building_the_parser_probes_nothing(monkeypatch):
    """`t1 shell-init` runs from every new terminal: the parser must not ask uv anything."""
    monkeypatch.setattr(
        pythons, "available_pythons", lambda: pytest.fail("build_parser() probed the interpreters")
    )
    build_parser()


def test_version_flag_reports_the_installed_version(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_command_without_a_terminal_explains_itself(monkeypatch, capsys):
    monkeypatch.setattr(cli, "interactive_terminal", lambda: False)
    assert main([]) == 1
    assert "Not a terminal" in capsys.readouterr().out


def test_dry_run_writes_nothing(tmp_path, capsys):
    code = main(["new", "demo project", "-C", str(tmp_path), "--dry-run"])
    assert code == 0
    assert not (tmp_path / "demo-project").exists()
    assert "demo-project/" in capsys.readouterr().out


def test_unknown_directory_key_is_rejected(tmp_path, capsys):
    assert main(["new", "demo", "-C", str(tmp_path), "--dirs", "nope"]) == 2
    assert "Unknown: nope" in capsys.readouterr().out


def test_none_and_all_are_accepted(tmp_path, capsys):
    assert main(["new", "a", "-C", str(tmp_path), "--dirs", "none", "--dry-run"]) == 0
    assert main(["new", "b", "-C", str(tmp_path), "--dirs", "all", "--dry-run"]) == 0
    assert "notebooks/" in capsys.readouterr().out


def test_invalid_name_exits_nonzero(tmp_path, capsys):
    # "class" slugifies to a Python keyword, so it can't be a package name.
    assert main(["new", "class", "-C", str(tmp_path)]) == 1
    assert "not a usable Python package name" in capsys.readouterr().out


def test_a_bad_python_series_is_rejected_before_anything_is_written(tmp_path, capsys):
    assert main(["new", "demo", "-C", str(tmp_path), "-p", "bogus"]) == 1
    assert "not a Python version series" in capsys.readouterr().out
    assert not (tmp_path / "demo").exists()


def test_new_builds_a_project(tmp_path):
    code = main(
        ["new", "real project", "-C", str(tmp_path), "--no-venv", "--no-git", "--dirs", "tests"]
    )
    assert code == 0
    root = tmp_path / "real-project"
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "real_project" / "__init__.py").is_file()
    assert not (root / ".venv").exists()


def test_options_and_pythons_list_cleanly(capsys):
    assert main(["options"]) == 0
    assert main(["pythons"]) == 0
    out = capsys.readouterr().out
    assert "DIRECTORIES" in out
    assert "EXTRAS" in out
    assert "3.13" in out


def test_shell_init_prints_a_function_to_eval(capsys):
    assert main(["shell-init", "zsh"]) == 0
    assert "t1() {" in capsys.readouterr().out
    assert main(["shell-init", "fish"]) == 0
    assert "function t1" in capsys.readouterr().out


def test_shell_init_speaks_powershell(capsys):
    assert main(["shell-init", "powershell"]) == 0
    out = capsys.readouterr().out
    assert "function t1 {" in out
    assert "Activate.ps1" in out


def test_shell_init_follows_the_shell_you_are_in(monkeypatch, capsys):
    monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
    assert main(["shell-init"]) == 0
    assert "function t1" in capsys.readouterr().out


def test_the_farewell_says_the_project_is_ready(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv(handoff.CD_FILE, raising=False)
    assert farewell(tmp_path / "demo", enter=False) == 0
    assert "demo is ready. Have fun." in capsys.readouterr().out


def test_stepping_in_prefers_the_shell_wrapper(tmp_path, monkeypatch):
    cd_file = tmp_path / "cd"
    monkeypatch.setenv(handoff.CD_FILE, str(cd_file))
    monkeypatch.setattr(handoff, "open_shell", _refuse)

    assert farewell(tmp_path / "demo", enter=True) == 0
    assert cd_file.read_text().strip() == str(tmp_path / "demo")


def test_without_a_wrapper_it_opens_a_shell_in_the_project(tmp_path, monkeypatch):
    monkeypatch.delenv(handoff.CD_FILE, raising=False)
    opened: list[Path] = []

    def fake_open_shell(root, shell=None):
        opened.append(root)
        return 0

    monkeypatch.setattr(handoff, "open_shell", fake_open_shell)
    assert farewell(tmp_path / "demo", enter=True) == 0
    assert opened == [tmp_path / "demo"]


def test_a_shell_that_will_not_start_is_reported_with_a_cd_to_type(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(handoff.CD_FILE, raising=False)

    def refuse(root, shell=None):
        raise OSError("no such shell")

    monkeypatch.setattr(handoff, "open_shell", refuse)
    assert farewell(tmp_path / "demo", enter=True) == 1
    out = capsys.readouterr().out
    assert "Could not open a shell" in out
    assert "cd " in out


def _refuse(*args, **kwargs):
    raise AssertionError("the wrapper should have handled the cd")
