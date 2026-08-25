---
title: Attribution Endpoint Configuration
description: Registered model attribution and comparison request contracts
compact: "Configures `POST /api/models/<model_id>/attribute` and `/api/models/compare`: registered identifiers, optional `pathReport` and `adsReport`, standard output rows, conservation validation, deterministic comparison, and Multi-Touch Attribution Simulator legacy-key requirements."
lang: en-US
---

# Attribution Endpoint Configuration

## Discover Models

Call `GET /api/models` and read `attribution.models`. Each entry states the
model identifier, version, determinism, persistence support, fitting
requirement, supported Outcomes, and output grain. Identifiers are read from
`MODEL_REGISTRY`; the endpoint does not maintain a second model list.

## Attribute One Model

Call `POST /api/models/<model_id>/attribute` with a JavaScript Object Notation
(JSON) object. Supported
fields are `pathReport`, an optional filesystem path to the aggregated path
Comma-Separated Values (CSV) file, and `adsReport`, an optional
[MTA-SIM](/en/reference/definitions#mta-sim-multi-touch-attribution-simulator) daily
performance CSV. Omitting `pathReport` selects
`MTA_SIM_DATA_DIR/amc_path_report.csv` when it exists, then falls back to the
committed five-segment sample. Omitting `adsReport` supplies no performance
table unless a configured MTA-SIM directory carries the exact strict table.

The response names model and version, reporting scope, runtime, touchpoint and
row counts, and standard rows. Rows are validated for schema, finite values,
supported Outcomes, unique keys, and Outcome-total conservation before they
leave the service.

## Compare Models

Call `POST /api/models/compare` with `modelIds`, a non-empty list of distinct
registered identifiers, plus the same optional paths. The dataset is loaded
once and every requested model runs against that one immutable instance.

## Legacy Multi-Touch Attribution Simulator Keys

Historical MTA-SIM files use four touchpoint segments and need an explicit
cost-type mapping to recover `IMPRESSION` versus `CLICK`. A raw legacy folder
without that adapter is rejected; the service never guesses the fifth segment
from delivery metrics. Use a generator output prepared through the standard
adapter, or submit native five-segment reports.
