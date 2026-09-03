/**
 * Verify the canonical Gate D R5 fixture suite and import ignored dashboard assets.
 *
 * This root command is the trust boundary between the external canonical release
 * and the browser-facing display adapter. It validates every byte before writing.
 */

import { execFile } from "node:child_process";
import { createHash, randomUUID, timingSafeEqual } from "node:crypto";
import {
  link,
  lstat,
  mkdir,
  readFile,
  readdir,
  realpath,
  rename,
  rm,
  writeFile,
} from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

export const CANONICAL_SOURCE_COMMIT =
  "816958b7c5fa44cedf55408a0797fea93b1f44bc";
export const CANONICAL_RELEASE_COMMIT =
  "cf5f2a7b78fb3d384f6d4fd815c830dfc2c21363";
export const CANONICAL_SUITE_ID = "gate-d-canonical-r5-v3";
export const CANONICAL_SOURCE_MANIFEST_SIZE = 1348;
export const CANONICAL_SOURCE_MANIFEST_SHA256 =
  "5f182e2f56550a7ba8d96959b712fea88f39d1f13867c1291d1e92969f86fd7e";

export const CANONICAL_RELEASE_IDENTITY = Object.freeze({
  ontology_version: "3.0-campaign-budget-policy",
  rule_version: "R5@3.0-budget-policy",
  engine_version: "3.0",
  schema_version: "2.0",
  source_commit: CANONICAL_SOURCE_COMMIT,
  package_checksum:
    "23aefa15460399623b82cd83a9708397ddafd8af7a1572cf73a1e8eee1199926",
});

export const CANONICAL_FIXTURES = Object.freeze([
  Object.freeze({
    file: "in-band.json",
    scenario: "in-band",
    sha256: "6f6b67a60b796d11e304be387d34f68a3e67f7f0431a26b308d52194adb057d4",
    size: 4552,
  }),
  Object.freeze({
    file: "exact-boundary.json",
    scenario: "exact-boundary",
    sha256: "4bcbcccf6ef4fc7b11b5699c6fedd3244b72c359ee4e5a98c69c1e3577300f85",
    size: 4559,
  }),
  Object.freeze({
    file: "conflict.json",
    scenario: "conflict",
    sha256: "1a5b71680eef72c499b56cbe8c8c44db325a8f313794484414812331b483e602",
    size: 4575,
  }),
  Object.freeze({
    file: "zero-baseline.json",
    scenario: "zero-baseline",
    sha256: "3556810aeb27f845d5aae968b1d4c862e0bf1a505e2126215d2bf37052eeb1e3",
    size: 4647,
  }),
  Object.freeze({
    file: "missing-policy.json",
    scenario: "missing-policy",
    sha256: "b06d18d9aaf5cbae935120d87bef67be3c0eef0f56af55a58d2cdd2a8e32d367",
    size: 4656,
  }),
]);

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const DEFAULT_SOURCE = join(
  PROJECT_ROOT,
  "dashboard",
  "fixtures",
  "ontology_review",
  "canonical_r5_v3",
);
const PUBLIC_DATA_ROOT = join(PROJECT_ROOT, "dashboard", "public", "data");
export const DEFAULT_OUTPUT = join(
  PROJECT_ROOT,
  "dashboard",
  "public",
  "data",
  "ontology-review",
);
const EXPECTED_CLIENT_ID = "demo_client_001";
const EXPECTED_PLAN_ID = "plan_demo_001";
const EXACT_FILES = Object.freeze([
  "manifest.json",
  ...CANONICAL_FIXTURES.map(({ file }) => file),
]);
const execFileAsync = promisify(execFile);

function fail(message) {
  throw new Error(`Canonical fixture validation failed: ${message}`);
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) fail(`${label} must be ${JSON.stringify(expected)}`);
}

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    fail(`${label} must be an object`);
  }
}

function assertExactKeys(value, expected, label) {
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    fail(`${label} keys must be exactly ${wanted.join(", ")}`);
  }
}

function validateReleaseIdentity(identity, label) {
  assertObject(identity, label);
  for (const [field, expected] of Object.entries(CANONICAL_RELEASE_IDENTITY)) {
    assertEqual(identity[field], expected, `${label}.${field}`);
  }
  assertEqual(Object.keys(identity).length, 6, `${label} field count`);
}

