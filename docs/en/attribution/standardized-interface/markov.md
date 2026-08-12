---
title: Markov Removal Effect
description: Algorithm, formulas, and code mapping for WeightedMarkovAttribution
compact: "Line-by-line internals of `WeightedMarkovAttribution` in `attribution_contract.py`: START/CONVERSION/NULL states, `amc_rows_to_markov_rows`, weighted `transition_matrix`, `conversion_probability` fixed-point iteration capped at 1000 steps and 1e-12, removal-effect normalization, `run_markov_attribution` output."
lang: en-US
---

# Markov Removal Effect

## Model Intuition <span class="status-label status-verified" aria-label="Verified"></span>

A first-order Markov chain treats `START`, every touchpoint, `CONVERSION`, and `NULL` as states. Historical aggregated paths provide weighted transition counts between states; normalization turns them into transition probabilities.

For background on data-driven path attribution, including transition-based methods, read [Data-driven Multi-touch Attribution Models](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf).

`WeightedMarkovAttribution` predicts the next state from the current state alone, so it does not remember the complete earlier path.

## Current Implementation <span class="status-label status-verified" aria-label="Verified"></span>

Implementation: class `WeightedMarkovAttribution` in `modules/mta_attribution/src/attribution_contract.py`. The relevant source blocks are reproduced directly below and decomposed line by line.

The implementation has five explicit parts: adapt AMC aggregates, inventory states, estimate transitions, solve absorption probability, and normalize removal effects. Each Outcome runs through a separate instance of the same algorithm.

### 1. Adapt AMC Aggregates into Weighted State Paths

For converted users, `amc_rows_to_markov_rows()` splits one AMC aggregate into its converting and non-converting populations:

```python
base_path = [START, *touchpoints]                                  # 1
if converted_users > 0:                                            # 2
    rows.append({                                                   # 3
        "path": " > ".join([*base_path, CONVERSION]),              # 4
        "weight": float(converted_users),                           # 5
    })
null_weight = users - converted_users                              # 6
if null_weight > 0:                                                # 7
    rows.append({                                                   # 8
        "path": " > ".join([*base_path, NULL]),                    # 9
        "weight": null_weight,                                     # 10
    })
```

| Line | Detailed step | Algorithm mapping | Reason |
| --- | --- | --- | --- |
| 1 | Prefix the observed touchpoint sequence with `START` | Creates the initial Markov state | Every journey needs a common origin for its conversion probability |
| 2-5 | Emit a `CONVERSION`-terminal path weighted by converted users | Adds converting transition mass | Aggregated rows represent populations, so one row must count as many users rather than one path observation |
| 6 | Derive non-converters as `users - converted_users` | Reconciles the aggregate into two mutually exclusive terminal populations | This preserves the input user total exactly |
| 7-10 | Emit a `NULL`-terminal path for positive non-converting mass | Adds failure/abandonment transition mass | Without a competing absorbing state, eventual conversion probability would be trivially one for every connected path |

For `purchase_count` and `revenue`, `amc_rows_to_outcome_markov_rows()` keeps only positive-Outcome paths, appends `CONVERSION`, and uses the selected Outcome as `weight`. This means the three models share mechanics but not weights: converted-user attribution models people versus non-converters, whereas purchase and revenue attribution model the network traversed by their respective Outcome mass.

### 2. Inventory the State Space

The constructor performs only deterministic preparation:

```python
self.path_rows = list(path_rows)                                    # 1
self.paths = [parse_path(str(row["path"])) for row in self.path_rows] # 2
self.touchpoints = sorted({                                         # 3
    state for path in self.paths for state in path                  # 4
    if state not in {START, CONVERSION, NULL}                       # 5
})
```

| Line | Detailed step | Why |
| --- | --- | --- |
| 1 | Materialize the input sequence | The rows are traversed repeatedly for baseline and every removal run |
| 2 | Parse serialized paths once | Transition estimation should operate on state lists, not repeatedly split strings |
| 3-5 | Collect nonterminal states and sort them | Every observed touchpoint is removed exactly once, and sorting makes output order reproducible |

### 3. Build the Weighted Transition Matrix

The key loop in `transition_matrix()` is:

```python
for row, path in zip(self.path_rows, self.paths):                   # 1
    weight = safe_float(row.get("weight", row.get("users")))        # 2
    if weight <= 0:                                                 # 3
        continue
    for current, nxt in zip(path, path[1:]):                        # 4
        if current == removed_touchpoint:                           # 5
            break
        if nxt == removed_touchpoint:                               # 6
            counts[current][NULL] += weight                         # 7
            break
        counts[current][nxt] += weight                              # 8
for current, next_counts in counts.items():                         # 9
    total = sum(next_counts.values())                               # 10
    matrix[current] = {nxt: count / total for nxt, count in next_counts.items()} # 11
```

| Line | Detailed step | Mapping to the Markov algorithm | Why it is implemented this way |
| --- | --- | --- | --- |
| 1 | Traverse each aggregate beside its parsed path | Associates the path topology with its population/Outcome mass | Aggregated observations cannot be counted equally |
| 2 | Prefer the explicit Outcome weight, falling back to users | Supports all three model adapters with one transition engine | The engine stays independent of a particular Outcome column |
| 3 | Ignore zero-mass rows | Zero weight cannot change a probability and may otherwise create empty transition totals | This keeps normalization defined |
| 4 | Convert each path into adjacent directed edges | Implements the first-order assumption | Only the current state determines the next-state distribution |
| 5 | Stop if the traversal has reached the removed node | Removes all outgoing behavior from that touchpoint | A removed state cannot transmit probability further |
| 6-7 | Redirect an edge entering the removed node to `NULL`, then stop | Implements failure when the path depends on the removed touchpoint | Simply deleting the node and joining its neighbors would invent a transition never observed |
| 8 | Add the complete row weight to the observed edge | Builds weighted transition counts | The resulting matrix represents mass, not just distinct path shapes |
| 9-11 | Normalize every current state's outgoing counts | Produces conditional probabilities whose row sums equal one | Absorption iteration requires probabilities rather than counts |

