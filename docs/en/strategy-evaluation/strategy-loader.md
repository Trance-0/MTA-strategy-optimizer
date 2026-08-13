---
title: Strategy Loader Specification
description: JSON configuration, registry, validation, and instantiation-by-identifier for the strategy evaluation layer
compact: "PROPOSED, unbuilt design for `strategy_registry.py`, `strategy_loader.py`, `strategy_validator.py`, declaration JSON such as `budget_seed_v4.json`, `build_strategy()` and `list_strategies()`, three-stage validation, determinism test. Read when implementing the registry; none of it exists yet."
lang: en-US
---

# Strategy Loader Specification

## Purpose <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The attribution layer's [`model_registry.py`](/en/attribution/standardized-interface/#model-registry-py) lets a caller run every registered model with one loop:

```python
for model_id in MODEL_REGISTRY:
    rows = build_model(model_id).fit(dataset).attribute(dataset)
```

The strategy loader provides the same capability for strategies: register them once, instantiate them by identifier, and run them through a shared contract. The caller does not need to know which file implements which strategy.

## JavaScript Object Notation (JSON) Configuration <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Each strategy is declared in one JSON file. The loader reads a directory of declarations rather than importing Python modules directly, which keeps strategy registration separate from strategy implementation and makes it auditable without executing code.

### Schema

```json
{
  "strategy_id": "budget_seed_v4",
  "strategy_version": "1.0.0",
  "display_name": "Multi-Touch Attribution-Driven Budget Seed (v4)",
  "description": "Deterministic initializer using Multi-Touch Attribution scores, entity bridge, and capacity rules.",
  "implementation": {
    "module": "mta_strategy_recommendation.src.budget_recommender",
    "function": "generate_budget_recommendation"
  },
  "capabilities": {
    "requires_attribution_evidence": true,
    "requires_candidate_pool": true,
    "requires_fit": false,
    "supports_persistence": false,
    "deterministic": true,
    "objective": "balanced",
    "constraint_types": ["total_budget", "min_budget", "max_budget"]
  },
  "input_contract": {
    "schema_version": "4.0",
    "required_inputs": [
      "strategy_request.json",
      "candidate_pool.json",
      "amc_mta_recommended_attribution.csv",
      "amc_touchpoint_entity_aggregate_sample.csv"
    ]
  }
}
```

