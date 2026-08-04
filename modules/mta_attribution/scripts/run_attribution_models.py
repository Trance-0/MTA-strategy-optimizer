"""Run both attribution models and publish the five contract outputs.

This is the stage that turns a validated path report into published attribution.
It runs the models, joins spend, compares the two, and writes all five CSVs as
one atomic set.

Data flow:
    path report + Amazon Ads report
      -> `validate_data_alignment_rows`  : scope, window, and key alignment
      -> `run_markov_attribution` / `run_shapley_attribution`
      -> `aggregate_spend_by_touchpoint` : cost joined by five-segment key
      -> `result_rows`                   : the 18-column model output
      -> `compare_attribution_models`    : touchpoint, summary, recommended
      -> `write_csv_set_atomic`

Alignment runs first because attribution and cost metrics are only meaningful
when both reports cover the same account, dates, and touchpoint set.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    ATTRIBUTION_OUTPUT_DIR,
    MARKOV_OUTPUT_FILE,
    MAX_TOUCHPOINT_GAP_DAYS,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    RECOMMENDED_ATTRIBUTION_FILE,
    SHAPLEY_OUTPUT_FILE,
)
from attribution_contract import (  # noqa: E402
    aggregate_spend_by_touchpoint,
    read_csv,
    result_rows,
    write_csv_set_atomic,
)
from markov_attribution_model import run_markov_attribution  # noqa: E402
from shapley_attribution_model import run_shapley_attribution  # noqa: E402
from scripts.validate_data_alignment import validate_data_alignment_rows  # noqa: E402
from attribution_model_comparison import (  # noqa: E402
    MODEL_OUTPUT_FIELDS,
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
    compare_attribution_models,
    read_amc_csv_strict,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Markov and Shapley attribution from an AMC aggregated path report."
    )
    parser.add_argument(
        "--amc-report",
        default=AMC_REPORT_FILE,
        type=Path,
        help="AMC aggregated path report CSV.",
    )
    parser.add_argument(
        "--output-dir",
        default=ATTRIBUTION_OUTPUT_DIR,
        type=Path,
        help="Directory where attribution result CSV files will be written.",
    )
    parser.add_argument(
        "--amazon-ads-report",
        default=AMAZON_ADS_REPORT_FILE,
        type=Path,
        help="Amazon Ads report CSV used to add cost and ROI metrics.",
    )
    parser.add_argument(
        "--max-touchpoint-gap-days", type=int, default=MAX_TOUCHPOINT_GAP_DAYS
    )
    return parser.parse_args()


def run_attribution_models(
    amc_report: Path,
    output_dir: Path,
    amazon_ads_report: Path = AMAZON_ADS_REPORT_FILE,
    *,
    max_touchpoint_gap_days: int = MAX_TOUCHPOINT_GAP_DAYS,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    amc_rows = read_amc_csv_strict(amc_report)
    amazon_ads_rows = read_csv(amazon_ads_report)

    # Attribution and cost metrics are meaningful only when both reports cover
    # the same account, dates, and complete touchpoint set.
    validate_data_alignment_rows(amc_rows, amazon_ads_rows)

    markov_results = run_markov_attribution(amc_rows)
    shapley_results = run_shapley_attribution(amc_rows)
    spend_by_touchpoint = aggregate_spend_by_touchpoint(amazon_ads_rows)

    markov_rows = result_rows("markov", markov_results, spend_by_touchpoint)
    shapley_rows = result_rows("shapley", shapley_results, spend_by_touchpoint)
    comparison = compare_attribution_models(
        markov_rows,
        shapley_rows,
        amc_rows,
        max_touchpoint_gap_days=max_touchpoint_gap_days,
    )

    markov_output = output_dir / MARKOV_OUTPUT_FILE
    shapley_output = output_dir / SHAPLEY_OUTPUT_FILE
    comparison_touchpoints_output = output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE
    comparison_summary_output = output_dir / MODEL_COMPARISON_SUMMARY_FILE
    recommended_output = output_dir / RECOMMENDED_ATTRIBUTION_FILE
    return write_csv_set_atomic(
        [
            (markov_output, markov_rows, MODEL_OUTPUT_FIELDS),
            (shapley_output, shapley_rows, MODEL_OUTPUT_FIELDS),
            (
                comparison_touchpoints_output,
                comparison.touchpoints,
                TOUCHPOINT_COMPARISON_FIELDS,
            ),
            (comparison_summary_output, comparison.summary, SUMMARY_FIELDS),
            (recommended_output, comparison.recommended, RECOMMENDED_FIELDS),
        ]
    )


def main() -> None:
    args = parse_args()
    output_files = run_attribution_models(
        args.amc_report,
        args.output_dir,
        args.amazon_ads_report,
        max_touchpoint_gap_days=args.max_touchpoint_gap_days,
    )

    for path in output_files:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
