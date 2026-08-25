/**
 * Preserve the former Node master-data derivation as a parity fixture.
 *
 * The Budget Manager's entity sections -- Ad Providers, Products, Campaigns,
 * Ad Groups, Touchpoints, Product Economics -- describe the account the
 * reports were pulled from. Those reports are tracked in the repository, so
 * the catalogue they imply is available in every deployment and does not
 * depend on any optional sidecar being configured: the entity aggregate names
 * every Campaign, Ad Group, ASIN, and SKU, and the daily platform report names
 * every touchpoint with its billing type and observed cost.
 *
 * Derivation rather than a second tracked file is deliberate. A catalogue
 * committed beside the reports would be free to disagree with them; one read
 * out of the reports cannot. Where a report does not carry a field -- a
 * Product's category, a unit price, a Campaign's baseline budget -- the field
 * stays null rather than being invented, and the interface renders it as
 * missing.
 *
 * Runtime requests use `backend/repository/master_data.py`. This implementation
 * remains the cross-language reference imported by `server/data_source.js`.
 *
 * Parity-test flow:
 *     committed reports -> here -> server/data_source.js -> dashboard/tests
 */

/** Sum a numeric column across rows, treating blanks as zero. */
function total(rows, field) {
  return rows.reduce((sum, row) => sum + (Number(row[field]) || 0), 0);
}

/** Distinct non-empty values of `field`, in first-seen order. */
function distinct(rows, field) {
  const seen = [];
  for (const row of rows) {
    const value = row[field];
    if (value !== undefined && value !== null && value !== "" && !seen.includes(value)) {
      seen.push(value);
    }
  }
  return seen;
}

/**
 * The five-segment touchpoint key's parts.
 *
 * `UNSPECIFIED` is the pipeline's marker for a segment the platform does not
 * report, and is mapped back to null so the interface shows it as absent
 * rather than as a literal value the account actually uses.
 */
function splitKey(key) {
  const [adProduct, format, placement, creative, interaction] = String(key).split(":");
  const clean = (value) => (value && value !== "UNSPECIFIED" ? value : null);
  return {
    ad_product: adProduct ?? null,
    format: clean(format),
    placement: clean(placement),
    creative: clean(creative),
    interaction_type: interaction ?? null,
  };
}

/**
 * The provider a five-segment key belongs to.
 *
 * The four Amazon ad products are the vocabulary `mta_common` defines for
 * `Provider.AMAZON_ADS`; anything else is reported under `GENERIC` rather
 * than being dropped, so an added provider surfaces instead of vanishing.
 */
const AMAZON_AD_PRODUCTS = new Set([
  "SPONSORED_PRODUCTS",
  "SPONSORED_BRANDS",
  "SPONSORED_DISPLAY",
  "AMAZON_DSP",
]);

function providerOf(adProduct) {
  return AMAZON_AD_PRODUCTS.has(adProduct) ? "AMAZON_ADS" : "GENERIC";
}

/** `AVAILABLE` when any row reports the segment, `NOT_PROVIDED` when none do. */
function availability(rows, field) {
  return rows.some((row) => row[field]) ? "AVAILABLE" : "NOT_PROVIDED";
}

/**
 * Build the catalogue.
 *
 * `adsRows` is the daily platform report and `bridgeRows` the touchpoint-to-
 * entity aggregate; both are already coerced by the loaders that read them.
 * Returns the same shape the research sidecar and the database produce, so
 * the views cannot tell which source filled it.
 */
export function deriveMasterData(adsRows, bridgeRows, strategyRequest = {}) {
  const touchpoints = deriveTouchpoints(adsRows);
  const campaigns = deriveCampaigns(bridgeRows, touchpoints, strategyRequest);
  // The account reports one currency; it is read from the data rather than
  // assumed, so a non-USD account is not silently relabelled.
  const currency =
    distinct(adsRows, "currency")[0] ??
    strategyRequest.campaign_group?.currency ??
    null;
  return {
    providers: deriveProviders(touchpoints),
    products: deriveProducts(bridgeRows),
    campaigns,
    adGroups: deriveAdGroups(bridgeRows),
    touchpoints,
    productEconomics: deriveProductEconomics(bridgeRows, currency),
    campaignProductLinks: deriveCampaignProductLinks(bridgeRows),
  };
}

