"""Tabelle1 brand assets: the palette, the icon set and the half-block wordmark."""

from rich.text import Text

# Brand palette
INK = "#f2f4f8"
FLAME = "#f18d4f"
MUTED = "#8b93a1"

AUTHOR = "p.formanek"
SITE = "tabelle1.at"
TAGLINE = "start a Python project without thinking about the boilerplate"
TAGLINE_SHORT = "start a Python project, minus the boilerplate"
PITCH = "venv · src layout · ruff + pytest · git — in less than a second"

# A deliberately small icon set. Every glyph is single-width in a monospace
# terminal (east-asian width N), so nothing here can shift a column.
ICON = {
    "name": "\u270e",  # pencil
    "location": "\u2302",  # house
    "python": "\u2756",  # diamond
    "layout": "\u2317",  # grid
    "dirs": "\u25b8",  # triangle
    "extras": "\u2726",  # star
    "create": "\u271a",  # cross
    "shell": "\u276f",  # chevron
}

# Half-block rasterisation of the Tabelle1 wordmark (63 cols x 5 rows).
LOGO_ROWS: tuple[tuple[tuple[str | None, str], ...], ...] = (
    (
        ("#f2f4f8", "▀▀██▀▀"),
        (None, "         "),
        ("#f2f4f8", "██"),
        (None, "                "),
        ("#f2f4f8", "▀██"),
        (None, "     "),
        ("#f2f4f8", "▀██"),
        (None, "             "),
        ("#f18d4f", "▄██"),
        (None, "   "),
    ),
    (
        (None, "  "),
        ("#f2f4f8", "██"),
        (None, "    "),
        ("#f2f4f8", "▀▀▀▀█▄"),
        (None, " "),
        ("#f2f4f8", "██▀▀▀█▄"),
        (None, " "),
        ("#f2f4f8", "▄█▀▀▀█▄"),
        (None, "    "),
        ("#f2f4f8", "██"),
        (None, "      "),
        ("#f2f4f8", "██"),
        (None, "   "),
        ("#f2f4f8", "▄█▀▀▀█▄"),
        (None, "    "),
        ("#f18d4f", "██"),
        (None, "   "),
    ),
    (
        (None, "  "),
        ("#f2f4f8", "██"),
        (None, "   "),
        ("#f2f4f8", "▄█▀▀▀██"),
        (None, " "),
        ("#f2f4f8", "██"),
        (None, "   "),
        ("#f2f4f8", "██"),
        (None, " "),
        ("#f2f4f8", "██▀▀▀▀▀"),
        (None, "    "),
        ("#f2f4f8", "██"),
        (None, "      "),
        ("#f2f4f8", "██"),
        (None, "   "),
        ("#f2f4f8", "██▀▀▀▀▀"),
        (None, "    "),
        ("#f18d4f", "██"),
        (None, "   "),
    ),
    (
        (None, "  "),
        ("#f2f4f8", "▀▀"),
        (None, "    "),
        ("#f2f4f8", "▀▀▀▀▀▀"),
        (None, "  "),
        ("#f2f4f8", "▀▀▀▀▀"),
        (None, "   "),
        ("#f2f4f8", "▀▀▀▀▀"),
        (None, "   "),
        ("#f2f4f8", "▀▀▀▀▀▀"),
        (None, "  "),
        ("#f2f4f8", "▀▀▀▀▀▀"),
        (None, "  "),
        ("#f2f4f8", "▀▀▀▀▀"),
        (None, "   "),
        ("#f18d4f", "▀▀▀▀▀▀"),
        (None, " "),
    ),
    (
        (None, "                                                       "),
        ("#f18d4f", "▀▀▀▀▀▀▀▀"),
    ),
)
LOGO_WIDTH = 63

# Column spans of the two glyphs the short mark is cut from.
_TEE = slice(0, 6)
_ONE = slice(55, 63)
_GAP = 2


def _cells(row: tuple[tuple[str | None, str], ...]) -> list[tuple[str | None, str]]:
    """One (colour, character) pair per column, padded to the full width."""
    cells = [(colour, char) for colour, run in row for char in run]
    return cells + [(None, " ")] * (LOGO_WIDTH - len(cells))


# The short mark: the T of the wordmark next to its flame 1, i.e. "t1".
MARK_ROWS: tuple[tuple[tuple[str | None, str], ...], ...] = tuple(
    tuple(_cells(row)[_TEE] + [(None, " ")] * _GAP + _cells(row)[_ONE]) for row in LOGO_ROWS
)
MARK_WIDTH = (_TEE.stop - _TEE.start) + _GAP + (_ONE.stop - _ONE.start)


def logo_text(*, dim: bool = False) -> Text:
    """The full wordmark as a Rich Text block."""
    text = Text(no_wrap=True, overflow="crop")
    for index, row in enumerate(LOGO_ROWS):
        if index:
            text.append("\n")
        for colour, run in row:
            text.append(run, style=f"{colour} dim" if colour and dim else colour or "")
    return text


def wordmark(*, width: int | None = None) -> Text:
    """The wordmark, falling back to a typographic lockup on narrow terminals."""
    if width is not None and width < LOGO_WIDTH:
        text = Text(no_wrap=True)
        text.append("Tabelle", style=f"bold {INK}")
        text.append("1", style=f"bold {FLAME}")
        return text
    return logo_text()


def mark_text(*, tall: bool = True) -> Text:
    """The short "t1" mark, for screens that do not need the whole wordmark.

    Drops to a one-line lockup where there is no room for the five-row block.
    """
    if not tall:
        text = Text(no_wrap=True)
        text.append("t", style=f"bold {INK}")
        text.append("1", style=f"bold {FLAME}")
        return text
    text = Text(no_wrap=True, overflow="crop")
    for index, row in enumerate(MARK_ROWS):
        if index:
            text.append("\n")
        for colour, char in row:
            text.append(char, style=colour or "")
    return text
