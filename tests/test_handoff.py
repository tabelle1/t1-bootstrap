import os
from pathlib import Path

from t1_bootstrap import handoff

BIN = "Scripts" if os.name == "nt" else "bin"


def test_hand_back_writes_the_path_for_the_shell_wrapper(tmp_path, monkeypatch):
    cd_file = tmp_path / "cd"
    monkeypatch.setenv(handoff.CD_FILE, str(cd_file))
    assert handoff.hand_back(tmp_path / "demo")
    assert cd_file.read_text().strip() == str(tmp_path / "demo")


def test_hand_back_is_false_without_a_wrapper(monkeypatch):
    monkeypatch.delenv(handoff.CD_FILE, raising=False)
    assert not handoff.hand_back(Path("demo"))


def test_activated_puts_the_venv_first_on_path(tmp_path):
    root = tmp_path / "demo"
    bin_dir = root / ".venv" / BIN
    bin_dir.mkdir(parents=True)

    env = handoff.activated(root, {"PATH": "/usr/bin", "PYTHONHOME": "/nope"})
    assert env["PATH"].split(os.pathsep)[0] == str(bin_dir)
    assert env["VIRTUAL_ENV"] == str(root / ".venv")
    assert env["VIRTUAL_ENV_PROMPT"] == "demo"
    assert "PYTHONHOME" not in env


def test_a_project_without_a_venv_leaves_the_environment_alone(tmp_path):
    before = {"PATH": "/usr/bin"}
    assert handoff.activated(tmp_path / "demo", before) == before
    assert handoff.venv_bin(tmp_path / "demo") is None


def test_the_wrapper_defines_a_t1_function_for_both_shell_families():
    posix = handoff.wrapper("zsh")
    assert "t1() {" in posix and handoff.CD_FILE in posix
    assert ". .venv/bin/activate" in posix

    fish = handoff.wrapper("fish")
    assert "function t1" in fish and "activate.fish" in fish


def test_shell_family_is_the_bare_name(monkeypatch):
    monkeypatch.setenv("SHELL", "/opt/homebrew/bin/fish")
    assert handoff.shell_family() == "fish"
    assert handoff.shell_family("/bin/zsh") == "zsh"


def test_the_venv_we_came_from_is_taken_off_the_path(tmp_path):
    outgoing = tmp_path / "old" / ".venv"
    (outgoing / BIN).mkdir(parents=True)
    root = tmp_path / "demo"
    (root / ".venv" / BIN).mkdir(parents=True)

    env = handoff.activated(
        root,
        {
            "VIRTUAL_ENV": str(outgoing),
            "PATH": os.pathsep.join([str(outgoing / BIN), "/usr/bin"]),
        },
    )
    # exactly one venv on PATH, not two stacked ones
    assert env["PATH"].split(os.pathsep) == [str(root / ".venv" / BIN), "/usr/bin"]
