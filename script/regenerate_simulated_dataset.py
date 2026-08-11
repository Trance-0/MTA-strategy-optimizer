"""Atomically reproduce the legacy deterministic five-segment sample dataset.

This compatibility command preserves the committed fixture and its strategy
entity bridge. New synthetic data generation uses ``generate_mta_sim_dataset``
and the pinned ZheyuanWu submodule.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AMC_MTA_ROOT = PROJECT_ROOT / "modules" / "mta_attribution"
sys.path.insert(0, str(PROJECT_ROOT))

from modules.mta_attribution.config import (  # noqa: E402
    AMAZON_ADS_REPORT_FILE, AMC_REPORT_FILE, AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE,
    AMC_TOUCHPOINT_EVENTS_FILE, SYNTHETIC_USER_EVENTS_FILE,
    ATTRIBUTION_OUTPUT_DIR, MARKOV_OUTPUT_FILE, MODEL_COMPARISON_SUMMARY_FILE,
    MODEL_COMPARISON_TOUCHPOINTS_FILE, RECOMMENDED_ATTRIBUTION_FILE,
    REPORT_END_DATE, REPORT_START_DATE, SHAPLEY_OUTPUT_FILE,
    SIMULATED_MAX_USER_EVENT_ROWS, SIMULATED_PRIVACY_MIN_USERS,
)
from modules.mta_attribution.src.attribution_contract import (  # noqa: E402
    ADS_FIELD_DESCRIPTIONS,
    read_csv,
    write_csv_atomic,
)
from modules.mta_attribution.src.synthetic_event_pipeline import (  # noqa: E402
    ADS_FIELDS,
    AMC_EVENT_FIELDS,
    ENTITY_AGGREGATE_FIELDS,
    SYNTHETIC_EVENT_FIELDS,
    derive_amazon_ads_rows,
    derive_amc_touchpoint_events,
    derive_touchpoint_entity_aggregate,
    generate_synthetic_user_events,
    validate_derivations,
    validate_no_user_identifiers,
)
from script.build_path_report import build_path_report  # noqa: E402
from script.run_attribution_models import run_attribution_models  # noqa: E402
from script.run_pipeline import match_outputs_by_name, publish_with_rollback  # noqa: E402


def default_destinations() -> list[Path]:
    return [
        Path(SYNTHETIC_USER_EVENTS_FILE),
        Path(AMC_TOUCHPOINT_EVENTS_FILE),
        Path(AMAZON_ADS_REPORT_FILE),
        Path(AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE),
        Path(AMC_REPORT_FILE),
        *[Path(ATTRIBUTION_OUTPUT_DIR) / name for name in (
            MARKOV_OUTPUT_FILE, SHAPLEY_OUTPUT_FILE, MODEL_COMPARISON_TOUCHPOINTS_FILE,
            MODEL_COMPARISON_SUMMARY_FILE, RECOMMENDED_ATTRIBUTION_FILE,
        )],
    ]


def regenerate(destinations: list[Path] | None = None) -> None:
    destinations = list(destinations or default_destinations())
    if len(destinations) != 10:
        raise ValueError("complete simulated dataset requires exactly 10 destinations")
    if len({path.name for path in destinations[:5]}) != 5:
        raise ValueError("the five simulated data destinations require unique basenames")
    with tempfile.TemporaryDirectory(prefix=".amc_mta_dataset_", dir=AMC_MTA_ROOT) as tmp:
        root = Path(tmp)
        source = root / destinations[0].name
        events = root / destinations[1].name
        ads = root / destinations[2].name
        entities = root / destinations[3].name
        paths = root / destinations[4].name
        source_rows = generate_synthetic_user_events(REPORT_START_DATE, REPORT_END_DATE)
        event_rows = derive_amc_touchpoint_events(source_rows)
        ads_rows = derive_amazon_ads_rows(source_rows, REPORT_START_DATE, REPORT_END_DATE)
        entity_rows = derive_touchpoint_entity_aggregate(
            source_rows,
            REPORT_START_DATE,
            REPORT_END_DATE,
            SIMULATED_PRIVACY_MIN_USERS,
        )
        validate_derivations(
            source_rows,
            event_rows,
            ads_rows,
            entity_rows,
            REPORT_START_DATE,
            REPORT_END_DATE,
            SIMULATED_PRIVACY_MIN_USERS,
            SIMULATED_MAX_USER_EVENT_ROWS,
        )
        write_csv_atomic(source, source_rows, SYNTHETIC_EVENT_FIELDS)
        write_csv_atomic(events, event_rows, AMC_EVENT_FIELDS)
        write_csv_atomic(ads, [ADS_FIELD_DESCRIPTIONS, *ads_rows], ADS_FIELDS)
        write_csv_atomic(entities, entity_rows, ENTITY_AGGREGATE_FIELDS)
        build_path_report(events, paths, amazon_ads_report=ads)
        outputs = run_attribution_models(paths, root / "outputs", ads)
        for artifact in (paths, *outputs):
            validate_no_user_identifiers(artifact.name, read_csv(artifact))
        replacements = [
            (source, destinations[0]),
            (events, destinations[1]),
            (ads, destinations[2]),
            (entities, destinations[3]),
            (paths, destinations[4]),
            *match_outputs_by_name(outputs, destinations[5:]),
        ]
        publish_with_rollback(replacements, root / "backups")


if __name__ == "__main__":
    regenerate()
    print("Regenerated 10 AMC MTA sample artifacts atomically.")
