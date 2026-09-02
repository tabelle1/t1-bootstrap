"""Interpreter discovery, driven by fake tool output - the uv JSON is an external contract."""

import json
import subprocess
import sys

import pytest

from t1_bootstrap import pythons
from t1_bootstrap.pythons import PythonOption


def entry(version: str, *, installed: bool, implementation="cpython", variant="default") -> dict:
    major, minor, *_ = version.split(".")
    return {
        "implementation": implementation,
        "variant": variant,
        "version": version,
        "version_parts": {"major": int(major), "minor": int(minor)},
        "path": f"/opt/python/{version}/bin/python" if installed else None,
    }


def uv_says(monkeypatch, entries) -> None:
    monkeypatch.setattr(pythons, "uv_path", lambda: "/usr/bin/uv")

    def fake_run(command, **kwargs):
        assert isinstance(command, list)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(entries), stderr="")

    monkeypatch.setattr(pythons.subprocess, "run", fake_run)


def test_uv_entries_collapse_to_one_option_per_series(monkeypatch):
    uv_says(
        monkeypatch,
        [
            entry("3.13.2", installed=False),
            entry("3.13.5", installed=True),
            entry("3.12.9", installed=False),
            entry("3.12.1", installed=True, implementation="pypy"),
            entry("3.13.5", installed=True, variant="freethreaded"),
        ],
    )
    options = pythons._from_uv()
    assert [o.series for o in options] == ["3.13", "3.12"]
    assert options[0].installed
    assert options[0].patch == "3.13.5"
    assert not options[1].installed


def test_prereleases_are_offered_only_when_already_installed(monkeypatch):
    uv_says(
        monkeypatch,
        [
            entry("3.15.0a5", installed=False),
            entry("3.14.0rc1", installed=True),
            entry("3.13.5", installed=True),
        ],
    )
    assert [o.series for o in pythons._from_uv()] == ["3.14", "3.13"]


def test_malformed_entries_are_skipped_not_fatal(monkeypatch):
    uv_says(
        monkeypatch,
        [
            {"implementation": "cpython", "variant": "default", "version": "3.13.1"},
            entry("3.12.4", installed=True),
        ],
    )
    assert [o.series for o in pythons._from_uv()] == ["3.12"]


def test_uv_failures_degrade_to_nothing(monkeypatch):
    monkeypatch.setattr(pythons, "uv_path", lambda: "/usr/bin/uv")

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 15)

    monkeypatch.setattr(pythons.subprocess, "run", timeout)
    assert pythons._from_uv() == []

    def garbage(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="not json", stderr="")

    monkeypatch.setattr(pythons.subprocess, "run", garbage)
    assert pythons._from_uv() == []


def test_without_uv_the_path_is_scanned(monkeypatch, tmp_path):
    monkeypatch.setattr(pythons, "uv_path", lambda: None)
    for name in ("python3.12", "python3.9", "python", "python3"):
        (tmp_path / name).touch()
    monkeypatch.setenv("PATH", str(tmp_path))
    assert [o.series for o in pythons._from_path()] == ["3.12", "3.9"]


@pytest.mark.parametrize(
    "listing",
    [
        " -V:3.13 *        Python 3.13 (64-bit)\n -V:3.12          Python 3.12 (64-bit)\n",
        " -3.13-64 *\n -3.12-64\n",
    ],
)
def test_the_py_launcher_listing_is_understood(monkeypatch, listing):
    monkeypatch.setattr(
        pythons.shutil, "which", lambda name: "C:/Windows/py.exe" if name == "py" else None
    )
    monkeypatch.setattr(
        pythons.subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, 0, stdout=listing, stderr=""),
    )
    options = pythons._from_py_launcher()
    assert [o.series for o in options] == ["3.13", "3.12"]
    assert all(o.installed for o in options)


def test_no_launcher_means_no_options(monkeypatch):
    monkeypatch.setattr(pythons.shutil, "which", lambda name: None)
    assert pythons._from_py_launcher() == []


def test_discover_falls_back_to_the_running_interpreter(monkeypatch):
    monkeypatch.setattr(pythons, "_from_uv", list)
    monkeypatch.setattr(pythons, "_from_path", list)
    monkeypatch.setattr(pythons, "_from_py_launcher", list)
    (only,) = pythons.discover()
    assert only.series == f"{sys.version_info[0]}.{sys.version_info[1]}"
    assert only.installed


def test_default_python_prefers_an_installed_series():
    # conftest pins the list: 3.14 and 3.13 installed, 3.12 downloadable
    assert pythons.default_python() == "3.14"


def test_default_python_is_the_newest_when_nothing_is_installed(monkeypatch):
    monkeypatch.setattr(
        pythons,
        "available_pythons",
        lambda: (
            PythonOption((3, 14), "3.14", "3.14.0", installed=False),
            PythonOption((3, 13), "3.13", "3.13.0", installed=False),
        ),
    )
    assert pythons.default_python() == "3.14"


def test_labels_say_whether_a_download_is_needed():
    assert PythonOption((3, 13), "3.13", "3.13.5", installed=True).label.endswith("installed")
    assert PythonOption((3, 12), "3.12", "3.12.0", installed=False).label.endswith("download")
