"""Outline entries mergepdf adds, and the ones it imports from its inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pypdf import PdfWriter

from support import meta, outline_titles, page_count

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


def test_one_outline_entry_per_merged_file(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    plain = pdf("plain.pdf", 1)
    out = tmp_path / "bm1.pdf"

    assert run(str(source), str(plain), "-o", str(out)).returncode == 0
    assert outline_titles(out) == ["bm", "plain"]


def test_no_add_outlines_keeps_only_the_imported_ones(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm2.pdf"

    assert run(str(source), "-o", str(out), "--no-add-outlines", "-f").returncode == 0
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


def test_no_outline_removes_every_entry(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # The common case: an output with no outline at all, so the filename
    # entries mergepdf would add and the entries the input already had are
    # both gone.
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm4.pdf"

    result = run(str(source), "-o", str(out), "--no-outline", "-f")

    assert result.returncode == 0
    assert outline_titles(out) == []


def test_no_outline_applies_to_a_multi_file_merge(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    outlined = _make_outlined_pdf(tmp_path / "first.pdf")
    plain = pdf("second.pdf", 2)
    out = tmp_path / "bm5.pdf"

    result = run(str(outlined), str(plain), "-o", str(out), "--no-outline", "-f")

    assert result.returncode == 0
    assert outline_titles(out) == []


def test_no_outline_equals_both_narrow_flags(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # Documented as shorthand, so it must not drift from the pair it stands in
    # for.
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    shorthand = tmp_path / "shorthand.pdf"
    both = tmp_path / "both.pdf"

    short = run(str(source), "-o", str(shorthand), "--no-outline", "-f")
    long = run(
        str(source),
        "-o",
        str(both),
        "--no-add-outlines",
        "--no-import-outlines",
        "-f",
    )

    assert short.returncode == 0
    assert long.returncode == 0
    assert outline_titles(shorthand) == outline_titles(both) == []


def test_no_outline_wins_regardless_of_flag_order(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # --no-outline sets two destinations, so the order it appears in must not
    # decide whether it takes effect.
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm6.pdf"

    result = run(
        str(source),
        "-o",
        str(out),
        "--no-add-outlines",
        "--no-outline",
        "-f",
    )

    assert result.returncode == 0
    assert outline_titles(out) == []


def test_no_outline_leaves_pages_and_metadata_alone(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # It removes outline entries and nothing else. The title comes from the
    # first input that carries one, so the titled file has to come first.
    titled = pdf("titled.pdf", 2, title="Kept Title")
    source = _make_outlined_pdf(tmp_path / "bm.pdf")
    out = tmp_path / "bm7.pdf"

    result = run(str(titled), str(source), "-o", str(out), "--no-outline", "-f")

    assert result.returncode == 0
    assert page_count(out) == 5
    assert meta(out, "/Title") == "Kept Title"


def test_no_outline_is_reported_in_the_debug_dump(
    run: Callable[..., CompletedProcess[str]],
    tmp_path: Path,
) -> None:
    # The resolved pair is logged, because "which flag turned this off" is
    # otherwise not visible anywhere in the output.
    source = _make_outlined_pdf(tmp_path / "bm.pdf")

    result = run(
        str(source), "-o", str(tmp_path / "o.pdf"), "--no-outline", "-f", "-vv"
    )

    assert result.returncode == 0
    assert "add_outlines=False" in result.stderr
    assert "import_outlines=False" in result.stderr
