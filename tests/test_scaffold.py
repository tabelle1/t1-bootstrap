import shutil
import subprocess
import sys
import tomllib

import pytest

from t1_bootstrap.options import DIRECTORIES
from t1_bootstrap.scaffold import build, next_steps, step_count
from t1_bootstrap.spec import ProjectSpec


def run(spec: ProjectSpec) -> dict[str, str]:
    """Build and return {label: status} for every reported step."""
    return {e.label: e.status for e in build(spec) if e.status != "start"}


@pytest.fixture
def spec(tmp_path):
    # No venv: keeps the suite fast and offline.
    return ProjectSpec(
        name="demo project",
        parent=tmp_path,
        python="3.13",
        directories={"tests", "data", "logs"},
        extras={"ruff", "readme", "env", "cli", "logging"},
    )


def test_build_creates_the_advertised_layout(spec):
    statuses = run(spec)
    assert "fail" not in statuses.values()

    root = spec.root
    for relative in spec.planned_dirs():
        assert (root / relative).is_dir(), relative
    for relative in spec.planned_files():
        assert (root / relative).is_file(), relative


def test_generated_project_pins_the_chosen_python(spec):
    run(spec)
    assert (spec.root / ".python-version").read_text().strip() == "3.13"
    data = tomllib.loads((spec.root / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.13"


def test_generated_package_imports(spec):
    run(spec)
    result = subprocess.run(
        ["python", "-c", "import demo_project; print(demo_project.__version__)"],
        cwd=spec.root / "src",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0"


def test_flat_layout_puts_the_package_at_the_root(spec):
    spec.layout = "flat"
    run(spec)
    assert (spec.root / "demo_project" / "__init__.py").is_file()
    assert not (spec.root / "src").exists()


def test_gitkeep_only_where_the_catalogue_asks_for_it(spec):
    run(spec)
    assert (spec.root / "logs" / ".gitkeep").is_file()
    assert not (spec.root / "tests" / ".gitkeep").exists()


def test_a_failed_root_aborts_without_a_traceback(tmp_path):
    blocker = tmp_path / "demo"
    blocker.write_text("I am a file, not a directory")
    spec = ProjectSpec(name="demo", parent=blocker)
    events = list(build(spec))
    assert events[-1].status == "done"
    assert "Nothing was created" in events[-1].label


def test_step_count_matches_what_build_reports(spec):
    reported = [e for e in build(spec) if e.status == "start"]
    assert step_count(spec) == len(reported)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_extra_produces_a_repository(spec):
    spec.extras.add("git")
    statuses = run(spec)
    assert statuses["Initialise git"] == "ok"
    # A commit must actually exist - "staged, commit skipped" is not good enough.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=spec.root, capture_output=True, text=True, check=False
    )
    assert head.returncode == 0, "no commit was created under commit.gpgsign=true"


def test_next_steps_quote_paths_containing_spaces(tmp_path):
    spaced = tmp_path / "a folder"
    spaced.mkdir()
    spec = ProjectSpec(name="demo", parent=spaced, directories={"tests"})
    assert next_steps(spec)[0].startswith("cd '")


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_initial_commit_lands_on_main(spec, monkeypatch, tmp_path):
    # Even where the machine defaults to another name.
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[init]\n\tdefaultBranch = master\n[user]\n\tname = T\n\temail = t@e.st\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    spec.extras.add("git")
    run(spec)
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=spec.root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch.stdout.strip() == "main"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_commit_survives_a_repo_that_demands_gpg_signing(spec, monkeypatch, tmp_path):
    # A global commit.gpgsign=true must not hang or fail the scaffold.
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[commit]\n\tgpgsign = true\n[user]\n\tname = T\n\temail = t@e.st\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    spec.extras.add("git")
    statuses = run(spec)
    assert statuses["Initialise git"] == "ok"
    # A commit must actually exist - "staged, commit skipped" is not good enough.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=spec.root, capture_output=True, text=True, check=False
    )
    assert head.returncode == 0, "no commit was created under commit.gpgsign=true"


def test_a_generated_project_passes_its_own_ruff_config(tmp_path):
    """A scaffold that fails the linter it ships is a broken scaffold."""
    spec = ProjectSpec(
        name="lint me",
        parent=tmp_path,
        python="3.13",
        directories={"tests", "logs"},
        extras={"ruff", "readme", "env", "cli", "logging", "editorconfig"},
    )
    run(spec)
    check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "."],
        cwd=spec.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr

    fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--no-cache", "--check", "."],
        cwd=spec.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_the_lockfile_is_in_the_initial_commit(tmp_path):
    """uv sync writes uv.lock, so git has to run after it, not before."""
    spec = ProjectSpec(
        name="locked",
        parent=tmp_path,
        python="3.13",
        directories={"tests"},
        extras={"git", "venv", "ruff"},
    )
    run(spec)
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=spec.root, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "uv.lock" in tracked
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=spec.root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert dirty == "", f"working tree not clean after scaffold: {dirty}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_every_gitkeep_survives_the_commit(tmp_path):
    """A .gitkeep git ignores is a directory that vanishes on clone."""
    spec = ProjectSpec(
        name="keepers",
        parent=tmp_path,
        python="3.13",
        directories={c.key for c in DIRECTORIES},
        extras={"git"},
    )
    run(spec)
    tracked = set(
        subprocess.run(
            ["git", "ls-files"], cwd=spec.root, capture_output=True, text=True, check=True
        ).stdout.split()
    )
    expected = {f for f in spec.planned_files() if f.endswith(".gitkeep")}
    assert expected, "the catalogue should place at least one .gitkeep"
    assert expected <= tracked, f"ignored by .gitignore: {sorted(expected - tracked)}"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_generated_data_files_are_still_ignored(tmp_path):
    spec = ProjectSpec(
        name="ignorer", parent=tmp_path, python="3.13", directories={"data", "logs"}, extras={"git"}
    )
    run(spec)
    (spec.root / "data" / "raw" / "big.csv").write_text("a,b\n")
    (spec.root / "logs" / "run.log").write_text("noise\n")
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=spec.root, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert dirty == "", f"data/log output should be ignored, got: {dirty}"
