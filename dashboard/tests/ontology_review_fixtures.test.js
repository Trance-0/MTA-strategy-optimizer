/**
 * Unit tests for the canonical Gate D Ontology Review loader and adapter.
 */

import assert from "node:assert/strict";
import {
  copyFile,
  link,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rename,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  buildOntologyReviewDataRoot,
  DEFAULT_ONTOLOGY_REVIEW_SCENARIO,
  loadOntologyReviewFixtures,
} from "../src/lib/ontologyReviewFixtures.js";
import {
  CANONICAL_FIXTURES,
  CANONICAL_RELEASE_COMMIT,
  CANONICAL_SOURCE_MANIFEST_SHA256,
  CANONICAL_SOURCE_MANIFEST_SIZE,
  CANONICAL_SOURCE_COMMIT,
  DEFAULT_SOURCE,
  canonicalReleaseManifestBytes,
  replaceDirectoryWithLock,
  validateCanonicalManifest,
  validateCanonicalPayload,
  validateCanonicalSourceManifestBytes,
  validateImportPathSeparation,
  verifyPublishedOntologyReviewBundle,
} from "../../script/import_ontology_review_fixtures.mjs";

const SOURCE_COMMIT = "816958b7c5fa44cedf55408a0797fea93b1f44bc";
const RELEASE_COMMIT = "cf5f2a7b78fb3d384f6d4fd815c830dfc2c21363";
const RELEASE = Object.freeze({
  ontology_version: "3.0-campaign-budget-policy",
  rule_version: "R5@3.0-budget-policy",
  engine_version: "3.0",
  schema_version: "2.0",
  source_commit: SOURCE_COMMIT,
  package_checksum: "23aefa15460399623b82cd83a9708397ddafd8af7a1572cf73a1e8eee1199926",
});
const FIXTURES = Object.freeze([
  { file: "in-band.json", scenario: "in-band", sha256: "6f6b67a60b796d11e304be387d34f68a3e67f7f0431a26b308d52194adb057d4", size: 4552 },
  { file: "exact-boundary.json", scenario: "exact-boundary", sha256: "4bcbcccf6ef4fc7b11b5699c6fedd3244b72c359ee4e5a98c69c1e3577300f85", size: 4559 },
  { file: "conflict.json", scenario: "conflict", sha256: "1a5b71680eef72c499b56cbe8c8c44db325a8f313794484414812331b483e602", size: 4575 },
  { file: "zero-baseline.json", scenario: "zero-baseline", sha256: "3556810aeb27f845d5aae968b1d4c862e0bf1a505e2126215d2bf37052eeb1e3", size: 4647 },
  { file: "missing-policy.json", scenario: "missing-policy", sha256: "b06d18d9aaf5cbae935120d87bef67be3c0eef0f56af55a58d2cdd2a8e32d367", size: 4656 },
]);

const POLICY_BY_SCENARIO = Object.freeze({
  "in-band": { current: "100", recommended: "120", ratio: "0.2", limit: "0.3", source: "demo_risk_policy", calibrated: false, triggered: false, outcome: "NO_CONFLICT_EMITTED", reason: null, verdict: "UNVERIFIED" },
  "exact-boundary": { current: "100", recommended: "130", ratio: "0.3", limit: "0.3", source: "demo_risk_policy", calibrated: false, triggered: false, outcome: "NO_CONFLICT_EMITTED", reason: null, verdict: "UNVERIFIED" },
  conflict: { current: "100", recommended: "130.01", ratio: "0.3001", limit: "0.3", source: "demo_risk_policy", calibrated: false, triggered: true, outcome: "CONFLICT", reason: null, verdict: "CONFLICT" },
  "zero-baseline": { current: "0", recommended: "50", ratio: null, limit: "0.3", source: "demo_risk_policy", calibrated: false, triggered: null, outcome: "INSUFFICIENT_EVIDENCE", reason: "zero_current_budget", verdict: "INSUFFICIENT_EVIDENCE" },
  "missing-policy": { current: "100", recommended: "120", ratio: "0.2", limit: null, source: null, calibrated: null, triggered: null, outcome: "INSUFFICIENT_EVIDENCE", reason: "missing_policy", verdict: "INSUFFICIENT_EVIDENCE" },
});

