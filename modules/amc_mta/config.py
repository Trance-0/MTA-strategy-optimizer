from __future__ import annotations

from pathlib import Path


AMC_MTA_ROOT = Path(__file__).resolve().parent

DATA_DIR = AMC_MTA_ROOT / "data" / "simulated"
SYNTHETIC_USER_EVENTS_FILE = DATA_DIR / "synthetic_user_events_sample.csv"
AMC_TOUCHPOINT_EVENTS_FILE = DATA_DIR / "amc_touchpoint_events_sample.csv"
AMC_REPORT_FILE = DATA_DIR / "amc_mta_path_report_raw_sample.csv"
AMAZON_ADS_REPORT_FILE = DATA_DIR / "amazon_ads_report_sample.csv"
AMC_TOUCHPOINT_ENTITY_AGGREGATE_FILE = (
    DATA_DIR / "amc_touchpoint_entity_aggregate_sample.csv"
)

REPORT_START_DATE = "2026-01-01"
REPORT_END_DATE = "2026-03-31"
MAX_TOUCHPOINT_GAP_DAYS = 14
SIMULATED_PRIVACY_MIN_USERS = 5
SIMULATED_MAX_USER_EVENT_ROWS = 20_000

ATTRIBUTION_OUTPUT_DIR = AMC_MTA_ROOT / "outputs" / "attribution"

MARKOV_OUTPUT_FILE = "amc_markov_attribution_results.csv"
SHAPLEY_OUTPUT_FILE = "amc_shapley_attribution_results.csv"
MODEL_COMPARISON_TOUCHPOINTS_FILE = "amc_mta_model_comparison_touchpoints.csv"
MODEL_COMPARISON_SUMMARY_FILE = "amc_mta_model_comparison_summary.csv"
RECOMMENDED_ATTRIBUTION_FILE = "amc_mta_recommended_attribution.csv"
