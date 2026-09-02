"""Fixtures that make every test hermetic: no host git identity, no host cwd, no host Pythons."""

from functools import lru_cache

import pytest

from t1_bootstrap import pythons
from t1_bootstrap.pythons import PythonOption

KNOWN_PYTHONS = (
    PythonOption((3, 14), "3.14", "3.14.2", installed=True),
    PythonOption((3, 13), "3.13", "3.13.7", installed=True),
    PythonOption((3, 12), "3.12", "3.12.11", installed=False),
)


@pytest.fixture(autouse=True)
def hermetic_git(tmp_path_factory, monkeypatch):
    """Isolate every test from the machine's git configuration.

    The scaffold creates an initial commit, which needs an identity. A dev box
    has one globally; a CI runner does not, and there the commit would fail and
    take several assertions with it. Tests that care about a specific config
    still set GIT_CONFIG_GLOBAL themselves - that wins over this.
    """
    config_dir = tmp_path_factory.mktemp("gitconfig")
    config = config_dir / "config"
    config.write_text("[user]\n\tname = t1 test\n\temail = test@example.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    # A file that does not exist: git reads nothing, on every platform.
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(config_dir / "no-system-config"))


@pytest.fixture(autouse=True)
def hermetic_cwd(tmp_path, monkeypatch):
    """The wizard defaults to Path.cwd() with venv and git switched on.

    A stray enter in a TUI test must never scaffold into this repository.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture(autouse=True)
def known_pythons(monkeypatch):
    """A fixed interpreter list: no `uv python list` per test, no host dependence.

    Real discovery is unit-tested in test_pythons.py through ``discover()``.
    """

    @lru_cache(maxsize=1)
    def fake() -> tuple[PythonOption, ...]:
        return KNOWN_PYTHONS

    monkeypatch.setattr(pythons, "available_pythons", fake)
