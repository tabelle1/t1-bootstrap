<div align="center">

```
▀▀██▀▀         ██                ▀██     ▀██             ▄██
  ██    ▀▀▀▀█▄ ██▀▀▀█▄ ▄█▀▀▀█▄    ██      ██   ▄█▀▀▀█▄    ██
  ██   ▄█▀▀▀██ ██   ██ ██▀▀▀▀▀    ██      ██   ██▀▀▀▀▀    ██
  ▀▀    ▀▀▀▀▀▀  ▀▀▀▀▀   ▀▀▀▀▀   ▀▀▀▀▀▀  ▀▀▀▀▀▀  ▀▀▀▀▀   ▀▀▀▀▀▀
                                                       ▀▀▀▀▀▀▀▀
```

**t1 bootstrap** — start a Python project without thinking about the boilerplate.

[![PyPI](https://img.shields.io/pypi/v/t1-bootstrap)](https://pypi.org/project/t1-bootstrap/)
[![Python](https://img.shields.io/pypi/pyversions/t1-bootstrap)](https://pypi.org/project/t1-bootstrap/)
[![CI](https://github.com/tabelle1/t1-bootstrap/actions/workflows/ci.yml/badge.svg)](https://github.com/tabelle1/t1-bootstrap/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/tabelle1/t1-bootstrap/blob/main/LICENSE)

</div>

`uv init` gives you a folder. This gives you the folder you actually wanted: a venv on the
Python you picked, a `src/` layout, the directories you always end up creating by hand, and a
`pyproject.toml` with your project name and lint config already filled in.

A start screen, then one screen with a live preview — keyboard or mouse. A full project lands
in **less than a second**.

<img src="https://raw.githubusercontent.com/tabelle1/t1-bootstrap/main/docs/wizard.svg" alt="The t1 wizard: the form on the left, a live preview of the project tree on the right" width="100%">

## Install

Runs on macOS, Linux and Windows (Windows Terminal with PowerShell 5.1 or 7). Needs
Python 3.13 or newer — `uv` fetches one if the machine has none.

```bash
uvx t1-bootstrap                  # try it without installing anything
uv tool install t1-bootstrap      # keep it: `t1` on your PATH
pipx install t1-bootstrap         # the same, without uv
```

## Use it

```bash
t1                                # start screen, then the wizard
```

`⏎` on the start screen opens the form.

| Key | |
| :-- | :-- |
| `↑` `↓` | move between fields |
| `←` `→` | move across a row of toggles, or pick a layout |
| `⇥` | next field, in reading order |
| `space` | toggle a directory or extra |
| `⏎` | open the Python menu, next field, or create from the last one |
| `^n` | create the project |
| `^p` | command palette |
| `^r` | reset the form |
| `^q` | quit |

The arrows walk the form the way it looks: `↓` from a toggle lands on the one below it, not the
one beside it, and the pane scrolls to follow rather than scrolling out from under you. A rail
in the accent colour marks the field you are in.

Mouse works everywhere too — click a field, click a toggle, scroll either pane.

The right-hand pane previews the exact tree you are about to get, and updates as you type.

### Landing in the project

The build screen ends with two ways out:

| Button | Key | |
| :-- | :-- | :-- |
| **Open a shell here** | `⏎` | quits into a shell inside the new project, `.venv` active |
| **Done** | `d` | quits and leaves your terminal where it was |

Out of the box the first one starts a shell in the project — `exit` returns you to where you
were. Install the wrapper once and your *own* shell follows along instead, so there is no
nested shell and `deactivate` works as usual:

```bash
eval "$(t1 shell-init)"                                    # ~/.zshrc or ~/.bashrc
t1 shell-init fish | source                                # ~/.config/fish/config.fish
```

```powershell
Invoke-Expression (t1 shell-init powershell | Out-String)  # $PROFILE
```

### Without the TUI

```bash
t1 new "sales pipeline"                          # sensible defaults
t1 new etl -p 3.13 --dirs data,logs,sql          # pick the Python and the directories
t1 new lib --flat --extras none                  # just the package
t1 new api -C ~/projects --no-venv --no-git      # elsewhere, and without the slow parts
t1 new thing --dry-run                           # print the plan, write nothing
t1 options                                       # list directories and extras
t1 pythons                                       # list interpreters you can build on
t1 shell-init                                    # the shell function, for your rc file
t1 install-uv                                    # install uv, if you don't have it
t1 --version
```

`--dirs` and `--extras` take a comma list, or `all` / `none`. `-p` takes a version series such
as `3.13`; anything else is refused before a file is written.

### If you don't have uv

uv builds the venv and installs dependencies. Without it you still get a project — just
`python -m venv` on the interpreter you asked for, and no install. If uv isn't on your `PATH`,
t1 offers to fetch it from
[Astral's official installer](https://docs.astral.sh/uv/getting-started/installation/) and
shows you the exact command first. It only asks when there's someone there to answer, never
installs on a `--dry-run`, and taking the offer is always optional:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                                # macOS, Linux
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

## What you get

```text
sales-pipeline/
├── data/{raw,interim,processed}/   # each with .gitkeep, contents git-ignored
├── logs/
├── src/sales_pipeline/
│   ├── __init__.py
│   └── py.typed
├── tests/test_smoke.py
├── pyproject.toml                  # name, ruff, pytest, uv_build — all filled in
├── README.md
├── .python-version
├── .gitignore
├── .env + .env.example
└── .venv/
```

**Directories** — `tests` `data` `logs` `scripts` `notebooks` `sql` `config` `docs` `assets` `output`

**Extras** — `.venv` · `git init` · `ruff + pytest` · `README.md` · `.env` · `.editorconfig` ·
`logging setup` · `console script`

Extras pull in what they need: choosing *logging setup* turns on `logs/` for you.

## Why it's quick

The generated `pyproject.toml` uses [`uv_build`](https://docs.astral.sh/uv/concepts/build-backend/)
rather than hatchling. Measured on a cold cache, first `uv sync`:

| backend | first sync |
| :-- | --: |
| hatchling | 3456 ms |
| `uv_build` | 323 ms |

Apple Silicon Mac, uv 0.9.30. Your numbers will differ; the ratio shouldn't.

`uv sync` also creates `.venv` on the pinned interpreter by itself, so there is no separate
`uv venv` call. Writing every file costs about 6 ms; the rest is `git` and `uv`.

## Development

```bash
git clone https://github.com/tabelle1/t1-bootstrap && cd t1-bootstrap
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
uv run ty check src
uv run t1                                                 # the wizard, from the checkout
uv run textual run --dev t1_bootstrap.app:BootstrapApp   # with the Textual devtools
uv run python scripts/screenshot.py                       # refresh docs/wizard.svg
```

CI runs the same checks on macOS, Linux and Windows, plus a leg on the oldest dependency
versions the package claims to support. User-visible changes are recorded in
[CHANGELOG.md](https://github.com/tabelle1/t1-bootstrap/blob/main/CHANGELOG.md) as they land.
Bugs and ideas: [open an issue](https://github.com/tabelle1/t1-bootstrap/issues). Security
concerns: see [SECURITY.md](https://github.com/tabelle1/t1-bootstrap/blob/main/SECURITY.md).

## License

[MIT](https://github.com/tabelle1/t1-bootstrap/blob/main/LICENSE) © Philipp Formanek.

---

Built with [Textual](https://textual.textualize.io). A [Tabelle1](https://tabelle1.at) tool.
