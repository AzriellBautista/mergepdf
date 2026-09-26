"""--output-dir: one merged PDF per supplied directory."""

from __future__ import annotations

from collections.abc import Callable
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

from support import page_count

if TYPE_CHECKING:
    from pathlib import Path

Run = Callable[..., CompletedProcess[str]]


def test_writes_one_output_per_directory(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("archive/2023/a.pdf", 1)
    pdf("archive/2023/b.pdf", 2)
    pdf("archive/2024/c.pdf", 4)
    out = tmp_path / "out"

    result = run(
        str(tmp_path / "archive" / "2023"),
        str(tmp_path / "archive" / "2024"),
        "--output-dir",
        str(out),
    )

    assert result.returncode == 0
    assert page_count(out / "2023.pdf") == 3
    assert page_count(out / "2024.pdf") == 4


def test_rejects_individual_files(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    only = pdf("a.pdf", 1)

    result = run(str(only), "--output-dir", str(tmp_path / "out"))

    assert result.returncode == 1
    assert "requires directories" in result.stderr


def test_rejects_a_page_selection(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("docs/a.pdf", 2)

    result = run(f"{tmp_path / 'docs'}:1", "--output-dir", str(tmp_path / "out"))

    assert result.returncode == 1
    assert "page selection" in result.stderr


def test_dry_run_lists_every_job(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    pdf("archive/2023/a.pdf", 1)
    pdf("archive/2024/b.pdf", 2)

    result = run(
        str(tmp_path / "archive" / "2023"),
        str(tmp_path / "archive" / "2024"),
        "--output-dir",
        str(tmp_path / "out"),
        "--dry-run",
    )

    assert result.returncode == 0
    assert "Job 1 of 2" in result.stdout
    assert "Job 2 of 2" in result.stdout
    assert not (tmp_path / "out").exists()
