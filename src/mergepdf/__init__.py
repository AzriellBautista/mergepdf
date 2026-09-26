"""mergepdf - merge multiple PDF files into a single PDF.

The implementation is split by concern: :mod:`mergepdf.arguments` builds the
parser, :mod:`mergepdf.discovery` finds and orders inputs, :mod:`mergepdf.merge`
drives pypdf, and :mod:`mergepdf.cli` sequences them.

The public surface is deliberately small: ``main`` does the work and returns an
:class:`~mergepdf.errors.ExitCode`, and ``run`` wraps it so a Ctrl-C anywhere
becomes exit 130 rather than a traceback. Both the console script and
``python -m mergepdf`` go through ``run``, so neither can drift from the other.
"""

from __future__ import annotations

from ._version import __version__
from .arguments import build_parser
from .cli import main
from .errors import ExitCode


def run() -> ExitCode:
    """Entry point: run mergepdf and return the code to exit with.

    ``main`` already handles an interrupt in the places it does real work, but
    a Ctrl-C during argument parsing or discovery would otherwise escape as a
    traceback. Catching it here covers every path in one spot.
    """
    try:
        return main()
    except KeyboardInterrupt:
        return ExitCode.INTERRUPTED


__all__ = ["ExitCode", "__version__", "build_parser", "main", "run"]
