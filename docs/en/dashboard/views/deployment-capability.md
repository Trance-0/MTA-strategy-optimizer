---
title: "Deployment Capability Governs the Interface"
compact: "Database mode controls editing, deployment accents and read-only remedies in dashboard views."
source_files: dashboard/src/lib/deployment.js, dashboard/src/lib/diagnostics.js
---

# Deployment Capability Governs the Interface

The dashboard ships in three deployments and only one of them can change data. Which one a reader is looking at governs how every number on the page may be used, so it is carried by the whole interface rather than by one badge in a corner.

**Capability is derived from the snapshot's own `mode`, never from the build flag.** A local run reading the committed files is read-only for exactly the same reason the published build is: there is no database behind it to write to. Deriving the answer from `VITE_STATIC_BUILD` would wrongly offer editing controls to that local run. `src/lib/deployment.js` is the single place the question is asked, and `writable` is true only when the server reports `mode === "database"`.

### The two accents

A deployment that cannot write wears Microsoft Excel's own green, `#217346`, which is the association a reader already has for a spreadsheet: this is a table of committed values. A deployment connected to PostgreSQL keeps the reference prototype's brand blue. Both sets live in `theme.js` beside every other colour, and `App.vue` applies the selected one by overriding the custom properties `style.css` already reads — so one override repaints the rail, the tabs, the primary buttons, and the selection highlight, and no component needs a deployment variant class.

**The chart series palette is deliberately excluded.** A series colour follows its entity, so the same Campaign must keep its colour across both deployments; a reader comparing the published site with a local run would otherwise see one Campaign in two colours. `tests/dashboard.test.js` asserts the deployment accents and the categorical palette never intersect.

### Read-only is stated, not merely enforced

A read-only deployment renders a notice above every data view naming why it is read-only and the remedy that applies to it: the published build points at running the dashboard locally, and a local file-mode run points at `DATABASE=true` and the Settings page. The two are named apart rather than collapsed into one label, because a reader can act on one and not the other.

Hiding the controls alone would not be enough. A reader should learn that editing is unavailable from the page, not by hunting for a button that is not there. The server enforces the same rule independently: `PUT` and `DELETE /api/master/…` are refused outside database mode regardless of what the client rendered.

## Source Files

### `src/lib/deployment.js`

Source: `dashboard/src/lib/deployment.js`

- Responsibility: Answer which deployment this is, and therefore whether data operations are available and which accent the interface wears.
- Inputs: The shared snapshot's `mode`, through `useDashboard()`. The build flag, read lazily, for naming only.
- Outputs: `THEMES`, re-exported from `theme.js`; and `useDeployment()` returning the computed `writable`, `theme`, `label`, `readOnlyReason`, and `isStatic`.
- Behavior contract: **`writable` is derived from `mode === "database"` and never from the build flag**, because a local file-mode run is read-only for the same reason the published build is. The build flag decides only how a read-only deployment names itself — "Published build" against "Local files" — and which remedy it offers, since a reader can act on one and not the other. Every value is returned as a computed ref rather than a plain value: the mode is unknown until the first snapshot resolves, so a component reading a plain boolean at setup time would fix itself to the pre-load default and never correct. The accent sets are re-exported rather than declared, because a colour declared twice is free to disagree with itself. The build flag is read through a function rather than imported from `src/api/client.js`, because `import.meta.env` exists only under Vite and importing that module would make this file unloadable in the Node test runner — which is where the capability contract is asserted.
- Dependencies: Vue's reactivity, `src/theme.js`, and `src/lib/useDashboard.js`.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts capability follows the snapshot mode rather than the build flag, that the two accents differ, that neither leaks into the chart palette, that both read-only deployments name a remedy, and that the rail's status dot matches the read-only accent.


### `src/lib/diagnostics.js`

Source: `dashboard/src/lib/diagnostics.js`

- Responsibility: Answer whether the surfaces that describe the pipeline rather than the account are shown.
- Inputs: `localStorage`, read once at module load under the key `mta-dashboard.diagnostics`.
- Outputs: `useDiagnostics()` returning the computed `diagnosticsOn` and `setDiagnostics(on)`.
- Behavior contract: **Off by default.** The dashboard's subject is an advertising account; a surface naming which run wrote a number, under which configuration and seed, answers an engineering question, and a reader planning budget should not have to walk past it. The surfaces are gated rather than deleted, because the question is real when a number looks wrong and removing them would mean reaching for a database client instead. The preference is per-browser rather than server-side: it is a property of who is looking, not of the deployment, and two people reading one hosted dashboard can want different answers. Every `localStorage` access is wrapped and falls back to off, because the Node test runner and a privacy-restricted browser have none, and an unguarded read would throw at import time rather than at use.
- Dependencies: Vue's reactivity.
- Verification: `dashboard/tests/dashboard.test.js`, which asserts the stored value must read exactly `"true"` to enable, that the guard falls back to off, that Budget Manager's diagnostic section exists only while the preference is on, and that the Settings page is what sets it.
