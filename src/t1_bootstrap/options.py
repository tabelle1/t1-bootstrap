"""The catalogue of directories and extras the wizard offers."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DirChoice:
    """An optional directory (or group of directories) the project can include."""

    key: str
    label: str
    hint: str
    paths: tuple[str, ...]
    default: bool = False
    gitignore: tuple[str, ...] = ()
    keep: bool = True
    """Drop a .gitkeep in each path so the empty directory survives a commit."""


@dataclass(frozen=True)
class ExtraChoice:
    """An optional piece of project furniture."""

    key: str
    label: str
    hint: str
    default: bool = False
    implies: frozenset[str] = field(default_factory=frozenset)
    """Directory keys this extra needs in order to make sense."""


DIRECTORIES: tuple[DirChoice, ...] = (
    DirChoice(
        key="tests",
        label="tests/",
        hint="smoke test included",
        paths=("tests",),
        default=True,
        keep=False,
    ),
    DirChoice(
        key="data",
        label="data/",
        hint="raw · interim · processed",
        paths=("data/raw", "data/interim", "data/processed"),
        default=True,
        # "data/**/*" would exclude data/raw itself, and git cannot re-include a
        # file whose parent directory is excluded - hence the "!data/**/" line.
        gitignore=("data/**", "!data/**/", "!data/**/.gitkeep"),
    ),
    DirChoice(
        key="logs",
        label="logs/",
        hint="git-ignored",
        paths=("logs",),
        default=True,
        gitignore=("logs/*", "!logs/.gitkeep"),
    ),
    DirChoice(
        key="scripts",
        label="scripts/",
        hint="one-off scripts",
        paths=("scripts",),
    ),
    DirChoice(
        key="notebooks",
        label="notebooks/",
        hint="checkpoints ignored",
        paths=("notebooks",),
        gitignore=(".ipynb_checkpoints/",),
    ),
    DirChoice(
        key="sql",
        label="sql/",
        hint="queries, migrations",
        paths=("sql",),
    ),
    DirChoice(
        key="config",
        label="config/",
        hint="settings, profiles",
        paths=("config",),
    ),
    DirChoice(
        key="docs",
        label="docs/",
        hint="long-form docs",
        paths=("docs",),
    ),
    DirChoice(
        key="assets",
        label="assets/",
        hint="images, fonts, static",
        paths=("assets",),
    ),
    DirChoice(
        key="output",
        label="output/",
        hint="git-ignored artefacts",
        paths=("output",),
        gitignore=("output/*", "!output/.gitkeep"),
    ),
)


EXTRAS: tuple[ExtraChoice, ...] = (
    ExtraChoice("venv", ".venv", "uv venv + uv sync", True),
    ExtraChoice("git", "git init", "repo + .gitignore", True),
    ExtraChoice("ruff", "ruff + pytest", "wired into pyproject", True),
    ExtraChoice("readme", "README.md", "quickstart + layout", True),
    ExtraChoice("env", ".env", "plus .env.example", True),
    ExtraChoice("editorconfig", ".editorconfig", "editor whitespace", False),
    ExtraChoice(
        "logging",
        "logging setup",
        "rotating file + console",
        False,
        implies=frozenset({"logs"}),
    ),
    ExtraChoice("cli", "console script", "argparse entry point", False),
)


DIRECTORIES_BY_KEY = {choice.key: choice for choice in DIRECTORIES}
EXTRAS_BY_KEY = {choice.key: choice for choice in EXTRAS}

DEFAULT_DIRECTORIES = frozenset(c.key for c in DIRECTORIES if c.default)
DEFAULT_EXTRAS = frozenset(c.key for c in EXTRAS if c.default)
