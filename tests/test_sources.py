"""The ``--list`` and ``--pattern`` input sources.

Both add files to a run without naming each one on the command line, so these
tests concentrate on the parts that are easy to get wrong: what counts as a
pattern, how ``--recursive`` changes one, the order files end up in, and which
exit code each kind of mistake produces.

The ``run`` fixture works from ``tmp_path``, so every relative path used here
resolves against it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from support import listed, page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


@pytest.fixture
def tree(pdf: Callable[..., Path]) -> None:
    """Build a small tree: two at the top, one in docs, two in docs/deep."""
    pdf("top/a.pdf", 1)
    pdf("top/b.pdf", 1)
    pdf("docs/c.pdf", 2)
    pdf("docs/deep/d.pdf", 1)
    pdf("docs/deep/e.pdf", 1)


def write_list(path: Path, *lines: str) -> Path:
    """Write a list file, one entry per line."""
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ------------------------------------------------------------------ --list


def test_list_merges_the_files_it_names(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    pdf("b.pdf", 2)
    listing = write_list(tmp_path / "pdfs.txt", "a.pdf", "b.pdf")
    out = tmp_path / "out.pdf"

    result = run("-L", str(listing), "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert page_count(out) == 3


def test_list_keeps_the_order_of_the_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        pdf(name, 1)
    listing = write_list(tmp_path / "pdfs.txt", "c.pdf", "a.pdf", "b.pdf")

    result = run("-L", str(listing), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf", "a.pdf", "b.pdf"]


def test_list_skips_blank_lines_and_comments(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    pdf("b.pdf", 1)
    listing = write_list(
        tmp_path / "pdfs.txt",
        "# a comment",
        "",
        "a.pdf",
        "   ",
        "   # indented comment",
        "b.pdf",
        "",
    )
    out = tmp_path / "out.pdf"

    result = run("-L", str(listing), "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert page_count(out) == 2


def test_list_entry_may_carry_a_page_selection(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("five.pdf", 5)
    pdf("three.pdf", 3)
    listing = write_list(tmp_path / "pdfs.txt", "five.pdf:1-2", "three.pdf:-1")
    out = tmp_path / "out.pdf"

    result = run("-L", str(listing), "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert page_count(out) == 3


def test_list_entry_with_a_bad_selection_names_the_line(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    listing = write_list(tmp_path / "pdfs.txt", "a.pdf", "b.pdf:1..2")

    result = run("-L", str(listing), "-o", str(tmp_path / "out.pdf"))

    assert result.returncode == 1
    assert "pdfs.txt:2" in result.stderr


def test_list_tolerates_a_byte_order_mark(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # utf-8-sig is used for exactly this: a list saved by a Windows editor may
    # carry a BOM, which would otherwise become part of the first filename.
    pdf("a.pdf", 1)
    listing = tmp_path / "pdfs.txt"
    listing.write_bytes("﻿a.pdf\n".encode())
    out = tmp_path / "out.pdf"

    result = run("-L", str(listing), "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert page_count(out) == 1


def test_missing_list_file_is_an_input_error(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    result = run("-L", str(tmp_path / "absent.txt"), "-o", str(tmp_path / "o.pdf"))

    assert result.returncode == 1
    assert "Cannot read list file" in result.stderr


def test_empty_list_file_is_an_input_error(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    listing = write_list(tmp_path / "pdfs.txt", "# only a comment", "")

    result = run("-L", str(listing), "-o", str(tmp_path / "o.pdf"))

    assert result.returncode == 1
    assert "no entries" in result.stderr


def test_list_entry_that_does_not_exist_is_reported_like_any_input(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    listing = write_list(tmp_path / "pdfs.txt", "a.pdf", "absent.pdf")

    result = run("-L", str(listing), "-o", str(tmp_path / "o.pdf"))

    assert result.returncode == 1
    assert "absent.pdf" in result.stderr


def test_list_is_combined_with_file_arguments(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("positional.pdf", 1)
    pdf("listed.pdf", 1)
    listing = write_list(tmp_path / "pdfs.txt", "listed.pdf")

    result = run("positional.pdf", "-L", str(listing), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["positional.pdf", "listed.pdf"]


def test_several_lists_are_appended_in_order(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    pdf("b.pdf", 1)
    pdf("c.pdf", 1)
    first = write_list(tmp_path / "one.txt", "a.pdf", "b.pdf")
    second = write_list(tmp_path / "two.txt", "c.pdf")

    result = run("-L", str(first), "-L", str(second), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["a.pdf", "b.pdf", "c.pdf"]


def test_list_paths_are_relative_to_the_working_directory(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # A list is read as written; its entries are not re-based on the directory
    # the list itself happens to live in.
    pdf("data/a.pdf", 1)
    listing = write_list(tmp_path / "pdfs.txt", "data/a.pdf")
    out = tmp_path / "out.pdf"

    result = run("-L", str(listing), "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert page_count(out) == 1


# ---------------------------------------------------------------- -P/--pattern


def test_pattern_matches_the_named_directory(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "top/*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["a.pdf", "b.pdf"]


def test_pattern_without_recursive_stays_at_the_top_level(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "docs/*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf"]


def test_recursive_widens_a_pattern_to_subdirectories(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "docs/*.pdf", "--recursive", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf", "d.pdf", "e.pdf"]


def test_explicit_recursive_pattern_works_without_the_flag(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "docs/**/*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf", "d.pdf", "e.pdf"]


def test_recursive_flag_does_not_widen_an_explicit_recursive_pattern(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    # "**" is already as wide as it goes; adding another would be redundant.
    plain = run("-P", "docs/**/*.pdf", "--dry-run")
    flagged = run("-P", "docs/**/*.pdf", "--recursive", "--dry-run")

    assert plain.returncode == 0, plain.stderr
    assert flagged.returncode == 0, flagged.stderr
    assert listed(plain.stdout) == listed(flagged.stdout)


def test_pattern_with_no_leading_directory_uses_the_working_directory(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("a.pdf", 1)
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")

    result = run("-P", "*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["a.pdf"]


def test_pattern_only_takes_files_not_directories(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "**", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf", "d.pdf", "e.pdf", "a.pdf", "b.pdf"]


def test_pattern_results_are_ordered_deterministically(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    # A bare Path.glob hands back whatever order the filesystem reports, which
    # would make two runs over one tree disagree. Sorting is what makes the
    # default order reproducible. The sort is on the whole path, so docs/ comes
    # before top/.
    first = run("-P", "**/*.pdf", "--dry-run")
    second = run("-P", "**/*.pdf", "--dry-run")

    assert listed(first.stdout) == listed(second.stdout)
    assert listed(first.stdout) == ["c.pdf", "d.pdf", "e.pdf", "a.pdf", "b.pdf"]


def test_pattern_still_honours_order_name(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
) -> None:
    for name in ("b.pdf", "a.pdf", "c.pdf"):
        pdf(f"d/{name}", 1)

    result = run("-P", "d/*.pdf", "--order", "name", "--sort", "desc", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["c.pdf", "b.pdf", "a.pdf"]


def test_pattern_bracket_is_a_character_class(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
) -> None:
    # --pattern is the glob-shaped input, so "[]" is a character class here.
    # A filename that literally contains a bracket belongs in a FILE argument
    # or a --list entry, both of which treat it literally.
    pdf("odd/report1.pdf", 1)
    pdf("odd/report2.pdf", 1)
    pdf("other.pdf", 1)

    result = run("-P", "odd/report[12].pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["report1.pdf", "report2.pdf"]


def test_pattern_may_name_a_directory_below_the_base(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "docs/deep/*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["d.pdf", "e.pdf"]


def test_several_patterns_are_appended_in_order(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "top/*.pdf", "-P", "docs/*.pdf", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert listed(result.stdout) == ["a.pdf", "b.pdf", "c.pdf"]


def test_pattern_matching_nothing_is_an_input_error(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    result = run("-P", "top/*.txt", "--dry-run")

    assert result.returncode == 1
    assert "matched no files" in result.stderr


def test_pattern_matching_nothing_is_not_skipped_by_skip_invalid(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
) -> None:
    # --skip-invalid is about files that cannot be read. A glob that matches
    # nothing is a mistyped pattern, and staying quiet about it would hide that.
    result = run("-P", "top/*.txt", "--skip-invalid", "--dry-run")

    assert result.returncode == 1
    assert "matched no files" in result.stderr


def test_pattern_with_a_missing_base_directory_is_an_input_error(
    run: Callable[..., CompletedProcess[str]],
) -> None:
    result = run("-P", "absent/*.pdf", "--dry-run")

    assert result.returncode == 1
    assert "Path not found" in result.stderr


def test_argument_without_a_glob_character_is_a_usage_error(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
) -> None:
    pdf("top/a.pdf", 1)

    result = run("-P", "top", "--dry-run")

    assert result.returncode == 2
    assert "not a pattern" in result.stderr


def test_absolute_pattern_is_a_usage_error(
    run: Callable[..., CompletedProcess[str]],
) -> None:
    result = run("-P", "/tmp/*.pdf", "--dry-run")

    assert result.returncode == 2
    assert "relative" in result.stderr


# --------------------------------------------------------------- combinations


def test_every_source_combines_positionals_then_list_then_pattern(
    run: Callable[..., CompletedProcess[str]],
    tree: None,
    tmp_path: Path,
) -> None:
    listing = write_list(tmp_path / "pdfs.txt", "top/b.pdf")
    out = tmp_path / "out.pdf"

    result = run("top/a.pdf", "-L", str(listing), "-P", "docs/*.pdf", "-o", str(out))

    assert result.returncode == 0, result.stderr
    assert listed(
        run("top/a.pdf", "-L", str(listing), "-P", "docs/*.pdf", "--dry-run").stdout
    ) == [
        "a.pdf",
        "b.pdf",
        "c.pdf",
    ]
    assert page_count(out) == 1 + 1 + 2


def test_no_inputs_at_all_is_a_usage_error(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    result = run("-o", str(tmp_path / "out.pdf"))

    assert result.returncode == 2
    assert "at least one input" in result.stderr


@pytest.mark.parametrize("flag", ["-L", "-P"])
def test_list_and_pattern_are_rejected_with_output_dir(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    flag: str,
) -> None:
    # --output-dir writes one file per supplied directory, so it needs
    # directories; these two name individual files.
    pdf("docs/a.pdf", 1)
    listing = write_list(tmp_path / "pdfs.txt", "docs/a.pdf")
    value = str(listing) if flag == "-L" else "docs/*.pdf"

    result = run(flag, value, "-d", str(tmp_path / "out"))

    assert result.returncode == 2
    assert "--output-dir" in result.stderr


def test_output_dir_still_works_from_directories_alone(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("docs/a.pdf", 1)
    pdf("other/b.pdf", 1)
    out_dir = tmp_path / "out"

    result = run("docs", "other", "-d", str(out_dir))

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in out_dir.iterdir()) == [
        "docs.pdf",
        "other.pdf",
    ]
