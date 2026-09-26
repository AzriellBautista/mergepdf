"""Merging directories, and everything about where the output goes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from support import listed, page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def _populate_docs(pdf: Callable[..., Path], docs: Path) -> None:
    """Lay out the fixture directory most merging tests share."""
    pdf("docs/a.pdf", 1)
    pdf("docs/b.pdf", 3)
    pdf("docs/sub/c.pdf", 2)


def test_merges_directory_in_alphabetical_order(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    _populate_docs(pdf, docs)
    out = tmp_path / "out.pdf"

    assert run(str(docs), "-o", str(out)).returncode == 0
    assert page_count(out) == 4


def test_recursive_descends_into_subdirectories(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    _populate_docs(pdf, docs)
    out = tmp_path / "out.pdf"

    assert run(str(docs), "-r", "-o", str(out), "-f").returncode == 0
    assert page_count(out) == 6


def test_dry_run_lists_flat_directory(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    _populate_docs(pdf, docs)

    result = run(str(docs), "--order", "name", "--dry-run")

    assert listed(result.stdout) == ["a.pdf", "b.pdf"]


def test_dry_run_lists_recursive_walk(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    _populate_docs(pdf, docs)

    result = run(str(docs), "-r", "--order", "name", "--dry-run")

    assert listed(result.stdout) == ["a.pdf", "b.pdf", "c.pdf"]


def test_existing_output_needs_force(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)
    out = tmp_path / "out.pdf"
    out.write_bytes(b"existing")

    assert run(str(source), "-o", str(out)).returncode == 3
    assert run(str(source), "-o", str(out), "-f").returncode == 0


def test_output_may_not_also_be_an_input(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
) -> None:
    only = pdf("only.pdf", 2)

    assert run(str(only), "-o", str(only), "-f").returncode == 1


def test_previous_output_inside_its_own_directory_is_excluded(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # Self-exclusion only shows up on a second run, when the previous output
    # sits inside the directory being merged. Without it that stale copy is
    # merged into itself and the page count grows on every run.
    docs = tmp_path / "docs"
    _populate_docs(pdf, docs)
    nested = docs / "merged.pdf"

    assert run(str(docs), "-o", str(nested)).returncode == 0
    assert page_count(nested) == 4

    assert run(str(docs), "-o", str(nested)).returncode == 3
    assert run(str(docs), "-o", str(nested), "-f").returncode == 0
    assert page_count(nested) == 4


def test_leaves_no_temporary_files_behind(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)

    assert run(str(source), "-o", str(tmp_path / "out.pdf")).returncode == 0
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


def test_dry_run_creates_nothing(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)
    out = tmp_path / "dry.pdf"

    assert run(str(source), "-o", str(out), "--dry-run").returncode == 0
    assert not out.exists()
