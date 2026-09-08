---
title: Navigation Rail and Settings
compact: "Eight lazy page imports and canonical deep links; Settings loads independently of dashboard data and restores deployment identity on refresh; Knowledge Base tabs, schema doctor, recovery, protected configuration, queued tasks, shared copyable LogViewer and package-native database imports."
lang: en-US
source_files: dashboard/src/pages.js, dashboard/src/App.vue, dashboard/src/main.js, dashboard/src/views/Settings.vue, dashboard/src/components/BackendTasks.vue, dashboard/src/components/SchemaRecovery.vue
---

# Navigation Rail and Settings

The rail is the shell around the eight pages listed on [Dashboard](./index.md#the-eight-pages). This page specifies the rail and the routed Settings page.

## Navigation Rail <span class="status-label status-verified" aria-label="Verified"></span>

The sidebar is one navy column of eight stacked destination buttons, with the
active item filled. It has no `OVERVIEW`, `PLANNING`, or `INSIGHTS` section
labels and no group containers. Data Generator follows Command Center; the
remaining destinations keep their existing relative order.

`src/pages.js` is the single place a view is registered. A page key appears
there, in `PAGE_KEYS`, and in `App.vue`'s component map;
`tests/dashboard.test.js` asserts the three agree, so the rail cannot offer a
destination the shell cannot render.

The location hash identifies both a page and the subsection visible inside it.
The canonical form is `#/page/section`: examples are
`#/budget/product-economics`, `#/campaigns/paths`, and
`#/optimizer/optimization`. Every destination has a default subsection, so a
single-panel page is still explicit: Command Center is `#/overview/summary`,
Data Generator is `#/generator/configure`, and Knowledge Base is
`#/knowledge/notice`. Settings is `#/settings/general`.

Clicking the rail opens that page's default subsection. Clicking an in-page tab
pushes another history entry, and browser Back and Forward restore both the
page and its selected tab. A direct deep link renders the same state after a
refresh. A legacy hash such as `#campaigns` is accepted once and replaced with
its canonical default, while an unknown page falls back to Command Center and
an unknown subsection falls back to that page's declared default. Normalizing
a legacy or invalid location uses `replaceState`; reader navigation uses
`pushState`.

`src/pages.js` owns the route registry as well as the rail registry. Each
subsection declares the allow-listed dashboard resources it requires. The
shell loads those resources before mounting the selected view; it does not
load resources declared only by sibling tabs. Completed resources remain in a
client cache, so revisiting a tab is immediate until Reload invalidates the
cache.

### Route and resource declarations

The exact declarations are part of the navigation contract. Every data page starts
with `shell`, which supplies deployment and report context. Settings has no
dashboard resource dependency, so recovery survives a failing data source.

#### Command Center, Data Generator, and Knowledge Base

- `overview/summary`: `performance`, `attribution`, and `budget`.
- `generator/configure`: no dashboard data beyond `shell`; the generator uses
  its own backend capability endpoint only after this route mounts.
- `knowledge/notice`: preserves the unavailable backend-knowledge status; no data beyond `shell`.
- `knowledge/ontology-review`: displays the separately imported canonical fixture release; no dashboard application programming interface (API) resource beyond `shell`.

#### Settings

- `settings/general`, `settings/source`, `settings/logging`, and
  `settings/tasks`: no dashboard resources, including `shell`; the page reads its own
  settings, schema-operation, and task endpoints only after the route mounts.

#### Budget Manager

- `budget/overview`: `budget` and `research-overview`.
- `budget/providers`: `research-providers`.
- `budget/products`: `research-products`.
- `budget/campaigns`: `research-campaigns`.
- `budget/ad-groups`: `research-ad-groups`.
- `budget/touchpoints`: `research-touchpoints`.
- `budget/product-economics`: `research-product-economics`.
- `budget/generation-configs`: `research-generation-configs`; this route
  normalizes to Overview while diagnostic mode is off.

#### Campaigns

- `campaigns/history`: `research-campaign-history`.
- `campaigns/performance`: `performance`.
- `campaigns/bridge`: `entity-bridge`.
- `campaigns/paths`: `path-report`.

#### Campaign Optimizer and Optimization Log

- `optimizer/attribution`: `attribution`.
- `optimizer/optimization`: `strategy`.
- `optimizer/evaluation`: `evaluation`.
- `log/provenance`: `attribution`, `budget`, and `strategy`.
- `log/attribution`, `log/optimization`, and `log/evaluation`: no dashboard
  data beyond `shell`; each requests the jobs endpoint only when selected.

### Below the wide breakpoint

At `1024px` the rail becomes a sticky, horizontally scrollable bar. The same
flat order is retained, and no disclosure or group state is introduced. The
selected destination stays visible through horizontal scrolling and carries
`aria-current="page"`. Both the single-column shell track and navigation
element have zero minimums, so the rail's own overflow scrolls without widening
the document or any page beneath it.

### The Settings page

Settings is the eighth routed destination and the last item in the same flat rail
as the data pages. It renders in the normal content area instead of a modal,
so its address, title, breadcrumb, browser history, and responsive layout follow
the same shell contract as every other page. The rail foot remains status-only:
it shows the active source, a status dot, whether logging is on, and the Docs and
Repo links.

The Settings page has four deep-linked tabs. **General** is first and contains
basic deployment identity only. **Data source** owns a four-step database doctor.
**Logging** owns request-log capture and inspection. **Tasks** owns long-running
service history, detail logs, queue state, copy, and stop controls. Deployment
identity appears nowhere in the latter three tabs.

When `DASHBOARD_CONFIG_READ_ONLY=true`, the server continues to report its configured source but rejects every settings mutation. The page replaces its connection form with the server-configuration instruction and disables logging controls, so a team-server visitor cannot rewrite protected credentials or process state through the browser.

That flag governs credentials, not data. Which schema is loaded, and setting one
up, stay available on a protected deployment: both act on the database the
platform already pointed the service at, and neither rewrites a credential.
Withholding them there would leave the one deployment whose readers have no
shell as the one deployment with no way to prepare a schema at all.

#### Data source

Contains the `DATABASE` toggle and the PostgreSQL host, port, database, user, password, and Secure Sockets Layer (SSL) mode, with **Test connection** and **Save to `.env`**.

It also contains **Reload data**. Reload is not rendered in the sidebar. The
button clears backend and client caches, reloads the selected schema, and keeps
the reader on the Settings page long enough to report success or failure.

The database doctor presents one standard sequence rather than mixing connection,
selection, and destructive setup controls in one undifferentiated form:

1. **Connect** — enable database mode, enter or inspect the protected connection,
   test it where editable, and save it.
2. **Inspect** — read the schema census and its readiness diagnosis.
3. **Import** — either select a dashboard-ready schema, parse a complete MTA-SIM
   source into scenario schemas, or initialize the explicitly synthetic sample in
   an empty/new schema. Replacement remains a separate confirmed choice.
4. **Verify** — monitor the queued task in Tasks, then select the resulting
   dashboard-ready schema and reload its actual data.

Each step reports `complete`, `current`, `blocked`, or `optional` from the state
already returned by the backend. Starting import switches the route to Tasks and
selects that task, so a bare “Parsing started” notice never substitutes for
observable work.

#### Runtime schema selection

In database mode, both the editable Dashboard schema selector and the protected
schema inventory are actionable. Selecting another dashboard-ready schema opens
a confirmation window naming the current and target schemas and explaining
that every view will reload. Cancelling restores the active selection.
Confirming calls `POST /api/settings/schema-selection`.

The backend accepts only a plain identifier present in the live census with
`selectable: true`. It sets the process runtime selection, disposes the old
connection pool, clears every snapshot cache, and returns fresh Settings state.
It does not rewrite `.env`; a restart returns to the deployment's configured
`PG_SCHEMA`. AppStack runs one backend worker while runtime schema selection is
enabled, so one process owns one active schema. A failed reload restores the
previous selection and leaves the current page usable.

#### Schema setup

Below the connection form on every deployment with a backend. It lists the
readable schemas on the saved connection and offers two actions against the one
selected: **Initialize sample model**, which writes the committed sample account
into an empty or new schema, and **Parse all scenarios**, which reads a source
schema without changing it and writes one dashboard schema per scenario.
**Replace existing target tables** is off by default and asks for confirmation,
because it destroys what is already there.

Whether setup is offered comes from the server, in the `available` and `reason`
fields `GET /api/schema-operations` returns beside the operation record, rather
than from a rule the page reconstructs. `SCHEMA_SETUP_ENABLED=false` withholds
it, and the page then states why instead of showing buttons the route would
refuse. `DASHBOARD_CONFIG_READ_ONLY` does not withhold it, on the same grounds
as `PIPELINE_RUNS_ENABLED`.

Each request is revalidated against a fresh census before entering the shared
operator queue, and each command is a fixed argument vector run without a shell.
The queue has one worker by default: initialization, parsing, attribution,
optimization, and evaluation execute one at a time in first-in/first-out order.
Output streams into the Tasks tab, bounded to the newest 600 lines per task.

#### When a schema cannot be read

A schema that does not carry the dashboard's tables makes `GET /api/dashboard`
answer 503, and the client renders its error card. Under that card,
`GET /api/schema-recovery` lists what the reader can do about it as controls:
load another schema that is ready, build dashboard schemas from a source schema,
or write the sample account into an empty one. Each is the same action the
Settings page offers, carried out by the same route and revalidated there.

The list excludes the schema that just failed, and excludes any schema nothing
can be done with — unlike the Settings dropdown, which lists an unusable schema
disabled so a reader learns why, this list exists only to be acted on. Nothing
it offers overwrites anything: replacement stays behind the Settings checkbox
that states what it destroys.

This is why the 503 message names no command. The census `detail` strings still
do, beside the schema they describe, for an operator at a terminal; the error
card is rendered to a reader who has a browser and nothing else.

#### Logging

Contains the streaming-data log switch, its minimum severity, source and
severity display filters, copy and clear actions, and the captured records.

**Test connection** opens a throwaway connection using what was typed rather than what is saved, so a correction can be validated before it is committed to `.env`. Saving rewrites `.env` in place — comments and unrelated keys are preserved, and a key already present is replaced rather than appended, so a file cannot end up with two values for one key and the winner decided by read order. Saving also drops the loader caches and disposes the connection pool, because both would otherwise hold the old mode until a restart.

**The password field is write-only.** The server never sends a stored password back, and an empty field means "keep the stored one" rather than "clear it", so the value is never rendered into the page. `config.safeSummary()` omits it by construction and is the only rendering of a connection the dashboard performs.

Logging is enabled at `INFO` by default. It captures actual data-source activity
as English, grep-friendly records with a Coordinated Universal Time (UTC)
timestamp, severity, source, message, and optional operation duration in a fixed-capacity in-memory ring
buffer rather than a file. A demonstration machine's disk cannot be filled by
leaving the dashboard open, and one long statement cannot dominate the buffer
because each message is truncated. Display filters do not mutate capture or
records. This structure adapts Trance-0's
[Notechondria operator-log component](https://github.com/Trance-0/notechondria/blob/main/frontend/notechondria_shared/lib/src/components/debug_log.dart):
bounded buffers, INFO defaults, severity/source filters, copy, and clear.

#### Tasks

Tasks lists queued, running, stopping, stopped, succeeded, and failed backend
operations newest first. Every row states task type, human label, safe input
summary, queue position where applicable, created/start/finish timestamps, and
progress. Selecting a row opens a build-style event stream: each line has a
timestamp, stream/severity marker, and message; the exact reproducible command is
separate and copyable. **Copy log** copies the visible task header, summary,
command, and lines. **Stop** cancels a queued task immediately or terminates the
running child. Completed tasks remain inspectable in bounded process history.

The task summary never contains credentials, arbitrary client paths, raw datasets,
or evaluation-only ground truth. A model task names the server-owned dataset label,
scope, and declared options; a schema task names the action, source or target
schema, and replacement choice.

### Links out of the app

The rail closes with **Docs** and **Repo**. A reader who arrives at the published dashboard has no other route to the specification or the source, so the app carries them. The documentation link is relative in the published build, where the documentation is a sibling directory, and absolute in a local run, where there is no sibling to point at.

Settings captured records, BackendTasks, and SchemaRecovery use the shared
[LogViewer](./views/stage-execution.md#logviewer-vue). Copy sits beside each
log, includes task context and command where available, and copies only the
filtered records on Settings. BackendTasks retains task timestamps and safe
summary in the copy payload; SchemaRecovery includes operation and exit state.

## Deferred view loading

The shell loads the seven Trance-0 page components with dynamic imports.
Knowledge Base retains its existing component import and behavior. Unvisited
Trance-0 pages and their chart dependencies load only when selected. The shell and navigation remain available during loading.
Settings declares no dashboard resources: even a failing database-backed shell
must leave the database doctor reachable at `#/settings/source`. Async component
loading shows an accessible status and a failed chunk shows a reload remedy.
The shell retains each successful Settings response separately from dashboard
resources and passes it to `useDeployment(settings)`, restoring the database
accent on a direct Settings refresh. Its existing status refresh runs at mount
and after Reload or a saved change. Failed status requests preserve the last
successful response. Display identity follows the
[deployment capability contract](./views/deployment-capability.md#the-two-accents);
write permission still requires a loaded database snapshot. The header receives
the display mode separately from that permission.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `src/pages.js`, `src/App.vue`, and `src/main.js`

Source: `dashboard/src/main.js`, `dashboard/src/App.vue`, `dashboard/src/pages.js`

- Responsibility: Register the eight routed pages, draw the shell around them, and dispatch to the selected one.
- Inputs: The location hash and the selected route's declared resource keys.
- Outputs: The rendered application. `PAGES` carries each view's title, breadcrumb, and inline icon; `PAGE_KEYS` is the one-column order; `REPO_URL` and `DOCS_URL` are where the app points a reader who wants the source or the specification.
- Behavior contract: `src/pages.js` is the single place a page and its subsections are registered, and `tests/dashboard.test.js` asserts that `PAGES`, `PAGE_KEYS`, route parsing, canonical serialization, defaults, and `App.vue`'s component map agree. Data Generator follows Command Center and Settings is the last destination. No group label, group container, or separate Settings foot button is rendered. Reload exists only on the Data source tab. Canonical hashes have the form `#/page/section`; reader navigation uses `pushState`, normalization uses `replaceState`, and Back and Forward restore the selected subsection. `App.vue` requests only the current route's resource declaration before mounting that page and passes the selected subsection plus a navigation event to tabbed pages. It renders loading, error, and loaded states itself, and a `database_unavailable` error links to `#/settings/source` while carrying `SchemaRecovery.vue` beneath it. The shell's general read-only data-operation notice is suppressed on Settings and Data Generator; Data Generator owns separate capability state and may still run in local file mode. Header context comes from the small `shell` resource on data pages. Settings remains reachable independently of that resource.
- Dependencies: Vue 3.
- Verification: `dashboard/tests/dashboard.test.js` for the registration contract; the rendered result is verified in a real browser for all eight pages.

### `src/views/Settings.vue` and `src/components/BackendTasks.vue`

Source: `dashboard/src/views/Settings.vue`,
`dashboard/src/components/BackendTasks.vue`

- Responsibility: Own the four routed Settings tabs — General deployment
  identity, the database doctor, reload, runtime schema selection, schema setup,
  request logging, and task inspection — and own
  none of the decisions about whether they are permitted.
- Inputs: `GET /api/settings`, `GET /api/schema-operations`, `GET /api/tasks`, and what the
  reader types. A stored password is never among them.
- Static-host instructions name the runnable import command `uv run --extra dashboard python -m backend.import_to_database`.
- Outputs: Settings, schema-selection, schema-operation, and task-stop requests,
  and the rendered page. Only the schema-selection confirmation is a modal.
- Behavior contract: The page defaults to General and each tab navigates to its
  canonical `#/settings/<tab>` hash. Deployment identity renders
  only there; it is basic build/runtime information with no setting control.
  **Protection and capability are separate branches.**
  Protected configuration replaces the credential form; it does not enclose
  schema setup, which renders as a sibling on every deployment with a backend.
  Nesting the two is what made setup unreachable on the protected deployment,
  and the test asserting that the `Schema setup` heading falls outside the
  editable branch exists to keep it from recurring. Whether the setup buttons
  are enabled is read from the server's `available` and `reason` fields rather
  than reconstructed, so the page and the backend route cannot disagree. The census
  is refreshed by reading settings on a protected server and by a connection
  test on an editable one, because the test action is itself refused when
  configuration is protected. The password field is write-only, and an empty
  one means keep the stored value. The Data source tab renders Connect, Inspect,
  Import, and Verify in that order; starting a schema operation navigates to Tasks with
  its returned identifier. Tasks polls only while at least one operation is
  queued, running, or stopping, keeps terminal records selectable, copies one
  complete detail log, and can stop the selected queued or running task.
- Dependencies: Vue 3, `src/api/client.js`, and `ConfirmDialog.vue`.
- Verification: `dashboard/tests/dashboard.test.js`, which pins the branch
  structure, the census-refresh path, and the schema-selection contract;
  exercised in a real browser against a protected server and an editable
  checkout.

### `src/components/SchemaRecovery.vue`

Source: `dashboard/src/components/SchemaRecovery.vue`

- Responsibility: Turn a `database_unavailable` error into the actions that
  resolve it, for a reader who has a browser and nothing else.
- Inputs: `GET /api/schema-recovery`.
- Outputs: A grouped list of select, derive, and initialize controls; a
  `recovered` event when an action succeeds; a `settings` event for the reader
  who wants the full Settings page.
- Behavior contract: It renders only what the server offered, so it grants
  nothing: the chosen action is sent to the same schema-selection or
  schema-operation route the Settings page uses and revalidated there against a fresh
  census. **It never sends `replace: true`.** Overwriting stays behind the
  settings checkbox that states what it destroys, because the reader here is
  the one least placed to judge what is about to be lost. A running operation
  is polled at 1200 ms while queued, running, or stopping; on success the offer list
  is refreshed before the page reloads, so a stale option cannot be pressed
  twice.
- Dependencies: Vue 3 and `src/api/client.js`.
- Verification: `backend/tests/test_schema_recovery.py` for the offers it can
  receive, `dashboard/tests/dashboard.test.js` for its presence under the error
  card and the absence of the command it replaced.