### 4. Solve Eventual Conversion Probability

`conversion_probability()` applies fixed-point iteration to the transition matrix:

```python
values = {state: 0.0 for state in states}                            # 1
values[CONVERSION] = 1.0                                            # 2
values[NULL] = 0.0                                                  # 3
for _ in range(1000):                                               # 4
    max_delta = 0.0                                                 # 5
    next_values = dict(values)                                      # 6
    for state in states:                                            # 7
        if state in {CONVERSION, NULL}:                             # 8
            continue
        prob = sum(p * values.get(nxt, 0.0)                          # 9
                   for nxt, p in matrix.get(state, {}).items())
        max_delta = max(max_delta, abs(prob - values.get(state, 0.0))) # 10
        next_values[state] = prob                                   # 11
    values = next_values                                            # 12
    if max_delta < 1e-12:                                           # 13
        break
return values.get(START, 0.0)                                      # 14
```

| Line | Detailed step | Algorithm mapping and reason |
| --- | --- | --- |
| 1-3 | Initialize unknown states to zero, conversion to one, and null to zero | These are the boundary conditions for eventual absorption |
| 4 | Limit the solver to 1,000 iterations | Prevents a malformed or non-convergent graph from hanging the pipeline |
| 5 | Reset the largest observed change for this iteration | Convergence is evaluated separately for each complete update |
| 6 | Copy the prior iteration before updating | Produces a synchronous update: every new value uses the same previous vector, independent of set iteration order |
| 7-8 | Update only transient states | Absorbing boundary values must remain fixed |
| 9 | Apply `value(state) = sum(P(state,next) * value(next))` | This is the Bellman-style fixed-point equation for eventual conversion probability |
| 10-11 | Record the largest change and store the new probability | The maximum norm gives a direct convergence test across all states |
| 12-13 | Commit the iteration and stop below `1e-12` | The tolerance yields stable downstream removal differences without solving a matrix inverse |
| 14 | Read the probability at the common initial state | This is the model's overall probability of eventual conversion |

If the limit is reached while transient states exist, the function raises an error instead of publishing an approximate result whose quality is unknown.

### 5. Convert Removal Effects into Attribution Shares

```python
base_prob = self.conversion_probability()                            # 1
for touchpoint in self.touchpoints:                                 # 2
    removed_prob = self.conversion_probability(                     # 3
        removed_touchpoint=touchpoint)
    effects[touchpoint] = max(base_prob - removed_prob, 0.0)        # 4
total_effect = sum(effects.values())                                # 5
if total_effect <= 0:                                               # 6
    equal_share = 1 / len(self.touchpoints) if self.touchpoints else 0.0 # 7
    return {touchpoint: equal_share for touchpoint in self.touchpoints} # 8
return {touchpoint: effect / total_effect for touchpoint, effect in effects.items()} # 9
```

| Line | Detailed step | Algorithm mapping and reason |
| --- | --- | --- |
| 1 | Solve the intact network once | Establishes the counterfactual reference probability |
| 2-3 | Rebuild and solve the network after removing each touchpoint | Measures each node with the same removal intervention |
| 4 | Take the non-negative probability loss | Defines removal effect and prevents numerical or structural increases from becoming negative attribution |
| 5 | Sum all effects | Creates the normalization denominator |
| 6-8 | Use an equal split only when no touchpoint has positive removal effect | Preserves a complete share vector in a degenerate but non-empty model |
| 9 | Normalize positive effects | Produces shares that sum to one |

### 6. Orchestrate Three Independent Outcome Models

`run_markov_attribution()` constructs separate instances for `converted_users`, `purchase_count`, and `revenue`, unions their touchpoint sets, calculates each model's shares, and multiplies each share by its original total Outcome. This separation is important: Amazon Marketing Cloud purchase Outcomes are never summed with Amazon Ads diagnostic conversions, and revenue weights never alter converted-user transition counts.

## Formulas

For touchpoint (t):

$$
\text{removal effect}(t)
= \max\left(
\text{base conversion probability}
- \text{conversion probability without } t,
0
\right)
$$

The attribution share is:

$$
\text{Markov share}(t)
= \frac{\text{removal effect}(t)}
{\sum_j \text{removal effect}(j)}
$$

## Interpretation <span class="status-label status-inference" aria-label="Inference"></span>

A higher share means that removing the touchpoint causes a larger model-estimated drop in conversion probability within the current historical transition network. This is an observational path association, not incremental return measured by a randomized experiment.

## Code Output <span class="status-label status-verified" aria-label="Verified"></span>

`run_markov_attribution()` builds separate weighted Markov models for converted users, purchase count, and revenue, then writes `amc_markov_attribution_results.csv`. Cost is aggregated from the Amazon Ads-style daily report through the normalized touchpoint key and does not enter Markov transition-probability training.

## References

- [Data-driven Multi-touch Attribution Models (PDF)](/research/mta/Data-driven%20Multi-touch%20Attribution%20Models.pdf)
