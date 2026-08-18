---
title: Shapley Path Attribution
description: Algorithm, formulas, and code mapping for AggregatedShapleyAttribution
compact: "Line-by-line internals of `AggregatedShapleyAttribution` in `attribution_contract.py`: `amc_rows_to_shapley_rows`, the `channels` coalition field, path-unanimity `coalition_value`, closed-form equal split over unique touchpoints in `_scores`, share normalization. Explains why order and repeats do not change credit."
lang: en-US
source_files: modules/mta_attribution/src/shapley_attribution_model.py, modules/mta_attribution/src/shapley_standard_attribution_model.py
---

# Shapley Path Attribution

## Model Intuition <span class="status-label status-verified" aria-label="Verified"></span>

The Shapley value comes from cooperative game theory and allocates a team's payoff using average marginal contributions across every possible joining order. This project implements a more specific **path-level unanimity game**: an aggregated path's Outcome is available only when all unique touchpoints on that path are present.

For Shapley-value applications in advertising attribution, read [Shapley Value Methods for Attribution Modeling in Online Advertising](/research/mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf).

Under this value function, the exact Shapley value has a closed-form solution: split a path's Outcome equally among its unique touchpoints.

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

Implementation: class `AggregatedShapleyAttribution` in `modules/mta_attribution/src/attribution_contract.py`. The relevant source blocks are reproduced directly below and decomposed line by line.

The code is decomposed into four steps: adapt ordered paths to coalitions, define the coalition value, apply the exact closed form, and convert scores into shares and attributed totals.

### 1. Convert a Path into One Coalition

`amc_rows_to_shapley_rows()` adapts each validated AMC aggregate:

```python
for idx, row in enumerate(amc_rows, start=1):                         # 1
    touchpoints = unique_touchpoints(                                 # 2
        validate_amc_aggregated_row(row, idx)                         # 3
    )
    rows.append({                                                     # 4
        "channels": ",".join(touchpoints),                            # 5
        "converted_users": safe_int(row.get("converted_users")),      # 6
        "purchase_count": safe_int(row.get("purchase_count")),        # 7
        "revenue": safe_float(row.get("revenue")),                    # 8
    })
```

#### Line 1 — Preserve a stable row identifier while traversing aggregates

- Algorithm mapping: Keeps validation errors attributable to an input row
- Why it is implemented this way: The adapter must fail before a malformed coalition enters the model

#### Line 2 — Retain each touchpoint's first occurrence only

- Algorithm mapping: Converts an ordered path into a set-like coalition
- Why it is implemented this way: In a unanimity game, membership matters; repeated exposure is not a second player

#### Line 3 — Enforce path, terminal-state, key, and Outcome invariants

- Algorithm mapping: Establishes a valid game record
- Why it is implemented this way: The model should not assign value to invalid or reserved states

#### Lines 4-5 — Serialize the unique members as `channels`

- Algorithm mapping: Supplies the class's coalition input
- Why it is implemented this way: The name distinguishes unordered membership from the ordered AMC `path`

#### Lines 6-8 — Carry each Outcome independently

- Algorithm mapping: Creates three games over the same coalitions
- Why it is implemented this way: People, purchases, and money are allocated separately and are never added together

`unique_touchpoints()` preserves first-occurrence order for deterministic serialization, but the scoring algorithm treats the result as a coalition. Therefore path order and exposure count do not affect a row's split.

### 2. Define the Coalition Value

The implementation retains `coalition_value()` as the explicit definition of the game:

```python
members = set(coalition)                                             # 1
return sum(                                                          # 2
    safe_float(row.get(outcome_field))                               # 3
    for row in self.rows                                             # 4
    if set(parse_channels(str(row["channels"]))).issubset(members)   # 5
)
```

#### Line 1 — Convert the evaluated coalition to a membership set

- Mapping to the Shapley game: Removes irrelevant order
- Reason: Cooperative-game coalitions are sets of players

#### Lines 2-4 — Sum the selected Outcome over eligible path games

- Mapping to the Shapley game: Defines the value `v(S)`
- Reason: Each aggregate contributes its own payoff mass

#### Line 5 — Include a path only when all its unique touchpoints are present

- Mapping to the Shapley game: Implements a unanimity game
- Reason: A path's payoff is unavailable to a partial subset of its members

In notation, the implemented value function is:

$$
v(S) = \sum_p \text{path outcome}(p)\,
\mathbf{1}\!\left[U_p \subseteq S\right]
$$

where $U_p$ is the unique-touchpoint set of path $p$.

### 3. Apply the Exact Closed Form

Because the total game is a sum of unanimity games, `_scores()` does not need to enumerate all subsets or permutations:

```python
scores = {touchpoint: 0.0 for touchpoint in self.touchpoints}        # 1
for row in self.rows:                                               # 2
    touchpoints = tuple(dict.fromkeys(                              # 3
        parse_channels(str(row["channels"]))
    ))
    if not touchpoints:                                             # 4
        continue
    outcome = safe_float(row.get(outcome_field))                    # 5
    per_touchpoint_credit = outcome / len(touchpoints)              # 6
    for touchpoint in touchpoints:                                  # 7
        scores[touchpoint] += per_touchpoint_credit                  # 8
return scores                                                       # 9
```

#### Line 1 — Initialize every observed player at zero

