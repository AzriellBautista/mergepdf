"""Shared fixtures for the mergepdf test suite.

Every test drives the tool as a subprocess rather than importing it, because the
exit codes and the log stream are part of what mergepdf promises and neither is
visible to an in-process caller.

Each run starts in pytest's ``tmp_path`` rather than the project root, so
nothing in the checkout can shadow the installed package on ``sys.path`` — the
failure mode that made a root-level ``mergepdf.py`` shadow the package before
the move to a src layout.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from support import page_count

if TYPE_CHECKING:
    from collections.abc import Callable

PROJECT = Path(__file__).resolve().parent.parent
PYPROJECT = PROJECT / "pyproject.toml"

# pyproject.toml is the one place the version is written down; _version.py reads
# it back out of the installed metadata. Reading it here too means the suite
# fails if those two ever disagree, instead of drifting unnoticed.
_VERSION = re.search(
    r'^version = "([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.MULTILINE
)
assert _VERSION is not None, "no version field in pyproject.toml"

VERSION = _VERSION.group(1)


@pytest.fixture
def version() -> str:
    """The version declared in pyproject.toml."""
    return VERSION


@pytest.fixture
def run(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Return a callable that runs ``python -m mergepdf`` and captures output."""

    def _run(*argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "mergepdf", *argv],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            cwd=tmp_path,
        )

    return _run


@pytest.fixture
def pdf(tmp_path: Path) -> Callable[..., Path]:
    """Return a callable that writes a blank PDF and gives back its path."""

    def _pdf(name: str, pages: int = 1, title: str | None = None) -> Path:
        from pypdf import PdfWriter

        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=200, height=200)
        if title:
            writer.add_metadata({"/Title": title})
        with path.open("wb") as handle:
            writer.write(handle)
        return path

    return _pdf


@pytest.fixture
def merge_count(
    run: Callable[..., subprocess.CompletedProcess[str]],
    tmp_path: Path,
) -> Callable[..., int]:
    """Return a callable that merges the given tokens and counts the pages.

    Returns -1 when the run failed, which is how the page-selection tests assert
    that a selection was rejected without having to inspect the exit code too.
    """

    def _merge_count(*tokens: str, name: str = "selection.pdf") -> int:
        target = tmp_path / name
        result = run(*tokens, "-o", str(target), "-f")
        return -1 if result.returncode != 0 else page_count(target)

    return _merge_count
