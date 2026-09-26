"""Validating and writing the output file.

Writing goes through a temporary file in the destination directory followed by
a rename, so an interrupted or failing merge never leaves a half-written PDF
where a good one used to be.
"""

from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import InputError, OutputError, OutputExistsError
from .identity import identity

if TYPE_CHECKING:
    from pypdf import PdfWriter

    from .inputs import InputSpec


def validate_output(
    specs: list[InputSpec],
    outfile: Path,
    *,
    force: bool,
    check_exists: bool = True,
) -> None:
    """Check the output path before doing any expensive work."""
    if outfile.is_dir():
        raise InputError(f"Output path is a directory: {outfile}")

    if identity(outfile) in {spec.key[0] for spec in specs}:
        raise InputError(f"Output file cannot also be an input file: {outfile}")

    if check_exists and outfile.exists() and not force:
        raise OutputExistsError(
            f"Output file already exists: {outfile}\nUse --force to overwrite it."
        )

    if outfile.parent.exists() and not outfile.parent.is_dir():
        raise InputError(f"Output parent is not a directory: {outfile.parent}")


def _target_mode(outfile: Path) -> int:
    """Choose permissions for the new file, respecting an existing target."""
    try:
        return stat.S_IMODE(outfile.stat().st_mode)
    except OSError:
        return 0o644


def write_atomically(writer: PdfWriter, outfile: Path) -> None:
    """Write to a temporary file alongside the target, then rename it in.

    The rename is atomic, so a failure part-way through never leaves a
    truncated PDF behind and never destroys a previous good output.
    """
    try:
        outfile.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(
            f"Cannot create output directory {outfile.parent}: {exc}"
        ) from exc

    mode = _target_mode(outfile)

    try:
        handle, temp_name = tempfile.mkstemp(
            dir=outfile.parent,
            prefix=f".{outfile.name}.",
            suffix=".tmp",
        )
    except OSError as exc:
        raise OutputError(
            f"Cannot create a temporary file beside {outfile}: {exc}"
        ) from exc

    temp_path = Path(temp_name)

    try:
        with os.fdopen(handle, "wb") as stream:
            writer.write(stream)
            stream.flush()
            os.fsync(stream.fileno())

        with contextlib.suppress(OSError):
            temp_path.chmod(mode)

        temp_path.replace(outfile)
    except OSError as exc:
        raise OutputError(f"Cannot write {outfile}: {exc}") from exc
    finally:
        with contextlib.suppress(OSError):
            temp_path.unlink(missing_ok=True)
