"""Atomically regenerate the complete deterministic AMC MTA sample dataset."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

AMC_MTA_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AMC_MTA_ROOT))
sys.path.insert(0, str(AMC_MTA_ROOT / "src"))

from amc_mta_attribution import ADS_FIELD_DESCRIPTIONS, write_csv_atomic  # noqa: E402
from config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE, AMC_REPORT_FILE, AMC_TOUCHPOINT_EVENTS_FILE,
    ATTRIBUTION_OUTPUT_DIR, MARKOV_OUTPUT_FILE, MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE, RECOMMENDED_ATTRIBUTION_FILE,
    REPORT_END_DATE, REPORT_START_DATE, SHAPLEY_OUTPUT_FILE,
)
from scripts.build_amc_path_report import build_amc_path_report  # noqa: E402
from scripts.generate_simulated_amazon_ads_report import FIELDS as ADS_FIELDS, generate_rows as generate_ads  # noqa: E402
from scripts.generate_simulated_amc_touchpoint_events import FIELDS as EVENT_FIELDS, generate_rows as generate_events  # noqa: E402
from scripts.run_amc_attribution import run_amc_attribution  # noqa: E402
from run_pipeline import match_outputs_by_name, publish_with_rollback  # noqa: E402
from datetime import date  # noqa: E402


def default_destinations() -> list[Path]:
    return [
        Path(AMC_TOUCHPOINT_EVENTS_FILE), Path(AMAZON_ADS_REPORT_FILE), Path(AMC_REPORT_FILE),
        *[Path(ATTRIBUTION_OUTPUT_DIR) / name for name in (
            MARKOV_OUTPUT_FILE, SHAPLEY_OUTPUT_FILE, MODEL_COMPARISON_TOUCHPOINTS_FILE,
            MODEL_COMPARISON_SUMMARY_FILE, RECOMMENDED_ATTRIBUTION_FILE,
        )],
    ]


def regenerate(destinations: list[Path] | None = None) -> None:
    destinations = list(destinations or default_destinations())
    if len(destinations) != 8:
        raise ValueError("complete simulated dataset requires exactly 8 destinations")
    with tempfile.TemporaryDirectory(prefix=".amc_mta_dataset_", dir=AMC_MTA_ROOT) as tmp:
        root = Path(tmp)
        events = root / destinations[0].name
        ads = root / destinations[1].name
        paths = root / destinations[2].name
        write_csv_atomic(events, generate_events(), EVENT_FIELDS)
        write_csv_atomic(ads, [ADS_FIELD_DESCRIPTIONS, *generate_ads(date.fromisoformat(REPORT_START_DATE), date.fromisoformat(REPORT_END_DATE))], ADS_FIELDS)
        build_amc_path_report(events, paths)
        outputs = run_amc_attribution(paths, root / "outputs", ads)
        replacements = [(events, destinations[0]), (ads, destinations[1]), (paths, destinations[2]), *match_outputs_by_name(outputs, destinations[3:])]
        publish_with_rollback(replacements, root / "backups")


if __name__ == "__main__":
    regenerate()
    print("Regenerated 8 AMC MTA sample artifacts atomically.")
