/**
 * Load, verify, and normalize canonical Gate D R5 fixtures for display only.
 *
 * The importer establishes the cross-repository boundary; this adapter repeats
 * byte and identity checks before exposing immutable view data. It never
 * calculates a ratio, compares a threshold, or infers a review verdict.
 */

export function buildOntologyReviewDataRoot(baseUrl) {
  if (typeof baseUrl !== "string" || !baseUrl || /[?#]/.test(baseUrl)) {
    throw new Error("Ontology Review fixtures unavailable: invalid deployment base URL");
  }
  const deploymentRoot = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return `${deploymentRoot}data/ontology-review`;
}

export const ONTOLOGY_REVIEW_DATA_ROOT = buildOntologyReviewDataRoot(
  import.meta.env?.BASE_URL ?? "./",
);
export const DEFAULT_ONTOLOGY_REVIEW_SCENARIO = "in-band";

const SOURCE_COMMIT = "816958b7c5fa44cedf55408a0797fea93b1f44bc";
const RELEASE_COMMIT = "cf5f2a7b78fb3d384f6d4fd815c830dfc2c21363";
const SUITE_ID = "gate-d-canonical-r5-v3";
const CLIENT_ID = "demo_client_001";
const PLAN_ID = "plan_demo_001";
const RELEASE_MANIFEST_SIZE = 1506;
const RELEASE_MANIFEST_SHA256 =
  "a8b516ca01b4e22f2101426a1b695626f24b107ae560ed77702975f3155e2003";

const RELEASE_IDENTITY = Object.freeze({
  ontology_version: "3.0-campaign-budget-policy",
  rule_version: "R5@3.0-budget-policy",
  engine_version: "3.0",
  schema_version: "2.0",
  source_commit: SOURCE_COMMIT,
  package_checksum:
    "23aefa15460399623b82cd83a9708397ddafd8af7a1572cf73a1e8eee1199926",
});

const FIXTURES = Object.freeze([
  Object.freeze({ file: "in-band.json", scenario: "in-band", sha256: "6f6b67a60b796d11e304be387d34f68a3e67f7f0431a26b308d52194adb057d4", size: 4552 }),
  Object.freeze({ file: "exact-boundary.json", scenario: "exact-boundary", sha256: "4bcbcccf6ef4fc7b11b5699c6fedd3244b72c359ee4e5a98c69c1e3577300f85", size: 4559 }),
  Object.freeze({ file: "conflict.json", scenario: "conflict", sha256: "1a5b71680eef72c499b56cbe8c8c44db325a8f313794484414812331b483e602", size: 4575 }),
  Object.freeze({ file: "zero-baseline.json", scenario: "zero-baseline", sha256: "3556810aeb27f845d5aae968b1d4c862e0bf1a505e2126215d2bf37052eeb1e3", size: 4647 }),
  Object.freeze({ file: "missing-policy.json", scenario: "missing-policy", sha256: "b06d18d9aaf5cbae935120d87bef67be3c0eef0f56af55a58d2cdd2a8e32d367", size: 4656 }),
]);

const PRESENTATION = Object.freeze({
  "in-band": Object.freeze({
    label: "In band · 20%",
    explanation: "No R5 conflict was emitted. This is not approval, a safety finding, or a claim of optimality.",
  }),
  "exact-boundary": Object.freeze({
    label: "Exact boundary · 30%",
    explanation: "No R5 conflict was emitted because the canonical rule uses strict > comparison. This is not approval.",
  }),
  conflict: Object.freeze({
    label: "Conflict · 30.01%",
    explanation: "R5 reports a policy conflict that requires human authorization. This does not mean the optimizer failed.",
  }),
  "zero-baseline": Object.freeze({
    label: "Zero baseline",
    explanation: "The canonical ratio is undefined because the current-budget baseline is zero; evidence is insufficient.",
  }),
  "missing-policy": Object.freeze({
    label: "Missing policy",
    explanation: "The client policy limit and provenance are unavailable; evidence is insufficient until policy is configured.",
  }),
});

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}

function fail(message) {
  throw new Error(`Ontology Review fixtures unavailable: ${message}`);
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) fail(`${label} does not match the canonical release`);
}

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(`${label} is malformed`);
  }
}

function assertExactKeys(value, expected, label) {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    fail(`${label} field set does not match the canonical release`);
  }
}

