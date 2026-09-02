import os
from pathlib import Path

from t1_bootstrap import handoff

BIN = "Scripts" if os.name == "nt" else "bin"


def test_hand_back_writes_the_path_for_the_shell_wrapper(tmp_path, monkeypatch):
    cd_file = tmp_path / "cd"
    monkeypatch.setenv(handoff.CD_FILE, str(cd_file))
    assert handoff.hand_back(tmp_path / "demo")
    assert cd_file.read_text().strip() == str(tmp_path / "demo")
    assert cd_file.read_bytes().endswith(b"\n")
    assert b"\r" not in cd_file.read_bytes()


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


def test_the_wrapper_defines_a_t1_function_for_every_shell_family():
    posix = handoff.wrapper("zsh")
    assert "t1() {" in posix
    assert handoff.CD_FILE in posix
    assert ". .venv/bin/activate" in posix
    assert ".venv/Scripts/activate" in posix  # Git Bash on Windows

    fish = handoff.wrapper("fish")
    assert "function t1" in fish
    assert "activate.fish" in fish

    for family in ("powershell", "pwsh"):
        powershell = handoff.wrapper(family)
        assert "function t1 {" in powershell
        assert handoff.CD_FILE in powershell
        assert "Activate.ps1" in powershell
        # The wrapper must call the executable, not recurse into itself.
        assert "Get-Command t1 -CommandType Application" in powershell


def test_shell_family_is_the_bare_name(monkeypatch):
    monkeypatch.setenv("SHELL", "/opt/homebrew/bin/fish")
    assert handoff.shell_family() == "fish"
    assert handoff.shell_family("/bin/zsh") == "zsh"
    assert handoff.shell_family("C:/Program Files/PowerShell/7/pwsh.exe") == "pwsh"


def test_user_shell_falls_back_when_shell_is_unset(monkeypatch):
    monkeypatch.delenv("SHELL", raising=False)
    monkeypatch.setattr(handoff, "WINDOWS", False)
    monkeypatch.setattr(handoff.shutil, "which", lambda name: "/bin/zsh" if name == "zsh" else None)
    assert handoff.user_shell() == "/bin/zsh"
    monkeypatch.setattr(handoff.shutil, "which", lambda name: None)
    assert handoff.user_shell() == "/bin/sh"


def test_user_shell_on_windows_prefers_powershell(monkeypatch):
    monkeypatch.delenv("SHELL", raising=False)
    monkeypatch.setattr(handoff, "WINDOWS", True)
    monkeypatch.setattr(
        handoff.shutil, "which", lambda name: "C:/pwsh/pwsh.exe" if name == "pwsh" else None
    )
    assert handoff.user_shell() == "C:/pwsh/pwsh.exe"
    assert handoff.wrapper() is handoff.POWERSHELL_WRAPPER

    monkeypatch.setattr(handoff.shutil, "which", lambda name: None)
    monkeypatch.setenv("COMSPEC", "C:/Windows/System32/cmd.exe")
    assert handoff.user_shell().endswith("cmd.exe")


def test_quote_path_matches_the_shell_it_is_for(monkeypatch):
    monkeypatch.setattr(handoff, "WINDOWS", False)
    assert handoff.quote_path("/home/me/a folder") == "'/home/me/a folder'"
    assert handoff.quote_path("/home/me/plain") == "/home/me/plain"

    monkeypatch.setattr(handoff, "WINDOWS", True)
    assert handoff.quote_path("C:/Users/me/a folder") == '"C:/Users/me/a folder"'
    assert handoff.quote_path("C:/Users/me/plain") == "C:/Users/me/plain"


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
