"""Exit codes and the exception hierarchy for expected failures.

Every failure a user can reasonably cause is one of these, and each carries the
exit code the process should return. Keeping the whole mapping in one module
means the answer to "what does this failure exit with?" is readable on one
screen, and the CLI never has to map exception types to numbers inline.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes returned by mergepdf.

    0    success
    1    usage or input error (bad path, bad page selection, no input files)
    2    argparse usage error
    3    the output already exists and --force was not given
    4    a PDF could not be read or written
    5    the output could not be written (permissions, disk, and similar)
    130  interrupted by the user
    """

    SUCCESS = 0
    ERROR = 1
    OUTPUT_EXISTS = 3
    PDF_ERROR = 4
    IO_ERROR = 5
    INTERRUPTED = 130


class MergePdfError(Exception):
    """Base class for expected, user-facing failures."""

    exit_code: ExitCode = ExitCode.ERROR


class InputError(MergePdfError):
    """A supplied path or page selection cannot be used."""

    exit_code = ExitCode.ERROR


class OutputExistsError(MergePdfError):
    """The output already exists and overwriting was not requested."""

    exit_code = ExitCode.OUTPUT_EXISTS


class PdfError(MergePdfError):
    """A PDF could not be parsed or produced."""

    exit_code = ExitCode.PDF_ERROR


class OutputError(MergePdfError):
    """The output file could not be written."""

    exit_code = ExitCode.IO_ERROR
