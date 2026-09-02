import subprocess

import pytest

from t1_bootstrap import cli, uv_setup


@pytest.fixture
def no_uv(monkeypatch):
    """A machine where uv is nowhere to be found."""
    monkeypatch.setattr(
        uv_setup.shutil, "which", lambda name: None if name == "uv" else f"/bin/{name}"
    )
    monkeypatch.setattr(uv_setup, "_candidate_dirs", list)
    return monkeypatch


def test_uv_path_prefers_the_one_on_path(monkeypatch):
    monkeypatch.setattr(
        uv_setup.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None
    )
    assert uv_setup.uv_path() == "/usr/bin/uv"


def test_uv_path_finds_a_fresh_install_not_yet_on_path(monkeypatch, tmp_path):
    """The installer drops uv in ~/.local/bin; this shell's PATH predates that."""
    binary = tmp_path / "uv"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    monkeypatch.setattr(uv_setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(uv_setup, "_candidate_dirs", lambda: [tmp_path])
    assert uv_setup.uv_path() == str(binary)


def test_a_non_executable_file_is_not_uv(monkeypatch, tmp_path):
    (tmp_path / "uv").write_text("not a binary")
    monkeypatch.setattr(uv_setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(uv_setup, "_candidate_dirs", lambda: [tmp_path])
    assert uv_setup.uv_path() is None


def test_nothing_is_offered_when_uv_is_already_there(monkeypatch):
    monkeypatch.setattr(uv_setup, "uv_path", lambda: "/usr/bin/uv")
    assert not uv_setup.missing()
    assert not uv_setup.should_offer()
    assert not uv_setup.should_offer_ui()


def test_nothing_is_offered_without_a_tty(no_uv):
    no_uv.setattr(uv_setup, "is_interactive", lambda: False)
    assert uv_setup.missing()
    assert not uv_setup.should_offer()


def test_the_offer_needs_curl_and_sh(monkeypatch):
    monkeypatch.setattr(uv_setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(uv_setup, "_candidate_dirs", list)
    assert not uv_setup.can_install()
    assert not uv_setup.should_offer_ui()


def test_install_runs_the_official_installer(monkeypatch, tmp_path):
    """Fetched with curl from astral.sh, then handed to sh - never a shell string."""
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "curl":
            # -o <path> is the last pair; write something so the size check passes.
            from pathlib import Path

            Path(command[-1]).write_text("#!/bin/sh\necho installed\n")
        return subprocess.CompletedProcess(command, 0, stdout="installing uv\n", stderr="")

    monkeypatch.setattr(uv_setup.subprocess, "run", fake_run)
    monkeypatch.setattr(uv_setup, "can_install", lambda: True)
    monkeypatch.setattr(uv_setup, "forget_uv", lambda: None)
    monkeypatch.setattr(uv_setup, "uv_path", lambda: "/home/me/.local/bin/uv")

    ok, detail = uv_setup.install()

    assert ok
    assert detail == "/home/me/.local/bin/uv"
    assert calls[0][0] == "curl"
    assert uv_setup.INSTALL_URL in calls[0]
    assert calls[0][1] == "-LsSf"
    assert calls[1][0] == "sh"
    # nothing is ever run through a shell we assemble ourselves
    assert all(isinstance(command, list) for command in calls)


def test_install_reports_a_download_failure(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 6, stdout="", stderr="could not resolve host\n")

    monkeypatch.setattr(uv_setup.subprocess, "run", fake_run)
    monkeypatch.setattr(uv_setup, "can_install", lambda: True)

    ok, detail = uv_setup.install()
    assert not ok
    assert "could not resolve host" in detail


def test_install_reports_an_empty_installer(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(uv_setup.subprocess, "run", fake_run)
    monkeypatch.setattr(uv_setup, "can_install", lambda: True)

    ok, detail = uv_setup.install()
    assert not ok
    assert "empty" in detail


def test_install_refuses_without_curl(monkeypatch):
    monkeypatch.setattr(uv_setup, "can_install", lambda: False)
    ok, detail = uv_setup.install()
    assert not ok
    assert "curl" in detail


# -- the CLI offer ---------------------------------------------------------


def test_the_cli_asks_nothing_when_uv_is_present(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "should_offer", lambda: False)
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("installed without being asked")
    )
    cli.offer_uv()
    assert capsys.readouterr().out == ""


def test_declining_installs_nothing(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "should_offer", lambda: True)
    monkeypatch.setattr(cli.Confirm, "ask", classmethod(lambda cls, *a, **k: False))
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: pytest.fail("installed after a no"))

    cli.offer_uv()

    out = capsys.readouterr().out
    assert "uv was not found" in out
    assert "Carrying on without uv" in out


def test_saying_yes_installs(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "should_offer", lambda: True)
    monkeypatch.setattr(cli.Confirm, "ask", classmethod(lambda cls, *a, **k: True))
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: (True, "/home/me/.local/bin/uv"))

    cli.offer_uv()
    assert "uv installed" in capsys.readouterr().out


def test_a_refused_prompt_is_a_no(monkeypatch, capsys):
    """Ctrl-C or a closed stdin at the question must not install anything."""
    monkeypatch.setattr(uv_setup, "should_offer", lambda: True)

    def interrupted(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(cli.Confirm, "ask", classmethod(interrupted))
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("installed after an interrupt")
    )
    cli.offer_uv()


def test_install_uv_command_is_a_noop_when_already_installed(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "uv_path", lambda: "/usr/bin/uv")
    monkeypatch.setattr(
        uv_setup, "install", lambda *a, **k: pytest.fail("reinstalled over a working uv")
    )
    assert cli.main(["install-uv"]) == 0
    assert "already installed" in capsys.readouterr().out


def test_install_uv_command_installs_when_missing(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "uv_path", lambda: None)
    monkeypatch.setattr(uv_setup, "can_install", lambda: True)
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: (True, "/home/me/.local/bin/uv"))
    assert cli.main(["install-uv"]) == 0
    assert "uv installed" in capsys.readouterr().out


def test_install_uv_command_reports_failure(monkeypatch, capsys):
    monkeypatch.setattr(uv_setup, "uv_path", lambda: None)
    monkeypatch.setattr(uv_setup, "can_install", lambda: True)
    monkeypatch.setattr(uv_setup, "install", lambda *a, **k: (False, "network unreachable"))
    assert cli.main(["install-uv"]) == 1
    assert "network unreachable" in capsys.readouterr().out
