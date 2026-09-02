"""t1 bootstrap - a modern TUI for starting Python projects."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("t1-bootstrap")
except PackageNotFoundError:  # a checkout that was never installed
    __version__ = "0+unknown"

__all__ = ["__version__"]
