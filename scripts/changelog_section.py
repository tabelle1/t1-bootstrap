#!/usr/bin/env python3
"""Print one version's section from CHANGELOG.md.

The release workflow uses this for the GitHub release body, and the release
agent uses it for the annotated tag message, so the changelog, the tag and the
release cannot drift apart. Exiting non-zero on a missing section is the point:
it is what stops an undocumented release, before PyPI has taken the version.

    python3 scripts/changelog_section.py 0.2.0
    python3 scripts/changelog_section.py v0.2.0 path/to/CHANGELOG.md
"""

import re
import sys
from pathlib import Path

# Link definitions and the comment that documents them close the last section.
_TRAILER = re.compile(r"^(\[[^\]]+\]:\s|<!--)")


def section(text: str, version: str) -> str | None:
    """The body under ``## [version]``, up to the next ``##`` heading."""
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return None
    lines = match[1].splitlines()
    for i, line in enumerate(lines):
        if _TRAILER.match(line):
            lines = lines[:i]
            break
    return "\n".join(lines).strip() or None


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print("usage: changelog_section.py VERSION [CHANGELOG.md]", file=sys.stderr)
        return 2
    version = argv[0].removeprefix("v")
    path = Path(argv[1]) if len(argv) == 2 else Path("CHANGELOG.md")
    body = section(path.read_text(encoding="utf-8"), version)
    if body is None:
        print(f"no '## [{version}]' section with content in {path}", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
