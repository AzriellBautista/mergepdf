"""Defining and parsing the command line.

The parser is assembled from small ``_add_*`` functions rather than one long
``build_parser``, so each group of related flags reads on its own and adding a
flag means editing one place.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ._version import __version__
from .inputs import InputSpec, parse_input, parse_metadata
from .logs import LOGGER
from .sources import parse_pattern

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .discovery import Direction, Order

_EPILOG = """\
Examples:

  Merge specific files in the supplied order:
    mergepdf 03.pdf 01.pdf 02.pdf

  Merge all PDFs in a directory:
    mergepdf .\\documents -o merged.pdf

  Recursively find PDFs:
    mergepdf .\\documents --recursive

  Read the list of files from a text file:
    mergepdf --list pdfs.txt

  Include page selections in the list file:
    mergepdf -L pages.txt

  Match files with a glob:
    mergepdf -P "*.pdf"

  Match in subdirectories as well:
    mergepdf -P "docs/*.pdf" --recursive

  Match everywhere, without -r, by spelling it out:
    mergepdf -P "**/scan-*.pdf"

  Mix every kind of input, merged positionals first:
    mergepdf cover.pdf -L body.txt -P "appendix/*.pdf"

  Sort alphabetically:
    mergepdf .\\documents --order name

  Sort newest first:
    mergepdf .\\documents --order modified --sort desc

  First three pages and page 7 of one file:
    mergepdf "report.pdf:1-3,7"

  Pages 1 to 4 of one file, plus the last two of another:
    mergepdf "front.pdf:1-4" "back.pdf:-2"

  Preview without writing anything:
    mergepdf .\\documents --recursive --dry-run

  Merge each folder into its own file:
    mergepdf .\\archive\\2023 .\\archive\\2024 --output-dir .\\out

  Carry on when one file is broken:
    mergepdf .\\documents --recursive --skip-invalid

  Stamp metadata on the output:
    mergepdf .\\documents -o out.pdf --metadata /Title="Q1 Report"

  Overwrite an existing output file:
    mergepdf .\\documents -o merged.pdf --force

Exit codes: 0 success, 1 input error, 2 usage error, 3 output
exists, 4 PDF error, 5 output error, 130 interrupted.

