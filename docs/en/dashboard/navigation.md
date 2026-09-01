---
title: Navigation Rail and Settings
compact: "Navigation and settings contract: one-column hash routing without section separators, Settings-owned reload, confirmed runtime PostgreSQL schema selection, browser schema setup and recovery on a protected deployment, write-only passwords, and bounded logging."
lang: en-US
source_files: dashboard/src/pages.js, dashboard/src/App.vue, dashboard/src/main.js, dashboard/src/components/SettingsDialog.vue, dashboard/src/components/SchemaRecovery.vue
---

# Navigation Rail and Settings

The rail is the shell around the seven views listed on [Dashboard](./index.md#the-seven-views). This page specifies the rail itself and the settings module pinned to its foot.

## Navigation Rail <span class="status-label status-verified" aria-label="Verified"></span>

The sidebar is one navy column of seven stacked destination buttons, with the
active item filled. It has no `OVERVIEW`, `PLANNING`, or `INSIGHTS` section
labels and no group containers. Data Generator follows Command Center; the
remaining destinations keep their existing relative order.

`src/pages.js` is the single place a view is registered. A page key appears
there, in `PAGE_KEYS`, and in `App.vue`'s component map;
`tests/dashboard.test.js` asserts the three agree, so the rail cannot offer a
destination the shell cannot render.

The rail writes the selected page into the location hash, so a view is linkable and survives a refresh. It is written with `replaceState` rather than assignment, so switching views does not fill the browser's back stack with intermediate pages.

### Below the wide breakpoint

At `1024px` the rail becomes a sticky, horizontally scrollable bar. The same
flat order is retained, and no disclosure or group state is introduced. The
selected destination stays visible through horizontal scrolling and carries
`aria-current="page"`.

### The settings module

Everything about the dashboard's own plumbing is pinned to the foot of the rail, ruled off from the view navigation above it, so it never reads as another destination. It shows the active source, a status dot, and whether logging is on, and opens a modal with two tabs:

When `DASHBOARD_CONFIG_READ_ONLY=true`, the server continues to report its configured source but rejects every settings mutation. The modal replaces its connection form with the server-configuration instruction and disables logging controls, so a team-server visitor cannot rewrite protected credentials or process state through the browser.

That flag governs credentials, not data. Which schema is loaded, and setting one
up, stay available on a protected deployment: both act on the database the
platform already pointed the service at, and neither rewrites a credential.
Withholding them there would leave the one deployment whose readers have no
shell as the one deployment with no way to prepare a schema at all.

#### Data source

Contains the `DATABASE` toggle and the PostgreSQL host, port, database, user, password, and Secure Sockets Layer (SSL) mode, with **Test connection** and **Save to `.env`**.

It also contains **Reload data**. Reload is not rendered in the sidebar. The
button clears backend and client caches, reloads the selected schema, and keeps
the Settings dialog open long enough to report success or failure.

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
than from a rule the dialog reconstructs. `SCHEMA_SETUP_ENABLED=false` withholds
it, and the dialog then states why instead of showing buttons the route would
refuse. `DASHBOARD_CONFIG_READ_ONLY` does not withhold it, on the same grounds
as `PIPELINE_RUNS_ENABLED`.

Each request is revalidated against a fresh census before a process starts, and
each command is a fixed argument vector run without a shell. Output streams into
the dialog, bounded to the newest 600 lines.

#### When a schema cannot be read

A schema that does not carry the dashboard's tables makes `GET /api/dashboard`
answer 503, and the client renders its error card. Under that card,
`GET /api/schema-recovery` lists what the reader can do about it as controls:
load another schema that is ready, build dashboard schemas from a source schema,
or write the sample account into an empty one. Each is the same action the
Settings dialog offers, carried out by the same route and revalidated there.

The list excludes the schema that just failed, and excludes any schema nothing
can be done with — unlike the Settings dropdown, which lists an unusable schema
disabled so a reader learns why, this list exists only to be acted on. Nothing
it offers overwrites anything: replacement stays behind the Settings checkbox
that states what it destroys.

This is why the 503 message names no command. The census `detail` strings still
do, beside the schema they describe, for an operator at a terminal; the error
card is rendered to a reader who has a browser and nothing else.

#### Logging

Contains the streaming-data log switch, its level, and the captured records.

**Test connection** opens a throwaway connection using what was typed rather than what is saved, so a correction can be validated before it is committed to `.env`. Saving rewrites `.env` in place — comments and unrelated keys are preserved, and a key already present is replaced rather than appended, so a file cannot end up with two values for one key and the winner decided by read order. Saving also drops the loader caches and disposes the connection pool, because both would otherwise hold the old mode until a restart.

**The password field is write-only.** The server never sends a stored password back, and an empty field means "keep the stored one" rather than "clear it", so the value is never rendered into the page. `config.safeSummary()` omits it by construction and is the only rendering of a connection the dashboard performs.

Logging is off by default, because recording every read costs time on each request. Enabled, it captures the actual data-source activity into a fixed-capacity ring buffer rather than a file: a demonstration machine's disk cannot be filled by leaving the dashboard open, and one long statement cannot dominate the buffer because each message is truncated.

### Links out of the app

The rail closes with **Docs** and **Repo**. A reader who arrives at the published dashboard has no other route to the specification or the source, so the app carries them. The documentation link is relative in the published build, where the documentation is a sibling directory, and absolute in a local run, where there is no sibling to point at.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `src/pages.js`, `src/App.vue`, and `src/main.js`

Source: `dashboard/src/main.js`, `dashboard/src/App.vue`, `dashboard/src/pages.js`

- Responsibility: Register the seven views, draw the shell around them, and dispatch to the selected one.
- Inputs: The location hash. Nothing else; each view reads the shared snapshot.
- Outputs: The rendered application. `PAGES` carries each view's title, breadcrumb, and inline icon; `PAGE_KEYS` is the one-column order; `REPO_URL` and `DOCS_URL` are where the app points a reader who wants the source or the specification.
- Behavior contract: `src/pages.js` is the single place a view is registered, and `tests/dashboard.test.js` asserts that `PAGES`, `PAGE_KEYS`, and `App.vue`'s component map agree. Data Generator follows Command Center. No group label or group container is rendered. Settings is a foot control rather than a page, and reload exists only inside its dialog. The page is written into the hash with `replaceState`, so a view is linkable and survives a refresh without filling the back stack. `App.vue` renders the loading, error, and loaded states itself rather than leaving each data-backed view to do it, and a `database_unavailable` error carries `SchemaRecovery.vue` beneath it so the state that stops every view also offers the way out of it. The report window and marketplace in the header are read from the selected schema's data rather than fixed in markup.
- Dependencies: Vue 3.
- Verification: `dashboard/tests/dashboard.test.js` for the registration contract; the rendered result is verified in a real browser for all seven views.

### `src/components/SettingsDialog.vue`

Source: `dashboard/src/components/SettingsDialog.vue`

- Responsibility: Own every control the rail's foot opens — the connection
  form, reload, runtime schema selection, schema setup, and logging — and own
  none of the decisions about whether they are permitted.
- Inputs: `GET /api/settings`, `GET /api/schema-operations`, and what the
  reader types. A stored password is never among them.
- Outputs: Settings, schema-selection, and schema-operation requests, and the
  rendered dialog.
- Behavior contract: **Protection and capability are separate branches.**
  Protected configuration replaces the credential form; it does not enclose
  schema setup, which renders as a sibling on every deployment with a backend.
  Nesting the two is what made setup unreachable on the protected deployment,
  and the test asserting that the `Schema setup` heading falls outside the
  editable branch exists to keep it from recurring. Whether the setup buttons
  are enabled is read from the server's `available` and `reason` fields rather
  than reconstructed, so the dialog and the route cannot disagree. The census
  is refreshed by reading settings on a protected server and by a connection
  test on an editable one, because the test action is itself refused when
  configuration is protected. The password field is write-only, and an empty
  one means keep the stored value.
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
  who wants the full dialog.
- Behavior contract: It renders only what the server offered, so it grants
  nothing: the chosen action is sent to the same schema-selection or
  schema-operation route the dialog uses and revalidated there against a fresh
  census. **It never sends `replace: true`.** Overwriting stays behind the
  settings checkbox that states what it destroys, because the reader here is
  the one least placed to judge what is about to be lost. A running operation
  is polled at 1200 ms against the same bounded log; on success the offer list
  is refreshed before the page reloads, so a stale option cannot be pressed
  twice.
- Dependencies: Vue 3 and `src/api/client.js`.
- Verification: `backend/tests/test_schema_recovery.py` for the offers it can
  receive, `dashboard/tests/dashboard.test.js` for its presence under the error
  card and the absence of the command it replaced.
