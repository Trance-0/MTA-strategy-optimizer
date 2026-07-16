from __future__ import annotations

import argparse
import sys
from pathlib import Path


MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MTA_ROOT / "src"))
sys.path.insert(0, str(MTA_ROOT))

from config import (
    ATTRIBUTION_OUTPUT_DIR,
    CHANNEL_SPEND_FILE,
    DATA_DIR,
    MARKOV_PATHS_FILE,
    SHAPLEY_CHANNEL_SETS_FILE,
)
from mta_attribution import attribution_rows, run_markov, run_shapley, write_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Markov Chain and Shapley Value attribution models."
    )
    parser.add_argument(
        "--data-dir",
        default=DATA_DIR,
        type=Path,
        help="Directory containing markov_user_paths.csv, shapley_user_channel_sets.csv, and channel_spend.csv.",
    )
    parser.add_argument(
        "--output-dir",
        default=ATTRIBUTION_OUTPUT_DIR,
        type=Path,
        help="Directory where attribution result CSV files will be written.",
    )
    return parser.parse_args()


def run_attribution(data_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    markov_results = run_markov(
        paths_path=data_dir / MARKOV_PATHS_FILE,
        spend_path=data_dir / CHANNEL_SPEND_FILE,
    )
    shapley_results = run_shapley(
        channel_sets_path=data_dir / SHAPLEY_CHANNEL_SETS_FILE,
        spend_path=data_dir / CHANNEL_SPEND_FILE,
    )

    fieldnames = [
        "channel",
        "contribution_share",
        "attributed_conversions",
        "attributed_revenue",
        "spend",
        "roas",
        "roi",
        "cpa",
    ]
    markov_output = output_dir / "markov_attribution_results.csv"
    shapley_output = output_dir / "shapley_attribution_results.csv"
    write_csv(
        markov_output,
        attribution_rows(markov_results),
        fieldnames,
    )
    write_csv(
        shapley_output,
        attribution_rows(shapley_results),
        fieldnames,
    )
    return [markov_output, shapley_output]


def main() -> None:
    args = parse_args()
    output_files = run_attribution(args.data_dir, args.output_dir)

    for path in output_files:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
