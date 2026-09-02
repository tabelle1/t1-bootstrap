"""Content for every file a new project gets."""

import re
import subprocess
from functools import lru_cache

from t1_bootstrap.spec import ProjectSpec
from t1_bootstrap.uv_setup import uv_path

FALLBACK_UV_BUILD = "uv_build>=0.9,<0.10"


@lru_cache(maxsize=1)
def uv_build_requirement() -> str:
    """Pin uv_build to the installed uv's minor series, the way `uv init` does."""
    uv = uv_path()
    if not uv:
        return FALLBACK_UV_BUILD
    try:
        out = subprocess.run(
            [uv, "--version"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return FALLBACK_UV_BUILD
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    if not match:
        return FALLBACK_UV_BUILD
    major, minor, patch = (int(g) for g in match.groups())
    return f"uv_build>={major}.{minor}.{patch},<{major}.{minor + 1}.0"


BASE_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/

# Environments
.venv/
venv/
.env

# Tooling
.ruff_cache/
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
"""

EDITORCONFIG = """\
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 4

[*.{json,toml,yaml,yml,md}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false
"""


def pyproject(spec: ProjectSpec) -> str:
    """A pyproject.toml with the project name already filled in."""
    lines = [
        "[project]",
        f'name = "{spec.slug}"',
        'version = "0.1.0"',
        'description = ""',
    ]
    if spec.has("readme"):
        lines.append('readme = "README.md"')
    lines += [
        f'requires-python = ">={spec.python}"',
        "dependencies = []",
        "",
    ]

    if spec.has("cli"):
        lines += ["[project.scripts]", f'{spec.slug} = "{spec.module}.cli:main"', ""]

    # uv_build over hatchling: same result, ~10x faster first sync.
    lines += [
        "[build-system]",
        f'requires = ["{uv_build_requirement()}"]',
        'build-backend = "uv_build"',
        "",
    ]
    backend: list[str] = []
    if spec.module != spec.slug.replace("-", "_"):
        backend.append(f'module-name = "{spec.module}"')  # not what uv would infer
    if spec.layout != "src":
        backend.append('module-root = ""')
    if backend:
        lines += ["[tool.uv.build-backend]", *backend, ""]

    dev: list[str] = []
    if "tests" in spec.directories:
        dev.append('"pytest>=8.0"')
    if spec.has("ruff"):
        dev.append('"ruff>=0.14"')
    if dev:
        lines += ["[dependency-groups]", f"dev = [{', '.join(dev)}]", ""]

    if spec.has("ruff"):
        target = "py" + spec.python.replace(".", "")
        src_dirs = '["src", "tests"]' if spec.layout == "src" else '["tests"]'
        lines += [
            "[tool.ruff]",
            "line-length = 100",
            f'target-version = "{target}"',
            f"src = {src_dirs}",
            "",
            "[tool.ruff.lint]",
            "# A pragmatic default: correctness, imports, modern syntax, common footguns.",
            'select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM", "RUF", "PTH", "RET", "DTZ", "LOG"]',
            'ignore = ["E501"]  # the formatter owns line length',
            "",
            "[tool.ruff.lint.isort]",
            f'known-first-party = ["{spec.module}"]',
            "",
            "[tool.ruff.format]",
            'quote-style = "double"',
            "skip-magic-trailing-comma = false",
            "",
        ]

    if "tests" in spec.directories:
        lines += [
            "[tool.pytest.ini_options]",
            'testpaths = ["tests"]',
            'addopts = "-q --strict-markers --strict-config"',
        ]
        if spec.layout == "src":
            lines.append('pythonpath = ["src"]')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def package_init(spec: ProjectSpec) -> str:
    return f'"""{spec.slug}."""\n\n__version__ = "0.1.0"\n'


def cli_module(spec: ProjectSpec) -> str:
    return f'''"""Command line entry point for {spec.slug}."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from {spec.module} import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="{spec.slug}", description="{spec.slug}")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print("hello from {spec.slug}", args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def dunder_main(spec: ProjectSpec) -> str:
    return (
        f"from {spec.module}.cli import main\n\n"
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )


def logging_module(spec: ProjectSpec) -> str:
    depth = 2 if spec.layout == "src" else 1
    return f'''"""Logging for {spec.slug}: rotating file in logs/, plus the console."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[{depth}] / "logs"
LOG_FILE = LOG_DIR / "{spec.module}.log"
FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Attach a rotating file handler and a console handler to the root logger."""
    global _configured
    if _configured:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(FORMAT)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [file_handler, console]
    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Module-level logger; safe to call before setup_logging()."""
    setup_logging()
    return logging.getLogger(name or "{spec.module}")
'''


def smoke_test(spec: ProjectSpec) -> str:
    return f"""import {spec.module}


def test_package_has_a_version() -> None:
    assert {spec.module}.__version__
"""


def readme(spec: ProjectSpec) -> str:
    run_lines = ["uv sync"]
    if spec.has("cli"):
        run_lines.append(f"uv run {spec.slug}")
    if "tests" in spec.directories:
        run_lines.append("uv run pytest")
    if spec.has("ruff"):
        run_lines.append("uv run ruff check --fix .")
        run_lines.append("uv run ruff format .")

    tree = "\n".join(f"{prefix}{name}" for prefix, name, kind in spec.tree() if kind != "file")
    quickstart = "\n".join(run_lines)
    return f"""# {spec.slug}

> Python {spec.python} · {"src" if spec.layout == "src" else "flat"} layout

## Quickstart

```bash
{quickstart}
```

## Layout

```text
{spec.slug}/
{tree}
```

---

Bootstrapped with [t1 bootstrap](https://github.com/tabelle1/t1-bootstrap) 🔸
"""


def env_file(spec: ProjectSpec) -> str:
    """The real .env: local values, never committed."""
    return f"""# Local settings for {spec.slug}. Never commit this file - .env.example is the template.
{spec.module.upper()}_ENV=local
# DATABASE_URL=
# API_TOKEN=
"""


def env_example(spec: ProjectSpec) -> str:
    return f"""# Copy to .env and fill in. .env is git-ignored; this file is not.
{spec.module.upper()}_ENV=local
# DATABASE_URL=
# API_TOKEN=
"""


def gitignore(spec: ProjectSpec) -> str:
    extra = spec.gitignore_extras()
    if not extra:
        return BASE_GITIGNORE
    return BASE_GITIGNORE + "\n# Project directories\n" + "\n".join(extra) + "\n"
