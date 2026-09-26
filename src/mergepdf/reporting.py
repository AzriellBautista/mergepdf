"""Presenting results to the user.

Diagnostics go through the logger and land on stderr, so they can be silenced
with ``--quiet`` or turned up with ``-v``. The dry-run listing is the one
exception: it is the thing the user asked for rather than a diagnostic, so it
goes to stdout and ignores ``--quiet``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .logs import LOGGER

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from .jobs import Job
    from .merge import MergeResult


def plural(count: int, noun: str) -> str:
    """Return ``"1 file"`` or ``"3 files"``."""
    return f"{count} {noun}{'' if count == 1 else 's'}"


def report_problems(problems: Sequence[str], *, skip_invalid: bool) -> None:
    """Log collected input problems as warnings or errors."""
    if not problems:
        return

    log = LOGGER.warning if skip_invalid else LOGGER.error
    log("%s could not be used:", plural(len(problems), "input"))

    for problem in problems:
        log("  %s", problem)


def print_dry_run(jobs: Sequence[Job], *, force: bool) -> None:
    """Write the merge plan to stdout.

    This is the requested result of --dry-run rather than a diagnostic, so it
    goes to stdout and is not suppressed by --quiet.
    """
    for number, job in enumerate(jobs, start=1):
        if len(jobs) > 1:
            print(f"Job {number} of {len(jobs)}")
            print()

        print(f"Would merge {plural(len(job.specs), 'PDF file')} into:")
        print()

        for index, spec in enumerate(job.specs, start=1):
            print(f"{index:>4}. {spec.display}")

        print()
        print(f"Output: {job.outfile}")

        if job.outfile.exists():
            verb = "overwritten." if force else "left untouched."
            print(f"Note: the output exists and would be {verb}")

        print()
        print("Dry run: no output file was created.")
        print()


def log_result(result: MergeResult, outfile: Path) -> None:
    """Report what one merge produced."""
    LOGGER.info(
        "Merged %s (%s) into %s",
        plural(len(result.added), "PDF file"),
        plural(result.pages, "page"),
        outfile,
    )

    if result.skipped:
        LOGGER.warning(
            "%s skipped. Re-run without --skip-invalid to fail on them.",
            plural(len(result.skipped), "file"),
        )
