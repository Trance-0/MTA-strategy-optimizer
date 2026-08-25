---
title: Run and Navigate the Initializer
compact: "Commands for generating and checking the initial budget recommendation, plus links to the model plan, detailed calculation, data flow, input schemas, and validation contract that explain each layer."
lang: en-US
---

# Run and Navigate the Initializer

## Run

```bash
uv run python -X utf8 -B script/generate_initial_budget.py --check-output
uv run python -X utf8 -B script/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommendation/tests -p 'test_*.py'
```

Without `--check-output`, the generator writes its result to standard output so downstream consumers can save it separately. The old `--check-fixture` option remains as a compatibility alias; current documentation and new calls consistently use `--check-output`.

## Documentation

- [Overall model plan](../model-plan.md)
- [Detailed current Ad Group initial-budget calculation](../current-budget-calculation/)
- [Campaign budget response model and optimizer](../campaign-budget-optimizer.md)
- [Problem definition and research plan from MTA to Ad Group budget](../optimization-plan.md)
- [Output data contract](../output-data-contract.md)
- [Budget strategy output contract](../strategy-output-contract.md)
- [Simulated input description](../../market-simulation/strategy-simulated-data.md)
- Canonical initial-budget result: `modules/mta_strategy_recommendation/outputs/initial_budget_recommendation.json`
