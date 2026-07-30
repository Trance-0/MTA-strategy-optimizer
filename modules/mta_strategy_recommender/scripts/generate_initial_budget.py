from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "src"))

from budget_recommender import BudgetRecommendationError, generate_budget_recommendation  # noqa: E402
from hierarchy_validator import HierarchyValidationError, load_aligned_strategy_inputs  # noqa: E402


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
        / "amc_mta"
        / "outputs"
        / "attribution"
        / "amc_mta_recommended_attribution.csv",
        help="Read-only AMC recommended attribution CSV.",
    )
    parser.add_argument(
        "--entity",
        type=Path,
        default=MODULE_ROOT.parent
        / "amc_mta"
        / "data"
        / "simulated"
        / "amc_touchpoint_entity_aggregate_sample.csv",
        help="Read-only AMC touchpoint/entity aggregate CSV.",
    )
    parser.add_argument(
        "--check-fixture",
        action="store_true",
        help="Compare generated output with the committed expected fixture.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=MODULE_ROOT / "tests" / "fixtures" / "expected_initial_recommendation.json",
        help="Fixture used by --check-fixture.",
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

    if args.check_fixture:
        try:
            fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"INVALID: cannot read fixture {args.fixture}: {exc}", file=sys.stderr)
            return 1
        if fixture != generated:
            print("INVALID: fixture does not match generated budget seed", file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
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
