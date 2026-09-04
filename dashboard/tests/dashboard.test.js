/**
 * Unit tests for the Vue client's contracts.
 *
 * The dashboard is a browser client over the Flask API in `backend/`, so what
 * is checkable here is what the client owns: its navigation table, its
 * deployment theming, its table and dialog behaviour, and the presentation
 * rules its views state. Everything server-side — reading artifacts, writing
 * `.env`, spawning a pipeline stage — belongs to the Python suite under
 * `backend/tests/`, which is where those contracts are now proven.
 *
 *   cd dashboard && npm test
 *
 * Data flow:
 *     src/pages.js, src/theme.js, src/lib/&#42;, src/views/&#42; -> here
 */

import assert from "node:assert/strict";
import { readFileSync, rmSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

const { PAGES, PAGE_KEYS, DEFAULT_PAGE, DASHBOARD_RESOURCES } = await import(
  "../src/pages.js"
);
const { TERM_HELP: TERM_REGISTRY } = await import("../src/lib/terms.js");

const HERE = resolve(import.meta.dirname);
const APP_VUE = readFileSync(resolve(HERE, "..", "src", "App.vue"), "utf8");
const BUDGET_MANAGER = readFileSync(
  resolve(HERE, "..", "src", "views", "BudgetManager.vue"),
  "utf8",
);
const CAMPAIGNS = readFileSync(
  resolve(HERE, "..", "src", "views", "Campaigns.vue"),
  "utf8",
);
const ENTITY_TABLE = readFileSync(
  resolve(HERE, "..", "src", "components", "EntityTable.vue"),
  "utf8",
);
const CONFIRM_DIALOG = readFileSync(
  resolve(HERE, "..", "src", "components", "ConfirmDialog.vue"),
  "utf8",
);
const TOP_BAR = readFileSync(
  resolve(HERE, "..", "src", "components", "TopBar.vue"),
  "utf8",
);
const SETTINGS_DIALOG = readFileSync(
  resolve(HERE, "..", "src", "components", "SettingsDialog.vue"),
  "utf8",
);
const BACKEND_TASKS = readFileSync(
  resolve(HERE, "..", "src", "components", "BackendTasks.vue"),
  "utf8",
);
const DATA_GENERATOR = readFileSync(
  resolve(HERE, "..", "src", "views", "DataGenerator.vue"),
  "utf8",
);
const KNOWLEDGE_BASE = readFileSync(
  resolve(HERE, "..", "src", "views", "KnowledgeBase.vue"),
  "utf8",
);
const ONTOLOGY_FIXTURES = readFileSync(
  resolve(HERE, "..", "src", "lib", "ontologyReviewFixtures.js"),
  "utf8",
);
const TERM_HELP = readFileSync(
  resolve(HERE, "..", "src", "components", "TermHelp.vue"),
  "utf8",
);
const SCHEMA_RECOVERY = readFileSync(
  resolve(HERE, "..", "src", "components", "SchemaRecovery.vue"),
  "utf8",
);
const TERMS = readFileSync(resolve(HERE, "..", "src", "lib", "terms.js"), "utf8");
const SIDEBAR_NAV = readFileSync(
  resolve(HERE, "..", "src", "components", "SidebarNav.vue"),
  "utf8",
);
const DEPLOYMENT = readFileSync(
  resolve(HERE, "..", "src", "lib", "deployment.js"),
  "utf8",
);
const DIAGNOSTICS = readFileSync(
  resolve(HERE, "..", "src", "lib", "diagnostics.js"),
  "utf8",
);
const STYLE_CSS = readFileSync(resolve(HERE, "..", "src", "style.css"), "utf8");
const CLIENT = readFileSync(resolve(HERE, "..", "src", "api", "client.js"), "utf8");
const VITE_CONFIG = readFileSync(resolve(HERE, "..", "vite.config.js"), "utf8");
const COMPOSE = readFileSync(
  resolve(HERE, "..", "..", "deploy", "docker", "compose.yaml"),
  "utf8",
);
const PUBLISH_WORKFLOW = readFileSync(
  resolve(HERE, "..", "..", ".github", "workflows", "publish-containers.yml"),
  "utf8",
);
const DASHBOARD_DOCKERFILE = readFileSync(
  resolve(HERE, "..", "..", "deploy", "docker", "Dockerfile.dashboard"),
  "utf8",
);
const DOCKERIGNORE = readFileSync(
  resolve(HERE, "..", "..", ".dockerignore"),
  "utf8",
);
const OPTIMIZATION_LOG = readFileSync(
  resolve(HERE, "..", "src", "views", "OptimizationLog.vue"),
  "utf8",
);
const CAMPAIGN_OPTIMIZER = readFileSync(
  resolve(HERE, "..", "src", "views", "CampaignOptimizer.vue"),
  "utf8",
);
const STAGE_RUNNER = readFileSync(
  resolve(HERE, "..", "src", "components", "StageRunner.vue"),
  "utf8",
);
const WILLOW_FORECAST = readFileSync(
  resolve(HERE, "..", "src", "components", "WillowGmvForecast.vue"),
  "utf8",
);
const RUN_PIPELINE_PY = readFileSync(
  resolve(HERE, "..", "..", "script", "run_pipeline.py"),
  "utf8",
);

/**
 * Import `src/api/client.js` under Node, with its private helpers exported.
 *
 * The module reads `import.meta.env` at load, which only Vite defines, and it
 * keeps the stream reader and the static windowing private because no view
 * calls them directly. Rather than widen the module's surface for the suite, a
 * copy is written beside it with the build flag substituted and those helpers
 * exported. The copy sits in `src/api/` so its own `../pages.js` import still
 * resolves, and is removed as soon as it is loaded.
 *
 * `staticBuild` selects which deployment the copy believes it is, which is the
 * only way to reach the branch a published build takes.
 */
const clientModules = new Map();
async function loadClientModule(staticBuild = false) {
  const flag = staticBuild ? "true" : "false";
  if (clientModules.has(flag)) return clientModules.get(flag);
  const shim = resolve(HERE, "..", "src", "api", `__client_test_shim_${flag}.mjs`);
  writeFileSync(
    shim,
    CLIENT.replaceAll("import.meta.env", `{ VITE_STATIC_BUILD: "${flag}" }`) +
      "\nexport { readResourceStream, windowStaticPayload };\n",
    "utf8",
  );
  try {
    clientModules.set(flag, await import(pathToFileURL(shim).href));
  } finally {
    rmSync(shim, { force: true });
  }
  return clientModules.get(flag);
}

/**
 * A stand-in `Response` that delivers `text` as many small byte chunks.
 *
 * The chunk is deliberately smaller than a network read. What is under test is
 * the per-chunk cost, so the count of chunks is the load, and a small chunk
 * reaches a telling count without holding a network-sized frame in memory.
 */
function chunkedResponse(text, chunkSize = 4096) {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return {
    body: {
      getReader: () => ({
        read: async () => {
          if (offset >= bytes.length) return { done: true, value: undefined };
          const value = bytes.subarray(offset, offset + chunkSize);
          offset += chunkSize;
          return { done: false, value };
        },
      }),
    },
  };
}

// ---------------------------------------------------------------------------
// CSV
// ---------------------------------------------------------------------------

test("every navigable page has an icon, a title, and a component", () => {
  for (const key of PAGE_KEYS) {
    assert.ok(PAGES[key], `${key} is grouped but absent from PAGES`);
    assert.ok(PAGES[key].title, `${key} has no title`);
    assert.ok(PAGES[key].icon, `${key} has no icon`);
    // The rail cannot offer a destination the shell cannot render.
    assert.match(
      APP_VUE,
      new RegExp(`\\b${key}:\\s*\\w+`),
      `${key} is in the rail but not in App.vue's component map`,
    );
  }
});

test("every subsection declares only allow-listed lazy resources", () => {
  for (const key of PAGE_KEYS) {
    const page = PAGES[key];
    assert.ok(page.sections[page.defaultSection], `${key} has no default route`);
    for (const [section, resources] of Object.entries(page.sections)) {
      assert.equal(resources[0], "shell", `${key}/${section} does not load shell first`);
      assert.equal(new Set(resources).size, resources.length, `${key}/${section} repeats a resource`);
      for (const resource of resources) {
        assert.ok(
          DASHBOARD_RESOURCES.includes(resource),
          `${key}/${section} declares unknown resource ${resource}`,
        );
      }
    }
  }
});

test("Settings is the only foot control and Reload lives inside it", () => {
  assert.ok(PAGES.settings, "settings has no icon entry");
  assert.ok(!PAGE_KEYS.includes("settings"), "settings must not be a navigable page");
  assert.ok(!PAGES.reload, "reload must not retain a sidebar page entry");
  assert.doesNotMatch(SIDEBAR_NAV, /Reload data|emit\("reload"\)/);
  assert.match(SETTINGS_DIALOG, />Reload data</);
});

test("page keys are unique, flat, and place Data Generator after Command Center", () => {
  assert.equal(new Set(PAGE_KEYS).size, PAGE_KEYS.length);
  assert.ok(PAGE_KEYS.includes(DEFAULT_PAGE));
  assert.deepEqual(PAGE_KEYS.slice(0, 2), ["overview", "generator"]);
  assert.match(SIDEBAR_NAV, /v-for="key in PAGE_KEYS"/);
  assert.doesNotMatch(SIDEBAR_NAV, /PAGE_GROUPS|nav-group|nav-label|OVERVIEW|INSIGHTS/);
});

// ---------------------------------------------------------------------------
// The snapshot, in file mode
// ---------------------------------------------------------------------------

test("the Optimization Log reports stage 5 from the plan, not a constant", () => {
  // The view previously hard-coded "NOT RUN", which would keep reading NOT RUN
  // after the optimizer had in fact produced a plan.
  assert.doesNotMatch(OPTIMIZATION_LOG, /count: 0,\s*status: "NOT RUN"/);
  assert.match(OPTIMIZATION_LOG, /data\.value\.campaignStrategy/);
  assert.match(OPTIMIZATION_LOG, /strategy\.value\.optimized_strategy/);

  // Every claim the plan must disclose rather than let a number stand alone.
  for (const field of ["is_extrapolated", "response_support",
    "ad_group_optimization_claim", "ad_group_projection_basis",
    "infeasibility_reasons", "excluded_campaign_ids"]) {
    assert.match(OPTIMIZATION_LOG, new RegExp(field));
  }
  assert.match(OPTIMIZATION_LOG, /Attribution is not an input here/);
  assert.match(OPTIMIZATION_LOG, /POOLED_TRANSFER/);
});

test("Budget Manager exposes progressive canonical entity sections", () => {
  for (const label of ["Overview", "Ad Providers", "Products", "Campaigns",
    "Ad Groups", "Touchpoints", "Product Economics", "Data Run Diagnostics"]) {
    assert.match(BUDGET_MANAGER, new RegExp(label));
  }
  for (const field of ["placement_availability", "creative_availability",
    "interaction_type_availability", "billing_type"]) {
    assert.match(BUDGET_MANAGER, new RegExp(field));
  }
  // Observed volume and spend, which the platform report actually states,
  // rather than a click-through rate derived across rows that share no
  // denominator.
  for (const field of ["observed_impressions", "observed_clicks", "observed_cost"]) {
    assert.match(BUDGET_MANAGER, new RegExp(field));
  }
  assert.match(BUDGET_MANAGER, /sku_id/);
  // The economics fields that are not summary columns remain reachable through
  // the row's own editor, which renders the whole record.
  assert.match(BUDGET_MANAGER, /variable_cost_per_unit/);
  assert.match(BUDGET_MANAGER, /unit_contribution_margin/);
  for (const behavior of ["Upload and validate JSON", "Validate and save"]) {
    assert.match(BUDGET_MANAGER, new RegExp(behavior));
  }
  // Missing economics stay missing; `renderCell` shows `--` for null rather
  // than letting a blank read as zero.
  assert.match(BUDGET_MANAGER, /missing Cost of Goods Sold is never treated as zero/i);
  assert.match(BUDGET_MANAGER, /Reported performance is read-only/);
});

// ---------------------------------------------------------------------------
// Deployment capability and theme
// ---------------------------------------------------------------------------

// The themes are read from `src/theme.js` rather than from `src/lib/deployment.js`,
// which re-exports them: `deployment.js` reaches `src/api/client.js` through
// `useDashboard.js`, and that module reads `import.meta.env`, which exists only
// under Vite. `theme.js` imports nothing, so it loads in the Node runner.
const { DEPLOYMENT_THEMES: THEMES } = await import("../src/theme.js");

test("write capability follows the snapshot's mode, not the build flag", async () => {
  const source = readFileSync(
    resolve(HERE, "..", "src", "lib", "deployment.js"),
    "utf8",
  );

  // A local file-mode run is read-only for the same reason the published build
  // is: there is no database behind it. Deriving `writable` from `IS_STATIC`
  // would wrongly offer editing controls to that run.
  assert.match(source, /mode === "database"/);
  assert.doesNotMatch(source, /writable\s*=\s*computed\(\(\)\s*=>\s*!isStaticBuild/);
  // The build flag decides only how a read-only deployment names itself, never
  // whether it may write.
  assert.match(source, /isStaticBuild\(\) \? "Published build" : "Local files"/);

  // The two accents are distinct, or the deployments would be indistinguishable
  // at a glance, which is the whole point of theming them apart.
  assert.notEqual(THEMES.read_only.accent, THEMES.writable.accent);
  assert.equal(THEMES.writable.accent, "#2456a6");
  // Microsoft Excel's own green, for the deployment that reads a table of
  // committed values rather than a database.
  assert.equal(THEMES.read_only.accent, "#217346");
});

test("the deployment theme repaints tokens but never the chart series", async () => {
  const { SERIES, MODEL_COLORS, OUTCOME_COLORS } = await import("../src/theme.js");
  const APP = readFileSync(resolve(HERE, "..", "src", "App.vue"), "utf8");

  // The accents are applied by overriding the custom properties the stylesheet
  // already reads, so one override repaints everything and no component needs
  // a deployment variant class.
  for (const token of ["--blue", "--blue2", "--navy", "--rail-active"]) {
    assert.match(APP, new RegExp(`"${token}"`), `${token} is not themed`);
  }

  // A series colour follows its entity, so the same Campaign must keep its
  // colour across both deployments. A deployment accent leaking into the
  // categorical palette would break that.
  const accents = Object.values(THEMES).flatMap((entry) => [
    entry.accent,
    entry.accentStrong,
  ]);
  for (const colour of [...SERIES, ...Object.values(MODEL_COLORS),
    ...Object.values(OUTCOME_COLORS)]) {
    assert.ok(
      !accents.includes(colour),
      `${colour} is both a series colour and a deployment accent`,
    );
  }
});

test("a read-only deployment states why, and names its remedy", () => {
  const APP = readFileSync(resolve(HERE, "..", "src", "App.vue"), "utf8");
  const source = readFileSync(
    resolve(HERE, "..", "src", "lib", "deployment.js"),
    "utf8",
  );

  // Stated once at the top of every view rather than at each absent control:
  // a reader should learn this from the page, not from a missing button.
  assert.match(APP, /deployment-notice/);
  assert.match(APP, /readOnlyReason/);

  // Each read-only deployment names the remedy that actually applies to it.
  assert.match(source, /DATABASE=true/);
  assert.match(source, /Run the dashboard locally/);

  // The two are named apart: a reader can act on one of them and not the other.
  assert.match(source, /"Published build"/);
  assert.match(source, /"Local files"/);
  assert.match(TOP_BAR, /deploymentLabel/);
});

test("the schema dropdown offers what it cannot select, and says why", () => {
  const schemas = readFileSync(
    resolve(HERE, "..", "..", "backend", "services", "schemas.py"),
    "utf8",
  );

  // Listed and disabled rather than omitted: a reader who knows a schema exists
  // would otherwise get no account of its absence.
  assert.match(SETTINGS_DIALOG, /:disabled="!option\.selectable"/);
  assert.match(SETTINGS_DIALOG, /v-for="option in schemaOptions"/);
  assert.match(SETTINGS_DIALOG, /:title="schemaTitle\(option\)"/);

  // The browser tooltip is not shown over an open dropdown everywhere, so the
  // same explanation is rendered as text under the field.
  assert.match(SETTINGS_DIALOG, /id="pg-schema-help"/);
  assert.match(SETTINGS_DIALOG, /aria-describedby="pg-schema-help"/);
  assert.match(SETTINGS_DIALOG, /describedSchema\.missingTables/);

  // The reason and the remedy are the server's, not the client's: the dialog
  // renders `detail` rather than reconstructing a message from table names.
  assert.match(SETTINGS_DIALOG, /describedSchema\.detail/);
  assert.match(schemas, /"--schema \{schema\} --replace"/);
  assert.match(schemas, /"databaseRevision": "not tracked"/);
  assert.match(SETTINGS_DIALOG, /option\.databaseRevision \?\? "not tracked"/);

  // The saved selection survives an unreachable database, or the dropdown would
  // show a schema the reader never chose and save it on the next write.
  assert.match(SETTINGS_DIALOG, /listed\.some\(\(item\) => item\.name === current\)/);
});

test("protected settings exposes schema versions without enabling configuration", () => {
  assert.match(SETTINGS_DIALOG, /v-else-if="state\?\.readOnly"/);
  assert.match(SETTINGS_DIALOG, /id="protected-schema"/);
  assert.match(SETTINGS_DIALOG, /v-for="option in schemaOptions"/);
  assert.match(SETTINGS_DIALOG, /option\.selected \? " — active"/);
  assert.match(SETTINGS_DIALOG, /database structure/);
  assert.match(SETTINGS_DIALOG, /protected deployment configuration/);
});

test("schema setup survives protected configuration, which governs credentials", () => {
  // The section used to sit inside the writable branch, which the read-only
  // branch pre-empts, so the one deployment whose readers have no shell was the
  // one deployment offering no way to populate a schema. It is now a sibling of
  // all three branches, gated only on there being a backend at all.
  const setup = SETTINGS_DIALOG.indexOf("<h3>Schema setup</h3>");
  const writable = SETTINGS_DIALOG.indexOf('<template v-else-if="state">');
  assert.ok(setup > 0, "the Schema setup section is rendered");
  assert.ok(
    setup > writable && writable > 0,
    "Schema setup follows the branch a protected deployment never reaches",
  );
  assert.match(SETTINGS_DIALOG, /<template v-if="!hosted && state">/);

  // The capability is the server's answer rather than a rule the dialog
  // reconstructs from the deployment flags, so the buttons and the route that
  // would carry them out cannot disagree.
  assert.match(SETTINGS_DIALOG, /schemaOperation\.value\.available === true/);
  assert.match(SETTINGS_DIALOG, /setupReason/);
  assert.match(SETTINGS_DIALOG, /setupAvailable\.value && connectionSaved\.value/);

  // Nothing on the page can be edited when configuration is protected, so
  // there is no unsaved edit for setup to be out of step with.
  assert.match(SETTINGS_DIALOG, /if \(readOnly\.value\) return true;/);

  const operations = readFileSync(
    resolve(HERE, "..", "..", "backend", "api", "schema_operations.py"),
    "utf8",
  );
  assert.match(operations, /schema_setup_enabled/);
  assert.doesNotMatch(operations, /config_read_only/);
});

test("a schema that cannot be read offers controls, not a shell command", () => {
  const recovery = readFileSync(
    resolve(HERE, "..", "src", "components", "SchemaRecovery.vue"),
    "utf8",
  );

  // A reader who reaches the error card has a browser and, on a deployed
  // instance, nothing else, so the remedies are rendered as controls.
  assert.match(APP_VUE, /<SchemaRecovery/);
  assert.match(APP_VUE, /routeError\.code === 'database_unavailable'/);
  assert.doesNotMatch(APP_VUE, /uv run --extra dashboard/);

  // The three actions the backend already implements, named as instructions.
  assert.match(recovery, /Load a schema that is ready/);
  assert.match(recovery, /Build dashboard schemas from a source/);
  assert.match(recovery, /Start from the sample account/);
  assert.match(recovery, /selectRuntimeSchema/);
  assert.match(recovery, /startSchemaOperation/);

  // Overwriting destroys data and stays behind the Settings checkbox that says
  // so, rather than behind a button pressed to escape an error page.
  assert.match(recovery, /option\.replace/);
  assert.doesNotMatch(recovery, /replace: true|replaceSchemas/);

  // Fetched precisely when something is already wrong, so a failed fetch must
  // not leave the card with nothing under it.
  assert.match(CLIENT, /fetchSchemaRecovery/);
  assert.match(CLIENT, /\/api\/schema-recovery/);
});

test("the schema selection is sent, saved, and refilled from a live test", () => {
  const settingsApi = readFileSync(
    resolve(HERE, "..", "..", "backend", "api", "settings.py"),
    "utf8",
  );

  assert.match(SETTINGS_DIALOG, /PG_SCHEMA: form\.value\.PG_SCHEMA/);
  // A connection test is the only moment the list is knowable, so it fills the
  // dropdown from the server just reached rather than from the saved one.
  assert.match(SETTINGS_DIALOG, /if \(result\.schemas\) schemas\.value = result\.schemas/);

  // A schema name reaches libpq as an identifier inside a connect option, so
  // the route refuses it before anything is written to `.env`.
  assert.match(settingsApi, /valid_schema_name\(updates\["PG_SCHEMA"\]\)/);
  assert.match(settingsApi, /"invalid_schema"/);
});

test("schema doctor queues imports and sends build logs to Tasks", () => {
  assert.match(SETTINGS_DIALOG, /id="setup-schema"/);
  assert.match(SETTINGS_DIALOG, /v-for="option in schemas\.schemas"/);
  assert.match(SETTINGS_DIALOG, /Initialize sample model/);
  assert.match(SETTINGS_DIALOG, /Parse all scenarios/);
  assert.match(SETTINGS_DIALOG, /Connect/);
  assert.match(SETTINGS_DIALOG, /Inspect/);
  assert.match(SETTINGS_DIALOG, /Import/);
  assert.match(SETTINGS_DIALOG, /Verify/);
  assert.match(SETTINGS_DIALOG, />\s*Tasks\s*<\/button>/);
  assert.match(BACKEND_TASKS, /selected\.lines/);
  assert.match(BACKEND_TASKS, /selected\.command/);
  assert.match(BACKEND_TASKS, /Copy log/);
  assert.match(BACKEND_TASKS, /stopTask/);

  const client = readFileSync(resolve(HERE, "..", "src", "api", "client.js"), "utf8");
  assert.match(client, /fetchSchemaOperation/);
  assert.match(client, /startSchemaOperation/);
  assert.match(client, /stopSchemaOperation/);
  assert.match(client, /\/api\/schema-operations/);
});

test("settings compares independently detected frontend and backend builds", () => {
  assert.match(SETTINGS_DIALOG, />\s*General\s*<\/button>/);
  assert.match(SETTINGS_DIALOG, /v-if="tab === 'general'"[\s\S]*Deployment identity/);
  assert.match(SETTINGS_DIALOG, /const tab = ref\("general"\)/);
  assert.match(SETTINGS_DIALOG, /Deployment identity/);
  assert.match(SETTINGS_DIALOG, /Dashboard version/);
  assert.match(SETTINGS_DIALOG, /Dashboard commit SHA/);
  assert.match(SETTINGS_DIALOG, /Backend version/);
  assert.match(SETTINGS_DIALOG, /Backend commit SHA/);
  assert.match(SETTINGS_DIALOG, /Backend Python/);
  assert.match(SETTINGS_DIALOG, /Backend Flask/);
  assert.match(SETTINGS_DIALOG, /Builds match/);
  assert.match(SETTINGS_DIALOG, /Build mismatch/);
  assert.match(SETTINGS_DIALOG, /Identity incomplete/);
  assert.match(SETTINGS_DIALOG, /frontendIdentity\.version !== backend\.version/);
  assert.match(SETTINGS_DIALOG, /frontendIdentity\.commit !== backend\.commit/);
  assert.doesNotMatch(SETTINGS_DIALOG, /\.slice\(0, 12\)/);

  assert.match(VITE_CONFIG, /__DASHBOARD_VERSION__/);
  assert.match(VITE_CONFIG, /__DASHBOARD_COMMIT__/);
  assert.match(VITE_CONFIG, /process\.env\.BUILD_COMMIT/);
  assert.match(VITE_CONFIG, /rev-parse", "HEAD"/);
  assert.match(CLIENT, /backendIdentity: null/);
  assert.match(COMPOSE, /BUILD_COMMIT: \$\{PROJECT_COMMIT:-unknown\}/);
  assert.match(PUBLISH_WORKFLOW, /BUILD_COMMIT=\$\{\{ github\.sha \}\}/);
});

test("dashboard image admits only its complete external build inputs", () => {
  assert.match(
    DASHBOARD_DOCKERFILE,
    /COPY script\/import_ontology_review_fixtures\.mjs \/workspace\/script\/import_ontology_review_fixtures\.mjs/,
  );
  assert.match(
    DASHBOARD_DOCKERFILE,
    /COPY docs\/en\/strategy-evaluation\/asin-gmv-nn-v1\/results\/demo_mlp_extended27\.json\s+\\\s+\/workspace\/docs\/en\/strategy-evaluation\/asin-gmv-nn-v1\/results\/demo_mlp_extended27\.json/,
  );

  const docsRules = DOCKERIGNORE.split(/\r?\n/).filter(
    (line) => line === "docs" || line.startsWith("docs/") || line.startsWith("!docs"),
  );
  assert.deepEqual(docsRules, [
    "docs",
    "!docs/",
    "docs/*",
    "!docs/en/",
    "docs/en/*",
    "!docs/en/strategy-evaluation/",
    "docs/en/strategy-evaluation/*",
    "!docs/en/strategy-evaluation/asin-gmv-nn-v1/",
    "docs/en/strategy-evaluation/asin-gmv-nn-v1/*",
    "!docs/en/strategy-evaluation/asin-gmv-nn-v1/results/",
    "docs/en/strategy-evaluation/asin-gmv-nn-v1/results/*",
    "!docs/en/strategy-evaluation/asin-gmv-nn-v1/results/demo_mlp_extended27.json",
  ]);
});

test("pipeline capability comes from the server rather than settings protection", () => {
  assert.doesNotMatch(STAGE_RUNNER, /props\.writable/);
  assert.match(STAGE_RUNNER, /props\.stage\.available/);
  assert.doesNotMatch(CAMPAIGN_OPTIMIZER, /:writable=/);
});

test("model output transfer stays behind fixed backend artifact routes", () => {
  assert.match(STAGE_RUNNER, /Upload and parse/);
  assert.match(STAGE_RUNNER, /Import to database/);
  assert.match(STAGE_RUNNER, /artifact\.downloadUrl/);
  assert.match(CLIENT, /uploadJobArtifacts/);
  assert.match(CLIENT, /importJobArtifacts/);
  assert.match(CLIENT, /new FormData\(\)/);
  assert.doesNotMatch(STAGE_RUNNER, /PG_PASSWORD|psycopg|create_engine/);
});

test("Willow Sakura renders native running widgets instead of a whole-page iframe", () => {
  assert.match(CAMPAIGN_OPTIMIZER, /<WillowGmvForecast\s*\/>/);
  assert.doesNotMatch(CAMPAIGN_OPTIMIZER, /iframe|srcdoc|willowDemoSource/);
  assert.match(WILLOW_FORECAST, /Sponsored Products budget/);
  assert.match(WILLOW_FORECAST, /Amazon Demand-Side Platform budget/);
  assert.match(WILLOW_FORECAST, /Placement and creative structure/);
  assert.match(WILLOW_FORECAST, /If all budgets increase 10%/);
  assert.match(WILLOW_FORECAST, /predictWillowGmv/);
  assert.match(WILLOW_FORECAST, /watch\(form, refreshPrediction/);
});

test("the rail's status dot agrees with the deployment accent", async () => {
  const settings = readFileSync(
    resolve(HERE, "..", "..", "backend", "services", "settings.py"),
    "utf8",
  );
  const client = readFileSync(resolve(HERE, "..", "src", "api", "client.js"), "utf8");

  // The rail and the theme must not disagree about which deployment this is.
  // The published build's dot is set in the client, the local one by the Flask
  // service that answers `/api/settings`.
  assert.match(client, new RegExp(THEMES.read_only.dot));
  assert.match(settings, new RegExp(THEMES.read_only.dot));
});

// ---------------------------------------------------------------------------
// The entity list
// ---------------------------------------------------------------------------

test("the entity list pages, and offers the five documented page sizes", () => {
  assert.match(ENTITY_TABLE, /PAGE_SIZES = \[10, 15, 30, 50, 100\]/);
  // 10 is the default, so a section opens at one screen rather than at 100 rows.
  assert.match(ENTITY_TABLE, /pageSize = ref\(PAGE_SIZES\[0\]\)/);
});

test("selection is keyed by identity, so it survives paging", () => {
  // Keyed by index, a batch action would act on whatever sits at that index
  // after the page turns, which is a different record.
  assert.match(ENTITY_TABLE, /rowKey: \{ type: Function, required: true \}/);
  assert.match(ENTITY_TABLE, /selected\.value\.has\(props\.rowKey\(row\)\)/);

  // A Set mutated in place is the same object, so Vue's reactivity would not
  // see the change and no checkbox would repaint.
  assert.match(ENTITY_TABLE, /const next = new Set\(selected\.value\)/);
  assert.doesNotMatch(ENTITY_TABLE, /selected\.value\.add\(/);
  assert.doesNotMatch(ENTITY_TABLE, /selected\.value\.delete\(/);
});

test("deletion always passes through a confirmation that names its rows", () => {
  // A count alone is not something a reader can check, and a batch selected
  // across several pages is exactly the case where they cannot see their pick.
  assert.match(CONFIRM_DIALOG, /items: \{ type: Array/);
  assert.match(CONFIRM_DIALOG, /const LISTED = 12/);
  // A capped list states its remainder rather than dropping it silently.
  assert.match(CONFIRM_DIALOG, /remainder/);
  assert.match(CONFIRM_DIALOG, /role="alertdialog"/);

  // Both row and batch deletion route through the same pending state, so
  // neither can reach the server without the dialog.
  assert.match(BUDGET_MANAGER, /function requestDelete/);
  assert.match(BUDGET_MANAGER, /function requestBatchDelete/);
  assert.match(BUDGET_MANAGER, /pendingDelete\.value = \{/);
  assert.match(BUDGET_MANAGER, /@confirm="confirmDelete"/);
});

test("a partial batch archive reports where it stopped", () => {
  // Sequential rather than concurrent: each archive clears the server's caches,
  // so a parallel batch would have them racing.
  assert.match(BUDGET_MANAGER, /for \(const \[index, id\] of ids\.entries\(\)\)/);
  // Reporting success after a partial batch would be a false statement about
  // what is now in the database.
  assert.match(BUDGET_MANAGER, /archived \$\{index\} of \$\{ids\.length\}/);
});

test("Budget Manager renders entity sections as paged tables, not detail lists", () => {
  // The previous view stacked every field of every record as `<details>`
  // paragraphs, which put hundreds of lines of prose on one page and left no
  // way to scan a column.
  assert.doesNotMatch(BUDGET_MANAGER, /<details/);
  assert.match(BUDGET_MANAGER, /<EntityTable/);
  assert.match(BUDGET_MANAGER, /SECTION_COLUMNS/);

  // Every section the rail offers has both columns and rows behind it.
  const { BUDGET_SECTIONS } = { BUDGET_SECTIONS: ["providers", "products",
    "campaigns", "adGroups", "touchpoints", "productEconomics",
    "generationConfigs"] };
  for (const key of BUDGET_SECTIONS) {
    assert.match(BUDGET_MANAGER, new RegExp(`${key}: \\[`), `${key} has no columns`);
    assert.match(BUDGET_MANAGER, new RegExp(`${key}: \\(\\) =>`), `${key} has no rows`);
  }
});

test("an empty section names its cause rather than reading as a fault", () => {
  // The catalogue is derived from the account's own committed reports, so a
  // section is empty only when those reports carry no such record. The message
  // says that, rather than "No records loaded", which reads as a fault.
  assert.match(BUDGET_MANAGER, /emptyMessage/);
  assert.match(BUDGET_MANAGER, /current reporting window/);
});

test("the dashboard never presents its data as generated or simulated", () => {
  // The dashboard's subject is a live advertising account. Naming the research
  // simulator in the interface would tell a reader the numbers are invented,
  // which is both wrong for a production deployment and unactionable.
  for (const [name, source] of Object.entries({
    BUDGET_MANAGER, CAMPAIGNS, SETTINGS_DIALOG, DEPLOYMENT,
  })) {
    for (const forbidden of [/MTA[_-]SIM/i, /MTA_SIM_DATA_DIR/, /simulator/i,
      /\bsynthetic\b/i, /generated (history|observation|run)/i]) {
      assert.doesNotMatch(source, forbidden, `${name} names ${forbidden}`);
    }
  }
});

test("the rail becomes a bar, not a tall block, below the wide breakpoint", () => {
  // Stacking the rail's vertical layout at full width pushed the dashboard
  // below the fold on a narrow screen, so every view opened on an empty
  // screen. The bar keeps navigation on one row and returns the height.
  const narrow = STYLE_CSS.slice(STYLE_CSS.indexOf("@media (max-width: 1024px)"));
  assert.match(narrow, /\.sidebar \{[^}]*flex-direction: row/);
  assert.match(narrow, /\.sidebar \{[^}]*position: sticky/);
  assert.match(narrow, /\.nav \{[^}]*flex-direction: row/);
  assert.match(narrow, /\.nav \{[^}]*overflow-x: auto/);

  // Labels are dropped only at the narrowest width, so the buttons must carry
  // their own accessible name rather than relying on the visible text.
  assert.match(STYLE_CSS, /@media \(max-width: 620px\)/);
  assert.match(SIDEBAR_NAV, /:aria-label="PAGES\[key\]\.title"/);
  assert.match(SIDEBAR_NAV, /aria-label="Settings"/);
});

test("Data Generator keeps execution and storage behind backend APIs", () => {
  assert.match(DATA_GENERATOR, /editorMode = ref\("guided"\)/);
  assert.doesNotMatch(DATA_GENERATOR, /structuredClone/);
  assert.match(DATA_GENERATOR, /chooseMode\(['"]json['"]\)/);
  assert.match(DATA_GENERATOR, /JSON configuration/);
  assert.match(DATA_GENERATOR, /preview\.rows/);
  assert.match(DATA_GENERATOR, /maximum 20/i);
  assert.match(DATA_GENERATOR, /generatorDownloadUrl/);
  assert.match(DATA_GENERATOR, /exportGeneratorRun/);
  assert.match(DATA_GENERATOR, /autocomplete="new-password"/);
  assert.match(DATA_GENERATOR, /exportForm\.value\.password = ""/);
  assert.match(DATA_GENERATOR, /window\.location\.protocol === "https:"/);
  assert.doesNotMatch(DATA_GENERATOR, /psycopg|postgresql:\/\//i);

  for (const route of [
    "/api/data-generator",
    "/api/data-generator/preset",
    "/api/data-generator/runs",
  ]) {
    assert.ok(CLIENT.includes(route), `${route} is absent from the API client`);
  }
});

test("Knowledge Base restores four operational references beside canonical review", () => {
  const expectedLabels = [
    "Touchpoint vocabulary",
    "Rules",
    "Entities",
    "Data sources",
    "Ontology Review",
  ];
  const tabDeclaration = KNOWLEDGE_BASE.match(/const tabs = Object\.freeze\(\[([\s\S]*?)\n\]\);/)?.[1] ?? "";
  const labels = [...tabDeclaration.matchAll(/label: "([^"]+)"/g)].map((match) => match[1]);

  assert.deepEqual(labels, expectedLabels);
  assert.match(KNOWLEDGE_BASE, /The first four tabs are operational references/);
  assert.match(KNOWLEDGE_BASE, /Ontology Review uses a[^;]+separate[^;]+canonical fixture source/s);
  assert.match(KNOWLEDGE_BASE, /The five-segment touchpoint key/);
  assert.match(KNOWLEDGE_BASE, /Reliability contract/);
  assert.match(KNOWLEDGE_BASE, /Advertising hierarchy/);
  assert.match(KNOWLEDGE_BASE, /Eligible targeting candidates/);
  assert.match(KNOWLEDGE_BASE, /Active source/);
  assert.match(KNOWLEDGE_BASE, /candidatePool/);
  for (const key of ["ArrowLeft", "ArrowRight", "Home", "End"]) {
    assert.match(KNOWLEDGE_BASE, new RegExp(key));
  }

  assert.match(KNOWLEDGE_BASE, /No Review API connected/);
  assert.match(KNOWLEDGE_BASE, /No request is sent and no verdict is calculated here/);
  assert.match(KNOWLEDGE_BASE, /new AbortController\(\)/);
  assert.match(KNOWLEDGE_BASE, /ontologyReviewAbortController\?\.abort\(\)/);
  assert.match(KNOWLEDGE_BASE, /section === "ontology-review"/);
  assert.match(ONTOLOGY_FIXTURES, /timeoutMs = 10000/);
  assert.match(ONTOLOGY_FIXTURES, /Promise\.race/);
  assert.match(ONTOLOGY_FIXTURES, /RELEASE_MANIFEST_SIZE = 1506/);
  assert.match(KNOWLEDGE_BASE, /Try again/);
  assert.doesNotMatch(KNOWLEDGE_BASE, /from "\.\.\/api\/client\.js"|globalThis\.fetch|ontologyReviewDemo/);
  assert.equal(PAGES.knowledge.defaultSection, "vocabulary");
  assert.deepEqual(Object.keys(PAGES.knowledge.sections), [
    "vocabulary",
    "rules",
    "entities",
    "sources",
    "ontology-review",
  ]);
});

test("Knowledge Base guards partial snapshot values without inventing provenance", () => {
  assert.match(KNOWLEDGE_BASE, /Array\.isArray\(data\.value\.attributionResults\)/);
  assert.match(KNOWLEDGE_BASE, /hasTotalDailyBudget/);
  assert.doesNotMatch(KNOWLEDGE_BASE, /total_daily_budget\s*\?\?\s*0/);
  assert.match(KNOWLEDGE_BASE, /mode === "database" \? "true" : mode \? "false" : "--"/);
  assert.match(KNOWLEDGE_BASE, /not stored in database mode/);
  assert.match(KNOWLEDGE_BASE, /No capacity rules are present in the current strategy_request\.json/);
  assert.match(KNOWLEDGE_BASE, /source has not been identified/);
  assert.doesNotMatch(KNOWLEDGE_BASE, /Switch <code>DATABASE<\/code>/);
  assert.match(KNOWLEDGE_BASE, /File-mode artifact contract/);
  assert.match(KNOWLEDGE_BASE, /this list is not\s+provenance for the active database/);
});

test("Knowledge Base keyboard navigation preloads before navigating and keeps narrow tabs reachable", () => {
  const preload = KNOWLEDGE_BASE.indexOf('await ensureResources(routeResources("knowledge", target.key))');
  const navigate = KNOWLEDGE_BASE.indexOf('emit("navigate", target.key)', preload);
  const focus = KNOWLEDGE_BASE.indexOf('document.getElementById', navigate);
  assert.ok(preload >= 0 && navigate > preload && focus > navigate);
  assert.match(KNOWLEDGE_BASE, /catch \{[\s\S]*route-level error/);

  const narrow = STYLE_CSS.slice(STYLE_CSS.indexOf("@media (max-width: 620px)"));
  assert.match(narrow, /\.knowledge-tabs\s*\{[^}]*overflow-x:\s*auto/s);
  assert.match(narrow, /\.knowledge-tabs \.tab\s*\{[^}]*flex:\s*0 0 auto/s);
  assert.match(narrow, /\.knowledge-tabs \.tab\s*\{[^}]*white-space:\s*nowrap/s);
});

test("Ontology Review exposes complete fail-closed fixture states and semantics", () => {
  for (const state of ["idle", "loading", "error", "empty", "ready"]) assert.match(KNOWLEDGE_BASE, new RegExp(`"${state}"`));
  for (const label of ["Plan identity", "Release identity", "Review and rule", "Evidence", "Limitations", "Risks and availability", "NEXT STEP"]) assert.match(KNOWLEDGE_BASE, new RegExp(label));
  for (const field of ["currentBudget", "recommendedBudget", "absoluteChangeRatio", "authorizationLimit", "source"]) assert.match(KNOWLEDGE_BASE, new RegExp(field));
  assert.match(ONTOLOGY_FIXTURES, /No R5 conflict was emitted/);
  assert.match(ONTOLOGY_FIXTURES, /strict > comparison/);
  assert.match(ONTOLOGY_FIXTURES, /does not mean the optimizer failed/i);
  assert.match(ONTOLOGY_FIXTURES, /not an industry benchmark/i);
  assert.doesNotMatch(ONTOLOGY_FIXTURES, /15%|0\.15/);
});

test("term help is accessible and links only into English documentation", () => {
  assert.match(TERM_HELP, /aria-describedby/);
  assert.match(TERM_HELP, /@mouseenter|@pointerenter/);
  assert.match(TERM_HELP, /@focusin/);
  assert.match(TERM_HELP, /@keydown\.esc/);
  assert.match(TERM_HELP, /target="_blank"/);

  const paths = TERM_REGISTRY.map((term) => term.href);
  assert.ok(paths.length > 0, "the term registry has no documentation links");
  assert.ok(paths.every((path) => path.startsWith("/en/")));
});

test("schema selection confirms, calls the backend, and reloads dashboard data", () => {
  assert.match(SETTINGS_DIALOG, /pendingSchema/);
  assert.match(SETTINGS_DIALOG, /Load another database schema\?/);
  assert.match(SETTINGS_DIALOG, /selectRuntimeSchema\(target\.name\)/);
  assert.match(SETTINGS_DIALOG, /@change="chooseDashboardSchema"/);
  assert.match(SETTINGS_DIALOG, /form\.value\.PG_SCHEMA = schemas\.value\.selected/);
  assert.match(SETTINGS_DIALOG, /emit\("changed"/);
  assert.match(CLIENT, /\/api\/settings\/schema-selection/);
});

test("database load recovery offers only backend-declared non-replacement actions", () => {
  assert.match(APP_VUE, /routeError\.code === 'database_unavailable'/);
  assert.match(APP_VUE, /<SchemaRecovery/);
  assert.match(SCHEMA_RECOVERY, /fetchSchemaRecovery/);
  assert.match(SCHEMA_RECOVERY, /selectRuntimeSchema/);
  assert.match(SCHEMA_RECOVERY, /startSchemaOperation/);
  assert.doesNotMatch(SCHEMA_RECOVERY, /replace\s*=\s*true|window\.confirm/);
  assert.match(CLIENT, /\/api\/schema-recovery/);
});

test("data-run diagnostics are a preference, off by default", () => {
  // The run identifier, seed, and configuration checksum answer an engineering
  // question about the pipeline rather than a marketing one, so they are
  // gated rather than shown beside the account's own records.
  assert.match(DIAGNOSTICS, /localStorage/);
  assert.match(DIAGNOSTICS, /enabled = ref\(readStored\(\)\)/);
  // Absent storage means off: a fresh reader never meets the diagnostic view.
  assert.match(DIAGNOSTICS, /getItem\(STORAGE_KEY\) === "true"/);
  assert.match(DIAGNOSTICS, /catch \{\s*return false;/);

  // The section exists only while the preference is on, and the open tab
  // falls back rather than stranding the reader on a hidden section.
  assert.match(BUDGET_MANAGER, /diagnosticsOn\.value\s*\?\s*\[\.\.\.BASE_SECTIONS/);
  assert.match(BUDGET_MANAGER, /watch\(SECTIONS/);
  assert.match(SETTINGS_DIALOG, /setDiagnostics\(\$event\.target\.checked\)/);
});

test("one cell renderer serves every table", () => {
  const dataTable = readFileSync(
    resolve(HERE, "..", "src", "components", "DataTable.vue"),
    "utf8",
  );
  // Two renderers would let the same column declaration mean two things in two
  // places. `DataTable` and `EntityTable` both read the shared helper.
  assert.match(dataTable, /renderCell/);
  assert.match(ENTITY_TABLE, /renderCell/);
  assert.match(dataTable, /NUMERIC_FORMATS/);
  assert.match(ENTITY_TABLE, /NUMERIC_FORMATS/);
});

test("table headers cycle ascending, descending, and backend order", async () => {
  const dataTable = readFileSync(
    resolve(HERE, "..", "src", "components", "DataTable.vue"),
    "utf8",
  );
  const { nextTableSort, sortTableRows } = await import("../src/lib/common.js");
  const sourceRows = [
    { name: "Beta", spend: 20 },
    { name: "alpha10", spend: null },
    { name: "Alpha2", spend: 3 },
  ];

  const ascending = nextTableSort({ key: null, direction: null }, "name");
  assert.deepEqual(ascending, { key: "name", direction: "asc" });
  const descending = nextTableSort(ascending, "name");
  assert.deepEqual(descending, { key: "name", direction: "desc" });
  const reset = nextTableSort(descending, "name");
  assert.deepEqual(reset, { key: null, direction: null });

  assert.deepEqual(
    sortTableRows(sourceRows, { key: "name", format: "text" }, "asc").map(
      ({ name }) => name,
    ),
    ["Alpha2", "alpha10", "Beta"],
  );
  assert.deepEqual(
    sortTableRows(sourceRows, { key: "spend", format: "money" }, "desc").map(
      ({ spend }) => spend,
    ),
    [20, 3, null],
  );
  assert.equal(sortTableRows(sourceRows, null, null), sourceRows);

  for (const component of [dataTable, ENTITY_TABLE]) {
    assert.match(component, /nextTableSort/);
    assert.match(component, /sortTableRows/);
    assert.match(component, /:aria-sort="ariaSort\(column\)"/);
    assert.match(component, /sort\.direction === "asc" \? "▲" : "▼"/);
  }
});

test("renderCell flattens the shapes the canonical records actually carry", async () => {
  const { renderCell } = await import("../src/lib/common.js");

  // A Provider's supported ad products are an array and a Product's provider
  // identifiers an object. `String(value)` renders the first as a comma-joined
  // list only by accident and the second as "[object Object]".
  assert.equal(
    renderCell({ key: "list" }, { list: ["SPONSORED_PRODUCTS", "AMAZON_DSP"] }),
    "SPONSORED_PRODUCTS, AMAZON_DSP",
  );
  assert.equal(renderCell({ key: "list" }, { list: [] }), "--");
  assert.equal(renderCell({ key: "map" }, { map: { a: 1 } }), '{"a":1}');

  // A missing number stays visibly missing rather than becoming zero.
  assert.equal(renderCell({ key: "n", format: "money" }, { n: null }), "--");
  assert.equal(renderCell({ key: "n", format: "money" }, { n: 12.5 }), "$12.50");
  assert.equal(renderCell({ key: "b", format: "flag" }, { b: false }), "No");
});

test("the destructive control is styled apart and never colour alone", () => {
  assert.match(STYLE_CSS, /\.btn\.danger/);
  // The cost of misreading a deletion is not symmetric with anything else, so
  // colour leads here — but the word is always present beside it.
  assert.match(ENTITY_TABLE, /btn small danger[\s\S]{0,80}Delete/);
  assert.match(CONFIRM_DIALOG, /btn danger/);
});

test("Campaigns exposes history filters and presentation-only similarity", () => {
  for (const label of ["Provider", "Product", "Campaign", "Ad product",
    "Marketplace", "Data run", "Configured budget vs actual spend",
    "Interaction-aware delivery"]) {
    assert.match(CAMPAIGNS, new RegExp(label, "i"));
  }
  // The data-run filter answers which pipeline run wrote a row, so it is
  // gated behind the diagnostics preference rather than shown by default.
  assert.match(CAMPAIGNS, /v-if="diagnosticsOn"[^>]*>\s*<label for="history-run"/);
  assert.match(
    CAMPAIGNS,
    /Historical reference only\. Not used by attribution or strategy optimization\./,
  );
  for (const field of ["subject_type", "subject_id", "comparable_id",
    "similarity_score", "rationale", "generated_by"]) {
    assert.match(CAMPAIGNS, new RegExp(field));
  }
  assert.match(CAMPAIGNS, /row\.similarity_score >= similarityThreshold\.value/);
  assert.match(CAMPAIGNS, /type="range" min="0" max="1" step="0\.05"/);
  assert.match(CAMPAIGNS, /row\.subject_id !== row\.comparable_id/);
  // Attribution output belongs to Campaign Optimizer, which owns the models
  // that produce it. This explorer restated that in a card carrying no figure
  // of its own, so the card is gone rather than duplicated here.
  assert.doesNotMatch(CAMPAIGNS, /Attribution evidence/);
  assert.doesNotMatch(CAMPAIGNS, /Attribution not available\./);
  assert.doesNotMatch(CAMPAIGNS, /data\.attributionResults/);
});

test("Campaigns chart bounds support the full database history", async () => {
  const { maxOf } = await import("../src/lib/common.js");
  const history = Array.from({ length: 100_000 }, (_, index) => ({
    configured_budget: index,
    actual_spend: index === 99_999 ? 125_000 : index + 0.5,
  }));

  assert.equal(maxOf(history, ["configured_budget", "actual_spend"], 1), 125_000);
  assert.equal(maxOf([{ value: null }, { value: Number.NaN }], ["value"], 1), 1);
  assert.match(CAMPAIGNS, /maxOf\(scopedHistory\.value/);
  assert.doesNotMatch(CAMPAIGNS, /\.\.\.scopedHistory\.value/);
});

test("merged observations keep their count and stay inside the grid", async () => {
  const { densityGrid } = await import("../src/lib/common.js");

  // The supported history size: one row per Campaign, date, and budget level.
  const rows = Array.from({ length: 100_000 }, (_, index) => ({
    configured_budget: (index % 800) + 1,
    actual_spend: ((index * 7) % 800) + 1,
  }));

  for (const resolution of [10, 40, 100]) {
    const grid = densityGrid(rows, "configured_budget", "actual_spend", 800, resolution);
    // Merging must not be losing: every observation lands in exactly one cell,
    // or the colour understates how much sits where.
    assert.equal(grid.total, rows.length);
    assert.equal(
      grid.z.flat().reduce((running, value) => running + (value ?? 0), 0),
      rows.length,
    );
    // The drawn marks follow the grid, not the row count. That is the whole
    // reason this replaced a scatter: 100,000 markers freeze the tab.
    assert.equal(grid.z.length, resolution);
    for (const line of grid.z) assert.equal(line.length, resolution);
    assert.ok(grid.occupied <= resolution * resolution);
    // The last cell's far edge sits on the bound, so no brick is drawn past
    // the axis range the layout sets.
    assert.ok(Math.abs(grid.x0 - grid.dx / 2 + grid.dx * resolution - 800) < 1e-9);
  }

  // A value exactly at the bound belongs in the last cell rather than one past
  // the end of the matrix, where it would be dropped silently.
  const atBound = densityGrid([{ x: 10, y: 10 }], "x", "y", 10, 10);
  assert.equal(atBound.z[9][9], 1);
  assert.equal(atBound.total, 1);

  // An empty cell is `null`, never 0: a drawn zero reads as "a few here".
  assert.ok(!atBound.z.flat().includes(0));
  assert.match(CAMPAIGNS, /hoverongaps: false/);

  // Degenerate inputs a filtered view reaches: no rows at all, and rows whose
  // measures are missing.
  assert.equal(densityGrid([], "x", "y", 1, 10).total, 0);
  assert.equal(densityGrid([], "x", "y", 1, 10).z.length, 10);
  assert.equal(
    densityGrid([{ x: null, y: 1 }, { x: "n/a", y: 2 }, { x: 1, y: 1 }], "x", "y", 10, 10).total,
    1,
  );
  assert.equal(densityGrid([{ x: 0, y: 0 }], "x", "y", 0, 4).densest, 1);
});

test("the delivery chart merges observations at a resolution the reader picks", () => {
  // Plotly's scatter emits one mark per observation. A full history is 100,000
  // of them, most landing where another has already drawn, so the ink said only
  // "something is here". The count is what the overplotting hid, so the chart
  // encodes the count and draws at most `resolution²` marks either way.
  assert.match(CAMPAIGNS, /const DENSITY_RESOLUTIONS = \[10, 40, 100\]/);
  assert.match(CAMPAIGNS, /densityGrid\(/);
  assert.match(CAMPAIGNS, /type: "heatmap"/);
  assert.doesNotMatch(CAMPAIGNS, /scattergl/);
  // Explicit origin and cell size. Given only the occupied coordinates Plotly
  // infers brick widths from their spacing, which on a sparse grid draws
  // bricks of uneven size that misstate where an observation sat.
  for (const key of ["x0", "dx", "y0", "dy"]) {
    assert.match(CAMPAIGNS, new RegExp(`${key}: grid\\.${key}`));
  }
  // The resolution is a control, not a constant, and its effect is stated.
  assert.match(CAMPAIGNS, /v-model\.number="densityResolution"/);
  assert.match(CAMPAIGNS, /observations in this cell/);
  assert.match(CAMPAIGNS, /densitySummary/);
  // The diagonal is what makes the chart readable: a cell above it overspent.
  assert.match(CAMPAIGNS, /dash: "dash"/);

  // Grouped in one pass. A `filter` per Campaign rescans the whole history
  // once per series, which is 40 full scans on every filter change.
  assert.doesNotMatch(
    CAMPAIGNS,
    /scopedHistory\.value\.filter\(\(row\) => row\.campaign_id === campaign\)/,
  );
});

test("a narrower history window is fetched, not filtered in the browser", async () => {
  const dashboardStore = readFileSync(
    resolve(HERE, "..", "src", "lib", "useDashboard.js"),
    "utf8",
  );
  const client = readFileSync(resolve(HERE, "..", "src", "api", "client.js"), "utf8");
  const { WINDOWED_RESOURCES } = await import("../src/pages.js");

  // Narrowing the range must shrink the transfer. Filtering rows already in the
  // browser only hides what the reader has already waited for.
  assert.ok(WINDOWED_RESOURCES.has("research-campaign-history"));
  assert.match(client, /query\.set\("start", window\.start\)/);
  assert.match(client, /query\.set\("end", window\.end\)/);

  // Cached per window as well as per resource, or widening the range would be
  // answered from the narrower slice already loaded under the bare name.
  assert.match(dashboardStore, /function cacheKey\(resource\)/);
  assert.match(dashboardStore, /\$\{resource\}:\$\{start \?\? ""\}:\$\{end \?\? ""\}/);
  assert.match(dashboardStore, /completed\.value\.has\(key\)/);
  // Only the windowed resources reload: the entity catalogues beside them do
  // not vary with the date, and refetching them would make changing a date
  // re-transfer everything.
  assert.match(dashboardStore, /currentResources\.filter\(\(resource\) =>\s*WINDOWED_RESOURCES\.has\(resource\)/);

  // The reader is told what was excluded; the rows that survived a window
  // cannot say what range they were taken from.
  assert.match(CAMPAIGNS, /loadedWindow\.earliest/);
  assert.match(CAMPAIGNS, /loadedWindow\.latest/);
  assert.match(CAMPAIGNS, /windowIsPartial/);
  // "Load everything" asks for the observed range, not for no window at all:
  // no window is what the backend answers with its recent-quarter default, so
  // clearing the dates would request the slice already loaded.
  assert.match(CAMPAIGNS, /setHistoryWindow\(\{ start: earliest, end: latest \}\)/);
  assert.match(CAMPAIGNS, /v-if="windowIsPartial"[\s\S]{0,120}Load everything/);

  // Budget Overview reads the same windowed resource and sums it into tiles.
  // A total labelled "Actual spend" over a slice the reader did not choose and
  // cannot see is a wrong number, so it states the period it covers.
  assert.match(BUDGET_MANAGER, /research\.value\.historyWindow/);
  assert.match(BUDGET_MANAGER, /historyPeriod/);
});

test("a static host honours the same window against its whole files", async () => {
  // A static file is written at build time and cannot be re-queried, so the
  // bounds are applied after it arrives. The view must not have to ask which
  // deployment it is in, so the payload reports the window either way.
  const { windowStaticPayload } = await loadClientModule(true);
  const whole = {
    simulationResearch: {
      campaigns: [{ campaign_id: "c1" }],
      history: [
        { report_date: "2026-01-01", configured_budget: 1 },
        { report_date: "2026-02-15", configured_budget: 2 },
        { report_date: "2026-03-30", configured_budget: 3 },
      ],
      delivery: [
        { report_date: "2026-01-01", cost: 1 },
        { report_date: "2026-03-30", cost: 3 },
      ],
      historyWindow: {
        start: null, end: null, earliest: "2026-01-01", latest: "2026-03-30",
      },
    },
  };

  const bounded = windowStaticPayload(whole, { start: "2026-02-01", end: "2026-03-01" });
  assert.deepEqual(
    bounded.simulationResearch.history.map((row) => row.report_date),
    ["2026-02-15"],
  );
  assert.deepEqual(bounded.simulationResearch.delivery, []);
  // The applied bounds are reported, and the full recorded range is left as the
  // file wrote it -- that is what tells the reader what the window excluded.
  assert.deepEqual(bounded.simulationResearch.historyWindow, {
    start: "2026-02-01", end: "2026-03-01",
    earliest: "2026-01-01", latest: "2026-03-30",
  });
  // Fields that do not vary with the window survive untouched.
  assert.deepEqual(bounded.simulationResearch.campaigns, [{ campaign_id: "c1" }]);
  // The source is not mutated, or a later widening would read a filtered cache.
  assert.equal(whole.simulationResearch.history.length, 3);

  // No window means the whole file, and a resource carrying no history at all
  // passes through as it came.
  assert.equal(
    windowStaticPayload(whole, null).simulationResearch.history.length,
    3,
  );
  const unwindowed = { simulationResearch: { providers: [{ provider: "p" }] } };
  assert.equal(windowStaticPayload(unwindowed, { start: "2026-02-01" }), unwindowed);
  assert.equal(windowStaticPayload({ adsDaily: [] }, { start: "2026-02-01" }).adsDaily.length, 0);
});

test("Campaigns reads through the same paged table Budget Manager uses", () => {
  // One table component across both views, so a reader who learns to page and
  // search in one already knows the other.
  assert.match(CAMPAIGNS, /import EntityTable from/);
  assert.doesNotMatch(CAMPAIGNS, /<TableView/);
  assert.doesNotMatch(CAMPAIGNS, /import TableView from/);
  for (const key of ["historyRowKey", "bridgeRowKey", "pathRowKey",
    "touchpointRowKey", "scopedRowKey"]) {
    assert.match(CAMPAIGNS, new RegExp(`const ${key} =`));
  }
  // Every tab is one branch of one chain. A second `v-if` would let the
  // trailing `v-else` render underneath an earlier tab's content.
  assert.equal((CAMPAIGNS.match(/<template v-if="tab === /g) ?? []).length, 1);
});

// ---------------------------------------------------------------------------
// Running a pipeline stage
// ---------------------------------------------------------------------------

test("a stage reports the phase it is in, not a timer", () => {
  // `aria-valuenow` and the visible percentage read one value: a screen reader
  // and the bar must not be able to report different progress.
  assert.match(STAGE_RUNNER, /role="progressbar"/);
  assert.match(STAGE_RUNNER, /:aria-valuenow="job\.percent"/);
  assert.match(STAGE_RUNNER, /job\.percent \}\}%/);
  // The command is shown verbatim, which is the point of running the real
  // script rather than a reimplementation of it.
  assert.match(STAGE_RUNNER, /job\.command/);
});

test("route resources load lazily with immediate backend phase progress", async () => {
  const client = readFileSync(
    resolve(HERE, "..", "src", "api", "client.js"),
    "utf8",
  );
  const dashboardStore = readFileSync(
    resolve(HERE, "..", "src", "lib", "useDashboard.js"),
    "utf8",
  );
  const progress = readFileSync(
    resolve(HERE, "..", "src", "components", "LoadingProgress.vue"),
    "utf8",
  );
  const { PAGES, parseRoute, routeHash, routeResources } = await import("../src/pages.js");
  assert.match(client, /\/api\/dashboard\/resources\//);
  assert.match(client, /response\.body\.getReader/);
  assert.match(client, /Content-Length/);
  assert.match(client, /application\/x-ndjson/);
  assert.match(client, /frame\.type === "progress"/);
  assert.match(dashboardStore, /visible: true/);
  assert.match(dashboardStore, /elapsedMs/);
  assert.match(progress, /role="progressbar"/);
  assert.match(dashboardStore, /const inFlight = new Map\(\)/);
  assert.match(dashboardStore, /completed\.value\.has\(cacheKey\(resource\)\)/);
  assert.deepEqual(parseRoute("#campaigns"), { page: "campaigns", section: "history" });
  assert.deepEqual(parseRoute("#/campaigns/paths"), { page: "campaigns", section: "paths" });
  assert.deepEqual(parseRoute("#/campaigns/not-declared"), {
    page: "campaigns", section: "history",
  });
  assert.deepEqual(parseRoute("#/not-declared/anything"), {
    page: "overview", section: "summary",
  });
  assert.equal(routeHash("budget", "product-economics"), "#/budget/product-economics");
  assert.deepEqual(routeResources("campaigns", "performance"), ["shell", "performance"]);
  assert.deepEqual(routeResources("campaigns", "paths"), ["shell", "path-report"]);
  assert.deepEqual(routeResources("knowledge", "vocabulary"), ["shell", "attribution"]);
  assert.deepEqual(routeResources("knowledge", "rules"), ["shell", "budget"]);
  assert.deepEqual(routeResources("knowledge", "entities"), ["shell", "budget"]);
  assert.deepEqual(routeResources("knowledge", "sources"), ["shell"]);
  assert.deepEqual(routeResources("knowledge", "ontology-review"), ["shell"]);
  assert.equal(PAGES.optimizer.defaultSection, "attribution");
  assert.match(APP_VUE, /pushState/);
  assert.match(APP_VUE, /popstate/);
  assert.match(APP_VUE, /route\.section === "generation-configs"/);
  assert.match(APP_VUE, /!diagnosticsOn\.value/);
  assert.match(CAMPAIGNS, /emit\('navigate', entry\.key\)/);
  assert.match(BUDGET_MANAGER, /navigateSection\(key\)/);
});

test("a resource stream is read in one pass over each chunk", async () => {
  // The result frame is the whole resource on one line -- tens of megabytes for
  // a full Campaign history. Reading it by appending to a buffer and splitting
  // that buffer per chunk rescans every byte already received, so the cost is
  // quadratic in the frame size and the tab stops answering for the duration.
  // This asserts the observable consequence rather than the implementation:
  // a large single-line frame must parse in time a reader would not notice.
  const { readResourceStream } = await loadClientModule();

  const rows = Array.from({ length: 60_000 }, (_, index) => ({
    campaign_id: `campaign_${index % 40}`,
    report_date: "2026-01-01",
    configured_budget: index,
    actual_spend: index + 0.5,
    note: "padding that makes each row a realistic width",
  }));
  const frames =
    JSON.stringify({ type: "progress", percent: 42, phase: "Querying" }) + "\n" +
    JSON.stringify({ type: "result", payload: { simulationResearch: { history: rows } } }) + "\n";

  const phases = [];
  const started = process.hrtime.bigint();
  const payload = await readResourceStream(chunkedResponse(frames), (update) => {
    if (update.phase) phases.push(update.phase);
  });
  const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;

  assert.equal(payload.simulationResearch.history.length, 60_000);
  // The server's own milestone must still reach the progress report, and the
  // terminal frame must mark completion.
  assert.deepEqual(phases, ["Querying", "Dashboard data ready"]);
  // Generous next to the quadratic read this replaced, which took tens of
  // seconds on a frame this size, and far above a linear read's own cost.
  assert.ok(
    elapsedMs < 4000,
    `reading a ${(frames.length / 1024 / 1024).toFixed(1)} MB frame took ${elapsedMs.toFixed(0)} ms`,
  );
});

test("a resource stream reports its terminal frames", async () => {
  const { readResourceStream } = await loadClientModule();

  // A backend that streams milestones and then dies must not resolve with a
  // half-populated snapshot; the route's error card is the honest outcome.
  await assert.rejects(
    readResourceStream(
      chunkedResponse(JSON.stringify({ type: "progress", percent: 5, phase: "x" }) + "\n"),
      () => {},
    ),
    /ended without data/,
  );

  // An error frame carries the code the shell reads to offer schema recovery.
  await assert.rejects(
    readResourceStream(
      chunkedResponse(
        JSON.stringify({
          type: "error",
          payload: { error: "database_unavailable", message: "no database" },
        }) + "\n",
      ),
      () => {},
    ),
    (error) => error.code === "database_unavailable" && /no database/.test(error.message),
  );
});

test("the offered budget policies are the ones the optimizer accepts", () => {
  const enums = readFileSync(
    resolve(HERE, "..", "..", "modules", "mta_common", "src", "enums.py"),
    "utf8",
  );
  // The view's dropdown, the server's whitelist, and the Python enum are three
  // copies of one list; a value in the dropdown that the enum does not declare
  // fails only once the run is already underway.
  for (const policy of ["SPEND_FULL_BUDGET", "SPEND_UP_TO_BUDGET"]) {
    assert.match(CAMPAIGN_OPTIMIZER, new RegExp(`value: "${policy}"`));
    assert.match(enums, new RegExp(`${policy} = "${policy}"`));
  }
});

test("each model run uses a server-issued dataset selection", () => {
  // Filtering the Ads report alone fails validation: every conversion must
  // fall inside the window the Ads report implies.
  assert.match(RUN_PIPELINE_PY, /_windowed_copy\(/);
  assert.match(RUN_PIPELINE_PY, /"reportDate"/);
  assert.match(RUN_PIPELINE_PY, /"event_time"/);
  // Reconciliation runs only under a narrowed window, so an unnarrowed run
  // still fails on a genuine extract mismatch instead of silently repairing it.
  assert.match(
    RUN_PIPELINE_PY,
    /if report_start_date is not None or report_end_date is not None:\s*\n\s*amazon_ads_report, excluded = _reconcile_windowed_ads_report/,
  );
  assert.match(RUN_PIPELINE_PY, /Excluded \{touchpoint\}/);
  // The dashboard sends only a server-issued dataset identifier; the service
  // materializes the selected scope and invokes the current interpreter.
  const jobs = readFileSync(
    resolve(HERE, "..", "..", "backend", "services", "jobs.py"),
    "utf8",
  );
  assert.match(STAGE_RUNNER, />Data<\/label>/);
  assert.match(STAGE_RUNNER, /options\.datasetId/);
  assert.match(jobs, /sys\.executable/);
  assert.match(jobs, /prepare_dataset\(stage, selected\)/);
  assert.doesNotMatch(CAMPAIGN_OPTIMIZER, /startDate|endDate/);
});
