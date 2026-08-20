/**
 * Field schema for the master-object Form editor and the JSON template.
 *
 * Sourced from the canonical vocabularies in
 * `modules/mta_common/src/enums.py` and `provider_capabilities.py`
 * (`Provider`, `FieldAvailability`, `MarginSource`, and the per-provider
 * `supported_ad_products`), plus the dashboard's own touchpoint shape in
 * `dashboard/server/data_source.js` (`billing_type`, `supported_interactions`).
 * Fields with no closed vocabulary in the data model (`status`, `category`,
 * `currency`, `format`, `placement`, `creative`, ...) get a plain text input;
 * a `select` field's options are suggestions, not a hard restriction, since
 * the server stores the payload as free-form JSON.
 */
export const PROVIDER_OPTIONS = ["AMAZON_ADS", "GENERIC"];

export const AD_PRODUCTS_BY_PROVIDER = {
  AMAZON_ADS: [
    "SPONSORED_PRODUCTS",
    "SPONSORED_BRANDS",
    "SPONSORED_DISPLAY",
    "AMAZON_DSP",
  ],
  GENERIC: ["DISPLAY", "SEARCH"],
};

export const FIELD_AVAILABILITY_OPTIONS = [
  "AVAILABLE",
  "NOT_APPLICABLE",
  "NOT_PROVIDED",
  "UNKNOWN",
  "REDACTED",
];

export const MARGIN_SOURCE_OPTIONS = ["EXPLICIT", "DERIVED"];

export const BILLING_TYPE_OPTIONS = ["CPC", "CPM"];

export const INTERACTION_OPTIONS = ["IMPRESSION", "CLICK"];

export const CURRENCY_OPTIONS = [
  "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CNY", "INR", "MXN", "BRL",
];

function adProductOptions(record) {
  return AD_PRODUCTS_BY_PROVIDER[record.provider] ?? [];
}

/**
 * One row per field: `text`/`number` are plain inputs, `select` is a
 * search-filterable dropdown seeded with `options` (or `optionsFor(record)`
 * when the choices depend on another field, e.g. `ad_product` on
 * `provider`), `multiselect` is the same dropdown collecting a list of
 * chips, and `boolean` is a three-way Yes/No/Unknown dropdown.
 */
