---
title: Master Object Editor
compact: "MasterObjectForm.vue and masterObjectFields.js specify editable future-run drafts, typed blank values, suggested provider vocabularies, preserved unknown fields, isolated templates, and the seven SECTION_FIELDS form schemas."
source_files: dashboard/src/components/MasterObjectForm.vue, dashboard/src/lib/masterObjectFields.js
test_files: dashboard/tests/master_editor.test.js
---

# Master Object Editor

Budget Manager edits future-run master drafts through the backend master routes.
It never rewrites observed spend, delivery, paths, or outcomes. The Form and
[JavaScript Object Notation (JSON)](/en/definitions#json-javascript-object-notation)
editors represent the same draft. Unknown fields survive a form edit because
each field update copies the full record before replacing that field.

## Field behavior

Text stays text, including an empty string. Blank numbers and the Unknown
boolean option become `null`; numeric zero and `false` retain their meaning.
Number controls accept decimal input. A suggested vocabulary uses a searchable
text input with a datalist and allows values outside its suggestions. The server
owns validation. Multiselect additions trim surrounding whitespace, ignore blank
and duplicate values, and append in selection order; removal removes the named
value. Required markers communicate intended completeness, not server acceptance.

`SECTION_FIELDS` maps the seven section keys below to ordered field descriptors:
`key`, `label`, `kind`, `default`, optional `required`, `options`, `optionsFor`,
`trueLabel`, and `falseLabel`. Kinds are `text`, `number`, `boolean`, `select`,
and `multiselect`. `buildTemplate(sectionKey)` returns every declared key in that
order; an unknown section returns `{}`. Each template owns fresh list defaults.

## Section fields and defaults

#### Providers

`provider` defaults to `AMAZON_ADS`; `supported_ad_products` to an empty list;
`format_availability`, `placement_availability`, `creative_availability`, and
`interaction_type_availability` to `AVAILABLE`; `active` to true.

#### Products

`product_id`, `name`, `sku_id`, `category`, `brand`, and `status` default to empty
text. `inventory_units` and `salable` default to null. The stock identifier
`sku_id` names the [Stock Keeping Unit](/en/reference/definitions#sku-stock-keeping-unit).

#### Campaigns

`campaign_id`, `campaign_name`, `ad_product`, and `status` default to empty text;
`provider` to `AMAZON_ADS`; `baseline_daily_budget` to null.

#### Ad Groups

`ad_group_id`, `campaign_id`, `allocation_basis`, and `status` default to empty
text. `budget_seed_share` and `initial_daily_budget` default to null.

#### Touchpoints

`identifier`, `ad_product`, `format`, `placement`, and `creative` default to empty
text; `provider` to `AMAZON_ADS`; the three placement, creative, and interaction
availability fields to `AVAILABLE`; `supported_interactions` to an empty list;
`billing_type` to `CPC` ([Cost Per Click](/en/reference/definitions#cpc-cost-per-click));
`cost_per_click`, `cost_per_thousand_impressions`, and `click_through_rate` to
null; `active` to true.

#### Product economics

`product_id` defaults to empty text and `currency` to `USD` (United States Dollar).
`unit_price`, `unit_cogs`, `variable_cost_per_unit`,
`variable_fulfillment_cost_per_unit`, `variable_platform_fee_per_unit`,
`other_variable_cost_per_unit`, `unit_contribution_margin`, and `margin_source`
default to null. `unit_cogs` means unit Cost of Goods Sold. Missing costs never
become measured zero or a fabricated margin.

#### Generation configurations

`run_id` and `configuration_sha256` default to empty text; `seed` to null.
This diagnostic section remains gated by the existing browser preference.
The configuration field is a [Secure Hash Algorithm](/en/reference/definitions#secure-hash-algorithm-sha-commit-identifier)
digest, not a value computed by this editor.

## Source Files

### `masterObjectFields.js`

Source: `dashboard/src/lib/masterObjectFields.js`

- Responsibility: Declare ordered form fields and reusable draft templates.
- Inputs: Section key; provider for provider-dependent product suggestions.
- Outputs: `SECTION_FIELDS`, option constants, and `buildTemplate(sectionKey)`.
- Dependencies: Canonical provider and availability vocabularies described in
  [Data models](/en/introduction/data-models/); no runtime backend import.
- Verification: `dashboard/tests/master_editor.test.js` and the production build.

### `MasterObjectForm.vue`

Source: `dashboard/src/components/MasterObjectForm.vue`

- Responsibility: Render one typed input per declared field.
- Inputs: Required `sectionKey: string` and `modelValue: object` props.
- Outputs: `update:modelValue` with a new full record; never mutates the prop.
- Behavior contract: Each field is an option row as specified in
  [Visual Contract](/en/dashboard/views/visual-contract#option-rows) — the field
  name and its required marker on the left, the input on the right — rather than
  a form layout private to this component. A section taller than the dialog
  scrolls inside the group.
- Dependencies: Vue and `SECTION_FIELDS`; no request or storage access.
- Verification: Production build and browser form interaction; template tests
  verify defaults and vocabulary selection separately.

## Verification

- **Scope:** Draft template identity, missing-value semantics, and field registry.
- **Cases:** Seven known sections, unknown section, independent list defaults,
  zero versus missing numeric values, and provider-specific suggestions.
- **Command:** `npm --prefix dashboard test` and `npm --prefix dashboard run build`.
- **Limitations:** The Node tests exercise the field schema, not browser inputs;
  backend authorization remains covered by the master-route tests.
