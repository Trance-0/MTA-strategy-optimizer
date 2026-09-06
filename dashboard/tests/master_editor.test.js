/** Verify future-run draft templates without a backend or a browser. */
import assert from "node:assert/strict";
import test from "node:test";
import { buildTemplate, SECTION_FIELDS } from "../src/lib/masterObjectFields.js";

test("draft templates retain missing values and own their lists", () => {
  assert.equal(Object.keys(SECTION_FIELDS).length, 7);
  assert.deepEqual(buildTemplate("unknown"), {});
  const first = buildTemplate("providers");
  first.supported_ad_products.push("custom");
  assert.deepEqual(buildTemplate("providers").supported_ad_products, []);
  assert.equal(buildTemplate("products").inventory_units, null);
  assert.equal(buildTemplate("productEconomics").unit_cogs, null);
  assert.equal(buildTemplate("providers").active, true);
  for (const [section, fields] of Object.entries(SECTION_FIELDS)) {
    assert.deepEqual(Object.keys(buildTemplate(section)), fields.map((field) => field.key));
  }
});
