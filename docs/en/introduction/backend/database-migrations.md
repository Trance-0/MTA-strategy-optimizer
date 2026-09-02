---
title: Database Migration and Continuous Deployment Plan
description: Versioned PostgreSQL schema upgrades for existing dashboard deployments
compact: "Migration plan for dashboard PostgreSQL schemas: current create/drop limitations, Alembic revision ledger, expand-contract compatibility, advisory-locked pre-deploy jobs, previous-release upgrade and lazy-resource endpoint tests, rollout gates, observability, and forward-only recovery."
lang: en-US
---

# Database Migration and Continuous Deployment Plan

## Scope and evidence labels

This plan governs the dashboard-owned tables declared in
`dashboard/models.py`. It does not migrate the external `mta_sim_*` source
tables. A database may contain several dashboard schemas, so an upgrade is not
complete until every selected dashboard schema is at a revision supported by
the backend being deployed.

Statements below use these labels:

- **Repository fact** describes behavior present in the current checkout.
- **Observed deployment fact** describes the directly probed running service.
- **Inference** explains the most likely consequence of those facts.
- **Recommendation** specifies the target design; it is not current behavior.

## Current implementation and failure mode

### Creation and replacement

**Repository fact:** `script/import_to_database.py` and
`script/derive_scenario_schemas.py` call SQLAlchemy `create_all()`. Their
replacement paths call `drop_all()` before recreating the model. There is no
ordered migration directory or database structure revision ledger.

**Repository fact:** `BudgetRecommendationRun.schema_version` versions one
strategy artifact. It is not a database structure version and cannot answer
whether a column, index, or constraint required by a backend release exists.

**Inference:** adding a mapped column may work for a newly created schema while
an existing schema remains unchanged. The backend then fails only when a query
touches the missing structure. Replacing the schema repairs drift by deleting
data, which is not an upgrade path for an existing deployment.

### Deployment behavior

**Repository fact:** AppStack uses a one-replica, `Recreate` rollout and a
database-independent `/api/health` probe. The validation sequence separately
checks `/api/dashboard` after deployment.

**Observed deployment fact (2026-09-01):** the remote settings response named
backend version `0.9.34`, active schema `public`, and five readable schemas,
while the served frontend asset did not contain the schema-operation or lazy
research-history routes.

**Inference:** liveness alone can admit an application whose client, backend,
and database structure are not one compatible release. The deployment needs
an explicit compatibility gate before application traffic moves.

## Target migration contract

### Revision ledger

**Recommendation:** adopt Alembic as the migration runner because the project
already uses SQLAlchemy models and needs ordered revisions, generated offline
Structured Query Language (SQL), and upgrade testing from a previous release.
Those are measurable capabilities not provided by `create_all()`.

Each dashboard schema receives its own `alembic_version` ledger. The external
source schema remains untouched. A project command in `script/` discovers
dashboard schemas through the same capability census as Settings, validates
their names, acquires one PostgreSQL advisory lock for the database, and runs
the ordered revisions against each target through that schema's isolated
`search_path`.

The settings census reports, per schema:

- the applied database revision;
- the minimum and maximum revision supported by the running backend;
- `compatible`, `upgrade required`, `newer than backend`, or `untracked`;
- the existing table-capability detail and active-schema marker.

Until the ledger is introduced, Settings must say **not tracked** rather than
inventing a version from table counts or from the strategy artifact.

### Baseline revision

**Recommendation:** revision `0001` is a stamped baseline matching the current
`dashboard/models.py` structure. Adoption is two-step:

1. For each existing schema, compare columns, types, nullability, indexes,
   unique constraints, and foreign keys with the baseline. Refuse stamping on
   any difference and print the exact drift.
2. Stamp only a matching schema; create the baseline normally for an empty
   schema. Never stamp based only on the fourteen-table readiness census.

`create_all()` remains valid only for disposable test setup while migration
adoption is in progress. Maintained import and derivation commands must
eventually invoke `upgrade head` for structure creation and then load rows.
They must not drop an existing schema unless the operator explicitly requests
the already documented destructive replacement action.

### Expand-contract changes

**Recommendation:** every change that affects stored data uses two compatible
releases.

1. **Expand:** add nullable columns, new tables, or new indexes without removing
   anything the previous backend reads.
