from __future__ import annotations

import sys
from pathlib import Path


MTA_STANDARD_ROOT = Path(__file__).resolve().parents[1]
MODULES_ROOT = MTA_STANDARD_ROOT.parent
AMC_MTA_SRC = MODULES_ROOT / "amc_mta" / "src"


def ensure_amc_mta_src_on_path() -> Path:
    """Make the existing ``amc_mta`` flat modules importable from this package.

    ``amc_mta`` is imported by module name rather than by package path
    (``from touchpoint_key import ...``), matching how its own entry points and
    tests bootstrap themselves. Centralising the ``sys.path`` insertion here
    keeps that one repository-layout assumption in a single documented place
    instead of repeating it in every standardized component.

    Returns:
        Path: the ``amc_mta/src`` directory that is guaranteed to be importable.

    Raises:
        FileNotFoundError: if ``amc_mta/src`` is missing, which means the
            standardized components cannot wrap the existing algorithms.

    Invariants:
        The directory is appended at most once and never shadows an entry that
        the caller placed on ``sys.path`` first.
    """
    if not AMC_MTA_SRC.is_dir():
        raise FileNotFoundError(f"amc_mta source directory is missing: {AMC_MTA_SRC}")
    location = str(AMC_MTA_SRC)
    if location not in sys.path:
        sys.path.append(location)
    return AMC_MTA_SRC
