"""Combining the selected pages of every input into one PDF.

This is the only module that talks to pypdf's reader and writer. It also owns
the per-file error policy: whether a failure aborts the run or just skips that
file is decided here, in one place, rather than at each call site.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pypdf import PdfReader, PdfWriter

from ._version import __version__
from .errors import InputError, MergePdfError, PdfError
from .logs import LOGGER
from .output import write_atomically

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from .inputs import InputSpec


@dataclass(slots=True)
class MergeResult:
    """What one merge job actually produced."""

    added: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    pages: int = 0
    title: str | None = None
    author: str | None = None


def _outline_name(spec: InputSpec, used: dict[str, int]) -> str:
    """Return a unique outline name for one input."""
    name = spec.outline_name
    count = used.get(name, 0) + 1
    used[name] = count
    return name if count == 1 else f"{name} ({count})"


def _pages_for(spec: InputSpec, total: int) -> list[int]:
    """Return the 0-based indices this spec contributes, warning about clamping."""
    if spec.selection is None:
        return list(range(total))

    pages, warnings = spec.selection.resolve(total)

    for warning in warnings:
        LOGGER.warning("%s: %s", spec.display, warning)

    return pages


def _copy_first_metadata(result: MergeResult, reader: PdfReader) -> None:
    """Take the title and author from the first input that carries them."""
    if result.added or not reader.metadata:
        return

    title = reader.metadata.get("/Title")
    author = reader.metadata.get("/Author")
    result.title = str(title) if title else None
    result.author = str(author) if author else None


def _output_metadata(
    result: MergeResult,
    metadata: Sequence[tuple[str, str]],
) -> dict[str, str]:
    """Build the metadata dict for the output.

    Applied last so an explicit ``--metadata`` wins over both the values copied
    from the first input and mergepdf's own defaults. Repeating a key is
    last-wins, which is the usual convention for a repeatable flag and lets a
    later flag override an earlier one.
    """
    values: dict[str, str] = {
        "/Producer": f"mergepdf {__version__}",
        "/Creator": f"mergepdf {__version__}",
    }

    if result.title:
        values["/Title"] = result.title
    if result.author:
        values["/Author"] = result.author

    for key, value in metadata:
        if key in values:
            LOGGER.debug("%s set again, overriding the earlier value", key)
        values[key] = value

    return values


@dataclass(frozen=True, slots=True)
class MergeOptions:
    """The switches that change how pages are combined.

    Grouped rather than passed as three loose booleans because a call site
    reading ``merge_pdfs(a, b, True, False, True)`` gives no way to tell which
    flag is which, and a transposed pair is silent.
    """

    skip_invalid: bool = False
    add_outlines: bool = True
    import_outlines: bool = True


@dataclass(slots=True)
class _Run:
    """The mutable state one merge accumulates across all its inputs.

    Bundling it keeps the per-file helper's parameter list to the spec being
    processed plus this, rather than the writer, the result, the outline
    title counts and the options.
    """

    writer: PdfWriter
    result: MergeResult
    options: MergeOptions
    used_titles: dict[str, int]


_DEFAULT_OPTIONS = MergeOptions()


def _no_pages_reason(spec: InputSpec) -> str:
    return (
        "page selection matched no pages"
        if spec.selection is not None
        else "document contains no pages"
    )


def _discard(run: _Run, spec: InputSpec, reason: str) -> None:
    LOGGER.warning("Skipping %s: %s", spec.display, reason)
    run.result.skipped.append((spec.display, reason))


def _fail(run: _Run, spec: InputSpec, exc: Exception) -> None:
    """Report a per-file failure, or re-raise it if skipping is not allowed.

    This is the single place that turns an arbitrary exception from pypdf into a
    decision, which is why the caller catches Exception broadly: a malformed PDF
    can surface as almost any error type, and enumerating them would only move
    the crash somewhere less predictable.
    """
    reason = str(exc).strip() or exc.__class__.__name__

    if run.options.skip_invalid:
        _discard(run, spec, reason)
        return

    raise PdfError(f"{spec.display}: {reason}") from exc


def _append(run: _Run, spec: InputSpec) -> None:
    """Copy one spec's pages into the writer, or report why it cannot be."""
    reader: PdfReader | None = None

    # Everything touching this file is guarded, so a password protected or
    # otherwise unreadable PDF is reported by name instead of escaping as an
    # anonymous failure. The reader is closed as soon as its pages are copied,
    # so a large merge cannot exhaust the process handle limit.
    try:
        reader = PdfReader(str(spec.path), strict=False)
        pages = _pages_for(spec, len(reader.pages))

        if not pages:
            _fail(run, spec, ValueError(_no_pages_reason(spec)))
            return

        LOGGER.debug("%s contributes %d page(s)", spec.display, len(pages))

        run.writer.append(
            reader,
            outline_item=(
                _outline_name(spec, run.used_titles)
                if run.options.add_outlines
                else None
            ),
            pages=pages,
            import_outline=run.options.import_outlines,
        )

        _copy_first_metadata(run.result, reader)
        run.result.added.append(spec.display)
        run.result.pages += len(pages)
    except MergePdfError:
        raise
    except Exception as exc:  # noqa: BLE001 - see _fail()
        _fail(run, spec, exc)
    finally:
        if reader is not None:
            with contextlib.suppress(Exception):
                reader.close()


def merge_pdfs(
    specs: list[InputSpec],
    outfile: Path,
    *,
    options: MergeOptions = _DEFAULT_OPTIONS,
    metadata: Sequence[tuple[str, str]] = (),
) -> MergeResult:
    """Merge every spec into outfile and report what happened."""
    if not specs:
        raise InputError("No PDF files to merge.")

    result = MergeResult()
    run = _Run(PdfWriter(), result, options, {})

    try:
        for spec in specs:
            LOGGER.info("Adding %s", spec.display)
            _append(run, spec)

        if not result.added:
            raise PdfError(
                "Every input was skipped, so there is nothing to write. "
                "Re-run without --skip-invalid to see the first failure."
            )

        run.writer.add_metadata(_output_metadata(result, metadata))

        LOGGER.info("Writing %s", outfile)
        write_atomically(run.writer, outfile)
    finally:
        run.writer.close()

    return result
