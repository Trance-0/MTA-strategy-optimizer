from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import read_csv, write_csv_set_atomic  # noqa: E402
from config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE,
    AMC_REPORT_FILE,
    ATTRIBUTION_OUTPUT_DIR,
    MARKOV_OUTPUT_FILE,
    MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE,
    MAX_TOUCHPOINT_GAP_DAYS,
    REFERENCE_WINDOW_DAYS,
    RECOMMENDED_ATTRIBUTION_FILE,
    SHAPLEY_OUTPUT_FILE,
)
from model_comparison import (  # noqa: E402
    MODEL_OUTPUT_FIELDS,
    RECOMMENDED_FIELDS,
    SUMMARY_FIELDS,
    TOUCHPOINT_COMPARISON_FIELDS,
    ComparisonArtifacts,
    compare_attribution_models,
    read_amc_csv_strict,
)
from scripts.validate_data_alignment import validate_data_alignment_rows  # noqa: E402


def read_model_csv_strict(path: str | Path) -> list[dict]:
    path = Path(path)
    with path.open(newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != MODEL_OUTPUT_FIELDS:
            raise ValueError(
                f"{path}: physical header must exactly match the model output contract; "
                f"expected={MODEL_OUTPUT_FIELDS}, got={reader.fieldnames}"
            )
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"{path}: row {row_number} contains extra column value(s)"
                )
            for field, value in row.items():
                if value is None:
                    raise ValueError(f"{path}: row {row_number} has missing columns")
                if value != value.strip():
                    raise ValueError(
                        f"{path}: row {row_number} field {field!r} contains missing or surrounding whitespace"
                    )
            rows.append(row)
    return rows


def write_comparison_artifacts(
    output_dir: str | Path, artifacts: ComparisonArtifacts
) -> list[Path]:
    output_dir = Path(output_dir)
    outputs = [
        output_dir / MODEL_COMPARISON_TOUCHPOINTS_FILE,
        output_dir / MODEL_COMPARISON_SUMMARY_FILE,
        output_dir / RECOMMENDED_ATTRIBUTION_FILE,
    ]
    return write_csv_set_atomic(
        [
            (outputs[0], artifacts.touchpoints, TOUCHPOINT_COMPARISON_FIELDS),
            (outputs[1], artifacts.summary, SUMMARY_FIELDS),
            (outputs[2], artifacts.recommended, RECOMMENDED_FIELDS),
        ]
    )


def compare_model_files(
    markov_file: str | Path,
    shapley_file: str | Path,
    amc_report: str | Path,
    amazon_ads_report: str | Path,
    output_dir: str | Path,
    *,
    max_touchpoint_gap_days: int = MAX_TOUCHPOINT_GAP_DAYS,
    reference_window_days: int = REFERENCE_WINDOW_DAYS,
) -> list[Path]:
    amc_rows = read_amc_csv_strict(amc_report)
    ads_rows = read_csv(amazon_ads_report)
    validate_data_alignment_rows(amc_rows, ads_rows)
    artifacts = compare_attribution_models(
        read_model_csv_strict(markov_file),
        read_model_csv_strict(shapley_file),
        amc_rows,
        max_touchpoint_gap_days=max_touchpoint_gap_days,
        reference_window_days=reference_window_days,
    )
    return write_comparison_artifacts(output_dir, artifacts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strictly compare complete Markov and Shapley AMC MTA outputs."
    )
    parser.add_argument(
        "--markov-file",
        type=Path,
        default=ATTRIBUTION_OUTPUT_DIR / MARKOV_OUTPUT_FILE,
    )
    parser.add_argument(
        "--shapley-file",
        type=Path,
        default=ATTRIBUTION_OUTPUT_DIR / SHAPLEY_OUTPUT_FILE,
    )
    parser.add_argument("--amc-report", type=Path, default=AMC_REPORT_FILE)
    parser.add_argument(
        "--amazon-ads-report", type=Path, default=AMAZON_ADS_REPORT_FILE
    )
    parser.add_argument("--output-dir", type=Path, default=ATTRIBUTION_OUTPUT_DIR)
    parser.add_argument(
        "--max-touchpoint-gap-days", type=int, default=MAX_TOUCHPOINT_GAP_DAYS
    )
    parser.add_argument(
        "--reference-window-days", type=int, default=REFERENCE_WINDOW_DAYS
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = compare_model_files(
        args.markov_file,
        args.shapley_file,
        args.amc_report,
        args.amazon_ads_report,
        args.output_dir,
        max_touchpoint_gap_days=args.max_touchpoint_gap_days,
        reference_window_days=args.reference_window_days,
    )
    for path in outputs:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
