---
title: Populating PostgreSQL
compact: "PostgreSQL schema initialization and simulator parsing through `import_to_database.py`, `derive_scenario_schemas.py`, `PG_SCHEMA`, and current-interpreter schema setup, plus optional `ModelArtifact` storage created only by explicit validated artifact import."
lang: en-US
source_files: dashboard/config.py, dashboard/models.py, script/import_to_database.py, script/derive_scenario_schemas.py
---

# Populating PostgreSQL

## Direct MTA-SIM Scale Insertion

The simulator's optional PostgreSQL writer accepts
`research-100k-postgresql.json`, inserts the stable three tables and canonical
research records in configurable batches, and requires the explicit
`--reset-database` flag before replacing populated simulator tables. A normal
dashboard start, connection test, or generation command never destroys data.
The database Uniform Resource Locator (URL) is supplied through
`MTA_SIM_DATABASE_URL` or the command line and is never committed.

The direct schema consists of `mta_simulation_run`, `mta_sim_provider`,
`mta_sim_product`, `mta_sim_product_economics`, `mta_sim_campaign`,
`mta_sim_ad_group`, `mta_sim_campaign_product_link`, `mta_sim_touchpoint`,
`mta_sim_delivery_observation`, `mta_sim_budget_observation`, and
`mta_sim_outcome_observation`, plus the unchanged three logical tables. The
100,000-row primary grain is Campaign × marketplace × day × budget level.
Indexes cover run, Campaign/date, Provider/date, Product/date, and the stable
report dates used by dashboard filters. `effective_configuration` is retained
per run so editing a future configuration does not change historical meaning.

The dashboard creates `dashboard_master_object` lazily for future Provider,
Product, Campaign, Ad Group, Touchpoint, Product Economics, and generation
configuration drafts. Its JSON payloads are separate from simulator-owned
history. Archiving a draft never deletes or updates a generated run.

