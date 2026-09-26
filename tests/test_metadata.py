"""The --metadata flag: precedence, key syntax, and rejected input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from support import meta

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def _merge(
    run: Callable[..., CompletedProcess[str]],
    source: Path,
    out: Path,
    *flags: str,
) -> None:
    result = run(str(source), *flags, "-o", str(out), "-f")
    assert result.returncode == 0, result.stderr


def test_title_comes_from_the_first_input(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    version: str,
) -> None:
    titled = pdf("titled.pdf", 1, title="Title From File")

    _merge(run, titled, tmp_path / "m0.pdf")

    assert meta(tmp_path / "m0.pdf", "/Title") == "Title From File"
    assert meta(tmp_path / "m0.pdf", "/Producer") == f"mergepdf {version}"


@pytest.mark.parametrize(
    ("flags", "key", "expected"),
    [
        (("--metadata", "/Subject=Testing"), "/Subject", "Testing"),
        (("--metadata", "/Title=Override"), "/Title", "Override"),
        (("--metadata", "/Producer=Custom"), "/Producer", "Custom"),
        (("--metadata", "Title=NoSlash"), "/Title", "NoSlash"),
        (("--metadata", "/Title=a=b=c"), "/Title", "a=b=c"),
        (("--metadata", "/Title="), "/Title", ""),
        (
            (
                "--metadata",
                "/Title=Override",
                "--metadata",
                "/Author=Me",
                "--metadata",
                "/Subject=S",
            ),
            "/Author",
            "Me",
        ),
        (
            ("--metadata", "/Title=First", "--metadata", "/Title=Second"),
            "/Title",
            "Second",
        ),
    ],
)
def test_metadata_is_applied(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    flags: tuple[str, ...],
    key: str,
    expected: str,
) -> None:
    titled = pdf("titled.pdf", 1, title="Title From File")
    out = tmp_path / "meta.pdf"

    _merge(run, titled, out, *flags)

    assert meta(out, key) == expected


@pytest.mark.parametrize("token", ["/Title", "=x", "/Bad Key=x"])
def test_malformed_metadata_is_a_usage_error(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    token: str,
) -> None:
    titled = pdf("titled.pdf", 1, title="Title From File")
    out = tmp_path / "bad.pdf"

    result = run(str(titled), "--metadata", token, "-o", str(out))

    assert result.returncode == 2
    assert not out.exists()
