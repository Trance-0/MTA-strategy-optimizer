---
title: Registered Analysis Datasets
compact: "Immutable native-report validation, templates, generator registration, datasetId resource projection, private digest checks and observed-only research capabilities; owns dataset services, transport and repository."
source_files: backend/services/datasets.py, backend/api/datasets.py, backend/repository/datasets.py
---

# Registered Analysis Datasets

An analysis dataset preserves one account's observed inputs independently from
temporary generator tasks and the configured legacy database. It is immutable;
changing inputs creates a new identifier. The browser explicitly selects one
dataset and the service never changes a global source configuration to serve it.

## Public input contract

The Application Programming Interface (API) accepts a JavaScript Object Notation
(JSON) object with `name`, nonempty `performance` rows, optional `paths` rows and
optional `research` object. File import uses the same role names as multipart
fields; performance and paths may be JSON arrays or Comma-Separated Values
(CSV). Research is JSON. A single JSON envelope is accepted by both preview and
publication. No storage paths or arbitrary field mappings are accepted.

#### Performance

Reuse the native simulator report fields defined by `MTA_SIM_ADS_FIELDS` in
`modules/mta_standard/src/dataloader.py`, in order: `reportDate`, `marketplace`,
`accountId`, `adProduct`, `adType`, `creativeType`, `inventoryType`, `placement`,
`normalizedTouchpoint`, `currencyCode`, `impressions`, `clicks`, `cost`,
`purchases`, `sales`, `unitsSold`. Interaction follows the fifth touchpoint
segment; billing is not supplied by this report and remains unavailable in
observation projections. Model input adaptation continues through the existing
attribution command's billing boundary, rather than adding a new public field.
Templates return this exact ordered field list and valid example rows.
Required scope, key and numeric fields must be present. Optional descriptive
fields may be blank when the canonical report permits them. Counts are finite
nonnegative integers; cost and sales are finite nonnegative numbers. Zero is
an observation, an empty required numeric value is invalid. `unitsSold` retains
the canonical optional diagnostic semantics: its column is present but its
value may be null. Native keys have five segments; generated historical keys
are adapted through the supplied simulator configuration before validation.

#### Paths

Reuse `MTA_SIM_PATH_REPORT_FIELDS`: `report_start_date`, `report_end_date`,
`marketplace`, `advertiser_id`, `path`, `users`, `converted_users`,
`purchase_count`, `revenue`. Validate ordered calendar dates and a nonempty
sequence of supported touchpoint keys. Converted users cannot exceed users.
Counts and revenue follow the performance numeric rules. Preserve daily path
windows for display; aggregate to the existing single-scope report only when
preparing attribution inputs. `prepare_single_scope_path_report` supplies the
model's inclusive scope from the performance dates, as in the generator adapter;
source path windows remain unchanged and may extend beyond those dates.

#### Research

Use the existing `simulation_research.json` contract and research adapter.
Referenced campaigns, products, ad groups and reporting scopes must agree.
Reject cross-account, marketplace and currency references and nonfinite
numeric values. Preserve experiment metadata and observation availability.
Do not expose optimal-allocation truth through ordinary resources or feed it
into response fitting. Missing research yields empty research observations,
never the committed simulator or database sidecar.
Malformed research collection members and nested entity objects are validation
failures with bounded issues, never uncaught parser errors or published datasets.
Budget observation identity is campaign, budget level and the complete reporting
scope: advertiser, marketplace, currency, campaign group, start date and end date.
Reject repeated identities even when their measured values differ. Delivery and
outcome identities additionally include the observed touchpoint; outcomes also
include product. Check each ordinary and evaluation collection separately.
History joins budgets to ordinary outcomes using that same complete window and
scope identity, so different end dates never merge. Touchpoint/product outcomes
may aggregate within one budget identity without multiplying the budget row.

#### Scope and validation failures

All inputs describe one account, marketplace and currency. Dates use
`YYYY-MM-DD`; malformed dates, missing keys, duplicate observation keys,
inconsistent references and mixed scope produce bounded row/field issues.
Suggest splitting a mixed dataset. A rejected import publishes nothing.
Dataset date bounds span all submitted observation windows. Sparse performance
days do not discard valid later path or research observations; the stage's
stricter continuous-grid and common-window checks determine model eligibility.
The existing transport limit is 26 MiB; oversized bodies retain a 413 response.
Validation preview returns at most 20 rows per role, counts and capabilities.

## Persistence and capabilities

Storage is `PIPELINE_OUTPUT_DIR/workbench/datasets/ds_<32hex>/`.
Publish validated inputs and `manifest.json` by an atomic directory rename.
The manifest has `id`, `name`, `source`, `createdAt`, `digest`, `scope`,
`counts`, `capabilities`. The digest is a content fingerprint; timestamps are
coordinated universal time strings. Scope contains `advertiserId`, `marketplace`,
`currency`, `start`, `end`. No absolute server paths appear in public metadata.
List newest first with identifier as a stable tie-breaker. `source` is
`generated`, `file`, or `api`. `isSynthetic` is true for generated simulation or
declared synthetic research lineage; false means no synthetic declaration was
supplied, not independently verified real-world origin. Private input reads
recompute the content digest and reject changed files rather than serving them.

