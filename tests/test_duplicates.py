"""Recognising the same file, or the same pages, supplied more than once."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from support import page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def test_repeated_input_is_merged_once(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    one = pdf("dup/one.pdf", 2)

    assert run(str(one), str(one), "-o", str(tmp_path / "d1.pdf")).returncode == 0
    assert page_count(tmp_path / "d1.pdf") == 2


def test_repeated_input_warns(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    one = pdf("dup/one.pdf", 2)

    result = run(str(one), str(one), "-o", str(tmp_path / "d1b.pdf"), "-f")

    assert "duplicate" in result.stderr.lower()


def test_relative_and_absolute_spellings_are_the_same_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    one = pdf("dup/one.pdf", 2)
    out = tmp_path / "d2.pdf"

    # run() starts in tmp_path, so the first token is genuinely relative.
    assert run("dup/one.pdf", str(one), "-o", str(out)).returncode == 0
    assert page_count(out) == 2


def test_dotted_relative_path_is_the_same_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("dup/one.pdf", 2)
    out = tmp_path / "d3.pdf"

    assert run("./dup/../dup/one.pdf", "-o", str(out)).returncode == 0
    assert page_count(out) == 2


def test_case_variant_collapses_only_on_case_insensitive_filesystems(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    one = pdf("dup/one.pdf", 2)

    if os.name == "nt":
        # The spelling differs, the file does not.
        variant = str(tmp_path / "DUP" / "ONE.pdf")
        expected = 2
    else:
        # Here the spelling really is a second file, so both get merged.
        variant = str(pdf("DUP/ONE.pdf", 2))
        expected = 4

    out = tmp_path / "d6.pdf"

    assert run(str(one), variant, "-o", str(out)).returncode == 0
    assert page_count(out) == expected


def test_hardlink_to_the_same_file_is_merged_once(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    one = pdf("dup/one.pdf", 2)
    link = tmp_path / "dup" / "hard.pdf"

    try:
        os.link(one, link)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"filesystem does not support hardlinks: {exc}")

    out = tmp_path / "d7.pdf"

    assert run(str(one), str(link), "-o", str(out)).returncode == 0
    assert page_count(out) == 2


def test_directory_given_twice_is_merged_once(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("docs/a.pdf", 1)
    pdf("docs/b.pdf", 3)
    docs = tmp_path / "docs"
    out = tmp_path / "d4.pdf"

    assert run(str(docs), str(docs), "-o", str(out)).returncode == 0
    assert page_count(out) == 4


def test_directory_plus_one_of_its_own_files_is_merged_once(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("docs/a.pdf", 1)
    pdf("docs/b.pdf", 3)
    docs = tmp_path / "docs"
    out = tmp_path / "d5.pdf"

    assert run(str(docs), str(docs / "a.pdf"), "-o", str(out)).returncode == 0
    assert page_count(out) == 4


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ("1-2", "1-2", 2),
        ("01-02", "1-2", 2),
        ("1-2,4", "4,1-2", 3),
        ("3", "3", 1),
        ("1-2", "3-4", 4),
        # A whole file is deliberately distinct from any range over it.
        ("1-2", None, 7),
        # Ranges are not merged, because comparing them needs the page count.
        ("1-3", "1-2,3", 6),
        ("-1", "-1", 1),
        ("4-", "4-", 2),
    ],
)
def test_duplicate_selection_handling(
    merge_count: Callable[..., int],
    pdf: Callable[..., Path],
    first: str,
    second: str | None,
    expected: int,
) -> None:
    five = pdf("sel/five.pdf", 5)
    tokens = [f"{five}:{first}"]
    tokens += [str(five) if second is None else f"{five}:{second}"]

    assert merge_count(*tokens) == expected


def test_multi_part_selection_from_one_input(
    merge_count: Callable[..., int],
    pdf: Callable[..., Path],
) -> None:
    five = pdf("sel/five.pdf", 5)

    assert merge_count(f"{five}:1-2,3,5") == 4
