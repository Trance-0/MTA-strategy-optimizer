---
title: Vocabularies
description: Controlled vocabularies used by the canonical data model
compact: "Routes to the seven `StrEnum` vocabularies in `modules/mta_common/src/enums.py`: Provider, FieldAvailability, StrategyObjective, BudgetUsagePolicy, AssignmentType, RecordClassification, and MarginSource."
order: 10
lang: en-US
---

# Vocabularies

These seven controlled vocabularies constrain values shared by the canonical data classes. They are defined together in `modules/mta_common/src/enums.py`; the [Canonical Data Model](../index.md) owns that source file's implementation contract.

## Class Index

- [Provider](./provider.md): the advertising platform from which a record came.
- [Field Availability](./field-availability.md): why an optional provider field does or does not carry a value.
- [Strategy Objective](./strategy-objective.md): what a future optimizer would maximize; no current class stores it.
- [Budget Usage Policy](./budget-usage-policy.md): whether a future optimizer may leave authorized budget unused.
- [Assignment Type](./assignment-type.md): how a budget intervention was assigned.
- [Record Classification](./record-classification.md): when a record became available in the decision cycle.
- [Margin Source](./margin-source.md): whether contribution margin was supplied or derived.
