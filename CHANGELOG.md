# Changelog

All notable changes to **t1-bootstrap** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). While the major version
is `0`, breaking changes are released as minor bumps and are always called out below.

## [Unreleased]

## [0.1.0] - 2026-09-02

First public release. Requires Python 3.13 or newer.

### Added

- Interactive TUI for scaffolding a Python project: a start screen, then a single form with a
  live preview of the exact tree that will be written.
- Full keyboard and mouse navigation — arrows walk the form the way it looks, `^n` creates,
  `^p` opens the command palette, `^r` resets.
- Non-interactive commands: `t1 new`, `t1 options`, `t1 pythons`, `t1 shell-init` and
  `t1 install-uv`, plus `--dry-run` to print the plan without writing anything.
- Selectable project directories (`tests`, `data`, `logs`, `scripts`, `notebooks`, `sql`,
  `config`, `docs`, `assets`, `output`) and extras (`.venv`, `git init`, ruff + pytest,
  `README.md`, `.env`, `.editorconfig`, logging setup, console script). Extras pull in what
  they need — logging turns on `logs/`.
- `src/` and flat layouts, and a chosen Python interpreter for the generated venv.
- Generated projects use the `uv_build` backend, which syncs roughly ten times faster than
  hatchling on a cold cache.
- `t1 shell-init` wrapper so the new project's venv activates in your own shell instead of a
  nested one.
- Graceful degradation without uv: projects still build via `python -m venv`, and t1 offers to
  install uv only when someone is there to answer.

<!-- Update on every release: [Unreleased] compares the newest tag to main. -->

[Unreleased]: https://github.com/tabelle1/t1-bootstrap/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/tabelle1/t1-bootstrap/releases/tag/v0.1.0
