---
title: Populating PostgreSQL
compact: "The `import_to_database.py` importer and the schema/`.env` contract it writes against: `--replace`, `--dry-run`, `--full-events` flags, one-transaction commit, and the surrogate `id` insert order the dashboard's row-order rule depends on. Specifies `config.py`, `models.py`, `import_to_database.py`."
lang: en-US
source_files: dashboard/config.py, dashboard/models.py, script/import_to_database.py
---

# Populating PostgreSQL

Setting `DATABASE=true` and the `PG_*` values in `.env` is not enough on its own — see [Two Data Sources, One Contract](./index.md#two-data-sources-one-contract) — the PostgreSQL tables have to be populated first. This page specifies the two files that define that schema and the one script that writes to it.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `config.py` and `models.py`

Source: `dashboard/config.py`, `dashboard/models.py`

- Responsibility: Define the PostgreSQL schema the dashboard reads and the `.env` contract the importer resolves against. The dashboard itself holds no Python; these two exist for `script/import_to_database.py`.
- Inputs: `.env` at the repository root, for `config.py`. Nothing at runtime for `models.py`.
- Outputs: `use_database()`, `database_settings()`, `DatabaseSettings.safe_summary()`, and the path constants; and `Base` plus eighteen mapped classes in four layers — entity, history, model output, and strategy. Field-level meaning is specified in [Dashboard data model](../market-simulation/dashboard-data-model.md).
- Behavior contract: `DatabaseSettings.url()` percent-encodes the user and password. This is required, not defensive: a password containing `@` or `/` otherwise corrupts the Uniform Resource Locator (URL) and fails as a misleading host-resolution error. `safe_summary()` never contains the password. These modules sit at the edge of the project: the attribution, standard, and strategy modules must never import them, because they read and write files and depend on the standard library alone. Every run-scoped table carries a foreign key to its run, so two report windows coexist rather than overwrite, and the `UniqueConstraint` on each output table is scoped by `run_pk`, which makes a re-import of the same window a conflict rather than a silent duplicate. **Every table carries a surrogate `id` primary key, and the row order the dashboard reads depends on it**: the importer inserts in the artifact's order, so `order by id` reproduces it.
- Dependencies: `python-dotenv` and SQLAlchemy 2.0. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run` reports the row count each class will receive without opening a connection.

### `import_to_database.py`

Source: `script/import_to_database.py`

- Responsibility: Read every committed artifact and write it into the PostgreSQL schema defined in `dashboard/models.py`, inside one transaction.
- Inputs: `modules/mta_attribution/data/simulated/*.csv`, `modules/mta_attribution/outputs/attribution/*.csv`, and the strategy module's JavaScript Object Notation (JSON) inputs and outputs. Connection settings come from `.env` through `dashboard/config.py`.
- Outputs: The eighteen populated tables, and a per-table row count printed on completion.
- Behavior contract: The command **refuses to overwrite a populated database** unless `--replace` is given, so an accidental second run cannot destroy existing rows; `--replace` drops and rebuilds every table, which is what a schema change requires. `--dry-run` reports the row count each table will receive without opening a connection. `--full-events` imports every synthetic event rather than the default bounded sample. `read_rows()` drops the Chinese field-description row by matching its exact first-cell marker; an earlier heuristic that tested for the absence of digits silently discarded a real touchpoint row from the files that have no description row. `Importer.touchpoint()` creates each `Touchpoint` on first sight and reuses it thereafter, which is what makes the five-segment key the join between spend and attribution. **Rows are inserted in each artifact's own order**, which is what the dashboard's `order by id` relies on to reproduce that order. The whole import runs in one session and commits once, so a failure part-way leaves the database untouched.
- Dependencies: SQLAlchemy, `psycopg`, and `python-dotenv`, plus `dashboard/config.py` and `dashboard/models.py`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run`, then `node script/verify_dashboard_parity.mjs` against the loaded instance.
