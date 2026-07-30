from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

from hierarchy_validator import HierarchyValidationError, validate_simulated_hierarchy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Campaign Group hierarchy initializer sample."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=MODULE_ROOT / "data" / "simulated",
        help="Directory containing strategy_request.json and candidate_pool.json.",
    )
    parser.add_argument(
        "--recommendation",
        type=Path,
        default=MODULE_ROOT / "tests" / "fixtures" / "expected_initial_recommendation.json",
        help="Explicit expected recommendation fixture to validate against the inputs.",
    )
    parser.add_argument(
        "--attribution",
        type=Path,
        default=MODULE_ROOT.parent / "amc_mta" / "outputs" / "attribution" / "amc_mta_recommended_attribution.csv",
        help="Read-only AMC recommended attribution CSV.",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        default=MODULE_ROOT.parent / "amc_mta" / "data" / "simulated" / "amc_touchpoint_entity_aggregate_sample.csv",
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
