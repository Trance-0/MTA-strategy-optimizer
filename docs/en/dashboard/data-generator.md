---
title: Data Generator
description: Dashboard workflow for configured MTA-SIM generation, preview, CSV download, and backend-only PostgreSQL export
compact: "Data Generator contract for `DataGenerator.vue`, `GeneratorConfigEditor.vue`, `configuration.js`, `lifecycle.js`, and `/api/data-generator`: lossless guided/JSON editing, authoritative preflight and stale-response guards, pinned MTA-SIM execution, bounded outputs, static capability handling, and write-only PostgreSQL export."
lang: en-US
source_files: dashboard/src/views/DataGenerator.vue, dashboard/src/components/GeneratorConfigEditor.vue, dashboard/src/generator/configuration.js, dashboard/src/generator/lifecycle.js, backend/api/data_generator.py, backend/services/data_generator.py
test_files: dashboard/tests/data-generator.test.js, backend/tests/test_data_generator.py
---

# Data Generator

The Data Generator is the second navigation destination, immediately after
Command Center. It is a controlled interface to the pinned
[MTA-SIM (Multi-Touch Attribution Simulator)](/en/reference/definitions#mta-sim-multi-touch-attribution-simulator)
package under `external/mta_sim_dataset`; it is not a second simulation
implementation in Vue or Flask.

The backend calls the reviewed generator function. The browser selects or
edits configuration, starts work, reads bounded status and previews, and asks
the backend to export a completed run. The browser never imports a database
driver, opens a database socket, builds Structured Query Language (SQL), or
receives a stored credential.

## Availability and ownership

The feature is available when a Flask backend is present, pipeline runs are
enabled, and the pinned simulator submodule has been initialized. Local-file
data mode does not disable generation when that backend capability is enabled.
The Data Generator therefore does not inherit the dashboard's general
read-only data-operation warning.

The static documentation deployment replaces the executable form with a
feature-specific explanation that generation, downloads, and PostgreSQL export
require a local or container full-stack deployment. It does not load presets,
show controls that cannot run, or simulate a successful request.

An ordinary backend test or image-publishing checkout may intentionally omit
Git submodules because external source does not enter those images. In that
environment, the overview remains a successful capability response with
`available: false`, an empty initial configuration, and a bounded reason. A
request for an allow-listed preset returns `503 generator_unavailable`; it must
not become an unhandled server error or reveal an absolute checkout path. The
one integration test that executes a real toy simulation skips when the pinned
checkout is absent. Request validation, route behavior, and credential tests
remain active and must not depend on that checkout.

One backend process owns at most one active generation or export operation.
A second start request receives a conflict response naming the active run.
Completed runs remain available until process restart through an opaque run
identifier. Generated files live only under the ignored
`generated/dashboard-generator/` runtime directory and must never be added to
Git automatically.

## Configuration editors

The page offers two editor modes over one configuration value. Changing modes
does not discard a valid edit.

### Guided editor

The guided editor is an accordion whose headers show complete, incomplete, or
error state. It exposes the complete configuration contract used by the
reviewed baseline and regional toy presets. Keyboard users can expand every
section and operate every list command without dragging.

Every field-level issue displays its JSON Pointer. Activating an issue opens
the owning accordion and focuses the exact input or ordered reference when that
control exists; the control also exposes `aria-invalid` and its error
description. Parseable objects with malformed arrays remain safe in Guided
mode: known array paths are rebuilt as arrays, and missing marketplace,
touchpoint, or path lists expose their normal creation controls.

#### Run basics

The section edits the integer `seed`, non-empty `advertiser_id`, inclusive
`report_start_date` and `report_end_date`, positive `base_product_price`, finite
`baseline_conversion_log_odds`, and integer `campaign_replications` from 1
through 50.

#### Global behavior

The section edits seven ordered `weekly_traffic_multipliers`, beginning with
Monday, plus `daily_traffic_trend`, five non-negative noise standard deviations,
`additional_unit_probability`, and `repeat_purchase_probability`. Traffic
multipliers are positive; probabilities are from zero through one.

#### Marketplace

The page supports exactly one marketplace. It edits a non-empty `code`, an
International Organization for Standardization (ISO) currency code, and
positive `traffic_multiplier` and `price_multiplier` values.

#### Touchpoints

Each card edits `identifier`, `ad_product`, `ad_type`, `creative_type`,
`inventory_type`, `placement`, non-negative `base_impressions`, Click-Through
Rate (CTR), platform conversion rate, either [CPC (Cost Per Click)](/en/reference/definitions#cpc-cost-per-click)
or [CPM (Cost Per Mille / Cost Per Thousand Impressions)](/en/reference/definitions#cpm-cost-per-mille--cost-per-thousand-impressions),
and non-negative conversion log-odds effect. Rates are from zero through one;
exactly one cost field is a non-negative number and the other is `null`.

The card list offers add, duplicate, delete, move up, and move down commands.
Duplication creates independent nested data and a unique identifier. Deleting a
touchpoint referenced by a path scenario is refused, the referencing path is
identified, and focus moves to that path. Reordering changes display and
configuration order only; it does not rewrite identifier references.

#### Path scenarios

Each card edits a unique `identifier`, a non-empty ordered list of
`touchpoint_identifiers`, positive `base_users`, and non-negative
`adjacent_synergy_log_odds`. A reference is chosen from existing touchpoints.
References can be added, removed, and moved with explicit buttons, and duplicate
or unknown references are invalid.

#### Regional behavior

This section is present only for the `regional` variant. It edits
`reference_internet_reach_rate`, `reference_target_audience_density`,
`reference_income_inequality_gini`,
`economic_willingness_log_odds_weight`, and
`income_inequality_noise_weight`. It also adds `internet_reach_rate`,
`target_audience_density`, `economic_willingness_multiplier`, and
`income_inequality_gini` to the marketplace card. Reach and density are greater
than zero and at most one, Gini values are from zero through one, the
willingness multiplier is positive, and both weights are non-negative.

The remaining configuration object is never reconstructed from only the visible
fields. Unknown fields and `provenance` survive guided edits, mode changes,
validation, and generation unchanged.

### Configuration-file editor

The advanced editor is a monospaced JavaScript Object Notation (JSON) text
editor with validation feedback, line-preserving input, and a **Format JSON**
action. It is intentionally a native text editor rather than an embedded
Integrated Development Environment (IDE): generation needs JSON validation,
not another runtime dependency and multi-megabyte editor bundle.

Moving from Guided to JSON serializes the complete current object. Moving from
JSON to Guided first parses the text and keeps every property. Invalid JSON
stays in the editor, shows a parse error, and prevents the mode change. Selecting
another preset or variant after any configuration edit requires confirmation;
cancelling retains the current variant, preset, configuration, and editor mode.
A failed or superseded preset request also retains that selection and edit.
Preset responses are sequence-bound, so an older response cannot overwrite a
newer choice.

The server accepts an object, never a client filesystem path. Configuration
inheritance through `extends` is refused because a browser-supplied path could
otherwise make the server read an unrelated local file. The request is also
bounded by the application body limit and by generator-specific limits on the
reporting window, touchpoints, references per path, path scenarios, Campaign
replication, configuration depth, and returned issue count. JSON parsing rejects
non-finite numbers before they can be normalized into `null`.

The browser performs immediate checks only for visible required values, numeric
ranges, duplicate identifiers, billing exclusivity, and touchpoint references.
The backend preflight remains authoritative and maps its issues back to the
owning accordion section and field. Generation is disabled while local parse or
field errors exist or while the latest configuration has not passed preflight.
The browser binds a successful preflight to the exact variant and complete
configuration revision that requested it. A late success or failure for an
older revision cannot enable generation or replace current validation feedback.
The editor, preset selector, and variant selector remain disabled while
generation or export is active, so results stay visibly bound to the
configuration that produced them. Browser preflight has a bounded timeout and
restores the controls if the service never answers.

The server writes an accepted run configuration to the run's ignored directory
and gives that path to the pinned generator. Configuration meaning and final
validation remain owned by MTA-SIM.

## Preflight validation

`POST /api/data-generator/validate` accepts:

```json
{
  "variant": "baseline",
  "configuration": {}
}
```

`variant` is `baseline` or `regional`; `configuration` is a self-contained
object. A valid configuration returns `200` with `valid: true` and an empty
`issues` array. An invalid configuration returns `400` with
`error: "invalid_configuration"`, `valid: false`, and one or more issues. Each
issue contains a JSON Pointer `path`, a `section`, and a user-readable
`message`. Sections are `basics`, `global_behavior`, `marketplace`,
`touchpoints`, `path_scenarios`, `regional_behavior`, or `configuration`.

Known field, range, uniqueness, billing, and reference failures point to the
specific property or array element. An upstream MTA-SIM failure that cannot be
safely classified uses `/` and section `configuration`. Messages are bounded
and remove server paths and other internal details. At most 128 issues are
returned, including a final deterministic truncation issue when further errors
exist. A path can contain at most 64 touchpoint references, and configuration
nesting cannot exceed 64 container levels.

Preflight applies the dashboard boundary checks and then the same variant
loader used by generation. It may use a temporary private configuration file
that is removed before the response, but it does not allocate a run identifier,
create a run directory, retain configuration, start a thread, or execute the
simulation. Missing pinned source returns the existing bounded `503
generator_unavailable` response.

The request must carry `variant`; generation does not silently default an
omitted value. Preflight requires only the selected variant loader, while a
preset request additionally requires only its selected preset file. Missing
files for another variant do not disable an otherwise complete request. Loader
entry is serialized because its module-resolution boundary is process-global;
temporary-file creation or cleanup failure is bounded infrastructure
unavailability rather than a configuration error.

## Generation lifecycle

`GET /api/data-generator` returns availability, reviewed presets, the default
variant and preset, and the initial self-contained configuration object when
the pinned simulator is present. Its absence is represented by the capability
response described above.

`GET /api/data-generator/presets/<variant>/<preset>` returns one allow-listed,
resolved, self-contained configuration. An unknown pair returns `404
unknown_preset`; a known pair whose pinned source is unavailable returns the
bounded `503 generator_unavailable` response.

`POST /api/data-generator/runs` accepts `variant` and `configuration`. Before it
allocates an opaque run identifier or starts a background operation, it reuses
the authoritative preflight service. Invalid input returns the same structured
`400 invalid_configuration` response. Existing successful response and run
status contracts remain compatible.

`GET /api/data-generator/runs/<run_id>` returns only bounded state:

- `queued`, `running`, `completed`, or `failed` generation status;
- a short phase and bounded error message;
- generator name and version, row counts, and selected reporting scope after
  completion;
- the two preview objects and their download names;
- `idle`, `running`, `completed`, or `failed` PostgreSQL export status.

The response never returns a server path, complete configuration, database
connection string, password, or simulation ground truth.

## Preview contract

A completed run exposes exactly two previews, each retaining the generator's
declared column order and at most the first 20 rows:

### Amazon Marketing Cloud path report

The preview comes from `amc_path_report.csv`. It preserves daily report
windows and the ordered five-segment paths emitted by MTA-SIM.

### Amazon Ads daily touchpoint performance

The preview comes from
`amazon_ads_daily_touchpoint_performance.csv`. It preserves the daily delivery,
cost, and reported-outcome fields emitted by MTA-SIM.

`simulation_ground_truth.csv` is evaluation-only. It is generated for the
model evaluation boundary but is neither previewed nor downloadable from this
workflow.

## Export stage

After generation completes, the page presents the next-stage choices.

### Comma-Separated Values downloads

`GET /api/data-generator/runs/<run_id>/files/<table>` accepts only the two
declared public table keys and sends the matching generated Comma-Separated
Values (CSV) file as an attachment. A path supplied by the browser is never
joined to the filesystem.

### PostgreSQL export

`POST /api/data-generator/runs/<run_id>/postgresql` accepts a host, port,
database, user, write-only password, Secure Sockets Layer (SSL) mode, existing
schema, and explicit replacement Boolean. The backend:

1. validates the port, SSL mode, and schema identifier;
2. opens a direct probe connection and confirms the schema exists and the role
   can use and create objects in it;
3. constructs the connection information with Psycopg rather than string
   interpolation;
4. reruns the same deterministic accepted configuration through MTA-SIM's
   explicit `PostgreSqlResearchWriter` adapter; and
5. clears the password and connection information from operation state as soon
   as the writer has been started.

Credentials exist only in the Transport Layer Security (TLS)-protected request
and the backend operation's local memory. They are not saved in `.env`, a run
directory, application logs, an Application Programming Interface (API)
response, or browser storage. A deployment served over plain Hypertext Transfer
Protocol (HTTP) must not offer PostgreSQL export to a remote browser; localhost
development is the only HTTP exception. A forwarded HTTPS protocol is honored
only when the backend deployment explicitly enables its one trusted reverse
proxy hop; an arbitrary caller-supplied forwarding header is ignored.

Replacement is false by default. When false, MTA-SIM refuses a target already
holding simulator runs. When true, the page displays a separate destructive
confirmation and the backend passes the explicit reset flag to the writer.

## Source Files

### `DataGenerator.vue` and `GeneratorConfigEditor.vue`

Source: `dashboard/src/views/DataGenerator.vue`,
`dashboard/src/components/GeneratorConfigEditor.vue`

- Responsibility: Render guided and JSON editors, generation state, two
  previews, CSV download controls, and the PostgreSQL export form.
- Inputs: Only the `/api/data-generator` contract through `src/api/client.js`.
- Outputs: Configuration and export requests; no direct filesystem or database
  operation.
- Behavior contract: The editor follows the section, mode synchronization,
  unknown-field preservation, reference protection, dirty confirmation,
  field-level preflight mapping, active-operation locking, preset sequencing,
  timeout, and static capability rules above. Preview tables declare
  their received columns and render at most 20 rows. The password field is never
  refilled, saved, or written to browser storage. A replacement export requires
  a separate confirmation naming the target schema.
- Dependencies: Vue 3 and the shared `DataTable.vue` component.
- Verification: `dashboard/tests/data-generator.test.js`,
  `dashboard/tests/dashboard.test.js`, and a browser exercise of both toy
  presets through preflight, preview, and CSV download.

### `configuration.js`

Source: `dashboard/src/generator/configuration.js`

- Responsibility: Provide lossless configuration cloning and synchronization,
  visible-field validation, section status, and card/list operations without a
  user-interface dependency.
- Inputs: Baseline or regional self-contained configuration objects and editor
  operations.
- Outputs: Detached configuration objects and structured local issues using the
  same paths and sections as the backend.
- Behavior contract: Unknown properties, explicit `null`, zero, and false values
  survive every operation. Duplicate cards share no nested object or array
  references. List operations preserve order and reject dangling references.
  Parse and fingerprint helpers reject non-finite or over-deep values without
  recursion failure, and malformed structural arrays never crash Guided mode.
- Dependencies: Standard JavaScript only.
- Verification: `dashboard/tests/data-generator.test.js`.

### `lifecycle.js`

Source: `dashboard/src/generator/lifecycle.js`

- Responsibility: Bind preflight acceptance to the exact current variant and
  complete configuration, and reject stale run-poll responses.
- Inputs: Variant/configuration snapshots, preflight request tokens, and opaque
  run identifiers.
- Outputs: Current-preflight and current-run decisions used by
  `DataGenerator.vue` before enabling generation or updating a run.
- Behavior contract: A configuration replacement clears accepted preflight.
  Only a response carrying the unchanged revision and stable full-object
  fingerprint may authorize generation. A poll response must carry the active
  run token and matching run identifier; cleared or replaced runs reject it.
- Public entry points: `createGeneratorLifecycle()` returns the configuration,
  preflight, and run-token guards. `replacePresetIfConfirmed({ dirty, confirm,
  loadPreset, variant, preset })` resolves to `false` without loading when a
  dirty replacement is declined; otherwise it loads that preset and resolves
  to the loader's Boolean success result.
- Dependencies: Standard JavaScript only.
- Verification: `dashboard/tests/data-generator.test.js`.

### `data-generator.test.js`

Tests: `dashboard/tests/data-generator.test.js`

- Responsibility: Pin lossless Guided/JSON round trips, conditional regional
  fields, card operations, reference protection, dirty preset confirmation,
  backend issue mapping, stale lifecycle responses, selector locking, and
  static unavailable rendering.
- Inputs: Toy configurations, unknown extension fields, and mocked generator
  capability and validation responses.
- Outputs: Frontend pass or fail.
- Dependencies: Node test runner and the dashboard source contract.
- Verification: `cd dashboard && npm test`.

### `backend/api/data_generator.py` and `backend/services/data_generator.py`

Source: `backend/api/data_generator.py`, `backend/services/data_generator.py`

- Responsibility: Own every generator route, run boundary, ignored artifact,
  preview, download resolution, and PostgreSQL connection.
- Inputs: A self-contained configuration object and, only for export, one
  write-only PostgreSQL credential form.
- Outputs: Bounded run state, two previews, two declared CSV attachments, and
  export status.
- Behavior contract: The service invokes the pinned MTA-SIM functions and does
  not reproduce simulation logic. Missing pinned source is capability state,
  not an unhandled exception; preset routes return a bounded 503 without an
  absolute path. Preflight produces structured issues without persistent state,
  caps issues and input depth, serializes loader entry, and run creation reuses
  it before allocating resources. One operation runs at a time. Variant is
  required, and capability checks cover only the requested loader and preset.
  Paths and external writers cannot come from the client. Ground truth
  remains absent from responses. Credentials are never retained in state or
  logs. PostgreSQL export targets only an existing validated schema and reset
  requires the explicit Boolean.
- Dependencies: Python standard library, Flask, Psycopg from the backend extra,
  and the pinned MTA-SIM submodule.
- Verification: `backend/tests/test_data_generator.py`.

## Verification

- **Scope:** The behavior and owned test files of Data Generator.
- **Cases:** Unavailable generator, bounded configuration, previews, downloads, export validation and credential redaction.
- **Command:** `uv run --extra backend python -X utf8 -B -m unittest backend.tests.test_data_generator`.
- **Limitations:** Runs against local fixtures or mocks, not a live production database. External generator execution requires the pinned checkout.

#### `backend/tests/test_data_generator.py`

Tests: `backend/tests/test_data_generator.py`

- Responsibility: Pin baseline and regional preflight, structured field and
  reference issues, request limits, no preflight side effects, asynchronous
  state, preview bounds, declared downloads, hidden ground truth,
  missing-submodule behavior, credential non-retention, and PostgreSQL export
  delegation.
- Inputs: Temporary directories, synthetic configurations, and patched writer
  boundaries; never a real database credential.
- Outputs: Backend pass or fail.
- Dependencies: Python `unittest` and the backend dependency extra. Only the
  real toy-run integration case depends on the initialized submodule and skips
  explicitly when it is absent; all boundary and route cases are hermetic.
- Verification: `uv run --extra backend python -X utf8 -m unittest
  backend.tests.test_data_generator -v`.
