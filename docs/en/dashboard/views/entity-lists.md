---
title: "Canonical Entities Are Lists, Not Prose"
compact: "EntityTable paging, identity-keyed selection, draft editing and named archive confirmation."
source_files: dashboard/src/components/SidebarNav.vue, dashboard/src/components/TopBar.vue, dashboard/src/components/DataTable.vue, dashboard/src/components/EntityTable.vue, dashboard/src/components/ConfirmDialog.vue, dashboard/src/components/TableView.vue, dashboard/src/components/MetricRow.vue, dashboard/src/components/KeyValuePanel.vue, dashboard/src/components/ReliabilityBanner.vue
---

# Canonical Entities Are Lists, Not Prose

Budget Manager's seven entity sections each render as one paged table, in the manner of a 1Panel resource list. A row is an **abstract** — a handful of declared summary columns — and the whole record sits behind that row's own Edit control.

This replaces a detail list that rendered every field of every record as stacked paragraphs. That layout put hundreds of lines of prose on one page, offered no way to scan a column or compare two records, and grew without bound with the data behind it.

`EntityTable.vue` owns paging, page size, selection, and the two row controls; it does not own what a row means. Columns are declared by the view exactly as `DataTable`'s are, so a new field in the snapshot cannot silently widen a table.

### Paging and page size

Ten rows per page by default, with 10, 15, 30, 50, and 100 offered. A section therefore opens at one screen rather than at a hundred rows. A free-text filter narrows across the rendered text of the declared columns, so what a reader searches is what a reader sees, and the page is clamped rather than reset when the filter narrows.

### Selection survives paging

Selection is keyed by a caller-supplied row identity, not by page index. Keyed by index, a batch action would act on whatever record happened to sit at that index after the page turned. The header checkbox acts on the current page, which is what it can show, and the count of everything selected is stated beside it.

### Deletion always asks, and names what it will remove

Every deletion — one row or a batch — routes through one confirmation that lists the affected identifiers rather than reporting a count alone. A count is not something a reader can check, and a batch selected across several pages is exactly the case where a reader cannot see what they picked. The list is capped at twelve with the remainder stated, so a large selection cannot produce an unreadable dialog.

A batch archives sequentially rather than concurrently, because each archive clears the server's caches and a parallel batch would have them racing. **A failure stops the run and reports which identifier it stopped at**, leaving the dialog open: reporting success after a partial batch would be a false statement about what is now in the database.

Deletion archives a planned change. It never removes reported performance, which no route mutates in either mode.

### Every deployment populates its entity sections

These records were previously read only from an optional research sidecar, so every default and published deployment showed all seven sections empty. `backend/repository/master_data.py` now derives the catalogue — Ad Providers, Products, Campaigns, Ad Groups, touchpoints, product economics, and Campaign-Product links — from the Amazon Ads report, entity bridge, and strategy request the repository already tracks. A sidecar, when one is configured, still takes precedence.

Derivation rather than a second committed catalogue file: a tracked catalogue sitting beside the reports can drift from them, while one read out of them cannot.

**Only what the reports support is reported.** A touchpoint's impressions and clicks arrive as separate per-interaction rows sharing no denominator, so `click_through_rate` is `null` and the observed impressions, clicks, and cost are reported instead — dividing one by the other yielded rates between 0.98 and 1.15. A rate is reported only where both its cost and its denominator are above zero, so a touchpoint whose impression rows carry no cost shows no CPM rather than a CPM of exactly zero. Unit COGS and contribution margin stay `null` rather than becoming zero, since no committed report carries them. Four touchpoints bill CPC on clicks and CPM on impressions at once; cost is accumulated per billing type and the billing type reported as `CPC + CPM`.

A section that is genuinely empty still names its cause — no records in the current reporting window — because "No records loaded" alone reads as a broken deployment.

### The dashboard describes market performance

No view names a data generator, a simulator, or synthesis. A reader of this dashboard is reading reported performance from the platform, and the interface says so throughout: reported performance is read-only, an editable row is a planned change, and a filter that answers which pipeline run wrote a row is diagnostic detail rather than something a marketing reader is shown by default.

Pipeline-run detail therefore sits behind one preference, `Show data run diagnostics` in Settings, persisted in `localStorage` and off by default. It gates Budget Manager's data-run section and the Campaigns data-run filter. `tests/dashboard.test.js` asserts no dashboard source presents its data as generated or simulated.

## Source Files

### The shared components

Source: `dashboard/src/components/SidebarNav.vue`, `dashboard/src/components/TopBar.vue`, `dashboard/src/components/DataTable.vue`, `dashboard/src/components/EntityTable.vue`, `dashboard/src/components/ConfirmDialog.vue`, `dashboard/src/components/TableView.vue`, `dashboard/src/components/MetricRow.vue`, `dashboard/src/components/KeyValuePanel.vue`, `dashboard/src/components/ReliabilityBanner.vue`