### Field Reference

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `strategy_id` | `string` | Yes | Unique identifier; lowercase, underscore-separated |
| `strategy_version` | `string` | Yes | [Semantic version](https://semver.org) of this declaration file |
| `display_name` | `string` | Yes | Human-readable name for logs and reports |
| `description` | `string` | Yes | One-sentence summary of what the strategy does |
| `implementation.module` | `string` | Yes | Fully qualified Python module path |
| `implementation.function` | `string` | Yes | The callable within that module |
| `capabilities` | `object` | Yes | Must match the [`StrategyCapabilities` fields](./strategy-structure#capabilities-declaration) |
| `input_contract.schema_version` | `string` | Yes | Version of the input contract this strategy expects |
| `input_contract.required_inputs` | `array[string]` | Yes | File names the strategy requires; used for pre-flight validation |

## Strategy Registry <span class="status-label status-recommendation" aria-label="Recommendation"></span>

### Loading the Registry

```python
from modules.mta_strategy_evaluation.src.strategy_registry import (
    STRATEGY_REGISTRY,
    build_strategy,
    list_strategies,
)

# List all registered strategies with their capabilities
for entry in list_strategies():
    print(f"{entry.strategy_id} v{entry.strategy_version} "
          f"objective={entry.capabilities.objective} "
          f"deterministic={entry.capabilities.deterministic}")

# Instantiate one strategy
strategy = build_strategy("budget_seed_v4")
allocation = strategy.allocate(scope, evidence, constraints)
```

### Registry Behavior

| Rule | Behavior |
| --- | --- |
| Duplicate `strategy_id` | The last declaration loaded wins; a warning is emitted |
| Missing implementation | `build_strategy()` raises `ImportError` with the missing module path |
| Version mismatch | If the declaration version and the implementing class's `strategy_version` differ, a warning is emitted but instantiation proceeds |
| Unregistered `strategy_id` | `build_strategy()` raises `KeyError` with the available identifiers listed |
| Empty registry | `build_strategy()` and `list_strategies()` raise `RuntimeError` — an empty registry is a configuration error, not a valid state |

### Registry Directory

```
modules/mta_strategy_evaluation/
├── src/
│   ├── __init__.py
│   ├── strategy_interface.py     # Strategy, StrategyCapabilities, etc.
│   ├── strategy_registry.py      # STRATEGY_REGISTRY, build_strategy, list_strategies
│   ├── strategy_loader.py        # JSON declaration loading and validation
│   ├── strategy_validator.py     # Output contract validation (conservation, field checks)
│   └── strategy_evaluator.py     # Baseline comparison and ground-truth scoring
├── declarations/
│   ├── budget_seed_v4.json       # Current initializer
│   └── ...                       # Future strategies
├── tests/
│   ├── test_strategy_interface.py
│   ├── test_strategy_registry.py
│   ├── test_strategy_loader.py
│   └── test_strategy_evaluator.py
└── outputs/
    └── ...
```

This layout mirrors `modules/mta_standard/`: the framework owns loading, validation, and evaluation; concrete strategies live in their owning modules and are referenced by the declarations.

## Validation Pipeline <span class="status-label status-recommendation" aria-label="Recommendation"></span>

Before a strategy's output is accepted, the loader runs a three-stage validation pipeline:

| Stage | Check | Failure behavior |
| --- | --- | --- |
| 1. Declaration validation | JSON schema, required fields, `strategy_id` format, capabilities types | `ValueError` with the specific field and reason |
| 2. Input validation | Evidence lineage (Secure Hash Algorithm 256-bit (SHA-256) hashes match), scope consistency, required files present | `HierarchyValidationError` — same exception class used by the [current initializer](/en/strategy_recommendation/module-overview#1-verify-evidence-lineage-before-calculation) |
| 3. Output validation | Conservation contract, field completeness, forbidden fields absent | `StrategyOutputError` before any file is written |

Stage 1 runs at registry load time. Stages 2 and 3 run when `allocate()` is called with the validated evidence wrapper.

### Output Validation in Detail

`strategy_validator.py` enforces the [conservation contract](./strategy-structure#conservation-contract) and additionally checks:

| Check | Rule | Tolerance |
| --- | --- | --- |
| Non-negativity | Every budget and share is finite and `>= 0` | Exact |
| Uniqueness | One `ad_group_slot_id` per Campaign, no duplicate slots | Exact |
| Slot completeness | Slot count matches `recommended_ad_group_count` | Exact |
| Campaign completeness | Every Campaign in scope has an allocation record | Exact |
| Forbidden fields | No candidate IDs, Targeting, Audiences, or activation actions in output | Exact |
| Execution status validity | Status is one of the three defined values | Exact |

## Integration with Existing Pipeline <span class="status-label status-recommendation" aria-label="Recommendation"></span>

The strategy loader does not replace the existing `script/generate_initial_budget.py`. It wraps it:

```
Current:  script/generate_initial_budget.py → modules/mta_strategy_recommendation/
Future:   script/evaluate_strategies.py      → modules/mta_strategy_evaluation/
               ↓
          build_strategy("budget_seed_v4")    → wraps generate_budget_recommendation()
          build_strategy("future_optimizer")  → new implementation
               ↓
          strategy_evaluator.compare()        → scores all registered strategies
```

The current initializer remains untouched. Its entry in the declarations directory points to the existing function. New strategies add their own declaration files and implementations without changing the framework.

## Determinism and Reproducibility <span class="status-label status-recommendation" aria-label="Recommendation"></span>

A strategy that declares `deterministic: true` must produce byte-identical output for the same inputs. The evaluation framework tests this property directly:

```python
def test_strategy_is_deterministic(strategy_id: str) -> None:
    strategy = build_strategy(strategy_id)
    first = strategy.allocate(scope, evidence, constraints)
    second = strategy.allocate(scope, evidence, constraints)
    assert first == second, (
        f"{strategy_id} declares deterministic: true "
        f"but produced different outputs for identical inputs"
    )
```

This is the same assertion pattern used by the [attribution evaluation layer](/en/attribution/model-testing#layer-3--ground-truth-evaluation).

## References

- [Recommended strategy structure](./strategy-structure.md)
- [Strategy evaluation framework](./index.md)
- [Module and script data flow](/en/reference/data-flow)
- [Standardized MTA interface](/en/attribution/standardized-interface/)