export const SECTION_FIELDS = {
  providers: [
    { key: "provider", label: "Provider", kind: "select", options: PROVIDER_OPTIONS, required: true, default: PROVIDER_OPTIONS[0] },
    { key: "supported_ad_products", label: "Supported ad products", kind: "multiselect", optionsFor: adProductOptions, default: [] },
    { key: "format_availability", label: "Format availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "placement_availability", label: "Placement availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "creative_availability", label: "Creative availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "interaction_type_availability", label: "Interaction availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "active", label: "State", kind: "boolean", trueLabel: "Active", falseLabel: "Archived", default: true },
  ],
  products: [
    { key: "product_id", label: "Product ID", kind: "text", required: true, default: "" },
    { key: "name", label: "Name", kind: "text", default: "" },
    { key: "sku_id", label: "SKU", kind: "text", default: "" },
    { key: "category", label: "Category", kind: "text", default: "" },
    { key: "brand", label: "Brand", kind: "text", default: "" },
    { key: "inventory_units", label: "Inventory units", kind: "number", default: null },
    { key: "salable", label: "Salable", kind: "boolean", trueLabel: "Yes", falseLabel: "No", default: null },
    { key: "status", label: "Status", kind: "text", default: "" },
  ],
  campaigns: [
    { key: "campaign_id", label: "Campaign ID", kind: "text", required: true, default: "" },
    { key: "campaign_name", label: "Name", kind: "text", default: "" },
    { key: "provider", label: "Provider", kind: "select", options: PROVIDER_OPTIONS, default: PROVIDER_OPTIONS[0] },
    { key: "ad_product", label: "Ad product", kind: "select", optionsFor: adProductOptions, default: "" },
    { key: "status", label: "Status", kind: "text", default: "" },
    { key: "baseline_daily_budget", label: "Baseline daily budget", kind: "number", default: null },
  ],
  adGroups: [
    { key: "ad_group_id", label: "Ad Group ID", kind: "text", required: true, default: "" },
    { key: "campaign_id", label: "Campaign ID", kind: "text", required: true, default: "" },
    { key: "allocation_basis", label: "Allocation basis", kind: "text", default: "" },
    { key: "budget_seed_share", label: "Budget seed share (0-1)", kind: "number", default: null },
    { key: "initial_daily_budget", label: "Initial daily budget", kind: "number", default: null },
    { key: "status", label: "Status", kind: "text", default: "" },
  ],
  touchpoints: [
    { key: "identifier", label: "Identifier", kind: "text", required: true, default: "" },
    { key: "provider", label: "Provider", kind: "select", options: PROVIDER_OPTIONS, default: PROVIDER_OPTIONS[0] },
    { key: "ad_product", label: "Ad product", kind: "select", optionsFor: adProductOptions, default: "" },
    { key: "format", label: "Format", kind: "text", default: "" },
    { key: "placement", label: "Placement", kind: "text", default: "" },
    { key: "placement_availability", label: "Placement availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "creative", label: "Creative", kind: "text", default: "" },
    { key: "creative_availability", label: "Creative availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "interaction_type_availability", label: "Interaction availability", kind: "select", options: FIELD_AVAILABILITY_OPTIONS, default: "AVAILABLE" },
    { key: "supported_interactions", label: "Supported interactions", kind: "multiselect", options: INTERACTION_OPTIONS, default: [] },
    { key: "billing_type", label: "Billing type", kind: "select", options: BILLING_TYPE_OPTIONS, default: "CPC" },
    { key: "cost_per_click", label: "Cost per click", kind: "number", default: null },
    { key: "cost_per_thousand_impressions", label: "Cost per thousand impressions", kind: "number", default: null },
    { key: "click_through_rate", label: "Click-through rate", kind: "number", default: null },
    { key: "active", label: "State", kind: "boolean", trueLabel: "Active", falseLabel: "Archived", default: true },
  ],
  productEconomics: [
    { key: "product_id", label: "Product ID", kind: "text", required: true, default: "" },
    { key: "currency", label: "Currency", kind: "select", options: CURRENCY_OPTIONS, required: true, default: "USD" },
    { key: "unit_price", label: "Unit price", kind: "number", default: null },
    { key: "unit_cogs", label: "Unit COGS", kind: "number", default: null },
    { key: "variable_cost_per_unit", label: "Variable cost per unit", kind: "number", default: null },
    { key: "variable_fulfillment_cost_per_unit", label: "Variable fulfillment cost per unit", kind: "number", default: null },
    { key: "variable_platform_fee_per_unit", label: "Variable platform fee per unit", kind: "number", default: null },
    { key: "other_variable_cost_per_unit", label: "Other variable cost per unit", kind: "number", default: null },
    { key: "unit_contribution_margin", label: "Unit contribution margin", kind: "number", default: null },
    { key: "margin_source", label: "Margin source", kind: "select", options: MARGIN_SOURCE_OPTIONS, default: null },
  ],
  generationConfigs: [
    { key: "run_id", label: "Run ID", kind: "text", required: true, default: "" },
    { key: "seed", label: "Seed", kind: "number", default: null },
    { key: "configuration_sha256", label: "Configuration SHA-256", kind: "text", default: "" },
  ],
};

/** A record pre-filled with every field this section recognizes. */
export function buildTemplate(sectionKey) {
  const fields = SECTION_FIELDS[sectionKey] ?? [];
  const template = {};
  for (const field of fields) {
    template[field.key] = field.kind === "multiselect" ? [] : field.default ?? null;
  }
  return template;
}
