---
title: "Layer 1 — Unit and Contract Tests"
compact: "Model conformance and unit acceptance cases, conservation, adapters, keys, report windows and reproducibility."
source_files: modules/mta_standard/src/mta_sim_generator_adapter.py
test_files: modules/mta_standard/tests/test_mta_sim_generator_adapter.py
---

# Layer 1 — Unit and Contract Tests

284 deterministic tests, no third-party runner, and no runtime network access after the submodule is initialized.

### `mta_attribution/tests/test_attribution_contract.py`

- Tests: 18
- Focus: Result shaping, spend aggregation, conservation-preserving rounding, row adapters, and both models' removal-effect and coalition behaviour

### `mta_attribution/tests/test_path_report_builder.py`

- Tests: 24
- Focus: Window boundaries, gap rules, journey segmentation

### `mta_attribution/tests/test_attribution_model_comparison.py`

- Tests: 29
- Focus: Reliability contract, gap metrics, atomic publication and rollback

### `mta_attribution/tests/test_auto_report_window.py`

- Tests: 8
- Focus: Window inferred from Ads data, never from config

### `mta_attribution/tests/test_touchpoint_key.py`

- Tests: 6
- Focus: Key component rules and data alignment

### `mta_attribution/tests/test_end_to_end_pipeline.py`

- Tests: 22
- Focus: Byte-reproducible dataset, six-artifact atomicity, outcome conservation

### `mta_standard/tests/test_touchpoint_adapter.py`

- Tests: 23
- Focus: Four ↔ five segment reversibility, rejected mappings

### `mta_standard/tests/test_dataloader.py`

- Tests: 21
- Focus: External paths, header validation, ground-truth isolation

### `mta_attribution/tests/test_attribution_model_interface.py`

- Tests: 17
- Focus: Interface conformance and the standard-model regression guarantee

### `mta_attribution/tests/test_markov_standard_attribution_model.py`

- Tests: 1
- Focus: Markov adapter ownership and standard output

### `mta_attribution/tests/test_shapley_standard_attribution_model.py`

- Tests: 1
- Focus: Shapley adapter ownership and standard output

### `mta_attribution/tests/test_uniform_attribution_model.py`

- Tests: 1
- Focus: Uniform baseline ownership and standard output

### `mta_standard/tests/test_output_contract.py`

- Tests: 22
- Focus: The four output invariants and the zero-outcome rule

### `mta_standard/tests/test_evaluation.py`

- Tests: 20
- Focus: Ground-truth grains, metric bounds, determinism

### `mta_attribution/tests/test_dnn_attribution_model.py`

- Tests: 33
- Focus: Features, unknown bucket, convergence, persistence

### `mta_standard/tests/test_model_pipeline.py`

- Tests: 2
- Focus: Registry-driven execution and immutable run collection

### `mta_standard/tests/test_mta_sim_generator_adapter.py`

- Tests: 2
- Focus: Pinned generator invocation and adapted output

### `mta_strategy_recommendation/tests/test_hierarchy_validator.py`

- Tests: 34
- Focus: Lineage, capacity, budget split, output boundary

Run them:

```bash
python -X utf8 -B -m unittest discover -s modules/mta_attribution/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_standard/tests -t . -p 'test_*.py'
python -X utf8 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -t . -p 'test_*.py'
```

One file at a time:

```bash
python -X utf8 -B -m unittest discover \
  -s modules/mta_attribution/tests \
  -p 'test_dnn_attribution_model.py' \
  -t .
```

> [!TIP]
> Use `-t .` so `unittest` imports tests and runtime code through their repository package paths.

### The wrapper regression guarantee

The most load-bearing test asserts that standardizing a model changed none of its numbers:

```python
def test_markov_matches_a_direct_call_exactly(self) -> None:
    standard = self._standard_shares(MarkovRemovalEffectModel())
    for result in run_markov_attribution(list(self.dataset.path_rows)):
        for outcome in SUPPORTED_OUTCOMES:
            share_field, value_field = OUTCOME_FIELDS[outcome]
            row = standard[(result.touchpoint, outcome)]
            self.assertEqual(row.attribution_share, getattr(result, share_field))
            self.assertEqual(row.attributed_value, getattr(result, value_field))
```

Note `assertEqual`, not `assertAlmostEqual`. The wrapper forwards and relabels; it computes nothing, so exact float equality is the correct assertion.

A second test pins the fixture's expected values:

```python
EXPECTED_MARKOV_CONVERTED_USER_SHARES = {
    fixtures.DISPLAY: 0.36666666666666664,
    fixtures.BRAND:   0.1666666666666667,
    fixtures.SEARCH:  0.46666666666666673,
}
```

> [!NOTE]
> The two tests catch different failures. The first catches a **wrapper** that alters results; the second catches a change to the **model mathematics** itself. Without the pinned values, editing the Markov solver would still pass, because the wrapper would faithfully reproduce the new, wrong number.

---

## Source Files

### `mta_sim_generator_adapter.py`

Source: `modules/mta_standard/src/mta_sim_generator_adapter.py`

- Responsibility: Invoke the pinned ZheyuanWu generator and prepare
  framework-compatible model/evaluation views. Public
  `prepare_single_scope_reports(source_path_report, performance_report,
  destination_path_report, destination_performance_report, marketplace)` also
  partitions and aggregates an existing uploaded daily report without invoking
  the generator. It refuses an ambiguous multi-marketplace upload when no
  marketplace is supplied. Current provider-aware configurations receive their
  matching ProviderCapabilities when compatibility keys are requested;
  historical configuration objects retain the no-argument key path. Public
  `export_mta_sim_dataset_to_postgresql(...)` invokes the external package's
  explicit PostgreSQL writer for an already accepted configuration; it accepts
  connection information only from the backend and never from a browser path
  or dynamically supplied writer reference.
- Inputs: Submodule path, configuration, output directory, and generator
  variant; or explicit uploaded path, performance, destination paths, and an
  optional exact marketplace selection; or a backend-owned PostgreSQL
  connection string plus explicit reset Boolean.
- Outputs: Generated manifest, model dataset, and evaluation-only ground truth
  path; or deterministic matching single-scope path and performance reports
  that preserve both source uploads; or the external writer's database
  manifest with no credential retained in the adapter result.
- Dependencies: External generator, dataloader, and touchpoint adapter.
- Verification: `modules/mta_standard/tests/test_mta_sim_generator_adapter.py`.
  The external toy integration runs only when the package entry points,
  configuration module, and toy configuration are regular files; directory-only
  remnants skip with an initialization remedy. Malformed present files still fail.
  Release checks require the [preflight](/en/introduction/backend/deployment-preflight)
  before this suite, so incomplete deployment inputs fail before tests.


## Verification

- **Scope:** The assurance behavior specified on this page.
- **Cases:** Normal, missing, invalid and deterministic outputs; evaluation truth remains isolated.
- **Command:** `uv run python -X utf8 -B -m unittest modules.mta_standard.tests.test_mta_sim_generator_adapter`.
- **Limitations:** The generator integration requires the pinned checkout; no production database is used.
