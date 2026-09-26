"""Parsing and resolving page selections such as ``1-3,7,10-``.

Selections are resolved against a page count, so this module never touches the
filesystem. It only turns text into indices, which keeps the awkward edge cases
(0 is invalid, ``:-2`` counts from the end, out-of-range clamps) testable
without writing any PDFs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# One component of a page selection: "5", "2-7", "9-", or "-3".
_PAGE_PART_RE = re.compile(r"^(?P<start>-?\d+)(?P<dash>-)?(?P<stop>\d*)$")


@dataclass(frozen=True, slots=True)
class PagePart:
    """A single component of a page selection.

    Page numbers are 1-based and inclusive, matching what a reader sees in a
    PDF viewer. A leading minus counts backwards from the last page.
    """

    raw: str
    start: int
    stop: int | None
    from_end: bool = False

    def resolve(self, total: int) -> range:
        """Return the 0-based page indices this part selects.

        Bounds are clamped the way slice() clamps them, so a selection that
        runs past the end of a short document yields only the pages that
        actually exist rather than an out-of-range index.
        """
        if self.from_end:
            start, stop = total + self.start, total
        else:
            start = self.start - 1
            stop = self.stop if self.stop is not None else total

        return range(*slice(start, stop).indices(total))


@dataclass(frozen=True, slots=True)
class PageSelection:
    """A page selection such as ``1-3,7,10-``."""

    parts: tuple[PagePart, ...]
    raw: str

    @classmethod
    def parse(cls, text: str) -> PageSelection:
        """Build a selection from text, raising ValueError if it is malformed."""
        text = text.strip()

        if not text:
            raise ValueError("empty page selection")

        parts: list[PagePart] = []

        for raw_chunk in text.split(","):
            chunk = raw_chunk.strip()
            match = _PAGE_PART_RE.match(chunk)

            if match is None:
                raise ValueError(f"invalid page selection: {chunk!r}")

            start = int(match.group("start"))
            has_dash = match.group("dash") is not None
            stop_text = match.group("stop")
            stop = int(stop_text) if has_dash and stop_text else None

            if start == 0 or stop == 0:
                raise ValueError(
                    f"page numbers are 1-based, so 0 is not valid: {chunk!r}"
                )

            if start < 0:
                if has_dash:
                    raise ValueError(
                        f"a count-from-the-end part cannot have an end: {chunk!r}"
                    )
                parts.append(PagePart(chunk, start, None, from_end=True))
                continue

            if stop is None and not has_dash:
                # A bare "5" means page 5, not "page 5 to the end".
                stop = start
            elif stop is not None and stop < start:
                raise ValueError(f"page range ends before it starts: {chunk!r}")

            parts.append(PagePart(chunk, start, stop))

        return cls(tuple(parts), text)

    def resolve(self, total: int) -> tuple[list[int], list[str]]:
        """Return the 0-based indices to keep, plus warnings about clamping."""
        selected: list[int] = []
        seen: set[int] = set()
        warnings: list[str] = []
        duplicates: list[int] = []

        for part in self.parts:
            requested = part.resolve(total)

            if not requested:
                warnings.append(
                    f"page selection {part.raw!r} is outside the document "
                    f"({total} page{'' if total == 1 else 's'})"
                )
                continue

            for index in requested:
                if index in seen:
                    duplicates.append(index + 1)
                    continue

                seen.add(index)
                selected.append(index)

        if duplicates:
            warnings.append(
                "duplicate pages ignored: "
                + ", ".join(str(page) for page in sorted(set(duplicates)))
            )

        return selected, warnings
