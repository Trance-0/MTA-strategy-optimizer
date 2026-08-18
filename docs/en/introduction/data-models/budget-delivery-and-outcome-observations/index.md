---
title: Budget, Delivery, and Outcome Observations
description: Budget constraints and observed campaign, delivery, and outcome values
compact: "Routes to BudgetConstraints, BudgetObservation, DeliveryObservation, and OutcomeObservation: forward-looking campaign bounds, observed budget/spend, touchpoint delivery, and total/organic/incremental outcomes."
order: 50
lang: en-US
---

# Budget, Delivery, and Outcome Observations

These classes keep forward-looking budget constraints separate from observed spend, and keep delivery metrics separate from total, organic, and incremental outcomes. See the [Canonical Data Model](../index.md) for the complete relationship diagram and source-file contracts.

## Class Index

- [Budget Constraints](./budget-constraints.md): campaign budget bounds and usage policy known before treatment.
- [Budget Observation](./budget-observation.md): configured budget, actual spend, and optional intervention metadata.
- [Delivery Observation](./delivery-observation.md): impressions, clicks, and cost for one Touchpoint and ReportingScope.
- [Outcome Observation](./outcome-observation.md): total, organic, and incremental outcomes kept as distinct claims.
