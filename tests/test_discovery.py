"""Directory walking, including the ways a directory graph can loop."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from support import page_count

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


def _make_loop(pdf: Callable[..., Path], tmp_path: Path) -> Path:
    """Build a directory containing a symlink back to its own ancestor."""
    loop = tmp_path / "loop"
    pdf("loop/real.pdf", 1)
    pdf("loop/inner/deep.pdf", 1)
    inner = loop / "inner"

    try:
        (inner / "back").symlink_to(loop, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlinks unavailable: {exc}")

    return loop


def test_symlink_loop_terminates(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    # Without a record of walked directories this recurses until the
    # interpreter gives up, which surfaces as a RecursionError.
    loop = _make_loop(pdf, tmp_path)
    out = tmp_path / "loop.pdf"

    result = run(str(loop), "-r", "-o", str(out))

    assert result.returncode == 0
    assert page_count(out) == 2
    assert "RecursionError" not in result.stderr


def test_directory_reached_through_two_routes_is_walked_once(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
) -> None:
    loop = _make_loop(pdf, tmp_path)
    alias = tmp_path / "alias"

    try:
        alias.symlink_to(loop, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - platform
        pytest.skip(f"symlinks unavailable: {exc}")

    out = tmp_path / "alias.pdf"

    assert run(str(loop), str(alias), "-r", "-o", str(out)).returncode == 0
    assert page_count(out) == 2