function validateIdentity(identity, label) {
  assertObject(identity, label);
  for (const [field, expected] of Object.entries(RELEASE_IDENTITY)) {
    assertEqual(identity[field], expected, `${label}.${field}`);
  }
  assertEqual(Object.keys(identity).length, 6, `${label} field set`);
}

function validateManifest(manifest) {
  assertObject(manifest, "manifest");
  assertExactKeys(
    manifest,
    ["schema_version", "suite_id", "release_identity", "fixtures", "import_identity"],
    "manifest",
  );
  assertEqual(manifest.schema_version, "1.0", "manifest.schema_version");
  assertEqual(manifest.suite_id, SUITE_ID, "manifest.suite_id");
  validateIdentity(manifest.release_identity, "manifest.release_identity");
  assertObject(manifest.import_identity, "manifest.import_identity");
  assertExactKeys(
    manifest.import_identity,
    ["source_commit", "release_commit"],
    "manifest.import_identity",
  );
  assertEqual(manifest.import_identity.source_commit, SOURCE_COMMIT, "import source commit");
  assertEqual(manifest.import_identity.release_commit, RELEASE_COMMIT, "import release commit");
  if (!Array.isArray(manifest.fixtures)) fail("manifest fixture list is malformed");
  assertEqual(manifest.fixtures.length, FIXTURES.length, "manifest fixture count");
  FIXTURES.forEach((expected, index) => {
    const actual = manifest.fixtures[index];
    assertObject(actual, `manifest fixture ${index + 1}`);
    for (const [field, value] of Object.entries(expected)) {
      assertEqual(actual[field], value, `manifest fixture ${index + 1} ${field}`);
    }
    assertEqual(Object.keys(actual).length, 4, `manifest fixture ${index + 1} field set`);
  });
}

function validatePayload(payload, expected) {
  assertObject(payload, expected.file);
  assertEqual(payload.schema_version, "1.0", `${expected.file} schema`);
  assertEqual(payload.fixture_mode, true, `${expected.file} fixture mode`);
  assertEqual(payload.scenario, expected.scenario, `${expected.file} scenario`);
  validateIdentity(payload.release_identity, `${expected.file} release identity`);
  assertEqual(payload.client_id, CLIENT_ID, `${expected.file} client`);
  assertObject(payload.plan, `${expected.file} plan`);
  assertEqual(payload.plan.plan_id, PLAN_ID, `${expected.file} plan`);
  if (!Array.isArray(payload.plan.items) || payload.plan.items.length !== 1) {
    fail(`${expected.file} must contain one plan item`);
  }
  assertObject(payload.review, `${expected.file} review`);
  assertEqual(payload.review.source, "ONTOLOGY_ENGINE", `${expected.file} review source`);
  assertEqual(payload.review.client_id, CLIENT_ID, `${expected.file} review client`);
  assertEqual(payload.review.plan_id, PLAN_ID, `${expected.file} review plan`);
  validateIdentity(payload.review.release_identity, `${expected.file} review identity`);
  if (!Array.isArray(payload.review.items) || payload.review.items.length !== 1) {
    fail(`${expected.file} must contain one review item`);
  }
  const planItem = payload.plan.items[0];
  const reviewItem = payload.review.items[0];
  assertEqual(reviewItem.plan_item_id, planItem.plan_item_id, `${expected.file} item linkage`);
  assertObject(reviewItem.policy_evaluation, `${expected.file} policy evaluation`);
  assertEqual(reviewItem.policy_evaluation.policy_rule_id, "R5", `${expected.file} rule`);
  assertEqual(
    reviewItem.policy_evaluation.policy_rule_version,
    "3.0-budget-policy",
    `${expected.file} rule version`,
  );
}

