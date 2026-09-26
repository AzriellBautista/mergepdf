"""Turning parsed arguments into the list of files mergepdf will produce.

One invocation can mean several outputs, because ``--output-dir`` merges each
supplied directory separately. A job is that pairing: one output path and the
ordered inputs that go into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .discovery import collect_pdfs, remove_duplicates, sort_pdfs
from .errors import InputError
from .identity import identity
from .logs import LOGGER
from .output import validate_output
from .reporting import report_problems
from .sources import expand_inputs

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from .arguments import MergePdfArguments
    from .inputs import InputSpec


@dataclass(frozen=True, slots=True)
class Job:
    """One output file and the inputs that go into it."""

    outfile: Path
    specs: tuple[InputSpec, ...]


def build_job(
    args: MergePdfArguments,
    inputs: Sequence[InputSpec],
    outfile: Path,
) -> Job:
    """Resolve one output file: discover, filter, sort, then validate."""
    discovery = collect_pdfs(inputs, recursive=args.recursive, outfile=outfile)
    report_problems(discovery.problems, skip_invalid=args.skip_invalid)

    specs = remove_duplicates(discovery.specs)

    if not specs:
        raise InputError("No PDF files found.")

    specs = sort_pdfs(specs, args.order, args.sort)

    LOGGER.debug("Final order (%s, %s):", args.order, args.sort)
    for index, spec in enumerate(specs, start=1):
        LOGGER.debug("%d. %s", index, spec.display)

    # Everything has been checked and reported by this point, so a run with bad
    # inputs fails once with the full list of problems rather than one per try.
    if discovery.problems and not args.skip_invalid:
        raise InputError(
            "Aborting because some inputs could not be used. "
            "Pass --skip-invalid to merge the rest anyway."
        )

    validate_output(
        specs,
        outfile,
        force=args.force,
        check_exists=not args.dry_run,
    )

    return Job(outfile, tuple(specs))


def build_jobs(args: MergePdfArguments) -> list[Job]:
    """Work out every output this invocation will produce."""
    inputs = expand_inputs(args)

    if args.output_dir is None:
        return [build_job(args, inputs, args.outfile)]

    jobs: list[Job] = []
    claimed: dict[str, Path] = {}

    for spec in inputs:
        if not spec.path.is_dir():
            raise InputError(f"--output-dir requires directories, but got: {spec.path}")
        if spec.selection is not None:
            raise InputError(
                f"--output-dir cannot be combined with a page selection: {spec.display}"
            )

        outfile = args.output_dir / f"{spec.path.resolve().name}.pdf"
        clash = claimed.get(identity(outfile))

        if clash is not None:
            raise InputError(
                f"{spec.path} and {clash} would both be written to {outfile}"
            )

        claimed[identity(outfile)] = spec.path
        jobs.append(build_job(args, [spec], outfile))

    return jobs
