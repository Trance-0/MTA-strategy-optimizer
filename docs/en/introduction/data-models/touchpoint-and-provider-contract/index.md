---
title: Touchpoint and Provider Contract
description: Provider capabilities, typed touchpoints, field availability, and reporting scope
compact: "Routes to ProviderCapabilities, Touchpoint, TouchpointFieldAvailability, and ReportingScope: the provider-independent observation key, provider capability ceiling, per-record field availability, and shared account/market/currency/date scope."
order: 20
lang: en-US
---

# Touchpoint and Provider Contract

These classes turn a provider-specific advertising key into a typed `Touchpoint`, state what the provider can supply, record what one touchpoint actually supplies, and define the reporting window shared by observations. See the [Canonical Data Model](../index.md) for the complete relationship diagram and source-file contracts.

## Class Index

- [Provider Capabilities](./provider-capabilities.md): the static field and ad-product ceiling for one provider.
- [Touchpoint](./touchpoint.md): the typed replacement for the five-segment legacy key.
- [Touchpoint Field Availability](./touchpoint-field-availability.md): availability states for one touchpoint's optional fields.
- [Reporting Scope](./reporting-scope.md): the account, market, currency, and date window shared by observations.
