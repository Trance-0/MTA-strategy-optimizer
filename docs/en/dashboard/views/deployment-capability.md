---
title: "Deployment Capability Governs the Interface"
compact: "deployment.js separates snapshot-based editing permission from Settings-backed deployment identity, preserving database accents on refresh and reload; pending, file, database and static states govern labels and remedies. diagnostics.js owns browser diagnostic visibility."
source_files: dashboard/src/lib/deployment.js, dashboard/src/lib/diagnostics.js
---

# Deployment Capability Governs the Interface

The dashboard ships in three deployments and only one of them can change data. Which one a reader is looking at governs how every number on the page may be used, so it is carried by the whole interface rather than by one badge in a corner.

**Capability is derived from the snapshot's own `mode`, never from the build flag.** A local run reading the committed files is read-only for exactly the same reason the published build is: there is no database behind it to write to. Deriving the answer from `VITE_STATIC_BUILD` would wrongly offer editing controls to that local run. `src/lib/deployment.js` is the single place the question is asked, and `writable` is true only when the server reports `mode === "database"`.

### The two accents

A deployment reading committed files wears Microsoft Excel's own green, `#217346`, which is the association a reader already has for a spreadsheet: this is a table of committed values. A deployment configured for PostgreSQL keeps the reference prototype's brand blue, including while its data is loading or unavailable. Both sets live in `theme.js` beside every other colour, and `App.vue` applies the selected one by overriding the custom properties `style.css` already reads — so one override repaints the rail, the tabs, the primary buttons, and the selection highlight, and no component needs a deployment variant class.

Settings declares no dashboard resources. On a direct Settings visit or browser refresh, the shell uses the successful `/api/settings` response's boolean `useDatabase` to identify the deployment without requesting dashboard data. A loaded snapshot's `mode` takes precedence; while Reload clears that snapshot, the retained Settings response preserves the accent. Configuration alone never enables editing. A configured database is labelled **Database configured** until a database snapshot loads, then **Database connected**. Local files and the published build remain green and read-only.

Before either response identifies a live deployment, the shell keeps the base blue palette with **Checking data source** and a neutral header badge; an empty store or failed request must not imply Local files. A static build is already known to read files. Failed Settings requests retain the last successful identity, and failed dashboard requests do not change a known database into a file deployment. The header badge follows deployment identity independently of editing permission, and its tooltip distinguishes configured database data that has not loaded from confirmed file data.

**The chart series palette is deliberately excluded.** A series colour follows its entity, so the same Campaign must keep its colour across both deployments; a reader comparing the published site with a local run would otherwise see one Campaign in two colours. `tests/dashboard.test.js` asserts the deployment accents and the categorical palette never intersect.

### Read-only is stated, not merely enforced

A read-only deployment renders a notice above every data view naming why it is read-only and the remedy that applies to it: the published build points at running the dashboard locally, and a local file-mode run points at `DATABASE=true` and the Settings page. The two are named apart rather than collapsed into one label, because a reader can act on one and not the other.

Hiding the controls alone would not be enough. A reader should learn that editing is unavailable from the page, not by hunting for a button that is not there. The server enforces the same rule independently: `PUT` and `DELETE /api/master/…` are refused outside database mode regardless of what the client rendered.

## Source Files

### `src/lib/deployment.js`

Source: `dashboard/src/lib/deployment.js`

- Responsibility: Answer which deployment this is, and therefore whether data operations are available and which accent the interface wears.
- Inputs: The shared snapshot's `mode`, through `useDashboard()`; an optional reactive Settings response supplied by the shell; and the lazily read static-build flag.
- Outputs: `THEMES`, re-exported from `theme.js`; and `useDeployment(settings = null)` returning computed `mode`, `writable`, `theme`, `label`, `readOnlyReason`, plus the boolean `isStatic`.
- Behavior contract: **`writable` is derived only from the snapshot's `mode === "database"`**, never from Settings or the build flag. Display `mode` uses a nonempty snapshot mode first, then an explicit Settings boolean (`true` means `database`, `false` means `local files`), then `local files` for a static build, otherwise the empty pending state. Only confirmed `local files` selects the green theme; database and pending states use the base blue theme. Labels and loading behavior follow the accent contract above. Pending and configured-but-unloaded states explain that the reader must check Settings or reload before editing; they never suggest a database is reading committed files. Computed refs react to Settings arrival, snapshot arrival, and snapshot invalidation without remounting. The accent sets are re-exported, and the build flag is read through a function so the capability module remains testable outside Vite.
- Dependencies: Vue's reactivity, `src/theme.js`, and `src/lib/useDashboard.js`.
- Verification: `dashboard/tests/dashboard.test.js` exercises pending Settings, database/file responses, snapshot precedence, clearing for reload, and static builds without granting writes from configuration; it also checks palette separation, read-only remedies, and header wiring.


### `src/lib/diagnostics.js`

Source: `dashboard/src/lib/diagnostics.js`

- Responsibility: Answer whether the surfaces that describe the pipeline rather than the account are shown.
- Inputs: `localStorage`, read once at module load under the key `mta-dashboard.diagnostics`.
- Outputs: `useDiagnostics()` returning the computed `diagnosticsOn` and `setDiagnostics(on)`.
- Behavior contract: **Off by default.** The dashboard's subject is an advertising account; a surface naming which run wrote a number, under which configuration and seed, answers an engineering question, and a reader planning budget should not have to walk past it. The surfaces are gated rather than deleted, because the question is real when a number looks wrong and removing them would mean reaching for a database client instead. The preference is per-browser rather than server-side: it is a property of who is looking, not of the deployment, and two people reading one hosted dashboard can want different answers. Every `localStorage` access is wrapped and falls back to off, because the Node test runner and a privacy-restricted browser have none, and an unguarded read would throw at import time rather than at use.
- Dependencies: Vue's reactivity.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts the stored value must read exactly `"true"` to enable, that the guard falls back to off, that Budget Manager's diagnostic section exists only while the preference is on, and that the Settings page is what sets it.
