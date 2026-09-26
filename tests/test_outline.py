"""Outline entries mergepdf adds, and the ones it imports from its inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf import PdfWriter

from support import outline_titles

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def _make_outlined_pdf(path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    writer.add_outline_item("Top", 0)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_one_bookmark_per_merged_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    plain = pdf("plain.pdf", 1)
    out = tmp_path / "bm1.pdf"

    assert run(str(source), str(plain), "-o", str(out)).returncode == 0
    assert outline_titles(out) == ["bm", "plain"]


def test_no_bookmarks_keeps_only_the_imported_ones(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm2.pdf"

    assert run(str(source), "-o", str(out), "--no-bookmarks", "-f").returncode == 0
    assert outline_titles(out) == ["Top"]


def test_no_import_outlines_keeps_only_mergepdf_entry(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm3.pdf"

    result = run(str(source), "-o", str(out), "--no-import-outlines", "-f")

    assert result.returncode == 0
    assert outline_titles(out) == ["bm"]