function payloadFor(scenario) {
  const policy = POLICY_BY_SCENARIO[scenario];
  return {
    schema_version: "1.0",
    fixture_mode: true,
    scenario,
    release_identity: { ...RELEASE },
    client_id: "demo_client_001",
    plan: {
      schema_version: "1.0",
      plan_id: "plan_demo_001",
      source: "DEMO_OPTIMIZER_STUB",
      source_version: "1.0",
      is_optimized: true,
      period: { type: "next_14_days", start_date: "2026-08-01", end_date: "2026-08-14" },
      items: [{ plan_item_id: "plan_item_001", entity_type: "campaign", entity_id: "Sponsored Products", action: "increase_budget", delta_pct: policy.ratio, current_budget: policy.current, recommended_budget: policy.recommended, currency: "USD" }],
      decision_evidence: [{ fact_id: "decision_fact_001", plan_item_id: "plan_item_001", entity_type: "campaign", entity_id: "Sponsored Products", name: "predicted_roas", value: 4.2, unit: "ratio", period: "next_14_days", source: "demo_prediction_output", scope: "public_output" }],
      review_evidence: [{ fact_id: "review_fact_001", plan_item_id: "plan_item_001", entity_type: "campaign", entity_id: "Sponsored Products", name: "spend_share", value: 0.28, unit: "ratio", period: "current_snapshot", source: "demo_platform_output", scope: "ontology_review" }],
    },
    review: {
      schema_version: "1.0",
      review_id: `review_${scenario}`,
      plan_id: "plan_demo_001",
      source: "ONTOLOGY_ENGINE",
      ontology_version: "3.0-campaign-budget-policy",
      release_identity: { ...RELEASE },
      confidence_state_version: "1.0",
      is_synthetic: true,
      client_id: "demo_client_001",
      overall_verdict: policy.verdict,
      items: [{
        review_item_id: `review_item_${scenario}`,
        plan_item_id: "plan_item_001",
        verdict: policy.verdict,
        rule_id: "R5",
        rule_version: "3.0-budget-policy",
        base_confidence: "UNVERIFIED",
        runtime_confidence: "UNVERIFIED",
        matched_fact_ids: [],
        missing_evidence: [],
        missing_rule_parameters: [],
        limitations: ["Canonical limitation"],
        policy_evaluation: {
          policy_type: "campaign_budget_review_policy",
          policy_rule_id: "R5",
          policy_rule_version: "3.0-budget-policy",
          current_budget: policy.current,
          recommended_budget: policy.recommended,
          currency: "USD",
          absolute_change_ratio: policy.ratio,
          authorization_limit: policy.limit,
          policy_source: policy.source,
          production_calibrated: policy.calibrated,
          triggered: policy.triggered,
          outcome: policy.outcome,
          insufficiency_reason: policy.reason,
          next_step: `Next step for ${scenario}`,
        },
      }],
    },
  };
}

function paddedBytes(value, size) {
  const json = JSON.stringify(value);
  assert.ok(json.length <= size, "test fixture must fit the canonical byte size");
  return new TextEncoder().encode(json.padEnd(size, " "));
}

function fixtureSet() {
  const manifest = {
    schema_version: "1.0",
    suite_id: "gate-d-canonical-r5-v3",
    release_identity: { ...RELEASE },
    fixtures: FIXTURES.map((fixture) => ({ ...fixture })),
    import_identity: { source_commit: SOURCE_COMMIT, release_commit: RELEASE_COMMIT },
  };
  const payloads = Object.fromEntries(
    FIXTURES.map((fixture) => [fixture.file, payloadFor(fixture.scenario)]),
  );
  return { manifest, payloads };
}

function harness(set = fixtureSet()) {
  const requested = [];
  const fetcher = async (url, options) => {
    requested.push({ url, options });
    const file = url.split("/").at(-1);
    const value = file === "manifest.json" ? set.manifest : set.payloads[file];
    if (!value) return { ok: false, arrayBuffer: async () => new ArrayBuffer(0) };
    const size = file === "manifest.json"
      ? 1506
      : FIXTURES.find((fixture) => fixture.file === file).size;
    const bytes = paddedBytes(value, size);
    return { ok: true, arrayBuffer: async () => bytes.buffer };
  };
  const digest = async (bytes) => {
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    if (payload.suite_id) {
      return "a8b516ca01b4e22f2101426a1b695626f24b107ae560ed77702975f3155e2003";
    }
    return FIXTURES.find((fixture) => fixture.scenario === payload.scenario).sha256;
  };
  return { fetcher, digest, requested };
}

