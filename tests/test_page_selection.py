"""Page-selection syntax, including the forms the --help text promises."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from subprocess import CompletedProcess


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (":1-2", 2),
        (":4-", 2),
        (":-1", 1),
        (":-2", 2),
        (":-99", 5),
        (":-5", 5),
        (":1-", 5),
        (":3", 1),
        (":2-4", 3),
        (":1,5", 2),
        (":1-99", 5),
        (":1-2,3,5", 4),
    ],
)
def test_accepted_selections(
    merge_count: Callable[..., int],
    pdf: Callable[..., Path],
    token: str,
    expected: int,
) -> None:
    # ``:-N`` is a count from the end, not an index, which is the reading the
    # help text commits to.
    five = pdf("sel/five.pdf", 5)

    assert merge_count(f"{five}{token}") == expected


@pytest.mark.parametrize("token", [":99-"])
def test_selection_outside_the_document_fails(
    merge_count: Callable[..., int],
    pdf: Callable[..., Path],
    token: str,
) -> None:
    five = pdf("sel/five.pdf", 5)

    assert merge_count(f"{five}{token}") == -1


@pytest.mark.parametrize("token", [":0", ":4-2", ":1-2-3"])
def test_malformed_selections_are_a_usage_error(
    run: Callable[..., CompletedProcess[str]],
    pdf: Callable[..., Path],
    tmp_path: Path,
    token: str,
) -> None:
    five = pdf("sel/five.pdf", 5)

    result = run(f"{five}{token}", "-o", str(tmp_path / "x.pdf"))

    assert result.returncode == 2
