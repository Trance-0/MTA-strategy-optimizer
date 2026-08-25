---
title: Navigation Rail and Settings
compact: "Navigation and settings contract: grouped hash routing, PostgreSQL controls, read-only deployments, write-only passwords, and bounded logging. Vue files own navigation; `dashboard/server/settings.js` remains a JavaScript parity fixture while Flask owns runtime settings."
lang: en-US
source_files: dashboard/src/pages.js, dashboard/src/App.vue, dashboard/src/main.js, dashboard/server/settings.js
---

# Navigation Rail and Settings

The rail is the shell around the six views listed on [Dashboard](./index.md#the-six-views). This page specifies the rail itself and the settings module pinned to its foot.

## Navigation Rail <span class="status-label status-verified" aria-label="Verified"></span>

The sidebar reproduces the prototype's rail: a navy column of stacked icon buttons, grouped under OVERVIEW, PLANNING, and INSIGHTS, with the active item filled.

`src/pages.js` is the single place a view is registered. A page key appears there, in `PAGE_GROUPS`, and in `App.vue`'s component map; `tests/dashboard.test.js` asserts the three agree, so the rail cannot offer a destination the shell cannot render.

The rail writes the selected page into the location hash, so a view is linkable and survives a refresh. It is written with `replaceState` rather than assignment, so switching views does not fill the browser's back stack with intermediate pages.

### The settings module

Everything about the dashboard's own plumbing is pinned to the foot of the rail, ruled off from the view navigation above it, so it never reads as a seventh place to navigate to. It shows the active source, a status dot, and whether logging is on, and opens a modal with two tabs:

When `DASHBOARD_CONFIG_READ_ONLY=true`, the server continues to report its configured source but rejects every settings mutation. The modal replaces its connection form with the server-configuration instruction and disables logging controls, so a team-server visitor cannot rewrite protected credentials or process state through the browser.

#### Data source

Contains the `DATABASE` toggle and the PostgreSQL host, port, database, user, password, and Secure Sockets Layer (SSL) mode, with **Test connection** and **Save to `.env`**.

#### Logging

Contains the streaming-data log switch, its level, and the captured records.

**Test connection** opens a throwaway connection using what was typed rather than what is saved, so a correction can be validated before it is committed to `.env`. Saving rewrites `.env` in place — comments and unrelated keys are preserved, and a key already present is replaced rather than appended, so a file cannot end up with two values for one key and the winner decided by read order. Saving also drops the loader caches and disposes the connection pool, because both would otherwise hold the old mode until a restart.

**The password field is write-only.** The server never sends a stored password back, and an empty field means "keep the stored one" rather than "clear it", so the value is never rendered into the page. `config.safeSummary()` omits it by construction and is the only rendering of a connection the dashboard performs.

Logging is off by default, because recording every read costs time on each request. Enabled, it captures the actual data-source activity into a fixed-capacity ring buffer rather than a file: a demonstration machine's disk cannot be filled by leaving the dashboard open, and one long statement cannot dominate the buffer because each message is truncated.

### Links out of the app

The rail closes with **Docs** and **Repo**. A reader who arrives at the published dashboard has no other route to the specification or the source, so the app carries them. The documentation link is relative in the published build, where the documentation is a sibling directory, and absolute in a local run, where there is no sibling to point at.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### Legacy parity harness: `server/settings.js`

Source: `dashboard/server/settings.js`

- Responsibility: Preserve the former Node settings behavior for the
  JavaScript regression suite. Runtime requests use the Flask settings service
  specified in [Backend Jobs and Settings](/en/introduction/backend/operations).
- Inputs: `.env` at the repository root, the live environment as a fallback, and the reader's entries in the modal.
- Outputs: `readEnv()`, `writeEnv()`, `status()`, `testConnection()`, `applyLogging()`, `loggingEnabled()`, `logState()`, `log()`, `clearLog()`, `settingsState()`, and `RingBuffer`.
- Behavior contract: **No credential is written to a tracked file, to the API response, or to the log.** `.env` is git-ignored, `sample.env` is the tracked template and holds no real value, and the password is rendered only through `config.safeSummary()`, which omits it by construction. `settingsState()` carries the read-only flag that lets the modal distinguish a protected server from an editable checkout. `writeEnv()` rewrites the file rather than appending to it, preserving comments and unrelated keys and replacing a key in place, so one key cannot end up with two values and the winner decided by read order; it does not accumulate a trailing blank line on repeated saves; and it then clears the loader caches and disposes the pool, because both would otherwise survive the edit. `testConnection()` connects with the values just typed rather than the values saved, and closes the client whether or not the probe succeeded, so a failed test cannot leave a socket open on a shared instance. The log is a fixed-capacity ring buffer, not a file, so an open dashboard cannot fill a disk; each message is truncated so one record cannot dominate it; and a record below the active level is dropped rather than stored and filtered on display. Logging is off by default because it costs time on every request.
- Dependencies: `pg` for the connection test, plus `server/config.js` and `server/data_source.js`.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts `writeEnv()` preserves comments and unrelated keys, appends a missing key exactly once, does not grow a blank line on repeated saves, and writes every key the dialog sends; and that the buffer stays bounded, starts disabled, honours its level, and truncates. The tests redirect the path to a temporary file, so the real `.env` is never touched.

### `src/pages.js`, `src/App.vue`, and `src/main.js`

Source: `dashboard/src/main.js`, `dashboard/src/App.vue`, `dashboard/src/pages.js`

- Responsibility: Register the six views, draw the shell around them, and dispatch to the selected one.
- Inputs: The location hash. Nothing else; each view reads the shared snapshot.
- Outputs: The rendered application. `PAGES` carries each view's title, breadcrumb, and inline icon; `PAGE_GROUPS` is the rail's grouping; `PAGE_KEYS` its flattening; `REPO_URL` and `DOCS_URL` are where the app points a reader who wants the source or the specification.
- Behavior contract: `src/pages.js` is the single place a view is registered, and `tests/dashboard.test.js` asserts that `PAGES`, `PAGE_GROUPS`, and `App.vue`'s component map agree, so the rail cannot offer a destination the shell cannot render. The two foot controls are drawn from the same icon set but are **not** navigable pages, and the test asserts that too. The page is written into the hash with `replaceState`, so a view is linkable and survives a refresh without filling the back stack. `App.vue` renders the loading, error, and loaded states itself rather than leaving each view to do it, so a failed load is one page naming both remedies rather than six broken charts. The report window and marketplace in the header are read from the data rather than fixed in the markup.
- Dependencies: Vue 3.
- Verification: `dashboard/tests/dashboard.test.js` for the registration contract; the rendered result was verified in a real browser for all six views.
