/** Verify Willow Sakura's contributed browser model without mounting Vue. */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import { buildWillowFeatures, predictWillowGmv } from "../src/lib/willowGmvModel.js";

const model = JSON.parse(
  readFileSync(
    resolve(
      import.meta.dirname,
      "..",
      "..",
      "docs",
      "en",
      "strategy-evaluation",
      "asin-gmv-nn-v1",
      "results",
      "demo_mlp_extended27.json",
    ),
    "utf8",
  ),
);
const input = {
  ...model.defaults,
  struct: { ...model.defaults.struct },
};

test("Willow Extended-27 feature construction follows the exported model", () => {
  const features = buildWillowFeatures(model, input);

  assert.equal(features.length, 27);
  assert.equal(features[8], 1);
  assert.equal(features[9], 0);
  assert.equal(features.slice(10, 17).reduce((sum, value) => sum + value, 0), 1);
  assert.deepEqual(features.slice(17, 19), [0, 1]);
});

test("Willow prediction is deterministic and the comparison changes only budgets", () => {
  const first = predictWillowGmv(model, input);
  const repeat = predictWillowGmv(model, input);
  const comparison = predictWillowGmv(model, input, 1.1);

  assert.deepEqual(repeat, first);
  assert.ok(Number.isFinite(first.revenue));
  assert.ok(first.revenue >= 0 && first.revenue <= model.rev_cap);
  assert.notEqual(comparison.revenue, first.revenue);
  assert.deepEqual(comparison.features.slice(8), first.features.slice(8));
});

test("Willow inference names malformed model dimensions", () => {
  const invalid = { ...model, scaler_mean: model.scaler_mean.slice(1) };

  assert.throws(
    () => predictWillowGmv(invalid, input),
    /scaler dimension does not match/,
  );
});
