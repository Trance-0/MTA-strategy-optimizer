---
title: path_report_builder.py
source_file: modules/mta_attribution/src/path_report_builder.py
compact: "Specifies build_aggregated_path_rows() and PATH_REPORT_FIELDS (report_start_date, report_end_date, marketplace, advertiser_id, path, users, converted_users, purchase_count, revenue); applies max_gap_days windowing and prior-purchase splitting to TOUCHPOINT/CONVERSION journey events. Read when changing path-window rules."
---

# `path_report_builder.py`

- Responsibility: Convert ordered journey events into privacy-safe aggregated paths.
- Inputs: Touchpoint and conversion event rows plus report-window rules.
- Outputs: Aggregated path-report rows.
- Dependencies: `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_path_report_builder.py`, with end-to-end coverage in `modules/mta_attribution/tests/test_end_to_end_pipeline.py` and report-window inference in `modules/mta_attribution/tests/test_auto_report_window.py`.
