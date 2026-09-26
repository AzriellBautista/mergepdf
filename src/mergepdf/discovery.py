"""Finding, filtering and ordering the PDFs named on the command line.

Discovery deliberately gathers every problem it meets rather than raising on
the first one, so a run over a mixed directory can tell the user about all the
unusable inputs at once instead of one per attempt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from .errors import InputError
from .identity import identity
from .inputs import InputSpec
from .logs import LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

Order = Literal["none", "name", "created", "modified"]
Direction = Literal["asc", "desc"]

PDF_SUFFIX = ".pdf"

_SORT_ORDERS: tuple[Order, ...] = ("none", "name", "created", "modified")


def _is_pdf(path: Path) -> bool:
    return path.suffix.casefold() == PDF_SUFFIX


def _iter_pdfs(
    directory: Path,
    seen: set[str],
    *,
    recursive: bool,
) -> Iterator[Path]:
    """Yield the PDFs in a directory in a stable, platform-independent order.

    ``seen`` holds the identity of every directory already walked. Without it a
    symlink or Windows junction pointing at an ancestor recurses until the
    interpreter gives up, which surfaces as a RecursionError rather than
    anything a user can act on.
    """
    key = identity(directory)

    if key in seen:
        LOGGER.debug("Not re-entering already-walked directory: %s", directory)
        return

    seen.add(key)

    try:
        entries = sorted(
            directory.iterdir(),
            key=lambda entry: os.path.normcase(entry.name),
        )
    except OSError as exc:
        raise InputError(f"Cannot read directory {directory}: {exc}") from exc

    for entry in entries:
        if entry.is_dir():
            if recursive:
                yield from _iter_pdfs(entry, seen, recursive=recursive)
        elif _is_pdf(entry):
            yield entry


def find_pdfs(path: Path, *, recursive: bool) -> list[Path]:
    """Return the PDF files contributed by a single input path."""
    if not path.exists():
        raise InputError(f"Path not found: {path}")

    if path.is_file():
        if not _is_pdf(path):
            raise InputError(
                f"Not a PDF file: {path} (expected a {PDF_SUFFIX} extension)"
            )
        return [path]

    if not path.is_dir():
        raise InputError(f"Not a regular file or directory: {path}")

    return list(_iter_pdfs(path, set(), recursive=recursive))


@dataclass(slots=True)
class Discovery:
    """The outcome of scanning every supplied input."""

    specs: list[InputSpec] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def collect_pdfs(
    inputs: Iterable[InputSpec],
    *,
    recursive: bool,
    outfile: Path | None = None,
) -> Discovery:
    """Scan inputs, gathering every problem instead of failing on the first."""
    discovery = Discovery()
    excluded = identity(outfile) if outfile is not None else None

    for spec in inputs:
        LOGGER.debug("Processing input: %s", spec.display)

        if spec.selection is not None and spec.path.is_dir():
            discovery.problems.append(
                f"Page selection {spec.selection.raw!r} cannot be applied to "
                f"the directory {spec.path}"
            )
            continue

        try:
            found = find_pdfs(spec.path, recursive=recursive)
        except InputError as exc:
            LOGGER.debug("Discarding input %s", spec.display, exc_info=True)
            discovery.problems.append(str(exc))
            continue

        specs = [InputSpec(pdf, spec.selection) for pdf in found]
        repeated = 0

        if excluded is not None:
            kept: list[InputSpec] = []

            for candidate in specs:
                if identity(candidate.path) == excluded:
                    repeated += 1
                    continue
                kept.append(candidate)

            specs = kept

        if spec.path.is_dir():
            LOGGER.info(
                "Found %d PDF file%s in %s",
                len(specs),
                "" if len(specs) == 1 else "s",
                spec.path,
            )

        if repeated:
            LOGGER.debug(
                "Ignored %d existing copy of the output in %s",
                repeated,
                spec.path,
            )

        discovery.specs.extend(specs)

    return discovery


def remove_duplicates(specs: Iterable[InputSpec]) -> list[InputSpec]:
    """Drop repeated (file, page selection) pairs, keeping the first."""
    result: list[InputSpec] = []
    seen: set[tuple[str, str]] = set()

    for spec in specs:
        key = spec.key

        if key in seen:
            LOGGER.warning("Skipping duplicate input: %s", spec.display)
            continue

        seen.add(key)
        result.append(spec)

    return result


def _birth_time(path: Path) -> float:
    info = path.stat()
    birth = getattr(info, "st_birthtime", None)

    if birth is not None:
        return float(birth)

    if os.name != "nt":
        LOGGER.debug(
            "%s has no birth time on this platform; using st_ctime, which "
            "reflects the last inode change rather than creation",
            path,
        )

    # st_ctime is deprecated only in that its meaning on Windows is changing.
    # This branch is the non-Windows fallback, where it is the inode change
    # time and is the closest portable stand-in for a creation time.
    return info.st_ctime  # ty: ignore[deprecated]


def sort_pdfs(
    specs: list[InputSpec],
    order: Order,
    direction: Direction,
) -> list[InputSpec]:
    """Sort inputs, always with a deterministic tiebreaker."""
    if order == "none":
        return list(specs)

    if order not in _SORT_ORDERS:
        raise InputError(f"Unsupported order: {order}")

    def primary(spec: InputSpec) -> float | str:
        if order == "name":
            return os.path.normcase(str(spec.path))
        if order == "created":
            return _birth_time(spec.path)
        return spec.path.stat().st_mtime

    # The secondary key makes the ordering total, so equal timestamps or
    # identical basenames in different directories never sort arbitrarily.
    return sorted(
        specs,
        key=lambda spec: (primary(spec), identity(spec.path)),
        reverse=direction == "desc",
    )
