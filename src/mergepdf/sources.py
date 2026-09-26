"""Expanding ``--list`` and ``--pattern`` into input specifications.

argparse can only record *where* inputs came from; working out what they
actually are needs the filesystem, so that step lives here rather than in the
parser. Both sources produce plain :class:`InputSpec` objects, which means
everything downstream — duplicate detection, ordering, the output guards —
treats a listed file and a typed one exactly the same.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import InputError
from .inputs import InputSpec, parse_input

if TYPE_CHECKING:
    from .arguments import MergePdfArguments

# Characters that make a path a pattern rather than a plain name.
_GLOB_CHARS = frozenset("*?[")


def parse_pattern(value: str) -> str:
    """Validate a ``--pattern`` argument, for use as an argparse type.

    Problems with the *shape* of a pattern are reported by argparse as usage
    errors, so the exit code matches a malformed flag rather than a missing
    file. Whether the pattern matches anything is a filesystem question and is
    left to :func:`match_pattern`.
    """
    if not any(char in _GLOB_CHARS for char in value):
        raise argparse.ArgumentTypeError(
            f"not a pattern: {value!r} has none of '*', '?' or '[' in it; give a "
            "glob, or pass a file or directory as a FILE argument"
        )

    if value.startswith(("/", "\\")) or Path(value).is_absolute():
        raise argparse.ArgumentTypeError(
            f"must be relative to the current directory: {value!r}"
        )

    return value


def _split_base(pattern: str) -> tuple[Path, str]:
    """Split a pattern into the directory to scan and the glob to match there.

    The base is the longest run of leading directory components that contain no
    wildcard, so ``docs/sub/*.pdf`` gives ``(docs/sub, *.pdf)`` and
    ``odd/report[12].pdf`` gives ``(odd, report[12].pdf)`` — the bracket belongs
    to the filename, not the directory. A component only counts as a directory
    if a separator follows it, so a wildcard in the final component leaves the
    base where it is. A pattern that begins with a wildcard is matched against
    the working directory.
    """
    parts = re.split(r"[/\\]", pattern)
    directories: list[str] = []
    for part in parts[:-1]:
        if any(char in _GLOB_CHARS for char in part):
            break
        directories.append(part)

    base = Path(*directories) if directories else Path()
    remainder = "/".join(parts[len(directories) :])
    return base, remainder


def _recursive(remainder: str) -> str:
    """Widen a pattern to match at any depth, unless it already says so."""
    if "**" in remainder:
        return remainder

    head, separator, tail = remainder.rpartition("/")
    return f"{head}/**/{tail}" if separator else f"**/{tail}"


def match_pattern(pattern: str, *, recursive: bool) -> list[Path]:
    """Return the files a glob matches, in a deterministic order.

    Ordering matters more here than anywhere else in the tool: a bare
    ``Path.glob`` yields whatever order the filesystem hands back, which would
    make two runs over the same tree produce different output. Sorting by
    case-folded path makes the discovery order stable, after which ``--order``
    can still re-sort it.
    """
    base, remainder = _split_base(pattern)

    if not base.exists():
        raise InputError(f"Path not found: {base}")

    # pathlib wants forward slashes in the pattern itself; a backslash is the
    # Windows directory separator and would be read as one mid-pattern.
    if os.name == "nt":
        remainder = remainder.replace("\\", "/")

    matches = base.glob(_recursive(remainder) if recursive else remainder)
    found = sorted((path for path in matches if path.is_file()), key=_sort_key)

    if not found:
        raise InputError(
            f"Pattern matched no files: {pattern!r}"
            + (" (with --recursive)" if recursive and "**" not in remainder else "")
        )

    return found


def _sort_key(path: Path) -> str:
    return os.path.normcase(str(path))


def read_list(path: Path) -> list[str]:
    """Return the meaningful lines of a list file.

    Blank lines and lines whose first non-space character is ``#`` are skipped,
    so a generated list can carry a header. ``utf-8-sig`` is used because a
    list written on Windows may carry a byte-order mark, which would otherwise
    become part of the first filename.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise InputError(f"Cannot read list file {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"List file is not valid UTF-8: {path}: {exc}") from exc

    return [
        stripped
        for stripped in (line.strip() for line in text.splitlines())
        if stripped and not stripped.startswith("#")
    ]


def _from_list(path: Path) -> list[InputSpec]:
    specs: list[InputSpec] = []

    for number, line in enumerate(read_list(path), start=1):
        try:
            specs.append(parse_input(line))
        except argparse.ArgumentTypeError as exc:
            # Re-raised as an input error rather than a usage error: the command
            # line was well formed, the file the user pointed it at was not.
            raise InputError(f"{path}:{number}: {exc}") from exc

    if not specs:
        raise InputError(f"List file has no entries: {path}")

    return specs


def expand_inputs(args: MergePdfArguments) -> list[InputSpec]:
    """Return every input for this run, from all three sources in order.

    Positional FILE arguments come first, then each ``--list`` in the order
    given, then each ``--pattern``. The order only matters when ``--order`` is
    left at ``none``.
    """
    specs = list(args.file)

    for list_path in args.list_path:
        specs.extend(_from_list(list_path))

    for pattern in args.pattern:
        specs.extend(
            InputSpec(found)
            for found in match_pattern(pattern, recursive=args.recursive)
        )

    return specs
