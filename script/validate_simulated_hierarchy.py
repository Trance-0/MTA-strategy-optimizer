"""Validate the simulated Campaign Group hierarchy end to end.

Public preflight command for the strategy module. Prints a summary of the
validated hierarchy, including touchpoint and Campaign counts, the recommended
Ad Group count per Campaign, and any warnings.

Data flow: attribution and bridge CSVs + request and candidate JSON
-> `hierarchy_validator` -> a summary dict printed as JSON. It writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = PROJECT_ROOT / "modules" / "mta_strategy_recommendation"
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_strategy_recommendation.src.hierarchy_validator import (  # noqa: E402
    HierarchyValidationError,
    validate_simulated_hierarchy,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the budget-only Campaign Group initializer sample."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=MODULE_ROOT / "data" / "simulated",
        help="Directory containing the v4 strategy request and candidate counts.",
    )
    parser.add_argument(
        "--recommendation",
        type=Path,
        default=MODULE_ROOT / "outputs" / "initial_budget_recommendation.json",
        help="Committed formal budget-only recommendation to reproduce.",
    )
    parser.add_argument(
        "--attribution",
        type=Path,
        default=MODULE_ROOT.parent / "mta_attribution" / "outputs" / "attribution" / "amc_mta_recommended_attribution.csv",
        help="Read-only AMC recommended attribution CSV.",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        default=MODULE_ROOT.parent / "mta_attribution" / "data" / "simulated" / "amc_touchpoint_entity_aggregate_sample.csv",
        help="Read-only AMC touchpoint/entity aggregate CSV.",
    )
    args = parser.parse_args()
    try:
        summary = validate_simulated_hierarchy(
            args.data_dir,
            args.recommendation,
            args.attribution,
            args.entity,
        )
    except HierarchyValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
