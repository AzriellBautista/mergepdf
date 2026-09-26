"""Helpers that read results back out of finished PDFs.

Kept apart from ``conftest`` because these are plain functions with no fixture
machinery: a test imports one when it needs to assert on the output, and
nothing here knows anything about pytest.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def page_count(path: Path) -> int:
    """Return the number of pages in a PDF."""
    with path.open("rb") as handle:
        return len(PdfReader(handle).pages)


def meta(path: Path, key: str) -> str | None:
    """Read one metadata field out of a finished PDF."""
    with path.open("rb") as handle:
        found = PdfReader(handle).metadata
    return None if found is None else found.get(key)


def outline_titles(path: Path) -> list[str]:
    """Return the titles of the PDF's top-level outline entries."""
    with path.open("rb") as handle:
        outline = PdfReader(handle).outline
        return [str(item.title) for item in outline if hasattr(item, "title")]


def listed(output: str) -> list[str]:
    """Pull the ordered filenames out of a ``--dry-run`` listing."""
    names = []
    for line in output.splitlines():
        head, separator, tail = line.partition(". ")
        if separator and head.strip().isdigit():
            names.append(Path(tail.strip()).name)
    return names
