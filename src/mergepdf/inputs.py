"""Turning command-line tokens into input specifications.

Both parsers here are wired into argparse as ``type=`` callables, so they
signal failure by raising :class:`argparse.ArgumentTypeError` rather than one of
mergepdf's own errors. That is what makes a bad token produce a usage message
and exit code 2 instead of a traceback.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from .identity import identity
from .selection import PageSelection

# Characters a PDF name object may not contain unescaped. Rejecting them here
# gives a readable message instead of whatever pypdf does with a bad name.
_BAD_NAME_CHARS = set(" \t\n\r()<>[]{}/%")


@dataclass(frozen=True, slots=True)
class InputSpec:
    """A single input: a PDF file, optionally narrowed to a page selection."""

    path: Path
    selection: PageSelection | None = None

    @property
    def display(self) -> str:
        """The token as a user would recognise it, selection included."""
        if self.selection is None:
            return str(self.path)
        return f"{self.path}:{self.selection.raw}"

    @property
    def selection_key(self) -> str:
        """A normalised description of which pages this input selects.

        Duplicate detection compares this rather than the raw text, because
        ``f:1-2`` and ``f:01-02`` are the same request written two ways and
        would otherwise both be merged. Parts are sorted, so ``f:1-2,3`` and
        ``f:3,1-2`` also match.

        Ranges are deliberately not merged: ``f:1-3`` and ``f:1-2,3`` still
        differ, because deciding they are equivalent needs the page count,
        which is unknown until the file is opened.
        """
        if self.selection is None:
            return ""

        parts = sorted(
            (part.start, part.stop, part.from_end) for part in self.selection.parts
        )
        return "|".join(
            f"{start}:{stop}:{int(from_end)}" for start, stop, from_end in parts
        )

    @property
    def key(self) -> tuple[str, str]:
        """Identity used for duplicate detection."""
        return (identity(self.path), self.selection_key)

    @property
    def outline_name(self) -> str:
        """The name this input contributes to the output outline."""
        name = self.path.stem or self.path.name
        if self.selection is not None:
            return f"{name} [{self.selection.raw}]"
        return name


def parse_metadata(token: str) -> tuple[str, str]:
    """Parse a ``KEY=VALUE`` metadata argument into a ``(key, value)`` pair.

    The leading slash on a PDF name is optional on the command line, so
    ``--metadata Title=Report`` and ``--metadata /Title=Report`` mean the same
    thing. Only the first ``=`` separates, which lets a value contain more of
    them.
    """
    key, separator, value = token.partition("=")

    if not separator:
        raise argparse.ArgumentTypeError(
            f"expected KEY=VALUE, got {token!r} (for example --metadata "
            "/Title=Annual Report)"
        )

    key = key.strip()

    if not key:
        raise argparse.ArgumentTypeError(f"missing key in {token!r}")

    if not key.startswith("/"):
        key = f"/{key}"

    if _BAD_NAME_CHARS & set(key[1:]):
        raise argparse.ArgumentTypeError(
            f"{key!r} is not a usable PDF name; keys cannot contain spaces or "
            "any of ( ) < > [ ] { } / %"
        )

    return key, value


def parse_input(token: str) -> InputSpec:
    """Parse a ``FILE`` or ``FILE:1-3,7`` command-line token.

    The page selection is separated by a colon, which Windows forbids in a
    filename, so no real file can be mistaken for a selection there. That is
    not true on POSIX, where a colon is an ordinary filename character, so an
    existing file always wins over reading the token as a selection.

    A Windows drive letter is part of the path rather than a separator, so
    ``C:1`` is the file ``1`` relative to drive C, not page 1 of a file
    called ``C``.
    """
    if not token.strip():
        raise argparse.ArgumentTypeError("empty file argument")

    head, colon, tail = token.rpartition(":")

    # A Windows drive-relative path is a single letter and a colon, and
    # rpartition has already consumed that colon, so a one-character head is a
    # drive rather than a file name. Only real inputs end in .pdf, so no
    # usable file name is this short.
    is_drive = len(head) == 1 and head.isalpha()

    if not (colon and tail) or is_drive or Path(token).exists():
        return InputSpec(Path(token))

    try:
        selection = PageSelection.parse(tail)
    except ValueError as exc:
        # A tail with no digit in it is not a mangled selection, it is just
        # part of a filename that does not exist. Saying so beats explaining
        # a syntax mistake the user may not have been making at all.
        if not any(character.isdigit() for character in tail):
            return InputSpec(Path(token))
        raise argparse.ArgumentTypeError(
            f"{token!r}: {exc}. Expected something like ':1', ':1-3', "
            "':1-3,7', ':5-', or ':-1'."
        ) from exc

    if not head:
        raise argparse.ArgumentTypeError(
            f"missing file name before page selection: {token!r}"
        )

    return InputSpec(Path(head), selection)