test("loads exactly five canonical engine scenarios in manifest order", async () => {
  const { fetcher, digest, requested } = harness();
  const scenarios = await loadOntologyReviewFixtures({ fetcher, digestBytes: digest });

  assert.equal(DEFAULT_ONTOLOGY_REVIEW_SCENARIO, "in-band");
  assert.deepEqual(scenarios.map(({ key }) => key), FIXTURES.map(({ scenario }) => scenario));
  assert.deepEqual(scenarios.map(({ review }) => review.verdict), [
    "UNVERIFIED",
    "UNVERIFIED",
    "CONFLICT",
    "INSUFFICIENT_EVIDENCE",
    "INSUFFICIENT_EVIDENCE",
  ]);
  assert.equal(scenarios[0].policy.absoluteChangeRatio, "0.2");
  assert.equal(scenarios[1].policy.absoluteChangeRatio, "0.3");
  assert.equal(scenarios[2].policy.recommendedBudget, "130.01");
  assert.equal(scenarios[3].policy.absoluteChangeRatio, null);
  assert.equal(scenarios[4].policy.authorizationLimit, null);
  assert.equal(scenarios[4].policy.source, null);
  assert.ok(Object.isFrozen(scenarios));
  assert.ok(Object.isFrozen(scenarios[0].policy));
  assert.equal(requested.length, 6);
  for (const { url, options } of requested) {
    assert.match(url, /^(?:\.\/|\/)data\/ontology-review\//);
    assert.equal(options.cache, "no-store");
    assert.equal(options.credentials, "same-origin");
    assert.ok(options.signal instanceof AbortSignal);
  }
});

test("real canonical bytes load through default WebCrypto end to end", async () => {
  const files = new Map([["manifest.json", canonicalReleaseManifestBytes()]]);
  for (const { file } of FIXTURES) {
    files.set(file, await readFile(join(DEFAULT_SOURCE, file)));
  }
  const fetcher = async (url) => {
    const bytes = files.get(url.split("/").at(-1));
    if (!bytes) return { ok: false, arrayBuffer: async () => new ArrayBuffer(0) };
    return {
      ok: true,
      arrayBuffer: async () => bytes.buffer.slice(
        bytes.byteOffset,
        bytes.byteOffset + bytes.byteLength,
      ),
    };
  };

  const scenarios = await loadOntologyReviewFixtures({ fetcher });
  assert.deepEqual(scenarios.map(({ key }) => key), FIXTURES.map(({ scenario }) => scenario));
});
test("root importer pins and validates the same canonical identities", () => {
  const set = fixtureSet();
  const { import_identity: _importIdentity, ...sourceManifest } = set.manifest;
  assert.equal(CANONICAL_SOURCE_COMMIT, SOURCE_COMMIT);
  assert.equal(CANONICAL_RELEASE_COMMIT, RELEASE_COMMIT);
  assert.deepEqual(CANONICAL_FIXTURES, FIXTURES);
  assert.doesNotThrow(() => validateCanonicalManifest(sourceManifest));
  FIXTURES.forEach((expected) => {
    assert.doesNotThrow(() =>
      validateCanonicalPayload(set.payloads[expected.file], expected),
    );
  });

  set.payloads["conflict.json"].review.items[0].policy_evaluation.policy_rule_id = "R4";
  assert.throws(
    () => validateCanonicalPayload(set.payloads["conflict.json"], FIXTURES[2]),
    /policy_rule_id must be "R5"/,
  );
});

test("source manifest bytes are pinned before JSON parsing", async (t) => {
  const canonical = await readFile(join(DEFAULT_SOURCE, "manifest.json"));
  assert.equal(canonical.byteLength, CANONICAL_SOURCE_MANIFEST_SIZE);
  assert.equal(CANONICAL_SOURCE_MANIFEST_SHA256, "5f182e2f56550a7ba8d96959b712fea88f39d1f13867c1291d1e92969f86fd7e");
  assert.doesNotThrow(() => validateCanonicalSourceManifestBytes(canonical));

  await t.test("trailing whitespace", () => {
    const altered = Buffer.concat([canonical, Buffer.from(" ")]);
    assert.throws(
      () => validateCanonicalSourceManifestBytes(altered),
      /source manifest byte size must be 1348/,
    );
  });

  await t.test("CRLF conversion", () => {
    const altered = Buffer.from(canonical.toString("utf8").replaceAll("\n", "\r\n"));
    assert.throws(
      () => validateCanonicalSourceManifestBytes(altered),
      /source manifest byte size must be 1348/,
    );
  });

  await t.test("same-size tamper", () => {
    const altered = Buffer.from(canonical);
    const offset = altered.indexOf(Buffer.from("gate-d-canonical-r5-v3"));
    assert.notEqual(offset, -1);
    altered[offset] = "G".charCodeAt(0);
    assert.throws(
      () => validateCanonicalSourceManifestBytes(altered),
      /source manifest SHA-256 must be/,
    );
  });
});

async function writePublishedFixtureBundle(directory) {
  await mkdir(directory, { recursive: true });
  await writeFile(join(directory, "manifest.json"), canonicalReleaseManifestBytes());
  for (const { file } of FIXTURES) {
    await copyFile(join(DEFAULT_SOURCE, file), join(directory, file));
  }
}

test("published verifier requires the one canonical release-manifest byte sequence", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-release-manifest-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const directory = join(root, "ontology-review");
  await writePublishedFixtureBundle(directory);
  await assert.doesNotReject(verifyPublishedOntologyReviewBundle(directory));
  const canonical = canonicalReleaseManifestBytes();

  for (const [label, alter] of [
    ["trailing whitespace", (bytes) => Buffer.concat([bytes, Buffer.from(" ")])],
    ["CRLF conversion", (bytes) => Buffer.from(bytes.toString("utf8").replaceAll("\n", "\r\n"))],
    ["same-size tamper", (bytes) => Buffer.from(bytes.toString("utf8").replace(RELEASE_COMMIT, `${RELEASE_COMMIT.slice(0, -1)}0`))],
  ]) {
    await t.test(label, async () => {
      await writeFile(join(directory, "manifest.json"), alter(canonical));
      await assert.rejects(
        verifyPublishedOntologyReviewBundle(directory),
        /published manifest bytes must match the canonical generated release manifest/,
      );
    });
  }
});