Use -vv when troubleshooting to see more detail. There is nothing
beyond -vv; extra -v flags do not raise the level any further.
"""


class MergePdfArguments(argparse.Namespace):
    """The parsed command line.

    argparse fills these attributes in place, so the annotations describe the
    result rather than anything constructed by hand.
    """

    file: list[InputSpec]
    list_path: list[Path]
    pattern: list[str]
    outfile: Path
    output_dir: Path | None
    recursive: bool
    order: Order
    sort: Direction
    force: bool
    dry_run: bool
    skip_invalid: bool
    bookmarks: bool
    import_outlines: bool
    metadata: list[tuple[str, str]]
    quiet: bool
    verbose: int


def _add_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "file",
        metavar="FILE",
        nargs="*",
        type=parse_input,
        help=(
            "PDF files and/or directories containing PDF files. A single file "
            "may be narrowed to some pages by appending a colon and a "
            "selection: ':1-3,7', ':5-' through the last page, ':-2' the last "
            "two. Note that '-2' is a count, not an index. Quote the argument "
            "if your shell would split it on the comma. Optional, as long as "
            "--list or --pattern supplies at least one input."
        ),
    )

    parser.add_argument(
        "-L",
        "--list",
        metavar="FILE",
        action="append",
        default=None,
        type=Path,
        dest="list_path",
        help=(
            "Read inputs from a text file, one per line, instead of (or as "
            "well as) FILE arguments. Blank lines and lines starting with '#' "
            "are ignored. Each remaining line takes the same syntax as a FILE "
            "argument, so a page selection may be included. Paths are relative "
            "to the current directory, not to the list file. Repeat for more "
            "than one list; later lists are appended after earlier ones."
        ),
    )

    parser.add_argument(
        "-P",
        "--pattern",
        metavar="GLOB",
        action="append",
        default=None,
        type=parse_pattern,
        help=(
            "Find inputs with a glob, such as 'docs/*.pdf' or '**/scan-*.pdf'. "
            "The leading directory components, up to the first one holding a "
            "'*', '?' or '[', are the directory to scan. A wildcard in a "
            "directory component ('a*/x.pdf') sends the whole match to the "
            "current directory instead, and a wildcard in the last component "
            "('odd/report[12].pdf') is matched within its directory. Matches "
            "are sorted so repeated runs agree. With --recursive a pattern "
            "that does not already contain '**' also matches in "
            "subdirectories. A pattern that matches nothing is an error, even "
            "with --skip-invalid. Repeat for more than one pattern. Cannot be "
            "combined with --output-dir."
        ),
    )


def _add_output_target(parser: argparse.ArgumentParser) -> None:
    output = parser.add_mutually_exclusive_group()

    output.add_argument(
        "-o",
        "--outfile",
        metavar="OUTFILE",
        type=Path,
        default=Path("merged.pdf"),
        help=(
            "Path of the output PDF. Defaults to 'merged.pdf' in the current "
            "directory. Cannot be combined with --output-dir."
        ),
    )

    output.add_argument(
        "-d",
        "--output-dir",
        metavar="DIR",
        type=Path,
        default=None,
        help=(
            "Write one merged PDF per supplied directory, named after that "
            "directory and placed in DIR. Individual FILE arguments are not "
            "allowed in this mode, and neither are --list or --pattern, which "
            "name individual files rather than directories."
        ),
    )


def _add_discovery(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help=(
            "Descend into subdirectories when a directory is supplied. Without "
            "this, only PDFs directly inside each supplied directory are "
            "included. A --pattern that does not already contain '**' also "
            "starts matching in subdirectories."
        ),
    )

    parser.add_argument(
        "--order",
        choices=("none", "name", "created", "modified"),
        default="none",
        help=(
            "How discovered PDFs are ordered before merging. 'none' keeps the "
            "supplied or discovered order and is the default. 'name' sorts by "
            "path. 'created' sorts by file creation time. 'modified' sorts by "
            "last modification time."
        ),
    )

    parser.add_argument(
        "--sort",
        choices=("asc", "desc"),
        default="asc",
        help=(
            "Sort direction for --order name, created or modified. 'asc' runs "
            "oldest or A-Z first, 'desc' reverses it. Ignored when --order is "
            "'none'."
        ),
    )


def _add_output_behaviour(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "List the files that would be merged, in their final order, "
            "without creating or modifying the output. The output file is not "
            "checked for existence in this mode."
        ),
    )

    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help=(
            "Skip inputs that cannot be read and PDFs that fail to parse "
            "instead of aborting, logging a warning for each. If every input "
            "fails, nothing is written."
        ),
    )


def _add_bookmarks(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-bookmarks",
        dest="bookmarks",
        action="store_false",
        help=(
            "Do not add an outline entry per merged file. By default each "
            "input contributes one top-level bookmark."
        ),
    )

    parser.add_argument(
        "--no-import-outlines",
        dest="import_outlines",
        action="store_false",
        help=(
            "Do not carry over the bookmarks already inside each input PDF. "
            "By default they are imported beneath mergepdf's own entry."
        ),
    )


def _add_metadata(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--metadata",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        type=parse_metadata,
        dest="metadata",
        help=(
            "Set a metadata field on the output, for example "
            "'--metadata /Title=\"Annual Report\"'. The value has a space in "
            "it, so quote it or your shell will split the argument. The "
            "leading slash is optional. Repeat for more than one field; if a "
            "key is repeated the last value wins. Overrides the title and "
            "author copied from the first input, and the Producer and Creator "
            "mergepdf sets by default."
        ),
    )


def _add_verbosity(parser: argparse.ArgumentParser) -> None:
    verbosity = parser.add_mutually_exclusive_group()

    verbosity.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress informational and warning messages. Errors still show.",
    )

    verbosity.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help=(
            "Increase diagnostic output. -v reports progress and -vv adds "
            "mergepdf's internal decisions, plus the originating traceback "
            "when the run fails outright."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the program version and exit.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the mergepdf command."""
    parser = argparse.ArgumentParser(
        prog="mergepdf",
        description=(
            "Merge multiple PDF files into a single PDF.\n"
            "See README.md for page-selection syntax, ordering rules and "
            "worked examples."
        ),
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    _add_inputs(parser)
    _add_output_target(parser)
    _add_discovery(parser)
    _add_output_behaviour(parser)
    _add_bookmarks(parser)
    _add_metadata(parser)
    _add_verbosity(parser)

    return parser


def parse_args(argv: Sequence[str] | None = None) -> MergePdfArguments:
    """Parse argv into a MergePdfArguments namespace.

    The cross-flag checks live here rather than in the parser so that they are
    reported as usage errors, with the usage text, instead of as input errors.
    """
    parser = build_parser()
    args = parser.parse_args(argv, namespace=MergePdfArguments())

    # argparse's "append" action appends to whatever default it is given, so a
    # shared list would accumulate across repeated calls in one process.
    args.metadata = args.metadata or []
    args.list_path = args.list_path or []
    args.pattern = args.pattern or []

    if not args.file and not args.list_path and not args.pattern:
        parser.error(
            "give at least one input: a FILE argument, --list FILE or --pattern GLOB"
        )

    if args.output_dir is not None and (args.list_path or args.pattern):
        parser.error(
            "--output-dir writes one file per supplied directory, but --list "
            "and --pattern name individual files; use FILE arguments naming "
            "directories instead"
        )

    return args


def configure_logging(args: MergePdfArguments) -> None:
    """Set the log level from the verbosity flags."""
    if args.quiet:
        level = logging.ERROR
    elif args.verbose == 0:
        level = logging.WARNING
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def log_arguments(args: MergePdfArguments) -> None:
    """Record the namespace argparse produced.

    This shows how each argument was actually understood, which is where a
    quoting mistake in a page selection or a stray flag becomes visible. The
    resolved file order is logged separately by build_job.
    """
    LOGGER.debug("Arguments: %s", args)