/**
 * One record per distinct five-segment key, with its observed economics.
 *
 * Cost per click and cost per thousand impressions are computed from the
 * report's own totals rather than assumed, and each is reported only for the
 * billing type that produced it: a CPM touchpoint has no meaningful cost per
 * click even when a stray click was recorded against it.
 */
function deriveTouchpoints(adsRows) {
  const byKey = new Map();
  for (const row of adsRows) {
    const key = row.touchpoint ?? row.normalizedTouchpoint;
    if (!key) continue;
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(row);
  }

  const byIdentifier = new Map();
  for (const [key, rows] of byKey) {
    const parts = splitKey(key);
    // The identifier drops the interaction segment: IMPRESSION and CLICK on
    // one placement are two interactions of a single touchpoint, which is the
    // grouping `supported_interactions` exists to express.
    const identifier = [
      parts.ad_product,
      parts.format ?? "UNSPECIFIED",
      parts.placement ?? "UNSPECIFIED",
      parts.creative ?? "UNSPECIFIED",
    ].join(":");

    const existing = byIdentifier.get(identifier);
    const record = existing ?? {
      identifier,
      provider: providerOf(parts.ad_product),
      ad_product: parts.ad_product,
      format: parts.format,
      placement: parts.placement,
      placement_availability: parts.placement ? "AVAILABLE" : "NOT_PROVIDED",
      creative: parts.creative,
      creative_availability: parts.creative ? "AVAILABLE" : "NOT_PROVIDED",
      interaction_type_availability: "AVAILABLE",
      supported_interactions: [],
      impression_enabled: false,
      click_enabled: false,
      billing_type: null,
      cost_per_click: null,
      cost_per_thousand_impressions: null,
      base_impressions: null,
      click_through_rate: null,
      platform_conversion_rate: null,
      conversion_log_odds_effect: null,
      compatibility_keys: [],
      active: true,
    };

    if (parts.interaction_type && !record.supported_interactions.includes(parts.interaction_type)) {
      record.supported_interactions.push(parts.interaction_type);
    }
    record.impression_enabled = record.supported_interactions.includes("IMPRESSION");
    record.click_enabled = record.supported_interactions.includes("CLICK");
    record.compatibility_keys.push(key);

    const impressions = total(rows, "impressions");
    const clicks = total(rows, "clicks");
    const cost = total(rows, "cost");

    // One touchpoint is commonly billed both ways -- CPC on its clicks and CPM
    // on its impressions -- so cost is accumulated against the billing type
    // that produced it rather than against the touchpoint as a whole. Dividing
    // a mixed total by either denominator would report a rate the platform
    // never charged.
    const billed = (record._billed ??= {});
    for (const row of rows) {
      const type = row.cost_type;
      if (!type) continue;
      const bucket = (billed[type] ??= { cost: 0, clicks: 0, impressions: 0 });
      bucket.cost += Number(row.cost) || 0;
      bucket.clicks += Number(row.clicks) || 0;
      bucket.impressions += Number(row.impressions) || 0;
    }

    const totals = (record._totals ??= { impressions: 0, clicks: 0, cost: 0 });
    totals.impressions += impressions;
    totals.clicks += clicks;
    totals.cost += cost;

    byIdentifier.set(identifier, record);
  }

  return [...byIdentifier.values()].map(({ _totals, _billed, ...record }) => {
    const types = Object.keys(_billed ?? {}).sort();
    const cpc = _billed?.CPC;
    const cpm = _billed?.CPM;
    return {
      ...record,
      // Both types when the platform bills both, so the row states what it is
      // rather than naming one and hiding the other.
      billing_type: types.length > 0 ? types.join(" + ") : null,
      // A rate only where cost was actually charged against that denominator.
      // An impression row that delivered volume at no recorded cost yields no
      // rate rather than a rate of zero, which would read as "free".
      cost_per_click: cpc?.cost > 0 && cpc.clicks > 0 ? round(cpc.cost / cpc.clicks, 4) : null,
      cost_per_thousand_impressions:
        cpm?.cost > 0 && cpm.impressions > 0
          ? round((cpm.cost / cpm.impressions) * 1000, 4)
          : null,
      observed_impressions: _totals?.impressions ?? 0,
      observed_clicks: _totals?.clicks ?? 0,
      observed_cost: round(_totals?.cost ?? 0, 2),
      // Deliberately not derived. The report records impressions and clicks in
      // separate per-interaction rows that share no denominator, so dividing
      // one by the other does not produce this touchpoint's click-through
      // rate; the observed counts above are what the platform actually states.
      click_through_rate: null,
      base_impressions: _totals?.impressions ?? null,
    };
  });
}