test("published verifier rejects a linked bundle root", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-linked-root-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const actual = join(root, "actual");
  const alias = join(root, "ontology-review");
  await writePublishedFixtureBundle(actual);
  try {
    await symlink(actual, alias, process.platform === "win32" ? "junction" : "dir");
  } catch (error) {
    if (["EPERM", "EACCES", "ENOSYS"].includes(error?.code)) {
      t.skip(`directory links unavailable: ${error.code}`);
      return;
    }
    throw error;
  }
  await assert.rejects(
    verifyPublishedOntologyReviewBundle(alias),
    /must be a real directory, not a link/,
  );
});
test("published verifier rejects hard-linked fixture files", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-hard-link-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writePublishedFixtureBundle(root);
  const linkedFixture = join(root, "conflict.json");
  await rm(linkedFixture);
  await link(join(root, "in-band.json"), linkedFixture);
  await assert.rejects(
    verifyPublishedOntologyReviewBundle(root),
    /must be a regular file, not a link/,
  );
});
test("source and imported manifests reject unknown fields", async (t) => {
  await t.test("source manifest top level", () => {
    const set = fixtureSet();
    const { import_identity: _importIdentity, ...sourceManifest } = set.manifest;
    sourceManifest.unknown = true;
    assert.throws(() => validateCanonicalManifest(sourceManifest), /manifest keys must be exactly/);
  });

  await t.test("browser manifest top level", async () => {
    const set = fixtureSet();
    set.manifest.unknown = true;
    const { fetcher, digest } = harness(set);
    await assert.rejects(
      loadOntologyReviewFixtures({ fetcher, digestBytes: digest }),
      /manifest field set/,
    );
  });

  await t.test("browser import identity", async () => {
    const set = fixtureSet();
    set.manifest.import_identity.unknown = true;
    const { fetcher, digest } = harness(set);
    await assert.rejects(
      loadOntologyReviewFixtures({ fetcher, digestBytes: digest }),
      /manifest\.import_identity field set/,
    );
  });
});

test("deployment-root fixture URLs are independent of hash routes", () => {
  assert.equal(buildOntologyReviewDataRoot("/"), "/data/ontology-review");
  assert.equal(
    buildOntologyReviewDataRoot("/marketing-roi-analysis/"),
    "/marketing-roi-analysis/data/ontology-review",
  );
  assert.equal(buildOntologyReviewDataRoot("./"), "./data/ontology-review");
  assert.equal(buildOntologyReviewDataRoot("/preview"), "/preview/data/ontology-review");
  assert.throws(() => buildOntologyReviewDataRoot("/preview/?route=bad"), /invalid deployment base/);
  assert.throws(() => buildOntologyReviewDataRoot("/preview/#deep"), /invalid deployment base/);
});

test("loader forwards one bounded internal signal to every fixture request", async () => {
  const controller = new AbortController();
  const { fetcher, digest, requested } = harness();
  await loadOntologyReviewFixtures({
    signal: controller.signal,
    fetcher,
    digestBytes: digest,
  });
  assert.equal(requested.length, 6);
  const internalSignal = requested[0].options.signal;
  assert.notEqual(internalSignal, controller.signal);
  assert.equal(internalSignal.aborted, false);
  for (const { options } of requested) assert.equal(options.signal, internalSignal);
});