async function sha256(bytes) {
  if (!globalThis.crypto?.subtle) fail("SHA-256 verification is unavailable");
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function fetchBytes(fetcher, url, signal) {
  let response;
  try {
    response = await fetcher(url, {
      cache: "no-store",
      credentials: "same-origin",
      ...(signal ? { signal } : {}),
    });
  } catch {
    fail(`${url} could not be loaded`);
  }
  if (!response?.ok || typeof response.arrayBuffer !== "function") {
    fail(`${url} could not be loaded`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

function parseJson(bytes, label) {
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    fail(`${label} is not valid JSON`);
  }
}

function evidenceRows(payload) {
  return [
    ...(payload.plan.decision_evidence ?? []),
    ...(payload.plan.review_evidence ?? []),
  ].map((fact) => ({
    id: fact.fact_id,
    name: fact.name,
    value: String(fact.value),
    unit: fact.unit,
    source: fact.source,
    scope: fact.scope,
  }));
}

function normalize(payload) {
  const planItem = payload.plan.items[0];
  const reviewItem = payload.review.items[0];
  const policy = reviewItem.policy_evaluation;
  const presentation = PRESENTATION[payload.scenario];
  return {
    key: payload.scenario,
    label: presentation.label,
    sourceKind: "Canonical Gate D fixture",
    apiConnected: false,
    explanation: presentation.explanation,
    suiteId: SUITE_ID,
    release: { ...payload.release_identity, release_commit: RELEASE_COMMIT },
    clientId: payload.client_id,
    plan: {
      id: payload.plan.plan_id,
      source: payload.plan.source,
      sourceVersion: payload.plan.source_version,
      itemId: planItem.plan_item_id,
      campaign: planItem.entity_id,
      action: planItem.action,
    },
    review: {
      id: payload.review.review_id,
      source: payload.review.source,
      verdict: payload.review.overall_verdict,
      itemVerdict: reviewItem.verdict,
    },
    rule: {
      id: policy.policy_rule_id,
      version: policy.policy_rule_version,
      triggered: policy.triggered,
      outcome: policy.outcome,
    },
    policy: {
      currentBudget: policy.current_budget,
      recommendedBudget: policy.recommended_budget,
      currency: policy.currency,
      absoluteChangeRatio: policy.absolute_change_ratio,
      authorizationLimit: policy.authorization_limit,
      source: policy.policy_source,
      productionCalibrated: policy.production_calibrated,
      insufficiencyReason: policy.insufficiency_reason,
    },
    evidence: evidenceRows(payload),
    limitations: [...reviewItem.limitations],
    availability: [
      policy.production_calibrated === false
        ? "Demo policy is not production calibrated and is not an industry benchmark."
        : "Production calibration is unavailable for this fixture.",
    ],
    nextStep: policy.next_step,
  };
}

export async function loadOntologyReviewFixtures({
  signal,
  fetcher = globalThis.fetch,
  digestBytes = sha256,
  timeoutMs = 10000,
} = {}) {
  if (typeof fetcher !== "function") fail("a fetch implementation is required");
  if (typeof digestBytes !== "function") fail("a SHA-256 implementation is required");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) fail("timeout must be positive");

  const controller = new AbortController();
  let timeoutId;
  let abortListener;
  const cancellation = new Promise((_, reject) => {
    const cancel = (message) => {
      controller.abort();
      reject(new Error(`Ontology Review fixtures unavailable: ${message}`));
    };
    timeoutId = setTimeout(
      () => cancel(`loading timed out after ${timeoutMs / 1000} seconds`),
      timeoutMs,
    );
    if (signal) {
      abortListener = () => cancel("loading was cancelled");
      if (signal.aborted) abortListener();
      else signal.addEventListener("abort", abortListener, { once: true });
    }
  });

  const operation = (async () => {
    const manifestBytes = await fetchBytes(
      fetcher,
      `${ONTOLOGY_REVIEW_DATA_ROOT}/manifest.json`,
      controller.signal,
    );
    assertEqual(manifestBytes.byteLength, RELEASE_MANIFEST_SIZE, "manifest byte size");
    assertEqual(
      await digestBytes(manifestBytes),
      RELEASE_MANIFEST_SHA256,
      "manifest SHA-256",
    );
    const manifest = parseJson(manifestBytes, "manifest");
    validateManifest(manifest);

    const scenarios = [];
    for (const expected of FIXTURES) {
      const bytes = await fetchBytes(
        fetcher,
        `${ONTOLOGY_REVIEW_DATA_ROOT}/${expected.file}`,
        controller.signal,
      );
      assertEqual(bytes.byteLength, expected.size, `${expected.file} byte size`);
      assertEqual(await digestBytes(bytes), expected.sha256, `${expected.file} SHA-256`);
      const payload = parseJson(bytes, expected.file);
      validatePayload(payload, expected);
      scenarios.push(normalize(payload));
    }
    return deepFreeze(scenarios);
  })();

  try {
    return await Promise.race([operation, cancellation]);
  } finally {
    clearTimeout(timeoutId);
    if (signal && abortListener) signal.removeEventListener("abort", abortListener);
  }
}
