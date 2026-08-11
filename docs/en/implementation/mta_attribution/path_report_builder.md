---
title: path_report_builder.py
source_file: modules/mta_attribution/src/path_report_builder.py
---

# `path_report_builder.py`

- Responsibility: Convert ordered journey events into privacy-safe aggregated paths.
- Inputs: Touchpoint and conversion event rows plus report-window rules.
- Outputs: Aggregated path-report rows.
- Dependencies: `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_path_report_builder.py`.
