"""The release notes a tag ships with are only as good as this extractor."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "changelog_section.py"

SAMPLE = """# Changelog

Preamble that belongs to no version.

## [Unreleased]

### Added

- Something not yet shipped.

## [0.2.0] - 2026-01-02

### Added

- The second thing.

### Fixed

- A bug.

## [0.1.0] - 2026-01-01

### Added

- The first thing.

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/releases/tag/v0.2.0
"""


@pytest.fixture
def changelog(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(SAMPLE)
    return path


def run(changelog, version):
    return subprocess.run(
        [sys.executable, str(SCRIPT), version, str(changelog)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_extracts_a_middle_section_without_its_neighbours(changelog):
    out = run(changelog, "0.2.0").stdout
    assert "The second thing." in out
    assert "A bug." in out
    assert "The first thing." not in out
    assert "not yet shipped" not in out
    # The version heading is the release title, not part of its body.
    assert "## [0.2.0]" not in out


def test_the_last_section_stops_before_the_link_definitions(changelog):
    out = run(changelog, "0.1.0").stdout
    assert "The first thing." in out
    assert "example.invalid" not in out


def test_a_leading_v_is_accepted(changelog):
    assert run(changelog, "v0.2.0").stdout == run(changelog, "0.2.0").stdout


def test_a_missing_version_fails_loudly(changelog):
    result = run(changelog, "9.9.9")
    assert result.returncode == 1
    assert "9.9.9" in result.stderr


def test_an_empty_section_counts_as_missing(tmp_path):
    path = tmp_path / "CHANGELOG.md"
    path.write_text("# Changelog\n\n## [1.0.0] - 2026-01-01\n\n## [0.9.0] - 2025-12-01\n\n- Real.\n")
    assert run(path, "1.0.0").returncode == 1
