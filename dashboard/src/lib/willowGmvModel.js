/**
 * Pure browser inference for Willow Sakura's contributed Extended-27 model.
 *
 * The Vue panel owns labels and editable state. This module owns only the
 * contributor's feature order and neural-network forward pass, so the same
 * calculation can be tested without rendering a page or mounting an iframe.
 */

const BUDGET_KEYS = ["budget_sp", "budget_sb", "budget_sd", "budget_dsp"];
const STRUCTURE_KEYS = [
  "share_cost_top_of_search",
  "share_cost_product_page",
  "share_cost_sb_headline",
  "share_cost_sp_product_ad",
  "share_cost_dsp_video",
  "share_cost_dsp_image",
  "share_cost_dsp_unspecified_creative",
  "n_placement_types",
];

function finite(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function multiply(matrix, vector, name) {
  if (!Array.isArray(matrix) || matrix.length !== vector.length) {
    throw new Error(`${name} input dimension does not match the feature vector.`);
  }
  const width = matrix[0]?.length ?? 0;
  if (!width || matrix.some((row) => row.length !== width)) {
    throw new Error(`${name} is not a rectangular weight matrix.`);
  }
  return Array.from({ length: width }, (_, column) =>
    matrix.reduce((sum, row, index) => sum + row[column] * vector[index], 0),
  );
}

function addBias(values, bias, name) {
  if (!Array.isArray(bias) || values.length !== bias.length) {
    throw new Error(`${name} bias dimension does not match its layer.`);
  }
  return values.map((value, index) => value + bias[index]);
}

function relu(values) {
  return values.map((value) => Math.max(0, value));
}

/** Build the exact 27 inputs declared by the exported model. */
export function buildWillowFeatures(model, input, budgetScale = 1) {
  const scale = Math.max(0, finite(budgetScale, 1));
  const budgets = BUDGET_KEYS.map((key) =>
    Math.max(0, finite(input[key])) * scale,
  );
  const total = budgets.reduce((sum, value) => sum + value, 0) || 1;
  const shares = budgets.map((value) => value / total);
  const day = Math.max(0, Math.min(6, Math.trunc(finite(input.dow))));
  const days = Array.from({ length: 7 }, (_, index) => (index === day ? 1 : 0));
  const countries = model.country_classes.map((country) =>
    country === input.country ? 1 : 0,
  );
  const structure = STRUCTURE_KEYS.map((key) =>
    Math.max(0, finite(input.struct?.[key])),
  );
  const features = [
    ...budgets.map((value) => Math.log1p(value)),
    ...shares,
    budgets.some((value) => value > 0) ? 1 : 0,
    input.is_weekend ? 1 : 0,
    ...days,
    ...countries,
    ...structure,
  ];
  if (features.length !== model.n_features) {
    throw new Error(
      `Willow model expects ${model.n_features} features; received ${features.length}.`,
    );
  }
  return features;
}

/** Run the exported scaler, two hidden layers, and capped revenue output. */
export function predictWillowGmv(model, input, budgetScale = 1) {
  const features = buildWillowFeatures(model, input, budgetScale);
  if (
    model.scaler_mean.length !== features.length ||
    model.scaler_std.length !== features.length
  ) {
    throw new Error("Willow scaler dimension does not match the feature vector.");
  }
  const scaled = features.map((value, index) => {
    const divisor = finite(model.scaler_std[index], 1) || 1;
    return (value - finite(model.scaler_mean[index])) / divisor;
  });
  const hiddenOne = relu(
    addBias(multiply(model.weights.W1, scaled, "W1"), model.weights.b1, "W1"),
  );
  const hiddenTwo = relu(
    addBias(
      multiply(model.weights.W2, hiddenOne, "W2"),
      model.weights.b2,
      "W2",
    ),
  );
  const output = addBias(
    multiply(model.weights.W3, hiddenTwo, "W3"),
    model.weights.b3,
    "W3",
  );
  if (output.length !== 1) {
    throw new Error("Willow output layer must contain exactly one value.");
  }
  const logPrediction = output[0];
  const revenue = Math.min(
    Math.expm1(Math.max(0, logPrediction)),
    finite(model.rev_cap, Number.POSITIVE_INFINITY),
  );
  return { features, logPrediction, revenue };
}

export { BUDGET_KEYS, STRUCTURE_KEYS };