/** Round to a fixed precision without carrying float noise into the interface. */
function round(value, digits) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

/**
 * One record per provider actually present in the reports.
 *
 * Each provider's supported ad products and per-segment availability are read
 * from its own touchpoints, so a provider that never reports a placement is
 * described as not providing one rather than as having none.
 */
function deriveProviders(touchpoints) {
  const byProvider = new Map();
  for (const touchpoint of touchpoints) {
    if (!byProvider.has(touchpoint.provider)) byProvider.set(touchpoint.provider, []);
    byProvider.get(touchpoint.provider).push(touchpoint);
  }
  return [...byProvider.entries()].map(([provider, rows]) => ({
    provider,
    supported_ad_products: distinct(rows, "ad_product"),
    format_availability: availability(rows, "format"),
    placement_availability: availability(rows, "placement"),
    creative_availability: availability(rows, "creative"),
    interaction_type_availability: "AVAILABLE",
    active: true,
  }));
}

/**
 * One record per advertised SKU.
 *
 * The reports identify a product by ASIN and SKU and carry nothing else about
 * it: no name, category, brand, or inventory. Those fields are present and
 * null, which is what lets the Form editor show the whole shape of a Product
 * while being honest that the platform report does not describe it.
 */
function deriveProducts(bridgeRows) {
  const bySku = new Map();
  for (const row of bridgeRows) {
    const sku = row.sku_id;
    if (!sku || bySku.has(sku)) continue;
    bySku.set(sku, {
      product_id: sku,
      name: null,
      sku_id: sku,
      advertised_asin: row.advertised_asin ?? null,
      category: null,
      brand: null,
      inventory_units: null,
      salable: null,
      status: "ADVERTISED",
    });
  }
  return [...bySku.values()];
}

/**
 * One record per Campaign, with the ad product it runs and its measured reach.
 *
 * `baseline_daily_budget` comes from the strategy request when that artifact
 * names one, and is otherwise null: the platform report records spend, not the
 * budget cap that governed it, and presenting observed spend as a budget would
 * misstate what the number is.
 */