- Responsibility: Hold the chrome and the repeated display shapes, so two views cannot render the same thing differently.
- Inputs: Props from the view that mounts them.
- Outputs: The rendered fragment, plus events for the rail's navigation, reload, and settings actions.
- Behavior contract: `SidebarNav.vue` draws the flat eight-page rail from `src/pages.js`, including Settings as its final destination, and keeps source status and external links in the foot. It renders no section label, group container, disclosure, reload button, or separate Settings foot button. Below `1024px` the same order becomes a horizontally scrollable bar. `Settings.vue` owns reload and confirmed runtime schema switching; it never renders a stored password or sends one back. In the published build it replaces backend operations with local-run instructions, while a protected team-server deployment keeps credential mutation unavailable. `SchemaRecovery.vue` replaces terminal-only advice on a database load error with backend-declared select, derive, or initialize buttons; it never offers replacement and polls the existing bounded operation log. `TermHelp.vue` and `src/lib/terms.js` provide keyboard-accessible definitions and precise English documentation links without hiding the original labels. `PlotlyChart.vue` is the only component that touches Plotly, so chart defaults in `src/theme.js` cannot be bypassed, and it disposes the plot on unmount. `TableView.vue` keeps every chart paired with readable values. `ReliabilityBanner.vue` always renders the status word beside its colour. `TopBar.vue` leads its tag row with the deployment.

`EntityTable.vue` owns paging, page size, free-text filtering, selection, and the two row controls, and owns nothing about what a row means: columns are declared by the mounting view exactly as `DataTable`'s are. Its default page size is 10, offering 10, 15, 30, 50, and 100. **Selection is keyed by a caller-supplied row identity rather than by page index**, so a batch action cannot act on whatever record happens to occupy that index after the page turns; the selection Set is reassigned rather than mutated, because a Set mutated in place is the same object and Vue's reactivity would not repaint the checkboxes. The header checkbox acts on the current page, which is what it can show. Both components read `renderCell` from `src/lib/common.js`, so one column declaration cannot mean two things in two tables.

Every declared column header in `DataTable.vue` and `EntityTable.vue` is a
keyboard-accessible sort control. Repeated activation cycles ascending,
descending, and unsorted; unsorted restores the rows' exact backend order.
Only the active header shows an upward or downward arrow, while `aria-sort`
exposes the same state without relying on the icon. Entity sorting applies
after filtering and before paging, and changing direction returns to page one.

`ConfirmDialog.vue` is the only route to a deletion. It **names the affected identifiers rather than reporting a count alone**, because a count is not something a reader can check and a batch selected across several pages is exactly the case where a reader cannot see their own selection. The list is capped at twelve with the remainder stated rather than dropped, and the dialog stays open on failure carrying the reason.

`Settings.vue` separates active selection from setup. Its **Dashboard
schema** field is a dropdown over the census returned by `/api/settings` and
refreshed by a connection test, described in [Backend Jobs and
Settings](/en/introduction/backend/operations.md#schema-selection). **A schema
that cannot serve the dashboard is listed and disabled rather than omitted**:
omitting it would leave a reader who knows the schema exists with no account
of its absence, while disabling it puts the reason at the moment they would
have chosen it. Each option carries the server's own `detail` as its `title`,
and the same explanation — the reason and tables the schema lacks — is
rendered as help text under the field. The stored selection stays in the list
when the census is empty, so an unreachable database cannot make the page
display a schema the reader never chose and then save it.

A protected team-server deployment does not hide that census. It renders a
separate **Database schemas** dropdown whose choices name the active schema,
capability kind, and database structure version. Choosing another
dashboard-ready schema opens the same confirmation window as the editable
selector and reloads actual data without rewriting `PG_SCHEMA` in deployment
configuration. Until a migration ledger exists, the version is displayed as
**not tracked**.

The **Schema setup** menu lists every censused schema, including disabled
active-schema choices, and labels its detected kind and available action.
Simulator sources expose **Parse all scenarios**; empty schemas expose
**Initialize sample model**; a valid new name can initialize a new schema.
Replacement is an explicit checkbox followed by browser confirmation. While
an operation runs, the page polls `/api/schema-operations` and shows its
status, exact command, bounded timestamped output, dropped-line count, and stop
control. Success refreshes the census so new targets immediately appear in the
Dashboard schema selector.

**Setup is a sibling of the protected connection form, not a child of it.**
It renders on every deployment with a backend, because writing tables into the
database the platform already named is not the same act as rewriting the
credential that names it; nesting it inside the editable-configuration branch
is what previously made it unreachable on exactly the deployment whose readers
have no other way to prepare a schema. Whether the buttons are enabled comes
from the `available` and `reason` fields the server returns beside the
operation record, so the page cannot offer an action the route would refuse,
and a withheld one is explained rather than silently absent. Each option's
summary is the census `remedy`, written for a reader; the `detail` command
stays in the dropdown's `title` for an operator.

Settings begins with a **Deployment identity** block. It renders the dashboard
bundle's project version and full commit
[Secure Hash Algorithm (SHA)](/en/reference/definitions#secure-hash-algorithm-sha-commit-identifier),
followed by the backend's independently detected project version and commit SHA and its
Python and Flask runtime versions. The status is **Builds match** only when both
project versions and both commit values are present and equal. Any unequal
value is **Build mismatch**; a missing or `unknown` value is **Identity
incomplete**. The values are selectable monospace text so an operator can copy
them into a deployment report. A static build states that no backend is
connected rather than comparing the dashboard against itself.