test("timeout fails closed even when a fetcher ignores abort", async () => {
  let observedSignal;
  await assert.rejects(
    loadOntologyReviewFixtures({
      timeoutMs: 5,
      fetcher: async (_url, options) => {
        observedSignal = options.signal;
        return new Promise(() => {});
      },
    }),
    /loading timed out after 0.005 seconds/,
  );
  assert.equal(observedSignal.aborted, true);
});

test("preserves distinct non-approval, conflict, and insufficiency meanings", async () => {
  const { fetcher, digest } = harness();
  const scenarios = await loadOntologyReviewFixtures({ fetcher, digestBytes: digest });
  const byKey = Object.fromEntries(scenarios.map((scenario) => [scenario.key, scenario]));

  assert.match(byKey["in-band"].explanation, /not approval/i);
  assert.match(byKey["exact-boundary"].explanation, /strict > comparison/);
  assert.match(byKey.conflict.explanation, /does not mean the optimizer failed/i);
  assert.equal(byKey["zero-baseline"].policy.insufficiencyReason, "zero_current_budget");
  assert.equal(byKey["missing-policy"].policy.insufficiencyReason, "missing_policy");
  assert.match(byKey.conflict.availability[0], /not an industry benchmark/i);
});

test("rejects digest and identity tampering before exposing scenarios", async (t) => {
  await t.test("fixture digest", async () => {
    const { fetcher } = harness();
    await assert.rejects(
      loadOntologyReviewFixtures({
        fetcher,
        digestBytes: async () => "0".repeat(64),
      }),
      /SHA-256 does not match/,
    );
  });

  for (const [label, tamper, pattern] of [
    ["release", (set) => { set.manifest.release_identity.engine_version = "forged"; }, /engine_version/],
    ["client", (set) => { set.payloads["in-band.json"].client_id = "forged"; }, /client/],
    ["plan link", (set) => { set.payloads["in-band.json"].review.plan_id = "forged"; }, /review plan/],
    ["item link", (set) => { set.payloads["in-band.json"].review.items[0].plan_item_id = "forged"; }, /item linkage/],
    ["rule", (set) => { set.payloads["in-band.json"].review.items[0].policy_evaluation.policy_rule_id = "R4"; }, /rule/],
    ["release commit", (set) => { set.manifest.import_identity.release_commit = "forged"; }, /release commit/],
  ]) {
    await t.test(label, async () => {
      const set = fixtureSet();
      tamper(set);
      const { fetcher, digest } = harness(set);
      await assert.rejects(
        loadOntologyReviewFixtures({ fetcher, digestBytes: digest }),
        pattern,
      );
    });
  }
});

test("rejects absent and reordered manifest entries", async (t) => {
  await t.test("absent manifest", async () => {
    const { digest } = harness();
    await assert.rejects(
      loadOntologyReviewFixtures({
        fetcher: async () => ({ ok: false }),
        digestBytes: digest,
      }),
      /manifest\.json could not be loaded/,
    );
  });

  await t.test("reordered fixtures", async () => {
    const set = fixtureSet();
    set.manifest.fixtures.reverse();
    const { fetcher, digest } = harness(set);
    await assert.rejects(
      loadOntologyReviewFixtures({ fetcher, digestBytes: digest }),
      /manifest fixture 1/,
    );
  });
});

