"""What happens when an input cannot be used, and how failures are reported."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf import PdfWriter

from support import page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def _make_broken_dir(pdf: Callable[..., Path], tmp_path: Path) -> Path:
    broken = tmp_path / "broken"
    pdf("broken/good.pdf", 2)
    (broken / "truncated.pdf").write_bytes(b"%PDF-1.7 truncated\n")
    (broken / "notes.txt").write_text("not a pdf", encoding="utf-8")
    return broken


def test_corrupt_file_fails_the_run(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    broken = _make_broken_dir(pdf, tmp_path)
    out = tmp_path / "f1.pdf"

    assert run(str(broken), "-o", str(out)).returncode == 4
    assert not out.exists()


def test_skip_invalid_keeps_the_readable_files(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    broken = _make_broken_dir(pdf, tmp_path)
    out = tmp_path / "f2.pdf"

    assert run(str(broken), "--skip-invalid", "-o", str(out)).returncode == 0
    assert page_count(out) == 2


def test_skipping_everything_still_fails(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    broken = _make_broken_dir(pdf, tmp_path)

    result = run(
        str(broken / "truncated.pdf"), "--skip-invalid", "-o", str(tmp_path / "f3.pdf")
    )

    assert result.returncode == 4


def test_missing_path_is_reported(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    result = run(str(tmp_path / "nope.pdf"), "-o", str(tmp_path / "f4.pdf"))

    assert "Path not found" in result.stderr


def test_non_pdf_is_reported(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    _make_broken_dir(pdf, tmp_path)

    result = run(str(tmp_path / "broken" / "notes.txt"), "-o", str(tmp_path / "f5.pdf"))

    assert "Not a PDF file" in result.stderr


def test_encrypted_file_fails(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    locked = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("pw")
    with locked.open("wb") as handle:
        writer.write(handle)

    result = run(str(locked), "-o", str(tmp_path / "f6.pdf"))

    assert result.returncode == 4