export function validateCanonicalManifest(manifest) {
  assertObject(manifest, "manifest");
  assertExactKeys(
    manifest,
    ["schema_version", "suite_id", "release_identity", "fixtures"],
    "manifest",
  );
  assertEqual(manifest.schema_version, "1.0", "manifest.schema_version");
  assertEqual(manifest.suite_id, CANONICAL_SUITE_ID, "manifest.suite_id");
  validateReleaseIdentity(manifest.release_identity, "manifest.release_identity");
  if (!Array.isArray(manifest.fixtures)) fail("manifest.fixtures must be an array");
  assertEqual(manifest.fixtures.length, CANONICAL_FIXTURES.length, "fixture count");
  CANONICAL_FIXTURES.forEach((expected, index) => {
    const actual = manifest.fixtures[index];
    assertObject(actual, `manifest.fixtures[${index}]`);
    for (const [field, value] of Object.entries(expected)) {
      assertEqual(actual[field], value, `manifest.fixtures[${index}].${field}`);
    }
    assertEqual(Object.keys(actual).length, 4, `manifest.fixtures[${index}] field count`);
  });
}

export function validateCanonicalPayload(payload, expected) {
  assertObject(payload, expected.file);
  assertExactKeys(payload, ["schema_version", "fixture_mode", "scenario", "release_identity", "client_id", "plan", "review"], expected.file);
  assertEqual(payload.schema_version, "1.0", `${expected.file}.schema_version`);
  assertEqual(payload.fixture_mode, true, `${expected.file}.fixture_mode`);
  assertEqual(payload.scenario, expected.scenario, `${expected.file}.scenario`);
  validateReleaseIdentity(payload.release_identity, `${expected.file}.release_identity`);
  assertEqual(payload.client_id, EXPECTED_CLIENT_ID, `${expected.file}.client_id`);

  assertObject(payload.plan, `${expected.file}.plan`);
  assertExactKeys(payload.plan, ["schema_version", "plan_id", "source", "source_version", "is_optimized", "period", "items", "decision_evidence", "review_evidence"], `${expected.file}.plan`);
  assertEqual(payload.plan.plan_id, EXPECTED_PLAN_ID, `${expected.file}.plan.plan_id`);
  assertObject(payload.plan.period, `${expected.file}.plan.period`);
  assertExactKeys(payload.plan.period, ["type", "start_date", "end_date"], `${expected.file}.plan.period`);
  if (!Array.isArray(payload.plan.items) || payload.plan.items.length !== 1) fail(`${expected.file}.plan.items must contain exactly one item`);
  assertExactKeys(payload.plan.items[0], ["plan_item_id", "entity_type", "entity_id", "action", "delta_pct", "current_budget", "recommended_budget", "currency"], `${expected.file}.plan.items[0]`);
  for (const [name, facts] of [["decision_evidence", payload.plan.decision_evidence], ["review_evidence", payload.plan.review_evidence]]) {
    if (!Array.isArray(facts)) fail(`${expected.file}.plan.${name} must be an array`);
    facts.forEach((fact, index) => assertExactKeys(fact, ["fact_id", "plan_item_id", "entity_type", "entity_id", "name", "value", "unit", "period", "source", "scope"], `${expected.file}.plan.${name}[${index}]`));
  }

  assertObject(payload.review, `${expected.file}.review`);
  assertExactKeys(payload.review, ["schema_version", "review_id", "plan_id", "source", "ontology_version", "release_identity", "confidence_state_version", "is_synthetic", "client_id", "overall_verdict", "items"], `${expected.file}.review`);
  assertEqual(payload.review.source, "ONTOLOGY_ENGINE", `${expected.file}.review.source`);
  assertEqual(payload.review.is_synthetic, true, `${expected.file}.review.is_synthetic`);
  assertEqual(payload.review.client_id, EXPECTED_CLIENT_ID, `${expected.file}.review.client_id`);
  assertEqual(payload.review.plan_id, EXPECTED_PLAN_ID, `${expected.file}.review.plan_id`);
  validateReleaseIdentity(payload.review.release_identity, `${expected.file}.review.release_identity`);
  if (!Array.isArray(payload.review.items) || payload.review.items.length !== 1) fail(`${expected.file}.review.items must contain exactly one item`);

  const planItem = payload.plan.items[0];
  const reviewItem = payload.review.items[0];
  assertExactKeys(reviewItem, ["review_item_id", "plan_item_id", "verdict", "rule_id", "rule_version", "base_confidence", "runtime_confidence", "matched_fact_ids", "missing_evidence", "missing_rule_parameters", "limitations", "policy_evaluation"], `${expected.file}.review.items[0]`);
  assertEqual(reviewItem.plan_item_id, planItem.plan_item_id, `${expected.file} plan/review item linkage`);
  assertObject(reviewItem.policy_evaluation, `${expected.file}.policy_evaluation`);
  assertExactKeys(reviewItem.policy_evaluation, ["policy_type", "policy_rule_id", "policy_rule_version", "current_budget", "recommended_budget", "currency", "absolute_change_ratio", "authorization_limit", "policy_source", "production_calibrated", "triggered", "outcome", "insufficiency_reason", "next_step"], `${expected.file}.policy_evaluation`);
  assertEqual(reviewItem.policy_evaluation.policy_rule_id, "R5", `${expected.file}.policy_rule_id`);
  assertEqual(reviewItem.policy_evaluation.policy_rule_version, "3.0-budget-policy", `${expected.file}.policy_rule_version`);
  if (![false, null].includes(reviewItem.policy_evaluation.production_calibrated)) fail(`${expected.file}.production_calibrated must be false or null`);

  const serialized = JSON.stringify(payload);
  if (/\b(?:password|secret|access[_-]?token|api[_-]?key|connection[_-]?string)\b/i.test(serialized) || /[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/.test(serialized)) {
    fail(`${expected.file} contains a forbidden public-data field or value`);
  }
}

async function assertExactRegularFiles(directory, label) {
  const directoryMetadata = await lstat(directory);
  if (!directoryMetadata.isDirectory() || directoryMetadata.isSymbolicLink()) {
    fail(`${label} must be a real directory, not a link`);
  }
  const entries = await readdir(directory, { withFileTypes: true });
  const actual = entries.map(({ name }) => name).sort();
  const expected = [...EXACT_FILES].sort();
  if (actual.length !== expected.length || actual.some((name, index) => name !== expected[index])) {
    fail(`${label} must contain exactly ${expected.join(", ")}`);
  }
  for (const entry of entries) {
    const metadata = await lstat(join(directory, entry.name));
    if (!entry.isFile() || entry.isSymbolicLink() || !metadata.isFile() || metadata.isSymbolicLink() || metadata.nlink !== 1) {
      fail(`${label}/${entry.name} must be a regular file, not a link`);
    }
  }
}

function parseJson(bytes, label) {
  try {
    return JSON.parse(bytes.toString("utf8"));
  } catch {
    fail(`${label} must be valid JSON`);
  }
}
function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

export function validateCanonicalSourceManifestBytes(bytes) {
  assertEqual(
    bytes.byteLength,
    CANONICAL_SOURCE_MANIFEST_SIZE,
    "source manifest byte size",
  );
  assertEqual(
    sha256(bytes),
    CANONICAL_SOURCE_MANIFEST_SHA256,
    "source manifest SHA-256",
  );
  const manifest = parseJson(bytes, "source manifest");
  validateCanonicalManifest(manifest);
  return manifest;
}

function canonicalReleaseManifest() {
  return {
    schema_version: "1.0",
    suite_id: CANONICAL_SUITE_ID,
    release_identity: { ...CANONICAL_RELEASE_IDENTITY },
    fixtures: CANONICAL_FIXTURES.map((fixture) => ({ ...fixture })),
    import_identity: {
      source_commit: CANONICAL_SOURCE_COMMIT,
      release_commit: CANONICAL_RELEASE_COMMIT,
    },
  };
}

export function canonicalReleaseManifestBytes() {
  return Buffer.from(`${JSON.stringify(canonicalReleaseManifest(), null, 2)}\n`, "utf8");
}

function assertCanonicalReleaseManifestBytes(bytes, label) {
  if (!Buffer.from(bytes).equals(canonicalReleaseManifestBytes())) {
    fail(`${label} bytes must match the canonical generated release manifest`);
  }
}

function isWithin(parent, child) {
  const relation = relative(parent, child);
  return relation === "" || (!relation.startsWith("..") && !isAbsolute(relation));
}

async function prospectiveRealpath(path, realpathFn = realpath) {
  const absolute = resolve(path);
  try {
    return await realpathFn(absolute);
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
    const parent = dirname(absolute);
    if (parent === absolute) throw error;
    return join(await prospectiveRealpath(parent, realpathFn), basename(absolute));
  }
}

export async function validateImportPathSeparation({
  sourceDirectory,
  outputDirectory,
  publicDataRoot = PUBLIC_DATA_ROOT,
  projectRoot = PROJECT_ROOT,
  realpathFn = realpath,
}) {
  const nominalProjectRoot = resolve(projectRoot);
  const nominalPublicData = resolve(publicDataRoot);
  if (!isWithin(nominalProjectRoot, nominalPublicData) || nominalProjectRoot === nominalPublicData) {
    fail("dashboard/public/data must be below the project root");
  }
  const resolvedProjectRoot = await realpathFn(nominalProjectRoot);
  const source = await realpathFn(resolve(sourceDirectory));
  const output = await prospectiveRealpath(outputDirectory, realpathFn);
  const publicData = await prospectiveRealpath(nominalPublicData, realpathFn);
  if (!isWithin(resolvedProjectRoot, publicData) || resolvedProjectRoot === publicData) {
    fail("resolved dashboard/public/data must stay below the project root");
  }
  if (!isWithin(publicData, output) || output === publicData) {
    fail("resolved output must stay below the project dashboard/public/data directory");
  }
  if (isWithin(source, output) || isWithin(output, source)) {
    fail("source and output must not be the same path or contain one another");
  }
  return { source, output, publicData };
}

async function verifyImportedDirectory(directory, importedManifestBytes, verified) {
  await assertExactRegularFiles(directory, "published Ontology Review bundle");
  const writtenManifestBytes = await readFile(join(directory, "manifest.json"));
  if (!writtenManifestBytes.equals(importedManifestBytes)) {
    fail("written manifest bytes must match the generated release manifest");
  }
  for (const { expected, bytes } of verified) {
    const written = await readFile(join(directory, expected.file));
    assertEqual(written.byteLength, bytes.byteLength, `${expected.file} written byte size`);
    assertEqual(sha256(written), expected.sha256, `${expected.file} written SHA-256`);
  }
}

export async function verifyPublishedOntologyReviewBundle(directory) {
  const absolute = resolve(directory);
  await assertExactRegularFiles(absolute, "published Ontology Review bundle");
  const manifestBytes = await readFile(join(absolute, "manifest.json"));
  assertCanonicalReleaseManifestBytes(manifestBytes, "published manifest");
  const manifest = parseJson(manifestBytes, "published manifest");
  assertExactKeys(manifest, ["schema_version", "suite_id", "release_identity", "fixtures", "import_identity"], "published manifest");
  const { import_identity: importIdentity, ...sourceManifest } = manifest;
  validateCanonicalManifest(sourceManifest);
  assertExactKeys(importIdentity, ["source_commit", "release_commit"], "published manifest.import_identity");
  assertEqual(importIdentity.source_commit, CANONICAL_SOURCE_COMMIT, "published source commit");
  assertEqual(importIdentity.release_commit, CANONICAL_RELEASE_COMMIT, "published release commit");
  for (const expected of CANONICAL_FIXTURES) {
    const bytes = await readFile(join(absolute, expected.file));
    assertEqual(bytes.byteLength, expected.size, `${expected.file} published byte size`);
    assertEqual(sha256(bytes), expected.sha256, `${expected.file} published SHA-256`);
    validateCanonicalPayload(parseJson(bytes, expected.file), expected);
  }
  return { directory: absolute, fixtureCount: CANONICAL_FIXTURES.length };
}

export async function verifyCanonicalGitProvenance(repositoryRoot, sourceDirectory = DEFAULT_SOURCE) {
  const git = async (...args) => execFileAsync("git", ["-C", resolve(repositoryRoot), ...args], { encoding: "buffer", maxBuffer: 1024 * 1024 });
  await git("cat-file", "-e", `${CANONICAL_SOURCE_COMMIT}^{commit}`);
  await git("cat-file", "-e", `${CANONICAL_RELEASE_COMMIT}^{commit}`);
  await git("merge-base", "--is-ancestor", CANONICAL_SOURCE_COMMIT, CANONICAL_RELEASE_COMMIT);
  await assertExactRegularFiles(resolve(sourceDirectory), "tracked canonical source");
  for (const name of EXACT_FILES) {
    const { stdout } = await git("show", `${CANONICAL_RELEASE_COMMIT}:gate_d/fixtures/canonical-r5-v3/${name}`);
    const local = await readFile(join(resolve(sourceDirectory), name));
    if (!Buffer.from(stdout).equals(local)) fail(`${name} differs from the pinned release commit`);
  }
  return { sourceCommit: CANONICAL_SOURCE_COMMIT, releaseCommit: CANONICAL_RELEASE_COMMIT };
}
const FILE_OPERATIONS = Object.freeze({ link, mkdir, readFile, rename, rm, writeFile });

function ownershipLost(lock, { recoveryPath = null, restored = false, cause } = {}) {
  const recovery = recoveryPath
    ? `; successor lock preserved at ${recoveryPath}${restored ? ` and restored at ${lock}` : ""}`
    : "";
  const error = new Error(`Import lock ownership lost at ${lock}${recovery}`);
  error.code = "IMPORT_LOCK_OWNERSHIP_LOST";
  error.recoveryPath = recoveryPath;
  error.lockRestored = restored;
  if (cause) error.cause = cause;
  return error;
}

function sameOwnerToken(actual, expected) {
  const actualBytes = Buffer.from(actual, "utf8");
  const expectedBytes = Buffer.from(expected, "utf8");
  return (
    actualBytes.byteLength === expectedBytes.byteLength &&
    timingSafeEqual(actualBytes, expectedBytes)
  );
}

export async function withDestinationImportLock({
  destination,
  action,
  operations = FILE_OPERATIONS,
  token = `${process.pid}-${randomUUID()}`,
}) {
  const lockOperations = { ...FILE_OPERATIONS, ...operations };
  const parent = dirname(destination);
  const name = basename(destination);
  const lock = join(parent, `.${name}.lock`);
  const release = join(parent, `.${name}.lock-release-${token}`);
  let acquired = false;
  let actionError = null;

  async function assertOwnership() {
    let actual;
    try {
      actual = await lockOperations.readFile(lock, "utf8");
    } catch (error) {
      if (error?.code === "ENOENT") throw ownershipLost(lock);
      throw error;
    }
    if (!sameOwnerToken(actual, token)) throw ownershipLost(lock);
  }

  await lockOperations.mkdir(parent, { recursive: true });
  try {
    await lockOperations.writeFile(lock, token, { encoding: "utf8", flag: "wx" });
    acquired = true;
  } catch (error) {
    if (error?.code === "EEXIST") {
      fail(`import lock is already held at ${lock}`);
    }
    throw error;
  }

  try {
    return await action(assertOwnership);
  } catch (error) {
    actionError = error;
    throw error;
  } finally {
    if (acquired) {
      try {
        await lockOperations.rename(lock, release);
        let actual;
        try {
          actual = await lockOperations.readFile(release, "utf8");
        } catch (error) {
          throw ownershipLost(lock, { recoveryPath: release, cause: error });
        }
        if (!sameOwnerToken(actual, token)) {
          let restored = false;
          let recoveryError;
          try {
            await lockOperations.link(release, lock);
            restored = true;
          } catch (error) {
            if (error?.code !== "EEXIST") recoveryError = error;
          }
          throw ownershipLost(lock, {
            recoveryPath: release,
            restored,
            cause: recoveryError,
          });
        }
        await lockOperations.rm(release, { force: true });
        acquired = false;
      } catch (releaseError) {
        if (releaseError?.code === "ENOENT") releaseError = ownershipLost(lock);
        if (actionError) {
          throw new AggregateError(
            [actionError, releaseError],
            "Fixture import failed and its lock could not be released safely",
          );
        }
        throw releaseError;
      }
    }
  }
}

export async function atomicReplaceDirectory({
  destination,
  populate,
  verify,
  beforeExchange = async () => {},
  operations = FILE_OPERATIONS,
  suffix = `${process.pid}-${randomUUID()}`,
}) {
  const parent = dirname(destination);
  const name = basename(destination);
  const temporary = join(parent, `.${name}.import-${suffix}`);
  const backup = join(parent, `.${name}.backup-${suffix}`);
  let movedPrevious = false;
  let installed = false;

  await operations.mkdir(parent, { recursive: true });
  try {
    await operations.mkdir(temporary, { recursive: false });
    await populate(temporary);
    await verify(temporary);
    await beforeExchange();
    try {
      await operations.rename(destination, backup);
      movedPrevious = true;
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
    try {
      await operations.rename(temporary, destination);
      installed = true;
    } catch (error) {
      if (movedPrevious) {
        try {
          await operations.rename(backup, destination);
          movedPrevious = false;
        } catch (restoreError) {
          throw new AggregateError(
            [error, restoreError],
            "Fixture exchange failed and the previous directory could not be restored",
          );
        }
      }
      throw error;
    }
    if (movedPrevious) {
      await operations.rm(backup, { recursive: true, force: true });
      movedPrevious = false;
    }
  } finally {
    if (!installed) await operations.rm(temporary, { recursive: true, force: true });
    if (!movedPrevious) await operations.rm(backup, { recursive: true, force: true });
  }
}

export async function replaceDirectoryWithLock(options) {
  const { destination } = options;
  const operations = { ...FILE_OPERATIONS, ...options.operations };
  return withDestinationImportLock({
    destination,
    operations,
    action: (assertOwnership) =>
      atomicReplaceDirectory({
        ...options,
        operations,
        beforeExchange: async () => {
          await assertOwnership();
          await options.beforeExchange?.();
        },
      }),
  });
}

export async function importOntologyReviewFixtures({
  sourceDirectory = DEFAULT_SOURCE,
  outputDirectory = DEFAULT_OUTPUT,
} = {}) {
  if (resolve(outputDirectory) !== resolve(DEFAULT_OUTPUT)) {
    fail("output must be the project ontology-review generated-data directory");
  }

  const { source, output } = await validateImportPathSeparation({
    sourceDirectory,
    outputDirectory,
  });
  await assertExactRegularFiles(source, "tracked canonical source");
  const manifestBytes = await readFile(join(source, "manifest.json"));
  validateCanonicalSourceManifestBytes(manifestBytes);

  const verified = [];
  for (const expected of CANONICAL_FIXTURES) {
    const bytes = await readFile(join(source, expected.file));
    assertEqual(bytes.byteLength, expected.size, `${expected.file} byte size`);
    assertEqual(sha256(bytes), expected.sha256, `${expected.file} SHA-256`);
    const payload = parseJson(bytes, expected.file);
    validateCanonicalPayload(payload, expected);
    verified.push({ expected, bytes });
  }

  const importedManifestBytes = canonicalReleaseManifestBytes();

  await replaceDirectoryWithLock({
    destination: output,
    populate: async (temporary) => {
      await writeFile(join(temporary, "manifest.json"), importedManifestBytes);
      for (const { expected, bytes } of verified) {
        await writeFile(join(temporary, expected.file), bytes);
      }
    },
    verify: (temporary) =>
      verifyImportedDirectory(temporary, importedManifestBytes, verified),
  });
  return { outputDirectory: output, fixtureCount: verified.length };
}

function parseArgs(argv) {
  if (argv.length === 0) return { mode: "prepare" };
  if (argv.length === 2 && argv[0] === "--source") return { mode: "prepare", sourceDirectory: argv[1] };
  if (argv.length === 2 && argv[0] === "--verify") return { mode: "verify", directory: argv[1] };
  if (argv.length === 2 && argv[0] === "--verify-upstream") return { mode: "upstream", repositoryRoot: argv[1] };
  fail("usage: [--source <directory> | --verify <directory> | --verify-upstream <repository>]");
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const options = parseArgs(process.argv.slice(2));
    if (options.mode === "verify") {
      const result = await verifyPublishedOntologyReviewBundle(options.directory);
      console.log(`Verified ${result.fixtureCount} published Ontology Review fixtures in ${result.directory}.`);
    } else if (options.mode === "upstream") {
      const result = await verifyCanonicalGitProvenance(options.repositoryRoot);
      console.log(`Verified canonical source ${result.sourceCommit} through release ${result.releaseCommit}.`);
    } else {
      const result = await importOntologyReviewFixtures({ sourceDirectory: options.sourceDirectory });
      console.log(`Prepared ${result.fixtureCount} verified Ontology Review fixtures in ${relative(PROJECT_ROOT, result.outputDirectory)}.`);
    }
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  }
}