test("import paths reject self, nesting, and resolved aliases", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-paths-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const publicData = join(root, "dashboard", "public", "data");
  const output = join(publicData, "ontology-review");
  const source = join(root, "canonical-source");
  await mkdir(output, { recursive: true });
  await mkdir(source, { recursive: true });

  await assert.doesNotReject(
    validateImportPathSeparation({
      sourceDirectory: source,
      outputDirectory: output,
      publicDataRoot: publicData,
      projectRoot: root,
    }),
  );
  await assert.rejects(
    validateImportPathSeparation({
      sourceDirectory: output,
      outputDirectory: output,
      publicDataRoot: publicData,
      projectRoot: root,
    }),
    /same path or contain one another/,
  );
  await assert.rejects(
    validateImportPathSeparation({
      sourceDirectory: publicData,
      outputDirectory: output,
      publicDataRoot: publicData,
      projectRoot: root,
    }),
    /same path or contain one another/,
  );
  await assert.rejects(
    validateImportPathSeparation({
      sourceDirectory: source,
      outputDirectory: join(source, "nested-output"),
      publicDataRoot: root,
      projectRoot: join(root, ".."),
    }),
    /same path or contain one another/,
  );

  await t.test("directory alias", async (subtest) => {
    const alias = join(root, "source-alias");
    try {
      await symlink(output, alias, process.platform === "win32" ? "junction" : "dir");
    } catch (error) {
      if (["EPERM", "EACCES", "ENOSYS"].includes(error?.code)) {
        subtest.skip(`directory links unavailable: ${error.code}`);
        return;
      }
      throw error;
    }
    await assert.rejects(
      validateImportPathSeparation({
        sourceDirectory: alias,
        outputDirectory: output,
        publicDataRoot: publicData,
        projectRoot: root,
      }),
      /same path or contain one another/,
    );
  });

  await t.test("output junction escaping public data", async (subtest) => {
    const outside = join(root, "outside");
    const escapedOutput = join(publicData, "escaped-output");
    await mkdir(outside, { recursive: true });
    try {
      await symlink(
        outside,
        escapedOutput,
        process.platform === "win32" ? "junction" : "dir",
      );
    } catch (error) {
      if (["EPERM", "EACCES", "ENOSYS"].includes(error?.code)) {
        subtest.skip(`directory links unavailable: ${error.code}`);
        return;
      }
      throw error;
    }
    await assert.rejects(
      validateImportPathSeparation({
        sourceDirectory: source,
        outputDirectory: escapedOutput,
        publicDataRoot: publicData,
        projectRoot: root,
      }),
      /resolved output must stay below/,
    );
  });

  await t.test("public data junction escaping the project", async (subtest) => {
    const project = join(root, "public-data-junction-project");
    const linkedPublicParent = join(project, "dashboard", "public");
    const linkedPublicData = join(linkedPublicParent, "data");
    const outside = join(root, "public-data-junction-outside");
    const linkedSource = join(project, "canonical-source");
    await mkdir(linkedPublicParent, { recursive: true });
    await mkdir(outside, { recursive: true });
    await mkdir(linkedSource, { recursive: true });
    try {
      await symlink(
        outside,
        linkedPublicData,
        process.platform === "win32" ? "junction" : "dir",
      );
    } catch (error) {
      if (["EPERM", "EACCES", "ENOSYS"].includes(error?.code)) {
        subtest.skip(`directory links unavailable: ${error.code}`);
        return;
      }
      throw error;
    }
    await assert.rejects(
      validateImportPathSeparation({
        sourceDirectory: linkedSource,
        outputDirectory: join(linkedPublicData, "ontology-review"),
        publicDataRoot: linkedPublicData,
        projectRoot: project,
      }),
      /resolved dashboard\/public\/data must stay below the project root/,
    );
  });

  await t.test("dashboard ancestor junction escaping the project", async (subtest) => {
    const project = join(root, "dashboard-junction-project");
    const outsideDashboard = join(root, "dashboard-junction-outside");
    const linkedDashboard = join(project, "dashboard");
    const linkedPublicData = join(linkedDashboard, "public", "data");
    const linkedSource = join(project, "canonical-source");
    await mkdir(project, { recursive: true });
    await mkdir(join(outsideDashboard, "public", "data"), { recursive: true });
    await mkdir(linkedSource, { recursive: true });
    try {
      await symlink(
        outsideDashboard,
        linkedDashboard,
        process.platform === "win32" ? "junction" : "dir",
      );
    } catch (error) {
      if (["EPERM", "EACCES", "ENOSYS"].includes(error?.code)) {
        subtest.skip(`directory links unavailable: ${error.code}`);
        return;
      }
      throw error;
    }
    await assert.rejects(
      validateImportPathSeparation({
        sourceDirectory: linkedSource,
        outputDirectory: join(linkedPublicData, "ontology-review"),
        publicDataRoot: linkedPublicData,
        projectRoot: project,
      }),
      /resolved dashboard\/public\/data must stay below the project root/,
    );
  });
});

async function seedDirectory(destination, value) {
  await mkdir(destination, { recursive: true });
  await writeFile(join(destination, "marker.txt"), value, "utf8");
}

async function assertNoSwapResidue(parent) {
  const names = await readdir(parent);
  assert.equal(
    names.filter((name) =>
      /^\.ontology-review\.(?:import-|backup-|lock(?:$|-release-))/.test(name),
    ).length,
    0,
  );
}