Setting `DATABASE=true` and the `PG_*` values in `.env` is not enough on its own — see [Two Data Sources, One Contract](./index.md#two-data-sources-one-contract) — the PostgreSQL tables have to be populated first. This page specifies the two files that define that schema and the one script that writes to it.

## Choosing the Target Schema

One instance can hold several scenarios side by side, one schema each. `--schema` names which receives the tables:

```powershell
uv run --extra dashboard python script/import_to_database.py --schema demo --replace
```

The target must be a schema this command owns. The importer carries its own
advertiser, Campaign Group, and Campaigns with it, so pointing it at a schema
already holding another account's history staples the sample's entities onto
that account's observations. For a schema populated by the external simulator,
see [Deriving a Schema per Scenario](#deriving-a-schema-per-scenario) below.

The flag defaults to `PG_SCHEMA` in `.env`, and to `public` when that is unset,
so the reader and the writer resolve their target from the same variable and an
import cannot land somewhere the dashboard is not looking. Passing `--schema`
overrides the variable for that one run without editing `.env`.

A named schema is created when it does not exist. This ordering matters: a
`search_path` pointing at a missing schema reports every table as absent rather
than saying the schema is not there, so `ensure_schema()` runs before any table
is created. The name is quoted as an identifier rather than bound as a
parameter, because it names an object; `config.valid_schema_name()` has already
refused anything that is not a plain PostgreSQL identifier.

`--replace` drops and rebuilds the tables **within the selected schema only**
and never touches another. The `Target:` line printed before any write names the
user, host, database, and — when it is not `public` — the schema, so a
destructive run states where it is about to act. The same selection governs
reads: `PG_SCHEMA` is described in
[Backend Setup and Deployment](../introduction/backend/setups.md#schema-selection),
and the settings dialog lists the schemas the connected server offers,
disabling the ones that cannot serve the dashboard.

## Deriving a Schema per Scenario

A schema written by the external simulator holds that pipeline's own tables —
its own advertisers, its own marketplaces, a full year of daily observations —
and none of the tables in `dashboard/models.py`. The importer above cannot
populate it, because it would write the committed sample's account over one
that already exists. `derive_scenario_schemas.py` computes the dashboard model
from the scenario's own rows instead:

```powershell
uv run --extra dashboard python script/derive_scenario_schemas.py --source mta --list
uv run --extra dashboard python script/derive_scenario_schemas.py --source mta --all --replace
```

`--list` reports the scenarios the source holds without writing anything.
`--all` derives each into its own schema, named `<source>_<marketplace>`, and
`--marketplace` with `--schema` derives one into a chosen name. The source
schema is only ever read; a target equal to it is refused.

One scenario becomes one schema rather than one filtered view of a shared one.
The dashboard model holds one advertiser, one marketplace, and one report
window, and reads `attribution_run` as a single row, so splitting on the way
out keeps that contract intact and makes the schema dropdown the scenario
picker.

The derivation runs the same attribution and comparison code the file pipeline
runs, imported from the modules that own it, so a derived schema and a
published artifact cannot drift into disagreeing. Where the source states a
quantity, it is read; where it does not, the field is left absent rather than
filled with a plausible number. A scenario whose Campaign shape or targeting
inventory cannot satisfy the strategy module's contract is derived without a
budget recommendation, and the command prints why rather than fabricating the
counts that would produce one.

## Initializing and Parsing from the Dashboard

Everything above this line is the command-line route, and it remains the route
for an operator at a terminal. This section is the same two operations for a
reader who has only a browser — the deployed case, where the commands above are
not available at all. Both use the same root scripts and are governed by the
same census. The server prefixes the script arguments with its current Python
interpreter rather than looking up `uv`; its deployed environment already
contains the required dependencies.

The dashboard settings separate the active **Dashboard schema** from the
**Schema setup** target. The active selector contains only schemas that already
hold the complete dashboard model. The setup menu contains every readable,
plain-identifier schema returned by PostgreSQL, including empty schemas,
simulator source schemas, complete dashboard schemas, and schemas owned by
other applications. Newly introduced readable schemas therefore appear
without a frontend code change.

An empty existing schema, or a valid new schema name entered by the operator,
can start the committed-sample initializer. This invokes
`script/import_to_database.py --schema <target>` as a fixed subprocess argument
vector. A non-empty schema is never treated as empty. Replacing a complete
dashboard schema requires an explicit replacement choice and browser
confirmation; a simulator or unrelated populated schema is never offered the
fixture initializer because that would mix accounts.

A schema is offered the parse action only when it holds every table in
`SOURCE_TABLES` from `derive_scenario_schemas.py`. Parsing invokes
`script/derive_scenario_schemas.py --source <source> --all`, discovers the
source's marketplaces at run time, and writes one target schema per scenario.
The source remains read-only. Replacement of already-derived target schemas is
off by default and requires an explicit choice and browser confirmation.

Initialization and parsing return immediately after starting and continue as
server-side operations in the unified first-in/first-out operator queue. The
Data source doctor moves from Connect, through Inspect and Import, to Verify;
starting the operation opens Settings Tasks on the new task. That tab renders
the exact reproducible command, safe source or target summary, queue position,
start and finish times, exit status, and each timestamped output line, with a
copy action for the complete detail. The log retains at most 600 lines and
reports how many earlier lines were dropped. A successful operation clears database read
caches and refreshes the schema census, so newly initialized or derived
schemas become available in the active selector without restarting the
dashboard. Closing the dialog does not stop an operation; the operator may
request termination explicitly, including while it is still queued.

Setup is available on a protected server. `DASHBOARD_CONFIG_READ_ONLY` keeps
the browser from rewriting credentials; it does not decide whether the database
those credentials already name may be populated. `SCHEMA_SETUP_ENABLED=false`
is how an operator withholds these two operations, and the dialog then says so
rather than offering a button the route would refuse.

### Recovering from a schema that cannot be read

Selecting a schema that lacks the dashboard tables makes every view fail with
one page-level error. Under that error the dashboard lists the schemas
something can be done with, from `GET /api/schema-recovery`, and each entry is
the same select, parse, or initialize action described above. The list omits the
schema that just failed and omits any schema with no available action, since it
exists only to be acted on.

Nothing offered there replaces anything. Replacement stays in the settings
dialog behind the explicit checkbox and its confirmation, because a reader
recovering from an error is the reader least placed to judge what is about to
be overwritten.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `config.py` and `models.py`

Source: `dashboard/config.py`, `dashboard/models.py`

- Responsibility: Define the PostgreSQL schema the dashboard reads and the `.env` contract the importer resolves against. The dashboard itself holds no Python; these two exist for `script/import_to_database.py`.
- Inputs: `.env` at the repository root, for `config.py`. Nothing at runtime for `models.py`.
- Outputs: `use_database()`, database settings and path constants; `Base` plus
  eighteen required mapped classes; and the separate `ArtifactBase` with
  optional `ModelArtifact`, so normal metadata creation does not create the
  optional table. Field-level meaning is specified in
  [Dashboard data model](../market-simulation/dashboard-data-model.md).
- Behavior contract: `DatabaseSettings.url()` percent-encodes the user and password. This is required, not defensive: a password containing `@` or `/` otherwise corrupts the Uniform Resource Locator (URL) and fails as a misleading host-resolution error. `safe_summary()` never contains the password, and names the schema in parentheses only when it is not `public`. `connect_args()` returns `connect_timeout`, plus `options: -csearch_path=<schema>` for a non-default schema — the selected schema alone, with no fallback behind it, so a partly populated schema reports a missing table rather than resolving it from another scenario. It raises `ValueError` rather than building an option from a name `valid_schema_name()` rejects. These modules sit at the edge of the project: the attribution, standard, and strategy modules must never import them, because they read and write files and depend on the standard library alone. Every run-scoped table carries a foreign key to its run, so two report windows coexist rather than overwrite, and the `UniqueConstraint` on each output table is scoped by `run_pk`, which makes a re-import of the same window a conflict rather than a silent duplicate. **Every table carries a surrogate `id` primary key, and the row order the dashboard reads depends on it**: the importer inserts in the artifact's order, so `order by id` reproduces it.
- Dependencies: `python-dotenv` and SQLAlchemy 2.0. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run` reports the row count each class will receive without opening a connection.

### `import_to_database.py`

Source: `script/import_to_database.py`

- Responsibility: Read every committed artifact and write it into the PostgreSQL schema defined in `dashboard/models.py`, inside one transaction.
- Inputs: `modules/mta_attribution/data/simulated/*.csv`, `modules/mta_attribution/outputs/attribution/*.csv`, and the strategy module's JavaScript Object Notation (JSON) inputs and outputs. Connection settings come from `.env` through `dashboard/config.py`; `--schema` overrides `PG_SCHEMA` for one run.
- Outputs: The eighteen populated tables in the selected schema, and a per-table row count printed on completion.
- Behavior contract: The command **refuses to overwrite a populated database** unless `--replace` is given, so an accidental second run cannot destroy existing rows; `--replace` drops and rebuilds every table, which is what a schema change requires. `--dry-run` reports the row count each table will receive without opening a connection. `--full-events` imports every synthetic event rather than the default bounded sample. `--schema` selects the target schema, defaulting to `PG_SCHEMA` and then to `public`; an invalid name is refused before a connection is opened, a non-default schema is created if absent through `ensure_schema()` before `create_all`, and `--replace` acts within that schema alone. `read_rows()` drops the Chinese field-description row by matching its exact first-cell marker; an earlier heuristic that tested for the absence of digits silently discarded a real touchpoint row from the files that have no description row. `Importer.touchpoint()` creates each `Touchpoint` on first sight and reuses it thereafter, which is what makes the five-segment key the join between spend and attribution. **Rows are inserted in each artifact's own order**, which is what the dashboard's `order by id` relies on to reproduce that order. The whole import runs in one session and commits once, so a failure part-way leaves the database untouched.
- Dependencies: SQLAlchemy, `psycopg`, and `python-dotenv`, plus `dashboard/config.py` and `dashboard/models.py`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run`, then `node script/verify_dashboard_parity.mjs` against the loaded instance.

### `derive_scenario_schemas.py`

Source: `script/derive_scenario_schemas.py`

- Responsibility: Compute the tables in `dashboard/models.py` from a schema the external simulator populated, writing one self-contained schema per scenario.
- Inputs: A source schema holding `mta_simulation_run`, `mta_sim_campaign`, `mta_sim_ad_group`, `mta_sim_touchpoint`, `mta_sim_product`, `mta_sim_campaign_product_link`, `mta_sim_delivery_observation`, `mta_sim_outcome_observation`, `amc_path_report`, and `amazon_ads_daily_touchpoint_performance`. Connection settings come from `.env` through `dashboard/config.py`.
- Outputs: One schema per scenario, holding the dashboard model plus a copy of that scenario's research tables; a per-table row count per scenario; and a stated reason for each layer that could not be derived.
- Behavior contract: The source schema is **read only** — a target equal to it is refused before any write, and the reading connection is deliberately unpinned so that which schema is read depends on the argument rather than on a setting. Every scenario's daily path rows are summed per path into the one report window `compare_attribution_models()` requires, using every row rather than sampling a day; row-level invariants survive the sum because they hold termwise. `interaction_type` is read back off the fifth segment of the stored touchpoint key and `cost_type` follows from it by the project's CPC/CPM pairing rule, so `touchpoint_key_from_ads_row()` verifies each rebuilt key against the value the simulator wrote. Attribution, spend aggregation, and model comparison are **imported from the modules that own them** rather than reimplemented. The touchpoint-to-entity bridge is the one derived quantity with no direct source: a touchpoint delivered by a single Campaign carries its whole attributed outcome, and one shared by several is split by each Campaign's share of that touchpoint's cost, then divided across Products by the revenue the simulator recorded per Campaign, touchpoint, and Product. Candidate counts state only what the scenario establishes; a count the simulator does not model is written as zero rather than invented, and `budget_blockers()` reports **every** reason a recommendation is impossible rather than the first, because fixing one alone would not make it possible. The `mta_sim_*` tables are copied per `run_id` into each derived schema, since the Research view reads them reflectively through `search_path` and a schema without them shows no history.
- Dependencies: SQLAlchemy, `psycopg`, and `python-dotenv`, plus `dashboard/config.py`, `dashboard/models.py`, `script/import_to_database.py`, and the attribution and strategy modules. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/derive_scenario_schemas.py --source mta --list` reports the scenarios without writing; selecting a derived schema in the settings dialog serves every view.