function deriveCampaigns(bridgeRows, touchpoints, strategyRequest) {
  const declared = new Map(
    (strategyRequest.campaigns ?? []).map((item) => [item.campaign_id, item]),
  );
  const adProductOf = new Map(
    touchpoints.map((item) => [item.identifier, item.ad_product]),
  );

  const byCampaign = new Map();
  for (const row of bridgeRows) {
    const id = row.campaign_id;
    if (!id) continue;
    if (!byCampaign.has(id)) byCampaign.set(id, []);
    byCampaign.get(id).push(row);
  }

  return [...byCampaign.entries()].map(([id, rows]) => {
    const fromRequest = declared.get(id) ?? {};
    // The Campaign's ad product is whichever its touchpoints report; the
    // reports keep one ad product per Campaign, and the first is taken rather
    // than a guess if that ever stops holding.
    const adProduct =
      fromRequest.ad_product ??
      distinct(
        rows.map((row) => ({
          ad_product: adProductOf.get(
            String(row.touchpoint ?? "").split(":").slice(0, 4).join(":"),
          ),
        })),
        "ad_product",
      )[0] ??
      null;
    return {
      campaign_id: id,
      campaign_name: fromRequest.campaign_name ?? null,
      campaign_group_id: rows[0]?.campaign_group_id ?? null,
      provider: providerOf(adProduct),
      ad_product: adProduct,
      marketplace: rows[0]?.marketplace ?? null,
      baseline_daily_budget: fromRequest.baseline_daily_budget ?? null,
      observed_cost: round(total(rows, "cost"), 2),
      status: fromRequest.status ?? null,
    };
  });
}

/**
 * One record per Ad Group, with the targeting it carries.
 *
 * `initial_daily_budget` is left null: an Ad Group's budget is what the
 * recommendation proposes, not something the historical report states, and the
 * Budget Manager shows the proposal in its own section.
 */
function deriveAdGroups(bridgeRows) {
  const byAdGroup = new Map();
  for (const row of bridgeRows) {
    const id = row.ad_group_id;
    if (!id) continue;
    if (!byAdGroup.has(id)) byAdGroup.set(id, []);
    byAdGroup.get(id).push(row);
  }

  return [...byAdGroup.entries()].map(([id, rows]) => ({
    ad_group_id: id,
    name: null,
    campaign_id: rows[0]?.campaign_id ?? null,
    keyword_count: distinct(rows, "keyword_id").length,
    target_count: distinct(rows, "target_id").length,
    audience_count: distinct(rows, "audience_id").length,
    sku_count: distinct(rows, "sku_id").length,
    allocation_basis: null,
    budget_seed_share: null,
    initial_daily_budget: null,
    status: null,
  }));
}

/**
 * Per-product unit economics, as far as the reports actually establish them.
 *
 * Attributed revenue divided by attributed purchases gives an observed average
 * selling price, which is a real measurement of the account. Cost of goods and
 * the variable costs beneath it are not in any advertising report -- they come
 * from the merchant's own books -- so they stay null, and the contribution
 * margin that depends on them stays null with them rather than being computed
 * from a cost silently assumed to be zero. `margin_source` is therefore left
 * unset: nothing here sourced a margin.
 */
function deriveProductEconomics(bridgeRows, currency) {
  const bySku = new Map();
  for (const row of bridgeRows) {
    const sku = row.sku_id;
    if (!sku) continue;
    const bucket = bySku.get(sku) ?? { revenue: 0, purchases: 0 };
    bucket.revenue += Number(row.assisted_revenue) || 0;
    bucket.purchases += Number(row.assisted_purchase_count) || 0;
    bySku.set(sku, bucket);
  }

  return [...bySku.entries()].map(([sku, totals]) => ({
    product_id: sku,
    currency,
    unit_price:
      totals.purchases > 0 ? round(totals.revenue / totals.purchases, 2) : null,
    unit_cogs: null,
    variable_cost_per_unit: null,
    variable_fulfillment_cost_per_unit: null,
    variable_platform_fee_per_unit: null,
    other_variable_cost_per_unit: null,
    unit_contribution_margin: null,
    margin_source: null,
    observed_revenue: round(totals.revenue, 2),
    observed_purchases: totals.purchases,
  }));
}

/** Which Products each Campaign advertised, as observed in the reports. */
function deriveCampaignProductLinks(bridgeRows) {
  const pairs = new Set();
  const links = [];
  for (const row of bridgeRows) {
    if (!row.campaign_id || !row.sku_id) continue;
    const key = `${row.campaign_id}|${row.sku_id}`;
    if (pairs.has(key)) continue;
    pairs.add(key);
    links.push({ campaign_id: row.campaign_id, product_id: row.sku_id });
  }
  return links;
}
