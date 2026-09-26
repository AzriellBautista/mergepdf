"""The installed version of mergepdf.

Kept in its own module so ``cli`` and the package ``__init__`` can both read
it without importing each other. ``pyproject.toml`` is the single place the
version is written down; this asks the installed distribution's metadata
rather than repeating the literal, so the two cannot drift.

Running from a source checkout that was never installed leaves no metadata to
read. That is a real state -- ``python src/mergepdf/cli.py`` or an un-synced
clone -- so it reports itself as unknown rather than pretending to be a
release.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mergepdf")
except PackageNotFoundError:  # pragma: no cover - depends on install state
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
