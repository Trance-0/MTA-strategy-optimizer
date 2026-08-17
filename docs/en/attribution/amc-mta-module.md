---
title: AMC MTA Module
compact: "Six-stage call order of `script/run_pipeline.py` with code walkthroughs of `infer_ads_report_window`, `canonical_amc_touchpoint_key`, `build_aggregated_path_rows`, `compare_attribution_models`, `publish_with_rollback`. Read for pipeline internals and the five-segment key; not for CSV column schemas."
lang: en-US
source_files: modules/mta_attribution/src/simulated_touchpoints.py, modules/mta_attribution/src/synthetic_event_pipeline.py
---

# AMC MTA Module

This attribution pipeline is based on anonymous aggregated paths from Amazon Marketing Cloud (AMC). The default example first derives anonymous conceptual events, an Amazon Ads daily report, and entity aggregates from a user-event master table used only for simulation. It then generates paths that distinguish impressions from clicks, runs Markov and Shapley, and joins cost and efficiency metrics using the five-segment interaction key.

> `synthetic_user_events_sample.csv` and `amc_touchpoint_events_sample.csv` demonstrate data integration and path construction only. Real AMC processing should occur inside the clean room, exporting only aggregates that satisfy privacy thresholds.

This module performs attribution analysis only. It is not responsible for budget allocation, activation optimization, or automated execution.

## Start Here