test("concurrent destination exchange admits exactly one importer", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-lock-concurrent-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const destination = join(root, "ontology-review");
  await seedDirectory(destination, "old");

  let signalHolderStarted;
  const holderStarted = new Promise((resolve) => {
    signalHolderStarted = resolve;
  });
  let releaseHolder;
  const holderMayFinish = new Promise((resolve) => {
    releaseHolder = resolve;
  });
  const holder = replaceDirectoryWithLock({
    destination,
    suffix: "holder",
    populate: async (temporary) => {
      await writeFile(join(temporary, "marker.txt"), "new", "utf8");
      signalHolderStarted();
      await holderMayFinish;
    },
    verify: async (temporary) => {
      assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
    },
  });
  await holderStarted;

  let contenderEntered = false;
  await assert.rejects(
    replaceDirectoryWithLock({
      destination,
      suffix: "contender",
      populate: async () => {
        contenderEntered = true;
      },
      verify: () => assert.fail("a contender must not reach verification"),
    }),
    /import lock is already held/,
  );
  assert.equal(contenderEntered, false);
  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "old");

  releaseHolder();
  await holder;
  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "new");
  await assertNoSwapResidue(root);
});

test("a holder never releases a successor owner token", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-lock-successor-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const destination = join(root, "ontology-review");
  const lock = join(root, ".ontology-review.lock");
  await seedDirectory(destination, "old");

  let signalPopulatePaused;
  const populatePaused = new Promise((resolve) => {
    signalPopulatePaused = resolve;
  });
  let releasePopulate;
  const populateMayFinish = new Promise((resolve) => {
    releasePopulate = resolve;
  });
  let holderReachedExchange = false;
  const holder = replaceDirectoryWithLock({
    destination,
    suffix: "displaced-holder",
    populate: async (temporary) => {
      await writeFile(join(temporary, "marker.txt"), "new", "utf8");
      signalPopulatePaused();
      await populateMayFinish;
    },
    verify: async (temporary) => {
      assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
    },
    beforeExchange: () => {
      holderReachedExchange = true;
    },
  });
  await populatePaused;

  const displacedToken = await readFile(lock, "utf8");
  assert.ok(displacedToken);
  await rm(lock, { force: true });
  const successorToken = "successor-owner-token";
  await writeFile(lock, successorToken, { encoding: "utf8", flag: "wx" });
  releasePopulate();

  await assert.rejects(holder, (error) => {
    assert.ok(error instanceof AggregateError);
    assert.match(error.message, /lock could not be released safely/);
    assert.ok(
      error.errors.every((item) => item.code === "IMPORT_LOCK_OWNERSHIP_LOST"),
    );
    return true;
  });
  assert.equal(holderReachedExchange, false);
  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "old");
  assert.equal(await readFile(lock, "utf8"), successorToken);
  const names = await readdir(root);
  assert.equal(names.some((name) => /\.ontology-review\.(?:import-|backup-)/.test(name)), false);
  const recovery = names.filter((name) => name.startsWith(".ontology-review.lock-release-"));
  assert.equal(recovery.length, 1);
  assert.equal(await readFile(join(root, recovery[0]), "utf8"), successorToken);
});

test("release atomically claims and preserves a lock replaced at rename", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-lock-release-race-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const destination = join(root, "ontology-review");
  const lock = join(root, ".ontology-review.lock");
  const successorToken = "release-race-successor";
  await seedDirectory(destination, "old");

  let replaced = false;
  const operations = {
    rename: async (from, to) => {
      if (!replaced && from === lock && to.includes(".lock-release-")) {
        const holderToken = await readFile(lock, "utf8");
        assert.notEqual(holderToken, successorToken);
        await rm(lock, { force: true });
        await writeFile(lock, successorToken, { encoding: "utf8", flag: "wx" });
        replaced = true;
      }
      return rename(from, to);
    },
  };

  let ownershipError;
  await assert.rejects(
    replaceDirectoryWithLock({
      destination,
      suffix: "release-race",
      operations,
      populate: (temporary) => writeFile(join(temporary, "marker.txt"), "new", "utf8"),
      verify: async (temporary) => {
        assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
      },
    }),
    (error) => {
      assert.equal(error.code, "IMPORT_LOCK_OWNERSHIP_LOST");
      assert.equal(error.lockRestored, true);
      assert.match(error.recoveryPath, /\.ontology-review\.lock-release-/);
      assert.match(error.message, new RegExp(error.recoveryPath.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
      ownershipError = error;
      return true;
    },
  );

  assert.equal(replaced, true);
  assert.equal(await readFile(ownershipError.recoveryPath, "utf8"), successorToken);
  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "new");
  assert.equal(await readFile(lock, "utf8"), successorToken);
  const names = await readdir(root);
  assert.equal(names.some((name) => /\.ontology-review\.(?:import-|backup-)/.test(name)), false);
  assert.equal(names.filter((name) => name.startsWith(".ontology-review.lock-release-")).length, 1);
});

