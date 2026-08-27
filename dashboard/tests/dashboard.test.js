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
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const { PAGES, PAGE_GROUPS, PAGE_KEYS, DEFAULT_PAGE } = await import("../src/pages.js");

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
const RUN_PIPELINE_PY = readFileSync(
  resolve(HERE, "..", "..", "script", "run_pipeline.py"),
  "utf8",
);

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

test("the two foot controls are drawn but are not navigable pages", () => {
  for (const key of ["reload", "settings"]) {
    assert.ok(PAGES[key], `${key} has no icon entry`);
    assert.ok(!PAGE_KEYS.includes(key), `${key} must not be a navigable page`);
  }
});

test("page keys are unique and the default is one of them", () => {
  assert.equal(new Set(PAGE_KEYS).size, PAGE_KEYS.length);
  assert.ok(PAGE_KEYS.includes(DEFAULT_PAGE));
  assert.equal(PAGE_GROUPS.flatMap((group) => group.pages).length, PAGE_KEYS.length);
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

  // The saved selection survives an unreachable database, or the dropdown would
  // show a schema the reader never chose and save it on the next write.
  assert.match(SETTINGS_DIALOG, /listed\.some\(\(item\) => item\.name === current\)/);
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

test("schema setup exposes discovery-driven initialization, parsing, and logs", () => {
  assert.match(SETTINGS_DIALOG, /id="setup-schema"/);
  assert.match(SETTINGS_DIALOG, /v-for="option in schemas\.schemas"/);
  assert.match(SETTINGS_DIALOG, /Initialize sample model/);
  assert.match(SETTINGS_DIALOG, /Parse all scenarios/);
  assert.match(SETTINGS_DIALOG, /operation\.lines/);
  assert.match(SETTINGS_DIALOG, /operation\.command/);

  const client = readFileSync(resolve(HERE, "..", "src", "api", "client.js"), "utf8");
  assert.match(client, /fetchSchemaOperation/);
  assert.match(client, /startSchemaOperation/);
  assert.match(client, /stopSchemaOperation/);
  assert.match(client, /\/api\/schema-operations/);
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

  // Labels are dropped only at the narrowest width, so the buttons must carry
  // their own accessible name rather than relying on the visible text.
  assert.match(STYLE_CSS, /@media \(max-width: 620px\)/);
  assert.match(SIDEBAR_NAV, /:aria-label="PAGES\[key\]\.title"/);
  assert.match(SIDEBAR_NAV, /aria-label="Settings"/);
  assert.match(SIDEBAR_NAV, /aria-label="Reload data"/);
});

test("the bar collapses each multi-page group instead of flattening it", () => {
  // Hiding the group headings dropped OVERVIEW, PLANNING, and INSIGHTS from the
  // bar entirely, leaving six views as one undifferentiated strip. The bar now
  // carries a labelled disclosure per group, so the sections survive the
  // breakpoint.
  const narrow = STYLE_CSS.slice(STYLE_CSS.indexOf("@media (max-width: 1024px)"));

  // The group is a positioned box only in the bar; the column leaves its
  // children directly in `.nav`, which is the layout it has always had.
  assert.match(STYLE_CSS, /\.nav-group,\s*\.nav-group-items \{\s*display: contents/);
  assert.match(narrow, /\.nav-group\.collapsible \{[^}]*position: relative/);

  // The panel floats over the content rather than growing the bar back into
  // the tall block the bar exists to avoid.
  assert.match(narrow, /\.nav-group\.collapsible > \.nav-group-items \{[^}]*position: absolute/);

  // A group with one page is not worth a disclosure, and a heading that does
  // nothing is not a button.
  assert.match(SIDEBAR_NAV, /group\.pages\.length > 1/);
  assert.match(SIDEBAR_NAV, /v-if="!isCollapsible\(group\)" class="nav-label"/);

  // The disclosure state is real state, so the component owns it rather than
  // the stylesheet, and the breakpoint it watches is the stylesheet's own.
  const breakpoint = SIDEBAR_NAV.match(/BAR_BREAKPOINT = "\(max-width: (\d+)px\)"/);
  assert.ok(breakpoint, "SidebarNav must state the breakpoint it collapses at");
  assert.ok(
    STYLE_CSS.includes(`@media (max-width: ${breakpoint[1]}px)`),
    "the rail's collapse breakpoint has drifted from the stylesheet's",
  );

  // A disclosure has to announce itself, say which panel it owns, and close on
  // the routes a reader expects.
  assert.match(SIDEBAR_NAV, /:aria-expanded="openGroup === group\.label"/);
  assert.match(SIDEBAR_NAV, /:aria-controls="panelId\(group\)"/);
  assert.match(SIDEBAR_NAV, /:hidden="isCollapsible\(group\) && openGroup !== group\.label"/);
  assert.match(SIDEBAR_NAV, /event\.key === "Escape"/);
  assert.match(SIDEBAR_NAV, /pointerdown/);

  // A closed group still shows the reader is inside it, and widening the
  // window cannot leave a panel open over an already-expanded column.
  assert.match(SIDEBAR_NAV, /currentGroup === group\.label/);
  assert.match(SIDEBAR_NAV, /if \(!event\.matches\) openGroup\.value = ""/);

  // Every listener the component adds is removed again.
  for (const event of ["pointerdown", "keydown"]) {
    assert.ok(
      SIDEBAR_NAV.includes(`document.removeEventListener("${event}"`),
      `SidebarNav leaks its ${event} listener`,
    );
  }
  assert.match(SIDEBAR_NAV, /query\?\.removeEventListener\("change"/);
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
  assert.match(CAMPAIGNS, /Attribution not available\./);
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

test("a narrowed run filters both inputs and names what it excluded", () => {
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
  // The dashboard passes the window through as the documented flags rather
  // than narrowing anything itself.
  const jobs = readFileSync(
    resolve(HERE, "..", "..", "backend", "services", "jobs.py"),
    "utf8",
  );
  assert.match(jobs, /"--report-start-date", options\["startDate"\]/);
  assert.match(jobs, /"--report-end-date", options\["endDate"\]/);
  assert.match(RUN_PIPELINE_PY, /"--report-start-date"/);
  assert.match(RUN_PIPELINE_PY, /"--report-end-date"/);
});
