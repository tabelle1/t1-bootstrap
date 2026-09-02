"""The project specification: what the wizard collects, and what it implies on disk."""

import keyword
import re
from dataclasses import dataclass, field
from pathlib import Path

from t1_bootstrap.options import DIRECTORIES, DIRECTORIES_BY_KEY, EXTRAS_BY_KEY

_SEPARATORS = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """ "My Cool Project " -> "my-cool-project"."""
    return _SEPARATORS.sub("-", name.strip().lower()).strip("-")


def modulize(name: str) -> str:
    """ "my-cool-project" -> "my_cool_project"."""
    slug = slugify(name).replace("-", "_")
    return f"_{slug}" if slug and slug[0].isdigit() else slug


@dataclass
class ProjectSpec:
    """Everything needed to lay down a project."""

    name: str = ""
    parent: Path = field(default_factory=Path.cwd)
    python: str = "3.13"
    layout: str = "src"
    """"src" or "flat"."""
    directories: set[str] = field(default_factory=set)
    extras: set[str] = field(default_factory=set)

    # -- derived ----------------------------------------------------------

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def module(self) -> str:
        return modulize(self.name)

    @property
    def root(self) -> Path:
        return (self.parent / self.slug).expanduser()

    @property
    def package_dir(self) -> str:
        return f"src/{self.module}" if self.layout == "src" else self.module

    def has(self, key: str) -> bool:
        return key in self.extras or key in self.directories

    # -- validation -------------------------------------------------------

    def problems(self) -> list[str]:
        """Human-readable reasons this spec cannot be built (empty means go)."""
        issues: list[str] = []
        if not self.name.strip():
            issues.append("Give the project a name.")
            return issues
        if not self.slug:
            issues.append("That name has no letters or digits to build a package name from.")
            return issues
        if not self.module.isidentifier() or keyword.iskeyword(self.module):
            issues.append(f"'{self.module}' is not a usable Python package name.")

        parent = self.parent.expanduser()
        if not parent.is_dir():
            issues.append(f"{parent} does not exist.")
        root = self.root
        if root.exists():
            if not root.is_dir():
                issues.append(f"{root.name} already exists as a file.")
            elif any(root.iterdir()):
                issues.append(f"{root.name}/ already exists and is not empty.")
        return issues

    @property
    def is_valid(self) -> bool:
        return not self.problems()

    # -- what this becomes on disk ---------------------------------------

    def planned_dirs(self) -> list[str]:
        dirs = [self.package_dir]
        for choice in DIRECTORIES:  # catalogue order, so the preview is stable
            if choice.key in self.directories:
                dirs.extend(choice.paths)
        return dirs

    def planned_files(self) -> list[str]:
        package = self.package_dir
        files = [
            "pyproject.toml",
            ".python-version",
            f"{package}/__init__.py",
            f"{package}/py.typed",
        ]
        if self.has("readme"):
            files.append("README.md")
        if self.has("git"):
            files.append(".gitignore")
        if self.has("env"):
            files += [".env", ".env.example"]
        if self.has("editorconfig"):
            files.append(".editorconfig")
        if self.has("cli"):
            files += [f"{package}/cli.py", f"{package}/__main__.py"]
        if self.has("logging"):
            files.append(f"{package}/logging_setup.py")
        if "tests" in self.directories:
            files.append("tests/test_smoke.py")
        for choice in DIRECTORIES:
            if choice.key in self.directories and choice.keep:
                files.extend(f"{path}/.gitkeep" for path in choice.paths)
        return files

    def gitignore_extras(self) -> list[str]:
        lines: list[str] = []
        for choice in DIRECTORIES:
            if choice.key in self.directories:
                lines.extend(choice.gitignore)
        return lines

    def tree(self) -> list[tuple[str, str, str]]:
        """Render the resulting layout as ``(prefix, name, kind)`` rows."""
        root: dict[str, dict] = {}
        kinds: dict[tuple[str, ...], str] = {}

        def insert(path: str, kind: str) -> None:
            node = root
            parts = tuple(path.split("/"))
            for depth, part in enumerate(parts, start=1):
                node = node.setdefault(part, {})
                branch = parts[:depth]
                if depth < len(parts):
                    kinds.setdefault(branch, "dir")
                else:
                    kinds[branch] = kind

        for directory in self.planned_dirs():
            insert(directory, "dir")
        if self.has("venv"):
            insert(".venv", "venv")
        for file in self.planned_files():
            insert(file, "file")

        rows: list[tuple[str, str, str]] = []

        def walk(node: dict[str, dict], trail: tuple[str, ...], prefix: str) -> None:
            headline = ("pyproject.toml", "README.md", ".python-version")

            def order(item: tuple[str, dict]) -> tuple[int, int, str]:
                name, children = item
                if children:
                    return (0, 0, name)
                rank = headline.index(name) if name in headline else len(headline)
                return (1, rank, name)

            entries = sorted(node.items(), key=order)
            for index, (name, children) in enumerate(entries):
                last = index == len(entries) - 1
                branch = (*trail, name)
                kind = kinds.get(branch, "dir")
                rows.append((prefix + ("└── " if last else "├── "), name, kind))
                if children:
                    walk(children, branch, prefix + ("    " if last else "│   "))

        walk(root, (), "")
        return rows

    def plan(self) -> list[str]:
        """One-line summaries of the work, for the confirmation panel."""
        steps = [f"Create {self.slug}/ ({self.layout} layout)"]
        directories = [DIRECTORIES_BY_KEY[k].label for k in self.planned_dir_keys()]
        if directories:
            steps.append("Add " + " ".join(directories))
        steps.append(f"pyproject.toml · Python {self.python}")
        if self.has("git"):
            steps.append("git init + first commit")
        if self.has("venv"):
            steps.append(f"uv sync · .venv on {self.python}")
        return steps

    def planned_dir_keys(self) -> list[str]:
        return [c.key for c in DIRECTORIES if c.key in self.directories]

    def resolve_implications(self) -> None:
        """Turn on directories that a selected extra depends on."""
        for key in list(self.extras):
            extra = EXTRAS_BY_KEY.get(key)
            if extra:
                self.directories |= extra.implies
