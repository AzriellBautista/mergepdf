"""The mergepdf entry point.

This module is only the top-level flow: parse, log, plan, merge, report. The
work itself lives in the modules it coordinates, so a change to page selection
or discovery never touches the file that decides the exit code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .arguments import configure_logging, log_arguments, parse_args
from .errors import ExitCode, MergePdfError
from .jobs import build_jobs
from .logs import LOGGER
from .merge import MergeOptions, merge_pdfs
from .reporting import log_result, print_dry_run

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .arguments import MergePdfArguments
    from .jobs import Job

_INTERRUPTED = ExitCode.INTERRUPTED


def _merge_one(job: Job, args: MergePdfArguments) -> ExitCode | None:
    """Merge a single job, returning its exit code or None on success.

    Returns None rather than SUCCESS so the caller can tell "this worked" apart
    from "nothing to do", and keep the first failure seen across several jobs.
    """
    try:
        result = merge_pdfs(
            list(job.specs),
            job.outfile,
            options=MergeOptions(
                skip_invalid=args.skip_invalid,
                add_outlines=args.add_outlines,
                import_outlines=args.import_outlines,
            ),
            metadata=args.metadata,
        )
    except MergePdfError as exc:
        LOGGER.error("%s", exc)

        if exc.__cause__ is not None:
            LOGGER.debug(
                "Caused by %s", type(exc.__cause__).__name__, exc_info=exc.__cause__
            )

        return exc.exit_code
    except Exception:  # noqa: BLE001 - a bad file must not lose the other jobs
        LOGGER.debug("Unexpected failure", exc_info=True)
        LOGGER.error("Failed to write %s", job.outfile)
        return ExitCode.PDF_ERROR

    log_result(result, job.outfile)
    return None


def main(argv: Sequence[str] | None = None) -> ExitCode:
    """Run mergepdf and return the process exit code."""
    args = parse_args(argv)
    configure_logging(args)
    log_arguments(args)

    if args.order == "none" and args.sort != "asc":
        LOGGER.warning(
            "--sort has no effect when --order is 'none'; files are merged in "
            "the order they were supplied or discovered"
        )

    try:
        jobs = build_jobs(args)
    except MergePdfError as exc:
        LOGGER.error("%s", exc)
        return exc.exit_code
    except OSError as exc:
        LOGGER.error("%s", exc)
        return ExitCode.IO_ERROR
    except KeyboardInterrupt:
        LOGGER.error("Interrupted before any work was done.")
        return _INTERRUPTED

    if args.dry_run:
        print_dry_run(jobs, force=args.force)
        return ExitCode.SUCCESS

    failure: ExitCode | None = None

    for job in jobs:
        try:
            failure = _merge_one(job, args) or failure
        except KeyboardInterrupt:
            LOGGER.error("Interrupted; %s was not written.", job.outfile)
            return _INTERRUPTED

    return failure or ExitCode.SUCCESS
