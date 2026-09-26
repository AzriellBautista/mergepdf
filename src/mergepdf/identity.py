"""Filesystem identity for a path.

Duplicate detection and the output-is-an-input guard both need to answer "is
this the same file?" rather than "is this the same string?", so that question
lives here on its own.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def identity(path: Path) -> str:
    """Return a comparable key identifying a path, case-insensitive on Windows.

    A path alone is not a file identity. It misses two cases that matter for
    duplicate detection: two spellings of one file only become equal after
    ``resolve``, and two hardlink entries share an inode while having
    completely unrelated paths. So the file id is the key wherever the
    filesystem reports a usable one, and the resolved path is only a fallback.

    The id is discarded when it looks unreliable: some filesystems report 0
    for ``st_ino``, and a few report 0 for every file, which would otherwise
    collapse unrelated files into a single key.
    """
    resolved = path.resolve()

    try:
        info = resolved.stat()
    except OSError:
        return f"path:{os.path.normcase(str(resolved))}"

    if info.st_ino == 0 or info.st_dev == 0:
        return f"path:{os.path.normcase(str(resolved))}"

    return f"id:{info.st_dev}:{info.st_ino}"