2. Deploy code that can read the old and new representation and writes the new
   representation.
3. Backfill in bounded, restartable batches and record completion separately
   from the structure revision.
4. **Contract:** only a later patch removes old columns or constraints after
   every running backend and rollback image no longer uses them.

Migrations are forward-only in routine operation. An application rollback
uses the previous image only while its declared revision range still includes
the migrated database. Data restoration is an incident-recovery action, not a
normal automated downgrade.

## Continuous deployment sequence

### 1. Pull-request verification

**Recommendation:** use a temporary PostgreSQL service to run four gates:

1. Create an empty database and upgrade every dashboard schema to `head`.
2. Restore a sanitized structure-and-fixture snapshot from the previous
   released revision, then upgrade it to `head` without data loss.
3. Run the backend and dashboard suites against the upgraded database,
   including Campaigns and Settings contracts.
4. Compare Alembic's model metadata with the migrated database and fail on an
   unrepresented model change or unexpected schema drift.

The previous-revision fixture contains public demonstration rows only. It must
not contain a production dump or production identifiers.

### 2. Immutable build

**Recommendation:** build the client and backend from one commit, inject the
same full commit identifier into both, and tag the image immutably by project
version and commit. Reject `unknown` build identity in the production
pipeline. Publish only after the migration and application suites pass.

### 3. Backup and migration job

**Recommendation:** before rollout, AppStack starts one finite migration Job
from the same image as the backend. The Job:

1. obtains the database advisory lock;
2. lists target dashboard schemas and their current revisions;
3. refuses an untracked, drifted, or newer-than-backend schema;
4. verifies the operator-confirmed backup or recovery point required by the
   environment;
5. runs revisions in transactions where PostgreSQL permits it;
6. writes revision, duration, row counts, and commit identity to the deployment
   log without credentials or row-level data;
7. exits non-zero before the application Deployment changes if any target
   fails.

The migration role may alter dashboard schemas but must not own or alter the
external source schema. The runtime role remains read/write only where the
application needs it and does not receive schema-alter privileges.

### 4. Compatibility gate and rollout

**Recommendation:** add a database-readiness endpoint distinct from
`/api/health`. It returns success only when the active schema revision is
inside the backend's supported range and the required tables are readable.
AppStack waits for the migration Job, starts the one-replica `Recreate`
Deployment, then checks:

1. `/api/health` for process liveness;
2. database readiness for revision compatibility;
3. `/api/settings` for matching client/backend identity and visible schema
   revisions;
4. `/api/dashboard` for the core snapshot;
5. `/api/dashboard/resources/research-campaign-history` for the lazy Campaigns history contract;
6. the Campaigns route in a browser with no console or request failure.

Traffic is not considered upgraded until all six checks pass.

### 5. Recovery

**Recommendation:** if the migration Job fails, do not roll out the new
application. Correct the migration and run it again from its recorded revision.
If the application smoke checks fail after a compatible migration, redeploy
the previous compatible image. If a destructive defect corrupts stored data,
stop writers and restore through the database provider's recovery mechanism;
do not attempt an automatic Alembic downgrade over live data.

## Delivery phases

### Phase A — visibility

Expose the active schema and complete schema inventory in protected Settings,
label the current structure version as **not tracked**, and keep configuration
controls unavailable. This removes the present observability gap without
pretending that a migration system already exists.

### Phase B — baseline and drift audit

Add Alembic, the baseline revision, a read-only drift command, schema revision
fields in the census, and tests covering empty and existing schemas. Run the
audit against every target schema before stamping any revision.

### Phase C — deployment gate

Add the advisory-locked AppStack migration Job, database-readiness endpoint,
immutable identity requirement, and previous-revision upgrade test. Make the
application rollout depend on the Job.

### Phase D — first expand-contract migration

Deliver one small additive change through the complete path, including
backfill telemetry and rollback verification. Only after that rehearsal should
larger table changes rely on the migration pipeline.

## Acceptance criteria

The plan is implemented when an operator can identify the active schema and
revision from Settings, a clean database and an existing previous-version
database reach the same `head`, a failed migration prevents rollout, a prior
compatible image can be restored without a database downgrade, and Campaigns
loads its core and observation data through separate verified requests.
