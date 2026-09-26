"""Filenames that could be mistaken for page selections, and vice versa.

Brackets are legal in filenames everywhere, so a name like ``report[1].pdf``
must never be read as a selection. Colons are the separator, and Windows forbids
them in filenames, which is what makes the syntax unambiguous there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from support import page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess

BRACKETED = [
    ("[1].pdf", 1),
    ("[1-2].pdf", 2),
    ("[[1]].pdf", 1),
    ("a[1].pdf", 1),
    ("x[abc].pdf", 1),
    ("my [file].pdf", 1),
]


@pytest.mark.parametrize(("name", "pages"), BRACKETED)
def test_bracketed_name_is_a_literal_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    name: str,
    pages: int,
) -> None:
    source = pdf(f"odd/{name}", pages)
    out = tmp_path / "odd_out" / name

    assert run(str(source), "-o", str(out)).returncode == 0
    assert page_count(out) == pages


def test_directory_of_bracketed_names_merges(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    for name, pages in BRACKETED:
        pdf(f"odd/{name}", pages)

    out = tmp_path / "odd_all.pdf"

    assert run(str(tmp_path / "odd"), "-o", str(out)).returncode == 0
    assert page_count(out) == sum(pages for _, pages in BRACKETED)


def test_name_ending_in_a_bracket_is_not_split_at_the_last_dot(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # Everything after the final dot is the suffix, so this is not a PDF at all
    # and is refused outright rather than being mistaken for report.pdf.
    odd = pdf("odd/report.pdf[2]", 3)

    result = run(str(odd), "-o", str(tmp_path / "nope.pdf"))

    assert result.returncode == 1
    assert "report.pdf[2]" in result.stderr


def test_old_bracket_syntax_is_no_longer_a_selection(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    five = pdf("sel/five.pdf", 5)

    result = run(f"{five}[1-2]", "-o", str(tmp_path / "nobrace.pdf"))

    assert result.returncode == 1
    assert f"{five.name}[1-2]" in result.stderr


def test_drive_relative_path_is_not_read_as_a_selection(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # ``C:1`` is the file "1" relative to drive C, not page 1 of a file "C".
    result = run("C:1", "-o", str(tmp_path / "drive.pdf"))

    assert result.returncode == 1
