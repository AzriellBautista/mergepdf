"""Verbosity flags, --version, and the usage errors argparse owns."""

from __future__ import annotations

from collections.abc import Callable
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

Run = Callable[..., CompletedProcess[str]]


@pytest.mark.parametrize(
    ("level", "expect_debug"),
    [("", False), ("-v", False), ("-vv", True), ("-vvv", True), ("-vvvvvv", True)],
)
def test_debug_detail_requires_double_v(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
    level: str,
    expect_debug: bool,
) -> None:
    source = pdf("a.pdf", 1)
    args = [str(source), "-o", str(tmp_path / "verb.pdf"), "-f"]
    if level:
        args.append(level)

    stderr = run(*args).stderr

    assert ("Arguments:" in stderr) is expect_debug
    assert "took" not in stderr


def test_quiet_is_silent(run: Run, pdf: Callable[..., Path], tmp_path: Path) -> None:
    source = pdf("a.pdf", 1)

    result = run(str(source), "-o", str(tmp_path / "q.pdf"), "-f", "--quiet")

    assert result.stderr.strip() == ""


def test_default_says_nothing_on_success(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)

    result = run(str(source), "-o", str(tmp_path / "s.pdf"), "-f")

    assert result.stderr.strip() == ""


def test_single_v_reports_progress(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)

    result = run(str(source), "-o", str(tmp_path / "i.pdf"), "-f", "-v")

    assert "[INFO]" in result.stderr


def test_version_matches_pyproject(run: Run, version: str) -> None:
    result = run("--version")

    assert result.stdout.strip() == f"mergepdf {version}"


def test_no_arguments_is_a_usage_error(run: Run) -> None:
    assert run().returncode == 2


def test_quiet_excludes_verbose(
    run: Run,
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    source = pdf("a.pdf", 1)

    result = run(str(source), "-o", str(tmp_path / "x.pdf"), "-f", "-vv", "--quiet")

    assert result.returncode == 2
