"""The logger shared by every module in the package.

Using one name means one stream. :func:`mergepdf.arguments.configure_logging`
configures the root logger, so giving every module a child of the same
``mergepdf`` logger is all it takes for ``--quiet`` and ``-v`` to reach every
message in the package.
"""

from __future__ import annotations

import logging

LOGGER = logging.getLogger("mergepdf")