- [Complete usage guide](complete-guide.md): scope, inputs, paths, models, metrics, reliability, execution, troubleshooting, and demo.
- [Current data-flow diagram](../introduction/amc-mta-architecture.md#current-data-flow): theme-aware Draw.io architecture covering the canonical AMC pipeline and standardized Markov, Shapley, Uniform, and [Deep Neural Network (DNN)](/en/reference/definitions#dnn-deep-neural-network) evaluation lane.
- [Canonical output index](output-reference.md): reading order, granularity, fields, and interpretation boundaries for the five CSV files.
- [Submission manifest](../reference/submission-manifest.md): required, optional, and excluded content plus acceptance status.
- [Current documentation index](reference-index.md): module sources of truth and topic-specific explanations.

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

The current implementation is a six-stage deterministic pipeline. The table follows the actual call order in `script/run_pipeline.py`, not merely the order in which the output files are presented.

| Stage | Code entry point | Algorithm responsibility | Why it is separated |
| --- | --- | --- | --- |
| 1. Establish the reporting window | `infer_ads_report_window()` | Derive one inclusive date window from Amazon Ads `reportDate` values | AMC paths, Ads cost, and model outputs must describe the same observation period |
| 2. Validate and canonicalize events | `_validated_events()` and `canonical_amc_touchpoint_key()` | Reject malformed events and construct the five-segment touchpoint key | A single key contract prevents attribution and cost from being joined at different grains |
| 3. Build anonymous paths | `build_aggregated_path_rows()` | Segment journeys at conversions, enforce the maximum gap, and aggregate identical paths | Attribution consumes anonymous aggregates rather than user-level event histories |
| 4. Run both attribution models | `run_markov_attribution()` and `run_shapley_attribution()` | Calculate three Outcome allocations with two different path algorithms | Markov is the official model; path-level Shapley is an independently structured benchmark |
| 5. Join spend and govern the recommendation | `aggregate_spend_by_touchpoint()`, `result_rows()`, and `compare_attribution_models()` | Add efficiency metrics, test support and model agreement, and select a point or range | Attribution, cost efficiency, and reliability are distinct calculations and remain auditable |
| 6. Publish the complete artifact set | `publish_with_rollback()` | Replace all six derived artifacts as one recoverable set | A partial run must not leave path, model, and recommendation files from different executions |

### 1. Canonicalize the Shared Touchpoint Grain

The key construction block in `src/touchpoint_key.py` is the first invariant shared by AMC events, Amazon Ads rows, attribution results, and the strategy handoff:

```python
interaction = _component(interaction_type, "interaction_type")       # 1
if interaction not in INTERACTION_TYPES:                              # 2
    raise ValueError(...)                                              # 3
return ":".join((                                                      # 4
    _component(ad_product, "ad_product"),                              # 5
    _component(format_value, "format"),                                # 6
    _component(placement, "placement", allow_missing=True),            # 7
    _component(creative, "creative", allow_missing=True),              # 8
    interaction,                                                       # 9
))
```

| Line | Detailed step | Mapping to the data algorithm | Why it is implemented this way |
| --- | --- | --- | --- |
| 1 | Trim, uppercase, and validate the interaction text through `_component()` | Normalizes the fifth key segment before any comparison | Case or surrounding whitespace must not create a second identity for the same interaction |
| 2 | Restrict the segment to `IMPRESSION` or `CLICK` | Preserves the billing and path semantics used later | [Cost Per Click (CPC)](/en/reference/definitions#cpc-cost-per-click) and [Cost Per Mille (CPM)](/en/reference/definitions#cpm-cost-per-mille--cost-per-thousand-impressions) assignment depends on this distinction; accepting arbitrary values would make cost validation ambiguous |
| 3 | Fail before a malformed key enters a path or output | Enforces the contract at ingestion | Silent repair would hide upstream schema errors |
| 4 | Join exactly five components with `:` | Creates the canonical attribution grain | A fixed shape makes equality checks and joins deterministic |
| 5-6 | Require ad product and format | Identifies the advertising product and inventory/ad type | These dimensions are never structurally nullable in the model |
| 7-8 | Convert missing placement or creative to `UNSPECIFIED` inside the normalized key | Preserves a complete key while keeping the raw structural-null rule separate | The key cannot contain empty segments, but the code does not pretend that missing raw data was observed |
| 9 | Append the already validated interaction | Completes the impression/click-specific identity | Impression and click nodes remain separate even when the first four segments match |

For Amazon Ads rows, `touchpoint_key_from_ads_row()` additionally chooses `inventoryType` for `AMAZON_DSP` and `adType` for sponsored products, reconstructs the expected key, and compares it with the stored `normalizedTouchpoint`. This turns the cost-side key into a verified value rather than trusting a precomputed string.

### 2. Validate Events before Constructing Paths

`_validated_events()` processes every row before any journey is aggregated:

```python
for row_number, row in enumerate(event_rows, start=2):                 # 1
    missing = [field for field in REQUIRED_FIELDS if ...]              # 2
    event_type = str(row["event_type"]).strip().upper()                # 3
    if event_type == TOUCHPOINT:                                        # 4
        touchpoint = canonical_amc_touchpoint_key(...)                  # 5
    if event_type == CONVERSION:                                        # 6
        users = int(_number(row, "users", integer=True))                # 7
        converted_users = int(_number(row, "converted_users", integer=True)) # 8
        if converted_users > users:                                     # 9
            raise ValueError(...)                                       # 10
    events.append({... "event_time_parsed": _parse_datetime(...), ...}) # 11
```

| Line | Detailed step | Algorithm mapping and reason |
| --- | --- | --- |
| 1 | Keep the CSV row number for precise errors | Validation is fail-fast and must identify the source record |
| 2 | Require journey identity, event type, and timestamp | These are the minimum fields needed for grouping, branching, and ordering |
| 3 | Normalize the discriminator once | Later branches compare one stable representation |
| 4-5 | Build touchpoint identity from component columns and reject the legacy free-form key | Path nodes can only enter through the canonical five-segment constructor |
| 6-8 | Parse conversion counts and money as finite, non-negative values | Outcomes become aggregation weights; invalid numbers cannot safely enter sums |
| 9-10 | Enforce `converted_users <= users` | The unique converters represented by a row cannot exceed its represented users |
| 11 | Store a UTC timestamp beside the normalized row | Sorting and gap calculations then use one time basis without mutating the input record |

The same block also enforces `purchase_count >= converted_users`, `new_to_brand_purchases <= purchase_count`, and the rule that a positive purchase, revenue, or new-to-brand Outcome requires at least one converted user. These checks encode the Outcome contract before modeling, rather than allowing a model to compensate for impossible input states.

### 3. Construct One Eligible Path for Each Conversion Segment

The central section of `build_aggregated_path_rows()` maps event history to the path algorithm:

```python
for conversion in sorted(conversions, key=lambda event: event["event_time_parsed"]): # 1
    eligible = [event for event in touchpoints                           # 2
                if (previous_conversion_time is None                     # 3
                    or event["event_time_parsed"] > previous_conversion_time)
                and event["event_time_parsed"] <= conversion["event_time_parsed"]] # 4
    previous_conversion_time = conversion["event_time_parsed"]           # 5
    path_events = _contiguous_path(eligible, max_gap)                     # 6
    if not path_events or path_events[0]["event_time_parsed"] <= start_boundary: # 7
        continue
    if conversion["event_time_parsed"] - path_events[-1]["event_time_parsed"] > max_gap: # 8
        continue
    path = " > ".join(event["touchpoint"] for event in path_events)      # 9
```

| Line | Detailed step | Mapping to the path algorithm | Why it is implemented this way |
| --- | --- | --- | --- |
| 1 | Process a journey's conversions chronologically | Defines non-overlapping conversion segments | Earlier conversions must establish the boundary before later ones are evaluated |
| 2-4 | Keep touchpoints after the prior conversion and no later than the current conversion | Assigns each touchpoint to at most one conversion segment | Prevents historical interactions from being reused to support multiple purchases |
| 5 | Move the segment boundary to the current conversion | Closes the current segment | The next iteration cannot look behind this purchase |
| 6 | Sort eligible touchpoints and keep only the last contiguous suffix whose adjacent gaps are within the configured maximum | Implements the 14-day adjacency rule across the path | A single old break removes the disconnected prefix without discarding the valid recent suffix |
| 7 | Reject empty paths and paths that start on or before the lower report boundary | Applies the strict path-start window | The full observable path must begin inside the analysis window |
| 8 | Enforce the same maximum gap from the last touchpoint to conversion | Adds the terminal edge to the adjacency rule | Checking touchpoint-to-touchpoint gaps alone would admit stale final interactions |
| 9 | Serialize the ordered canonical nodes with ` > ` | Produces the AMC path contract | Order is retained for Markov; Shapley later derives a unique set explicitly |

Identical `(marketplace, advertiser_id, path)` records are then summed for `users`, `converted_users`, `purchase_count`, and `revenue`. Revenue is rounded only after aggregation, and rows are sorted by the grouping key so identical inputs produce identical output order.

### 4. Map Paths to the Two Algorithms

The models deliberately receive different representations of the same validated aggregate:

| Representation | Construction | Algorithm meaning |
| --- | --- | --- |
| Converted-user Markov path | One `START ... CONVERSION` row weighted by `converted_users`, plus one `START ... NULL` row weighted by `users - converted_users` | Estimates the probability of reaching conversion versus non-conversion |
| Purchase and revenue Markov paths | Only positive-Outcome paths, ending in `CONVERSION` and weighted by the selected Outcome | Applies the same removal-effect network independently to order and revenue mass |
| Shapley coalition row | Ordered path converted to its first-occurrence unique touchpoint set | Defines the members of the path-level unanimity game; position and repetition intentionally do not change the split |

See [Markov removal effect](standardized-interface/markov.md) and [Shapley path attribution](standardized-interface/shapley.md) for the line-by-line model internals.

### 5. Join Cost and Preserve Output Totals

`aggregate_spend_by_touchpoint()` rebuilds and verifies every Amazon Ads key, validates `CPC -> CLICK` and `CPM -> IMPRESSION`, and aggregates spend at the same five-segment grain. `result_rows()` refuses to emit a model touchpoint without matching spend.

Before serialization, `_rounded_with_residual()` uses the largest-remainder method:

1. scale each non-negative raw value to integer output units;
2. floor every value;
3. round the original total to obtain the target number of units;
4. give the remaining units to the largest fractional remainders, with deterministic tie-breaks;
5. divide by the scale.

This is why displayed shares and attributed amounts conserve their displayed totals even when each row must be rounded independently.

### 6. Compare Models and Select the Handoff Value

For every touchpoint and each of the three Outcomes, `compare_attribution_models()` performs the following code-level sequence:

```python
gap_pp, relative_gap = _decimal_gap_metrics(markov_share, shapley_share) # 1
support = support_five[touchpoint]                                       # 2
reliability = reliability_fields(                                       # 3
    calculation_valid=True,                                             # 4
    data_support_sufficient=data_support_is_sufficient(support),         # 5
    models_consistent=models_are_consistent(gap_pp, relative_gap, ...),  # 6
)
recommended_value = _recommended_value(row, has_outcome=has_outcome)     # 7
```

| Line | Detailed step | Why it is implemented this way |
| --- | --- | --- |
| 1 | Calculate absolute percentage-point and mean-relative gaps from preserved decimal shares | Reliability must not change because an output column was rounded for display |
| 2 | Retrieve raw unique-path, converted-user, and purchase support for the complete touchpoint | Support is evidence about the source data, not about the model's allocated result |
| 3-6 | Require calculation validity, all support thresholds, and both consistency thresholds | The contract exposes three independent Boolean criteria and labels a row `RELIABLE` only when all pass |
| 7 | Return the official Markov share when reliable; otherwise return the ordered Markov-Shapley interval | Downstream use receives either one governed point or an explicit sensitivity range |

Zero-total Outcomes remain empty because a normalized attribution recommendation is undefined when there is no Outcome mass.

### 7. Publish Atomically with Rollback

`run_pipeline()` builds the path report and all five attribution artifacts in one temporary directory. `publish_with_rollback()` then stages copies beside their destinations, backs up existing destinations, and replaces each with `os.replace()`. If any replacement fails, already replaced files are restored in reverse order. The design protects the six-file snapshot as a unit: successful validation publishes everything, while model, validation, or I/O failure leaves the previous published set intact.

## Quick Run

Run from the repository root:

```bash
uv run python -X utf8 -B script/run_pipeline.py
uv run python -X utf8 -B script/validate_data_alignment.py
```

Update the events and Amazon Ads input files, then run directly. The canonical pipeline determines its window automatically from the earliest through latest Ads `reportDate`; it supports any duration, cross-year windows, and leap days without changing configuration dates. Aggregated paths and all five model results are published together only after every artifact passes validation. On failure, the previous six derived artifacts remain in place, and raw inputs are not overwritten. See [running the module](../introduction/environment/amc-mta-usage.md) for custom file locations and complete validation rules.

Default canonical outputs:

- `modules/mta_attribution/outputs/attribution/amc_markov_attribution_results.csv`
- `modules/mta_attribution/outputs/attribution/amc_shapley_attribution_results.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_touchpoints.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_model_comparison_summary.csv`
- `modules/mta_attribution/outputs/attribution/amc_mta_recommended_attribution.csv`

The first two are each model's primary five-segment result. The final three provide diagnostics for “touchpoint count × 3 Outcomes,” an overall summary for three Outcomes, and recommendation records for the same “touchpoint count × 3” shape. The current 90-day sample has 17 touchpoints, so diagnostics and recommendations contain 51 rows each. All three dual-model artifacts directly expose the three Booleans “calculation valid,” “data support sufficient,” and “models consistent,” plus a binary reliability result. All three must be true for `RELIABLE`. For each Outcome, the summary AND-aggregates the three Booleans over every touchpoint; the overall comparison status and other difference metrics are diagnostic only. The current sample has `51 RELIABLE / 0 UNRELIABLE`.

The recommendation table adds `recommended_value`: reliable records for a nonzero Outcome use the Markov `official_share`; unreliable records use the ascending closed interval `[low,high]` of Markov and Shapley shares; zero Outcomes remain empty. The recommendation table therefore has 15 columns, while the schemas of other outputs remain unchanged.

There is currently no rolling-window stability evidence. Existing results can therefore only be interpreted as exploratory attribution in the current window, not as long-term stable contribution or causal incrementality. Stability and automated-decision constraints do not enter the reliability calculation, and `RELIABLE` never enables automatic budget execution.

For a first review, read “this page → [complete usage guide](complete-guide.md) → [canonical output index](output-reference.md) → [submission manifest](../reference/submission-manifest.md).”

## Documentation

- [Data contract](../datasets/amc-data-contract.md): the only complete description of fields, 14-day path rules, AMC/Ads five-segment keys, billing assignment, and model semantics.
- [Running the module](../introduction/environment/amc-mta-usage.md): commands, parameters, and outputs.
- [Single-touchpoint attribution reliability](reliability.md): judge a result using calculation validity, sufficient data support, and model consistency.
- [Amazon Ads sample](../datasets/amazon-ads-sample.md): cost table and join key.
- [Simulated data](../datasets/amc-simulated-data.md): roles of the user-event master table and four derived artifacts.
- AMC platform background research and project-management material are external to the original project. They are neither runtime dependencies nor included with the standalone `mta_attribution/` submission.

AMC paths, Amazon Ads inputs, and attribution outputs all use `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`, where `INTERACTION_TYPE` may only be `IMPRESSION` or `CLICK`. CPC cost is assigned only to CLICK, CPM cost only to IMPRESSION, and non-billable interactions have zero cost. AMC input explicitly distinguishes `converted_users` (unique purchasing users) from `purchase_count` (order count). The [data contract](../datasets/amc-data-contract.md) defines the complete constraints.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `simulated_touchpoints.py`

Source: `modules/mta_attribution/src/simulated_touchpoints.py`

- Responsibility: Define the fixed legacy touchpoint catalogue used by committed sample generation.
- Inputs: Declarative touchpoint specifications.
- Outputs: Validated touchpoint and entity specifications.
- Dependencies: `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_end_to_end_pipeline.py`.

### `synthetic_event_pipeline.py`

Source: `modules/mta_attribution/src/synthetic_event_pipeline.py`

- Responsibility: Reproduce the legacy five-segment sample and its Ads/entity projections.
- Inputs: Report dates and the fixed simulated touchpoint catalogue.
- Outputs: Synthetic user events, path events, Ads rows, and entity aggregates.
- Dependencies: `simulated_touchpoints.py` and `touchpoint_key.py`.
- Verification: `modules/mta_attribution/tests/test_end_to_end_pipeline.py`.

