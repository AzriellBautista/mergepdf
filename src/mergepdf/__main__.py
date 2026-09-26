"""Allow ``python -m mergepdf``, which the console script cannot provide."""

from __future__ import annotations

import sys

from . import run

if __name__ == "__main__":
    sys.exit(run())
