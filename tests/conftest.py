import pytest


@pytest.fixture(autouse=True)
def hermetic_git(tmp_path_factory, monkeypatch):
    """Isolate every test from the machine's git configuration.

    The scaffold creates an initial commit, which needs an identity. A dev box
    has one globally; a CI runner does not, and there the commit would fail and
    take several assertions with it. Tests that care about a specific config
    still set GIT_CONFIG_GLOBAL themselves - that wins over this.
    """
    config = tmp_path_factory.mktemp("gitconfig") / "config"
    config.write_text("[user]\n\tname = t1 test\n\temail = test@example.invalid\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
