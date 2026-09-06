---
title: "Key-Term Help"
compact: "Accessible term help, registry lookup and definition links for dashboard labels."
source_files: dashboard/src/components/TermHelp.vue, dashboard/src/lib/terms.js
---

# Key-Term Help

`TermHelp.vue` adds an accessible help button after declared key terms in metric
labels, key/value labels, and table headers. Hover, focus, or activation reveals
a short definition. When the term needs more context, the popover links to the
specific English definition or owning specification page; a generic Docs link
is not substituted for a precise reference.

`src/lib/terms.js` is the only term registry. Each entry contains a normalized
label, plain-language definition, and optional documentation path. The initial
registry covers Return on Ad Spend (ROAS), Click-Through Rate (CTR), Cost Per
Click (CPC), Cost Per Mille (CPM), attribution, touchpoint, reliability,
configured budget, actual spend, contribution profit, conversion path,
database schema, and ground truth. The visible label remains in the page, so a
tooltip is never the only source of a value or column name.

The button uses `aria-describedby`; the popover opens on keyboard focus as well
as pointer hover; Escape and focus departure close it. Documentation links open
normally and remain keyboard reachable. Tests assert every registered path is
an English documentation path.

Optimization Log's fifth stage now reports the [Campaign budget optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md) from its artifact rather than from a constant. When `outputs/campaign_strategy.json` is absent — the state of any checkout that has not run the research command — the stage reads `NOT RUN` and the initializer's seed remains the current recommendation. When the artifact is present the view shows the optimized allocation beside its evidence, and when the optimizer refused it shows the refusal and its reasons instead of an allocation. Every Campaign optimized outside the budget range its fit observed, and every Campaign whose curve was pooled from comparable Campaigns rather than its own history, is named rather than left implicit in a number.

## Source Files

### `TermHelp.vue`, `terms.js`

Source: `dashboard/src/components/TermHelp.vue`, `dashboard/src/lib/terms.js`

- Responsibility: Implement the reader-facing contract on this page.
- Inputs and outputs: termFor(label) returns a registry term or no match; TERM_HELP supplies title, definition and English documentation link. TermHelp takes a term and exposes accessible help without issuing requests.
- Dependencies: Vue and the shared client; Plotly for charts, browser cryptography for fixture verification.
- Verification: `npm --prefix dashboard test`; production build and browser navigation.
