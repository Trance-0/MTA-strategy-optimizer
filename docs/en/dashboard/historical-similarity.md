---
title: Historical similarity reference
compact: "Specifies Campaigns historical checkbox filters, report-performance fallback, search, selection counts, draft application, strict identity grouping, display-only scoring, missing data, errors, and capped results; verified by dashboard/tests/historical-similarity-mvp.test.js."
---

# Historical similarity reference

The feature is intentionally a dashboard-only historical lookup. Its objects follow
`SimilarityReference`, and the selected set is never passed back into attribution,
response prediction, budget recommendation, outcome evaluation, or strategy
optimization. The view must not start or mutate a production run when the user
opens or filters this modal.

The MVP may directly implement the fields already present in the dashboard
research payload and in the history rows it already reads:

- Provider (`provider`)
- Product (`product_id`)
- Campaign (`campaign_id`)
- Ad product (`ad_product`)
- Marketplace (`marketplace`)
- Reporting window (`report_date`, filtered by start and end date)
- Data run (`run_id`, only when diagnostics are enabled)
- Budget level (`budget_level`)
- Configured budget (`configured_budget`)

The following fields are not stable enough to invent in this MVP and must remain
unimplemented unless the backend adds them to the shipped research resource:

- Advertiser ID (`advertiser_id`)
- Ad Group ID (`ad_group_id`)
- Creative ID (`creative_id`)
- Canonical normalized touchpoint (`normalizedTouchpoint`), unless the research
  transport already exposes its equivalent field under a stable name
- Interaction type (`interaction_type`), unless the dashboard has a merged row
  that carries it for the historical candidate set
- A synthetic `adProduct` expansion when the backend has not yet populated the
  field on the history row itself

The modal therefore treats the historical reference as a guarded browser-only
selector heuristic: it reads only what the dashboard already owns and is
explicitly forbidden from manufacturing missing fields.

The checkbox-style filter panel is an ordered group of filter sections, one per
field family. Each section contains a label, a list of checkboxes, and a row of
controls:

- Select all: marks every visible option in the current section as selected
- Clear: deselects every visible option in the current section
- Reset: restores the section to the default state for the current view
- Apply: closes the section's draft state and recomputes the candidate list

The selection state is draft-local until Apply is pressed. A user may iterate
several sections without re-running the query on every click; the final query runs
once and makes the section state visible in the table. If a filter group has no
available values in the current slice, its checkbox list remains empty and the
control still renders a clear explanation rather than a broken blank state.

Candidate grouping must be based on the true historical identity of the record, not
just the visible campaign or product label. The fixed grouping key is:

- `run_id`
- `campaign_id`
- `marketplace`
- `advertiser_id`
- `product_id`
- `budget_level`
- `report_date`

This key is the minimum safe set for the MVP. Each group represents one historical
record family and may contain multiple rows for a given campaign, but it can no
longer collapse different advertiser, marketplace, or budget-level histories into a
single bucket. When the backend does not populate one of those values for a row, the
row must be treated as a separate partial-history record and excluded from a strict
match rather than merged into a different subject.

The similarity score is computed only for the rows that survive the draft filter.
For each candidate row, the profile is built from the selected filters and from the
currently chosen subject campaign or product. Each selected component contributes
one of two values:

- String match: `1` when equal, `0` when different
- Budget gap score: `1 - abs(candidate_budget - profile_budget) / max(profile_budget, 1)`
  with the result clamped to `[0, 1]`

The dashboard then averages the scored components and stores that mean as the
`similarity_score` for the reference. A row is included only when the final score is
at least the currently selected threshold. The table sorts by descending
`similarity_score`, and rows with the same score remain in a deterministic order by
`comparable_id` and then by `historical_period`.

The modal exposes four UI states with explicit wording:

- Loading: “Loading historical references…” while the candidate slice is being
  filtered and grouped
- Empty: “No historical references meet this filter set.” when the score threshold
  or the selected filters remove every candidate
- Error: “Historical references are unavailable.” when the resource cannot be read or
  the payload is malformed
- Success: the filtered list of references sorted by score, with a short summary such
  as “Showing 20 of 143 matches.”

The dashboard must render the table with a fixed maximum result cap for the MVP,
for example 20 or 50 rows after sorting, so the browser remains bounded even when
reviewing a large research slice. The cap is a rendering guard only; it does not
change the backend data or the optimizer inputs.

Acceptance criteria for the MVP are:

- This modal uses only historical research rows and never writes to attribution,
  optimization, response, or strategy state.
- The candidate key includes `marketplace`, `advertiser_id`, and `budget_level`.
- The modal supports checkbox multi-select, select-all, clear, reset, and apply.
- A user can see a loading state, empty state, and error state without the view
  crashing or rendering a stale table.
- The final result is a presentation-only reference list sorted by similarity score.
- No missing field is fabricated by the client; if a required filter is absent from
  the resource, it remains unavailable and explicitly labelled as such.


## Selection and display details

Checkbox groups use OR within a group and AND across groups. An empty selection
means no restriction for that group. Defaults and Reset all clear all selections;
Reset all also clears the budget and subject and restores threshold 0.60.
Selected checkbox groups contribute one binary match component each. Campaign
profile values supply components only where the corresponding group is empty.
The result retains the ad-product field for filtering. Missing-field notices are
derived from the current payload. The displayed total counts all matching rows
before the 20-row cap. Equal scores sort by comparable identifier, period, and
strict historical identity. Invalid history payloads, including malformed report rows, produce an error state.

Verification: `cd dashboard && npm test` exercises the actual Campaigns script with
Vue reactive state and populated history fixtures, including draft/apply, reset,
OR/AND filtering, strict identities, result caps, missing fields, and invalid data.

## Searchable filter panel

Each filter group has a case-insensitive option search, a selected/total count,
and a bounded scrolling list. Search changes only option visibility, never the
applied results or existing selections. Select all selects visible search results
and preserves selections outside the search; Clear clears the entire group.
Reset clears both that group's selection and search. Reset all clears every
search. No search matches has a distinct message from missing source options.
A pending-changes status compares selected sets without depending on order;
Apply filters commits the draft. An empty group selection means no restriction.
The panel uses three columns on wide screens and one column on narrow screens.

## Report performance fallback

When budget history is empty, the Campaign History route loads `entity-bridge`
and offers historical ad performance from its report rows. Product uses `sku_id`,
ad product and interaction type use the first and fifth canonical touchpoint segments;
normalizedTouchpoint preserves that source key. Provider uses
the Campaign catalogue or the established Amazon ad-product vocabulary. Unknown
providers remain unavailable. Campaign options come from the report itself.
Each source row remains a distinct candidate, retaining its full start/end period,
marketplace, advertiser, Campaign, product and touchpoint scope. No daily budget
record or simulator run identifier is fabricated. Spend uses `cost`; revenue uses
`reported_sales`, never assisted revenue. Budget and profit remain unavailable.
Budget input is disabled for report performance. No selected scoring components
means an unscored browse result; a supplied Campaign or checkbox profile enables
selector scoring and the threshold. Existing strict budget grouping is unchanged.
The fallback table clearly identifies the report source and period granularity.