- Algorithm mapping: Creates a complete deterministic result domain
- Why it is implemented this way: Touchpoints remain present even if one Outcome has zero mass

#### Line 2 — Treat each aggregate as one weighted unanimity subgame

- Algorithm mapping: Uses Shapley additivity
- Why it is implemented this way: The Shapley value of a sum of games equals the sum of their Shapley values

#### Line 3 — Defensively deduplicate while retaining first occurrence

- Algorithm mapping: Defines the row's unique members
- Why it is implemented this way: It protects the equal split even if an adapter is bypassed

#### Line 4 — Skip an empty coalition

- Algorithm mapping: Avoids division by zero
- Why it is implemented this way: Valid AMC paths normally make this branch unreachable, but the class remains safe in isolation

#### Line 5 — Read only the Outcome requested by the caller

- Algorithm mapping: Runs the same mechanics for three distinct measures
- Why it is implemented this way: Outcome types remain separate

#### Line 6 — Divide the row payoff equally among all coalition members

- Algorithm mapping: Applies the exact Shapley value for a unanimity game
- Why it is implemented this way: Every member is essential and symmetric within that subgame

#### Lines 7-8 — Accumulate the member's credit across all path games

- Algorithm mapping: Uses Shapley additivity
- Why it is implemented this way: A touchpoint's final score includes every path on which it appears

#### Line 9 — Return unnormalized attributed mass

- Algorithm mapping: Preserves the Outcome total before shares are calculated
- Why it is implemented this way: The caller can expose both amount and share

Thus, if path $p$ has unique-touchpoint set $U_p$ and Outcome $y_p$, the score for touchpoint $t$ is:

$$
\text{Shapley score}(t)
= \sum_{p: t \in U_p}
\frac{\text{path outcome}(p)}{|U_p|}
$$

### 4. Produce Shares and Attributed Amounts

`attribute()` runs `_scores()` three times and then builds one result per touchpoint:

```python
converted_user_scores = self._scores("converted_users")             # 1
purchase_count_scores = self._scores("purchase_count")              # 2
revenue_scores = self._scores("revenue")                             # 3
total_revenue_score = sum(revenue_scores.values())                   # 4
revenue_share = (                                                    # 5
    revenue_scores[touchpoint] / total_revenue_score                 # 6
    if total_revenue_score > 0 else 0.0                              # 7
)
AttributionResult(                                                   # 8
    revenue_share=revenue_share,                                    # 9
    attributed_revenue=revenue_scores[touchpoint],                  # 10
    ...
)
```

#### Lines 1-3 — Calculate independent score vectors for the three Outcomes

Algorithm mapping and reason: No Outcome is used as a proxy or added to another Outcome.

#### Line 4 — Sum one score vector

Algorithm mapping and reason: Shapley efficiency makes this equal the input Outcome total, subject only to floating-point arithmetic.

#### Lines 5-7 — Normalize when the Outcome total is positive; otherwise return zero

Algorithm mapping and reason: Avoids an undefined division and correctly represents a zero-Outcome dataset.

#### Lines 8-10 — Emit both normalized share and original allocated mass

Algorithm mapping and reason: Consumers can use proportions while auditors can verify conservation against source totals.

The converted-user and purchase-count branches use the same lines and guards. Output rounding is handled later by the shared largest-remainder serializer, so row formatting does not change the model's internal scores.

Its share is:

$$
\text{Shapley share}(t)
= \frac{\text{Shapley score}(t)}
{\sum_j \text{Shapley score}(j)}
$$

## Difference from General Shapley Implementations <span class="status-label status-verified" aria-label="Verified"></span>

The current code does not train a predictive model and then enumerate every feature subset, nor does it use the SHAP package. It computes an exact closed-form solution for an explicitly defined path-unanimity value function. The result is deterministic, conserves totals, and is easy to reproduce, but touchpoints on the same path do not receive different credit based on position or time.

## Interpretation <span class="status-label status-inference" aria-label="Inference"></span>

Shapley results provide a sensitivity reference that is symmetric with respect to touchpoint co-occurrence on paths. They do not automatically identify causal order, budget saturation, or genuine interaction effects among touchpoints.

The canonical output is `amc_shapley_attribution_results.csv`, which enters model comparison together with Markov results.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `shapley_attribution_model.py`

Source: `modules/mta_attribution/src/shapley_attribution_model.py`

- Responsibility: Implement exact path-level Shapley attribution as a sum of unanimity games.
- Inputs: Validated five-segment aggregated paths.
- Outputs: Native `AttributionResult` records.
- Dependencies: `attribution_contract.py`.
- Verification: `modules/mta_attribution/tests/test_attribution_contract.py`. There is no model-specific suite; the shared contract tests exercise `run_shapley_attribution` and `AggregatedShapleyAttribution` directly.

### `shapley_standard_attribution_model.py`

Source: `modules/mta_attribution/src/shapley_standard_attribution_model.py`

- Responsibility: Adapt the native path-level Shapley model to the common interface.
- Inputs: `MtaSimDataset` with model-facing path rows.
- Outputs: Four-segment `StandardAttributionRow` records.
- Dependencies: Native Shapley model plus `mta_standard` framework contracts.
- Verification: `modules/mta_attribution/tests/test_shapley_standard_attribution_model.py`.

## References

- [Shapley Value Methods for Attribution Modeling in Online Advertising (PDF)](/research/mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf)