test("backup cleanup failure preserves the installed bundle and recovery copy", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-backup-recovery-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const destination = join(root, "ontology-review");
  const backup = join(root, ".ontology-review.backup-cleanup-failure");
  await seedDirectory(destination, "old");

  await assert.rejects(
    replaceDirectoryWithLock({
      destination,
      suffix: "cleanup-failure",
      operations: {
        rm: async (path, options) => {
          if (path === backup) {
            const error = new Error("injected backup cleanup failure");
            error.code = "EACCES";
            throw error;
          }
          return rm(path, options);
        },
      },
      populate: (temporary) => writeFile(join(temporary, "marker.txt"), "new", "utf8"),
      verify: async (temporary) => {
        assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
      },
    }),
    /injected backup cleanup failure/,
  );

  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "new");
  assert.equal(await readFile(join(backup, "marker.txt"), "utf8"), "old");
  const names = await readdir(root);
  assert.equal(names.some((name) => name.includes(".import-")), false);
  assert.equal(names.some((name) => name.includes(".lock")), false);
});
test("an existing import lock leaves destination untouched", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "ontology-lock-existing-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const destination = join(root, "ontology-review");
  const lock = join(root, ".ontology-review.lock");
  await seedDirectory(destination, "old");
  await writeFile(lock, "other-owner-token", { encoding: "utf8", flag: "wx" });

  let entered = false;
  await assert.rejects(
    replaceDirectoryWithLock({
      destination,
      suffix: "blocked",
      populate: async () => {
        entered = true;
      },
      verify: () => assert.fail("a blocked importer must not verify"),
    }),
    /import lock is already held/,
  );
  assert.equal(entered, false);
  assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "old");
  assert.deepEqual((await readdir(root)).sort(), [".ontology-review.lock", "ontology-review"]);
});

test("atomic directory replacement preserves the previous valid output", async (t) => {
  await t.test("successful verified exchange", async (subtest) => {
    const root = await mkdtemp(join(tmpdir(), "ontology-swap-success-"));
    subtest.after(() => rm(root, { recursive: true, force: true }));
    const destination = join(root, "ontology-review");
    await seedDirectory(destination, "old");
    await replaceDirectoryWithLock({
      destination,
      suffix: "success",
      populate: (temporary) => writeFile(join(temporary, "marker.txt"), "new", "utf8"),
      verify: async (temporary) => {
        assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
      },
    });
    assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "new");
    await assertNoSwapResidue(root);
  });

  await t.test("write failure", async (subtest) => {
    const root = await mkdtemp(join(tmpdir(), "ontology-swap-write-"));
    subtest.after(() => rm(root, { recursive: true, force: true }));
    const destination = join(root, "ontology-review");
    await seedDirectory(destination, "old");
    await assert.rejects(
      replaceDirectoryWithLock({
        destination,
        suffix: "write-failure",
        populate: async (temporary) => {
          await writeFile(join(temporary, "marker.txt"), "partial", "utf8");
          throw new Error("injected write failure");
        },
        verify: () => assert.fail("partial data must not be verified"),
      }),
      /injected write failure/,
    );
    assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "old");
    await assertNoSwapResidue(root);
  });

  await t.test("exchange failure", async (subtest) => {
    const root = await mkdtemp(join(tmpdir(), "ontology-swap-exchange-"));
    subtest.after(() => rm(root, { recursive: true, force: true }));
    const destination = join(root, "ontology-review");
    await seedDirectory(destination, "old");
    const operations = {
      mkdir,
      rm,
      rename: async (from, to) => {
        if (from.includes(".ontology-review.import-") && to === destination) {
          const error = new Error("injected exchange failure");
          error.code = "EACCES";
          throw error;
        }
        return rename(from, to);
      },
    };
    await assert.rejects(
      replaceDirectoryWithLock({
        destination,
        operations,
        suffix: "exchange-failure",
        populate: (temporary) => writeFile(join(temporary, "marker.txt"), "new", "utf8"),
        verify: async (temporary) => {
          assert.equal(await readFile(join(temporary, "marker.txt"), "utf8"), "new");
        },
      }),
      /injected exchange failure/,
    );
    assert.equal(await readFile(join(destination, "marker.txt"), "utf8"), "old");
    await assertNoSwapResidue(root);
  });
});
