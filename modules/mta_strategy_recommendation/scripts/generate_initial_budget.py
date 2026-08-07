"""Generate the initial budget recommendation JSON.

Command-line entry point for the strategy module.

Data flow: attribution and bridge CSVs + request and candidate JSON
-> `budget_recommender` -> `outputs/initial_budget_recommendation.json`.

`--check-output` re-runs the calculation and compares it against the committed
file instead of overwriting it, which is how the deterministic seed is verified
in tests and documentation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_strategy_recommendation.src.budget_recommender import (  # noqa: E402
    BudgetRecommendationError,
    generate_budget_recommendation,
)
from modules.mta_strategy_recommendation.src.hierarchy_validator import (  # noqa: E402
    HierarchyValidationError,
    load_aligned_strategy_inputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic MTA-driven Ad Group budget seed."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=MODULE_ROOT / "data" / "simulated",
        help="Directory containing the v4 strategy request and candidate counts.",
    )
    parser.add_argument(
        "--attribution",
        type=Path,
        default=MODULE_ROOT.parent
        / "mta_attribution"
        / "outputs"
        / "attribution"
        / "amc_mta_recommended_attribution.csv",
        help="Read-only AMC recommended attribution CSV.",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        default=MODULE_ROOT.parent
        / "mta_attribution"
        / "data"
        / "simulated"
        / "amc_touchpoint_entity_aggregate_sample.csv",
        help="Read-only AMC touchpoint/entity aggregate CSV.",
    )
    parser.add_argument(
        "--check-output",
        "--check-fixture",
        dest="check_output",
        action="store_true",
        help="Compare generated output with the committed formal output.",
    )
    parser.add_argument(
        "--output",
        "--fixture",
        dest="output",
        type=Path,
        default=MODULE_ROOT / "outputs" / "initial_budget_recommendation.json",
        help="Committed formal output used by --check-output.",
    )
    args = parser.parse_args()
    try:
        request, pool, attribution_rows, entity_rows = load_aligned_strategy_inputs(
            args.data_dir, args.attribution, args.entity
        )
        generated = generate_budget_recommendation(
            request, pool, attribution_rows, entity_rows
        )
    except (HierarchyValidationError, BudgetRecommendationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if args.check_output:
        try:
            committed_output = args.output.read_bytes()
        except OSError as exc:
            print(f"INVALID: cannot read output {args.output}: {exc}", file=sys.stderr)
            return 1
        expected_output = (
            json.dumps(generated, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        ).encode("utf-8")
        if committed_output != expected_output:
            print("INVALID: formal output does not match generated budget seed", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "output_matches": True,
                    "fixture_matches": True,
                    "recommended_ad_group_count": sum(
                        campaign["recommended_ad_group_count"]
                        for campaign in generated["campaigns"]
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0

    print(json.dumps(generated, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
