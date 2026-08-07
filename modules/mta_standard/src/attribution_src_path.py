"""Locate the attribution module's source directory for cross-module imports.

``mta_standard`` wraps the estimators in ``mta_attribution``, but that module is
imported by module name (``from markov_attribution_model import ...``) rather
than by package path, matching how its own entry points and tests bootstrap
themselves. Centralising the ``sys.path`` insertion here keeps that single
repository-layout assumption in one documented place instead of repeating it in
every standardized component.

Data flow: no data passes through this file. It runs before the first
cross-module import in each ``mta_standard`` file and only makes those imports
resolvable.
"""

from __future__ import annotations

import sys
from pathlib import Path


MTA_STANDARD_ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = MTA_STANDARD_ROOT.parent
ATTRIBUTION_SRC = MODULES_ROOT / "mta_attribution" / "src"


def ensure_attribution_src_on_path() -> Path:
    """Make ``mta_attribution``'s flat modules importable from this package.

    Returns:
        Path: the ``mta_attribution/src`` directory that is guaranteed to be
        importable.

    Raises:
        FileNotFoundError: if ``mta_attribution/src`` is missing, which means the
            standardized components cannot wrap the existing algorithms.

    Invariants:
        The directory is appended at most once and never shadows an entry that
        the caller placed on ``sys.path`` first.
    """
    if not ATTRIBUTION_SRC.is_dir():
        raise FileNotFoundError(
            f"mta_attribution source directory is missing: {ATTRIBUTION_SRC}"
        )
    location = str(ATTRIBUTION_SRC)
    if location not in sys.path:
        sys.path.append(location)
    return ATTRIBUTION_SRC