Each capability is `{available, reason}`. Performance supports observation
charts. Attribution requires matching paths plus the existing attribution
command's spend, billing, date-grid and scope validation after native adaptation.
Failed alignment makes that capability unavailable with its reason, while
valid observations remain readable. Campaign history requires genuine
research observations. Optimization availability follows existing response-model
eligibility, not just the presence of research: the canonical episode bridge,
response dataset and fitter must yield usable models for every observed Campaign.
Capability keys are `performance`, `attribution`, `history`, `optimization`,
and `evaluation`. Evaluation also needs a completed
same-dataset optimization run, checked at admission. Unsupported operations name
the missing evidence. Candidate pools and business margins are never invented.

## Routes

#### List, detail and templates

`GET /api/datasets` returns `{datasets: [...]}` plus runtime availability.
`GET /api/datasets/<id>` returns one descriptor. Identifiers must exactly match
the issued pattern; unknown identifiers return 404. `GET /api/datasets/templates`
returns the canonical fields and valid minimal examples for download.
The response maps `performance` and `paths` to `{fields, rows}`, and describes
the optional research format separately.

#### Validate and register

`POST /api/datasets/validate` accepts either transport and returns preview
without writing. `POST /api/datasets` validates again, publishes and returns
the descriptor with 201. Errors use `{error,message,issues?}` with 400 for
content, 413 for size and 503 for unavailable storage. File roles are allowlisted.
Generator completion registers its daily performance, daily paths and available
research before temporary retention eviction. It exposes `datasetId`, or a
bounded `registrationError` while keeping the completed preview downloadable.

#### Selected resources

`GET /api/dashboard/resources/<resource>?datasetId=<id>` dispatches to the
registered repository before checking legacy database health. It returns the
existing snapshot keys and `dataset` descriptor. Shell scope comes from the
manifest. Performance, paths and research come only from that directory.
Requested inclusive `start` and `end` bounds filter observation dates, with
full-dataset bounds preserved in context. Missing model results are empty;
completed results must match both dataset identity and fingerprint. Invalid
identifiers and unavailable files are errors, never fallback triggers.

Without `datasetId`, the existing explicit legacy source remains compatible.
Static builds show the labeled sample source and reject backend operations
locally. Existing database data is never overwritten by an ordinary registration.

## Source Files

### datasets.py service

Source: `backend/services/datasets.py`

Responsibility: validate, register, list and read immutable datasets. Inputs are
the canonical envelope or generator file content. Outputs are bounded previews,
descriptors and private validated model inputs. Dependencies are existing report
and research contracts, filesystem and backend runtime configuration. All IDs
are validated before path resolution; writes publish atomically. Verification:
`uv run --extra backend python -m unittest backend.tests.test_datasets`.

Public Python entry points are `validate_dataset(payload) -> dict`,
`register_dataset(payload, *, source="api") -> dict`, `get_dataset(id) -> dict`,
`list_datasets() -> list[dict]` and `register_generated_dataset(generated, name)`.
Server-only `dataset_inputs(id) -> dict` reads native `performance`, `paths`
and optional `research`; `dataset_directory(id) -> Path` resolves the validated
identifier. Neither server-only return value is serialized as public metadata.
Validation creates no registered data; the path-only canonical research adapter
may use a temporary file that is removed when validation finishes.
`research_observation_key(row)` returns the campaign, numeric budget level and
complete reporting-scope tuple defined above; validation and history projection
share it to prevent duplicate counting and joins across different date windows.

### datasets.py transport

Source: `backend/api/datasets.py`

Responsibility: parse the declared JSON/multipart roles, apply common validation
and HTTP errors, and return no private paths. Inputs/outputs are the routes above.
Depends on Flask and the dataset service; verification is backend route tests.

### datasets.py repository

Source: `backend/repository/datasets.py`

Responsibility: project one registered dataset into existing resource shapes,
using pure explicit-input adapters. Normalize performance fields for display and
derive catalogues only from present observations. It must not consult legacy
loaders or environment-mutating adapters. Inputs are dataset ID, resource and
optional bounds; output is the resource payload with provenance. Tests cover
two distinct datasets, missing optional inputs and an unavailable legacy database.
The entry point is `load_dataset_resource(id, resource, start=None, end=None)`.
Research display joins ordinary `outcome_observations` to budget observations;
evaluation-only outcomes and latent touchpoints are excluded. Reported billing
remains null when no observation supplies it. Reusable projections never import
the legacy repository's fallback-producing entry points.
