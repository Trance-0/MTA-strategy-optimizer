---
title: Dashboard
description: The Streamlit dashboard, its six views, its dual data source, and the published browser build
compact: "Presentation layer specification: `streamlit run dashboard/app.py`, the six views (Command Center, Budget Manager, Campaigns, Campaign Optimizer, Optimization Log, Knowledge Base), the navigation rail and its settings module, the DATABASE=true/false dual source contract, the stlite browser build published to GitHub Pages, and the rule that the dashboard never recomputes a pipeline number. Read before adding a view or a chart."
lang: en-US
source_files: dashboard/config.py, dashboard/models.py, dashboard/data_source.py, dashboard/theme.py, dashboard/app.py, dashboard/settings.py, dashboard/views/command_center.py, dashboard/views/budget_manager.py, dashboard/views/campaigns.py, dashboard/views/campaign_optimizer.py, dashboard/views/optimization_log.py, dashboard/views/knowledge_base.py, dashboard/views/common.py, dashboard/run.sh, dashboard/run.bat, web/index.html, script/import_to_database.py, script/verify_source_parity.py, script/build_pages_site.mjs
---

# Dashboard

The dashboard is the project's presentation layer. It reads the artifacts the pipeline already produces and renders them for a reader who will not run Python: attribution evidence per touchpoint, the reliability verdict that governs it, the recommended budget allocation, and the historical record all three were derived from.

It is deployable locally with one command and is the surface used for demonstrations.

```bash
uv sync --extra dashboard
uv run --extra dashboard streamlit run dashboard/app.py
```

## The Rule That Shapes Everything Else <span class="status-label status-verified" aria-label="Verified"></span>

**The dashboard never computes an attribution share or a budget figure.** It reads them.

This is the constraint the whole module is built around. A presentation layer that recomputed a pipeline number would become a second, divergent implementation of it: the chart and the CSV would disagree, and nothing would say which one was wrong. Every number on screen therefore traces to an artifact under `modules/*/outputs/` or `modules/*/data/simulated/`, or to the database mirror of those files.

The one place the dashboard derives anything is the Campaign Optimizer's implied budget shift, which restates the recommended attribution as a spend split at constant total budget. It is labelled as a restatement wherever it appears, it does not predict the outcome of acting on it, it never overrides the pipeline's own allocation, and it is withheld entirely when the Outcome's verdict is UNRELIABLE.

## Dependency Boundary <span class="status-label status-verified" aria-label="Verified"></span>

The attribution, standard, and strategy modules use the Python standard library alone, and that property is worth keeping: it is what lets a reader reproduce every published number with no installation step. The dashboard needs Streamlit, Plotly, pandas, SQLAlchemy, and a PostgreSQL driver, so those dependencies are declared as an **optional extra** rather than as project dependencies.

```bash
uv sync --extra dashboard
```

Nothing under `modules/` imports anything from `dashboard/`, and the dependency never points the other way: `dashboard/` reads the modules' output files, not their Python code.

## Two Data Sources, One Contract <span class="status-label status-verified" aria-label="Verified"></span>

A single switch in `.env` decides where the numbers come from. `sample.env` is the tracked template; `.env` itself is ignored and must never be committed.

| `DATABASE` | Reads from | Used for |
| --- | --- | --- |
| `false` | The committed CSV and JSON artifacts | Cloud demonstrations, and any checkout that has not run an import |
| `true` | The PostgreSQL schema in [Dashboard data model](../datasets/dashboard-data-model.md) | A deployment with a populated database |

`dashboard/data_source.py` is the only module that knows which mode is active. Every loader it exposes returns the **same columns, dtypes, and values in both modes**, so no view can tell them apart and no view contains a branch on the data source. `script/verify_source_parity.py` asserts that property against a live database and exits non-zero on any difference.

Three real differences must be normalised for that contract to hold, and all three are handled in the loader rather than in a view:

- PostgreSQL folds unquoted identifiers to lowercase, so the advertising platform's camelCase field names survive only in file mode. Both modes are renamed to `snake_case`.
- The pipeline writes the reliability flags as the strings `true` and `false`. The non-empty string `"false"` is truthy in Python, so a view filtering on the raw string would keep unreliable rows in one mode and drop them in the other. They are parsed to real booleans.
- A date read from a file is a string; the same date from the database is a `date`. Pandas assigns each a different datetime unit, so both are parsed and pinned to one.

When `DATABASE=true` but the database is unreachable or empty, the dashboard says so on its own page and names the remedy, rather than surfacing a connection error from inside whichever chart happened to read it first.

## The Six Views <span class="status-label status-verified" aria-label="Verified"></span>

The navigation mirrors the reference design in `external/UI_design`. Each view is one module under `dashboard/views/` exposing a single `render()` that takes no arguments.

| View | Question it answers |
| --- | --- |
| Command Center | What was spent and returned, which touchpoints earned credit, and is that credit trustworthy? |
| Budget Manager | What daily budget does each Campaign get, and what derived it? |
| Campaigns | What actually happened, filtered and queried against the raw record? |
| Campaign Optimizer | Where do the two models disagree, and what spend shift does the recommendation imply? |
| Optimization Log | Which run produced these numbers, from which inputs, and can it be reproduced? |
| Knowledge Base | What do the terms mean and which rules do the numbers obey? |

Two of the reference design's views had no backing data in this project. Rather than ship placeholder content, each was pointed at the real record that answers the same question: Optimization Log shows run provenance and pipeline stage state, including the fact that the optimisation stage has **not** run; Knowledge Base is populated from the data in use, so it cannot drift from the charts beside it.

### Reliability is never a footnote

Every view that displays an attributed share displays its reliability verdict beside it, because an UNRELIABLE share must not be read as a fact. The verdict is the AND of the three flags, one false flag is enough to fail a row, and an UNRELIABLE Outcome carries an interval rather than a point value. The Campaign Optimizer refuses to show a budget shift for such an Outcome at all: an interval cannot carry a spend split.

## Visual Contract <span class="status-label status-recommendation" aria-label="Recommendation"></span>

`dashboard/theme.py` holds every colour, chart default, and card style, so a change lands everywhere at once and no view invents its own styling. The brand palette — navy sidebar, blue accent, light plane — is taken from the reference design. The series palette is a separate validated set, because the reference design contains no real charts and so could not supply one; it passes the lightness band, chroma floor, colourblind-separation, and normal-vision checks against the dashboard's white chart surface.

Three rules the views depend on:

- **Colour follows the entity, never its rank.** Markov is always the same blue and Shapley always the same orange, so filtering a chart never repaints the rows that survive and a reader who learned one association is never contradicted.
- **Status colour is reserved and never carries meaning alone.** A reliability pill always shows the status word itself.
- **One axis per chart.** Where two measures differ by orders of magnitude, as spend and sales do, both are indexed to their own window average and share one scale. A second y-axis would invent a correlation the data does not contain.

Every chart is paired with the values behind it — a table view, direct labels, or both — so no number is reachable only by hovering.

## Navigation Rail <span class="status-label status-verified" aria-label="Verified"></span>

The sidebar reproduces the reference design's rail rather than offering a select list: a navy column of stacked icon buttons, grouped under OVERVIEW, PLANNING, and INSIGHTS, with the active item filled in `#143a79`.

Streamlit has no icon-button navigation widget, so each item is a real `st.button` and the selection is held in session state. Two consequences are worth stating, because both are constraints Streamlit imposes rather than choices:

- **The icon is a background image on the button, not an element beside it.** An inline `<svg>` cannot live inside a button label, and a marker element drawn above the button cannot be reached from it: Streamlit wraps every element in its own container, so the two are never DOM siblings and no CSS combinator spans them. Painting the icon onto the button keeps glyph and label in one element, which is also what makes the whole tile a single hit target. Because a colour keyword does not inherit into a background image, `app.py` bakes the resting and active colours into two separate data URIs.
- **The active item is styled by a generated rule, not by a class.** The app cannot add a class to a container Streamlit owns, but a widget `key` becomes a `st-key-<key>` class on that container, so `app.py` emits a rule naming it. Those rules address the button through `.stButton > button`; without that extra class they tie on specificity with the shared button rule and lose the tie-break by document order.

### The settings module

Everything about the dashboard's own plumbing is pinned to the foot of the rail, ruled off from the view navigation above it, so it never reads as a seventh place to navigate to. It shows the active source, a status dot, and whether logging is on, and opens a modal with two tabs:

| Tab | Contains |
| --- | --- |
| Data source | The `DATABASE` toggle and the PostgreSQL host, port, database, user, password, and SSL mode, with **Test connection** and **Save to `.env`** |
| Logging | The streaming-data log switch, its level, and the captured records |

**Test connection** opens a throwaway connection using what was typed rather than what is saved, so a correction can be validated before it is committed to `.env`. Saving rewrites `.env` in place — comments and unrelated keys are preserved, and a key already present is replaced rather than appended, so a file cannot end up with two values for one key and the winner decided by read order. Saving also clears the config and loader caches, because `config.use_database()` is `lru_cache`d and would otherwise hold the old mode until a restart.

The password is never rendered back to the page or written to the log: `DatabaseSettings.safe_summary()` omits it by construction, and it is the only rendering of a connection the dashboard performs.

Logging is off by default, because logging every query costs time on each rerun. Enabled, it attaches a bounded in-memory handler to `dashboard`, `sqlalchemy.engine`, and `sqlalchemy.pool` — so what it captures is the actual SQL and connection activity as the data streams, not a decorative message. The buffer is a fixed-capacity deque rather than a file: a demonstration machine's disk cannot be filled by leaving the dashboard open.

### Links out of the app

The rail closes with **Docs** and **Repo**. A reader who arrives at the published dashboard has no other route to the specification or the source, so the app carries them. The documentation link is relative in the published build, where the documentation is a sibling directory, and absolute in a local run, where there is no sibling to point at.

## Running It Locally <span class="status-label status-verified" aria-label="Verified"></span>

```bash
./dashboard/run.sh          # macOS, Linux, Git Bash
dashboard\run.bat           # Windows
```

Both take an optional port, resolve the repository root themselves so they work from any directory, verify `uv` is installed, and copy `sample.env` to `.env` when none exists — so a fresh clone starts in file mode rather than failing on a missing variable. They skip `uv sync` when the extra is already present. Reading the PostgreSQL mirror is a matter of setting `DATABASE=true` and the `PG_*` values in `.env`; nothing about the command changes.

## Published Build <span class="status-label status-verified" aria-label="Verified"></span>

The dashboard is deployed to GitHub Pages at the site root, with the documentation one level down at `/docs/`.

GitHub Pages serves static files and cannot run a Streamlit server, so the published copy runs the **same `dashboard/` Python in the visitor's browser** through [stlite](https://github.com/whitphx/stlite), which executes Streamlit on Pyodide — CPython compiled to WebAssembly. `script/build_pages_site.mjs` copies the sources rather than forking them: the web build is a different runtime, never a different codebase. It fails the build if `web/index.html` and its own file list disagree, because a file added to one and not the other would otherwise surface as a missing-module error in a visitor's console.

Three consequences follow from running in a browser tab, and each is handled rather than hidden:

- **The database source is unavailable.** WebAssembly has no raw TCP socket, so no configuration could reach PostgreSQL from that page. `web/index.html` exports `DASHBOARD_HOSTED`, `config.use_database()` returns false whenever it is set, and the settings modal replaces the credential form with the local-run instructions. A visitor is never invited to type a real password into a page that cannot use it.
- **The first load is slow.** Downloading and starting the Python runtime takes roughly 30–80 seconds on a cold cache, against about a second locally. The page states that on its splash rather than showing a blank screen, and the splash is held until the dashboard's own first paint rather than lifted on a timer, so a slow runtime is never revealed as an empty page.
- **Only the artifacts the loaders read are published.** Eleven files, about 330 KB. The 2.8 MB synthetic-events extract is excluded because no view reads it, and publishing it would cost every visitor a download for nothing.

The workflow is `.github/workflows/deploy-pages.yml`. It builds the documentation with its base path set to the Pages base plus `docs/`, because Pages performs no rewrites and every internal link is resolved at build time, then assembles both into `site/` and uploads that as the Pages artifact.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

The code-level specification for the Python files this page describes. Each entry states responsibility, inputs, outputs, dependencies, and the test that verifies it.

### `config.py`

Source: `dashboard/config.py`

- Responsibility: Read `.env` at the repository root and expose the one switch that decides the data source, the PostgreSQL settings, and the artifact paths every other dashboard module resolves against.
- Inputs: `.env` at the repository root, loaded without overriding real environment variables so a shell export or a container secret wins. `DATABASE` is true for any of `1`, `true`, `yes`, `on`, case-insensitively; anything else, including absence, is false. `DASHBOARD_HOSTED` uses the same vocabulary and is set only by the published browser build.
- Outputs: `use_database() -> bool`; `is_hosted() -> bool`; `database_settings() -> DatabaseSettings`; the path constants `REPO_ROOT`, `SIMULATED_DIR`, `ATTRIBUTION_OUTPUT_DIR`, `STRATEGY_INPUT_DIR`, and `STRATEGY_OUTPUT_DIR`; and `DESCRIPTION_ROW_MARKERS`, the exact first-cell values that identify the Chinese field-description row every reader must drop.
- Behavior contract: `DatabaseSettings.url()` percent-encodes the user and password. This is required, not defensive: a password containing `@` or `/` otherwise corrupts the URL and fails as a misleading host-resolution error. `safe_summary()` returns a display string that never contains the password, and is what the sidebar and the import command print. `database_settings()` raises `RuntimeError` naming every missing variable and pointing at `sample.env`, rather than failing later at connection time. `use_database()` returns false whenever `is_hosted()` is true, regardless of `DATABASE` — the browser has no socket to open, so the hosted flag decides before the switch is read. The accessors are `lru_cache`d, so the mode is fixed for the life of the process.
- Dependencies: `python-dotenv`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/verify_source_parity.py`, which loads both modes in separate subprocesses precisely because the cache prevents one process from holding both.

### `models.py`

Source: `dashboard/models.py`

- Responsibility: Define the PostgreSQL schema the dashboard reads when `DATABASE=true`. This module is the single definition of that schema; no other file declares a table.
- Inputs: None at runtime. The classes are declarations, instantiated by `script/import_to_database.py` and queried by `dashboard/data_source.py`.
- Outputs: `Base` plus eighteen mapped classes in four layers — entity (`Advertiser`, `CampaignGroup`, `Campaign`, `AdGroup`, `Touchpoint`, `TargetingCandidate`), history (`AdsDailyPerformance`, `PathReport`, `TouchpointEntityBridge`, `SyntheticUserEvent`), model output (`AttributionRun`, `AttributionResult`, `ModelComparisonTouchpoint`, `ModelComparisonSummary`, `RecommendedAttribution`), and strategy (`BudgetRecommendationRun`, `CampaignBudgetRecommendation`, `AdGroupBudgetSlot`). Field-level meaning is specified in [Dashboard data model](../datasets/dashboard-data-model.md).
- Behavior contract: This module sits at the edge of the project. The attribution, standard, and strategy modules must never import it, because they read and write files and depend on the standard library alone. Every run-scoped table carries a foreign key to its run, so two report windows coexist rather than overwrite. The `UniqueConstraint` on each output table is scoped by `run_pk`, which is what makes a re-import of the same window a conflict rather than a silent duplicate. `Touchpoint.touchpoint_key` is globally unique and stores its five segments as columns as well, so a view can group by any segment without parsing the key.
- Dependencies: SQLAlchemy 2.0. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run` reports the row count each class will receive without opening a connection. A schema change requires `--replace`, which drops and rebuilds every table.

### `data_source.py`

Source: `dashboard/data_source.py`

- Responsibility: Be the only module that knows whether the dashboard is reading files or a database, and return results a view cannot distinguish between the two.
- Inputs: `dashboard.config` for the mode and the paths; the committed artifacts under `modules/*/`; or the PostgreSQL tables in `dashboard/models.py`.
- Outputs: Seven `DataFrame` loaders — `load_ads_daily`, `load_attribution_results`, `load_comparison_touchpoints`, `load_comparison_summary`, `load_recommended_attribution`, `load_entity_bridge`, `load_path_report` — and three that return the JSON artifacts' own nested shape: `load_budget_recommendation`, `load_strategy_request`, `load_candidate_pool`. Also `active_mode()`, `source_label()`, `database_available()`, and `clear_caches()`.
- Behavior contract: **Every loader returns identical columns, dtypes, and values in both modes.** A view must never branch on the data source, and none does. Three differences are normalised here to make that true: PostgreSQL folds unquoted identifiers to lowercase, so file mode is renamed to `snake_case` to match rather than the database quoting every alias; the pipeline writes reliability flags as the strings `true`/`false` and the non-empty string `"false"` is truthy, so they are coerced to real booleans; dates arrive as strings from a file and as `date` objects from the database, and pandas infers a different unit for each, so both are parsed and pinned. `_read_csv` drops the Chinese description row by matching its exact marker rather than by heuristic, because a heuristic silently discards a real data row from the files that have no such row. `database_available()` returns a `(usable, message)` pair instead of raising, so the shell can report a connection failure as a page rather than as a stack trace inside a chart.
- Dependencies: pandas, Streamlit's `cache_data`, SQLAlchemy, and `psycopg`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/verify_source_parity.py`. It compares columns, dtypes, row counts, numeric totals, boolean sums, and the document loaders' key sets across the two modes, and exits non-zero naming any field that differs.

### `theme.py`

Source: `dashboard/theme.py`

- Responsibility: Hold every colour, chart default, card style, and value format the dashboard uses, so a change lands everywhere at once and no view invents its own styling.
- Inputs: None. The module is constants and pure display helpers.
- Outputs: Brand constants taken from the reference design (`NAVY`, `BLUE`, `PLANE`, `SURFACE`, `LINE`, `TEXT`, `MUTED`, `SUBTLE`), the rail constants (`RAIL_TEXT`, `RAIL_ICON`, `RAIL_ICON_ACTIVE`, `RAIL_ACTIVE`, `RAIL_DIM`, `RAIL_RULE`), and the reserved status colours; the `SERIES`, `SEQUENTIAL`, and `DIVERGING` palettes; the fixed `MODEL_COLORS` and `OUTCOME_COLORS` maps; `series_colors()`; `style_figure()`; `inject_css()`; `status_pill()`, `panel()`, and `caption()`; and the `money()`, `number()`, and `percent()` formatters.
- Behavior contract: `SERIES` is a fixed order assigned by slot and **never cycled**; a ninth series folds into "Other" rather than receiving a generated hue, which under colourblind simulation would be indistinguishable from an existing slot. `MODEL_COLORS` and `OUTCOME_COLORS` bind a colour to an entity rather than to a rank, so filtering a chart never repaints the rows that survive. The status colours are reserved for reliability state, are never reused as a series colour, and are always rendered with the status word beside them by `status_pill()`. `style_figure()` sets a hairline grid, solid axes, and a height that includes the axis band, so a chart card never grows an inner scrollbar; it sets the figure title to the empty string rather than only styling it, because styling a title that has no text leaves Plotly drawing the literal word `undefined` above the plot. Every chart is titled by the markdown heading above it, so no figure carries a title of its own. The rail stylesheet restates two wrappers Streamlit leaves as `display: block`, because pinning the settings module to the foot needs an unbroken flex column from the sidebar down to the item list; `margin-top: auto` goes on the layout wrapper rather than the keyed container, which is the flex item's actual parent. The series palette is not the reference design's: that design contains no real charts, so its three brand colours could not supply one. The eight hues used here pass the lightness band, chroma floor, colourblind separation, and normal-vision floor against this dashboard's white chart surface.
- Dependencies: Streamlit. Installed with `uv sync --extra dashboard`.
- Verification: Rendered visually. The palette is checked with the data-visualisation validator against the white chart surface; three light-mode hues fall below 3:1 contrast, which is why every chart also ships direct labels or a table view.

### `app.py`

Source: `dashboard/app.py`

- Responsibility: Configure the page, draw the navigation rail and its settings module, report where data is being read from, and dispatch to the selected view.
- Inputs: The rail selection, held in `st.session_state["view"]`. Nothing else; each view pulls its own data.
- Outputs: The rendered page. `NAV_GROUPS` maps each section label to the views beneath it in the reference design's order, `VIEWS` is its flattening and the single place a view is registered, `FOOT_ITEMS` names the two controls in the settings module, and `ICONS` holds one inline SVG per rail item.
- Behavior contract: `main()` checks `database_available()` before dispatching whenever `DATABASE=true`, and renders an error page naming both remedies — switch the mode, or run the import — rather than letting a connection failure surface as a stack trace inside whichever chart read it first. `rail_key()` is the single spelling shared by each widget's `key` and the CSS that targets it; it contains no space, because Streamlit rewrites a space to a hyphen in the generated `st-key-` class and the rule would then miss its button. `_icon_css()` emits the per-item background images and the active-item rule, both of which exist because Streamlit owns the containers and neither an icon element nor a class can be inserted into them; see [Navigation Rail](#navigation-rail). The Reload button clears the loader caches and reruns, which is the only supported way to pick up changed artifacts without restarting. `app.py` inserts the repository root on `sys.path` because Streamlit executes it as a script rather than importing it as part of the package.
- Dependencies: Streamlit, `dashboard.settings`, and every `dashboard.views` module. Installed with `uv sync --extra dashboard`.
- Verification: `dashboard/tests/test_views_render.py`, which uses Streamlit's `AppTest` to start the real app, assert the rail carries a button for every view and both foot items, assert no rail key contains a space, and render each view without raising. Run it with `uv run --extra dashboard python -X utf8 -B -m unittest discover -s dashboard/tests -p "test_*.py"`.

### `settings.py`

Source: `dashboard/settings.py`

- Responsibility: Back the settings module in the foot of the rail — edit the credentials this dashboard connects with, and capture the data access log while it streams.
- Inputs: `.env` at the repository root, the live environment as a fallback, and the reader's entries in the modal.
- Outputs: `settings_dialog()`, the two-tab modal; `status()`, the `(label, colour, detail)` triple the rail displays; `read_env()` and `write_env()`; `apply_logging()` and `logging_enabled()`; and `RingBufferHandler`, the bounded capture.
- Behavior contract: **No credential is written to a tracked file, to the page, or to the log.** `.env` is git-ignored, `sample.env` is the tracked template and holds no real value, and the password is rendered only through `config.DatabaseSettings.safe_summary()`, which omits it by construction. `write_env()` rewrites the file rather than appending to it, preserving comments and unrelated keys and replacing a key in place, so one key cannot end up with two values and the winner decided by read order; it then clears `config.use_database`, `config.database_settings`, and the loader caches, because the mode is `lru_cache`d and would otherwise survive the edit. `_test_connection()` connects with the values just typed rather than the values saved, so a correction can be validated before it is committed. The log handler is a fixed-capacity `deque`, not a file, so an open dashboard cannot fill a disk; it attaches to `dashboard`, `sqlalchemy.engine`, and `sqlalchemy.pool`, which is what makes the capture the real streaming activity rather than a decorative message, and it sets `propagate = False` so those records do not also flood the server console. Logging is off by default because it costs time on every rerun. `_escape()` escapes each captured message, so a log line cannot inject markup into the page.
- Dependencies: Streamlit and `dashboard.config`; SQLAlchemy for the connection test. Installed with `uv sync --extra dashboard`.
- Verification: `dashboard/tests/test_views_render.py::SettingsTests`, which asserts `write_env()` preserves comments and unrelated keys, appends a missing key exactly once, and that the handler stays bounded. The tests redirect `ENV_PATH` to a temporary file, so the real `.env` is never touched.

### The six view modules

Source: `dashboard/views/command_center.py`, `dashboard/views/budget_manager.py`, `dashboard/views/campaigns.py`, `dashboard/views/campaign_optimizer.py`, `dashboard/views/optimization_log.py`, `dashboard/views/knowledge_base.py`

The six share one contract and are specified together. `dashboard/views/__init__.py` is the package marker only and declares nothing.

- Responsibility: Render the six pages of the dashboard, one module per view, in the reference design's navigation order.

  | Module | Content |
  | --- | --- |
  | `command_center.py` | Five headline tiles, spend against return over time, the per-Outcome reliability verdict, and attributed revenue by ad product for both models. |
  | `budget_manager.py` | Handoff state, the recommended daily budget per Campaign against its required minimum, the derivation that produced it, the score composition, and the Ad Group slots. |
  | `campaigns.py` | Three tabs over the historical record: filterable daily performance, the Campaign and Ad Group bridge, and searchable conversion paths. |
  | `campaign_optimizer.py` | Markov against Shapley per touchpoint, the governed recommendation, and the budget shift the recommendation implies. |
  | `optimization_log.py` | Run identifiers, the report window, the input digests, the pipeline stage trail, and the per-touchpoint reliability flags. |
  | `knowledge_base.py` | The five-segment vocabulary, the reliability contract, the Outcomes, capacity rules, the hierarchy, and the artifacts in use. |

- Inputs: None. Each module exposes a single `render()` that takes no arguments and pulls what it needs from `dashboard.data_source`, so a view never holds a file path or a SQL statement.
- Outputs: The rendered page. Nothing is returned and nothing is written.
- Behavior contract: **No view computes an attribution share or a budget figure.** Every value displayed is read. A view that recomputed one would become a second implementation of the pipeline, and the chart would be free to disagree with the CSV. The single exception is `campaign_optimizer.py`'s implied budget shift, which restates the recommended attribution as a spend split at constant total budget; it is labelled as a restatement, does not predict the result of acting on it, never overrides the allocation in `budget_manager.py`, and is refused outright when the Outcome's verdict is UNRELIABLE, because an interval cannot carry a spend split. Every view that shows an attributed share shows its reliability verdict beside it, so an unreliable number is never presented as a fact. Filters sit in one row above everything they scope, so all panels on a page show the same slice, and every chart is paired with a table view or direct labels, so no value is reachable only by hovering. `optimization_log.py` and `knowledge_base.py` back the two reference views that had no data of their own: the first reports the real run record and states plainly that the optimisation stage has not run, and the second is populated from the data in use, so it cannot drift from the charts beside it.
- Dependencies: Streamlit, Plotly, and pandas, through `dashboard.data_source`, `dashboard.theme`, and `dashboard.views.common`. Installed with `uv sync --extra dashboard`.
- Verification: `dashboard/tests/test_views_render.py` renders every view and asserts none raises.

### `common.py`

Source: `dashboard/views/common.py`

- Responsibility: Hold the label vocabulary, filter controls, and display helpers that more than one view needs, so two views cannot name the same thing differently.
- Inputs: The `DataFrame` a control filters, plus the reader's selections.
- Outputs: The `OUTCOME_LABELS`, `OUTCOME_SHARE_COLUMNS`, and `OUTCOME_VALUE_COLUMNS` maps; `currency_symbol()`, `pretty()`, and `short_touchpoint()`; the `date_range_filter()`, `multiselect_filter()`, and `outcome_selector()` controls; and the `table_view()`, `empty_notice()`, and `reliability_banner()` display helpers.
- Behavior contract: Only presentation lives here; nothing in this module computes an attribution or budget number. The three `OUTCOME_*` maps are the single binding between an Outcome key as the pipeline writes it, its display label, and the columns that carry it, so a renamed column is corrected in one place. `short_touchpoint()` drops the `UNSPECIFIED` segments, which carry no information and would otherwise make every axis label the same length and unreadable. Each filter returns the frame unchanged when nothing is selected, so "no selection" means all rather than none. `table_view()` exists so that every chart can be paired with the values behind it, which is what keeps a tooltip an enhancement rather than the only way to read a number.
- Dependencies: Streamlit and pandas, plus `dashboard.theme` for the banner colours. Installed with `uv sync --extra dashboard`.
- Verification: Exercised by `dashboard/tests/test_views_render.py` through the views that call it.

### `import_to_database.py`

Source: `script/import_to_database.py`

- Responsibility: Read every committed artifact and write it into the PostgreSQL schema defined in `dashboard/models.py`, inside one transaction.
- Inputs: `modules/mta_attribution/data/simulated/*.csv`, `modules/mta_attribution/outputs/attribution/*.csv`, and the strategy module's JSON inputs and outputs. Connection settings come from `.env` through `dashboard.config`.
- Outputs: The eighteen populated tables, and a per-table row count printed on completion.
- Behavior contract: The command **refuses to overwrite a populated database** unless `--replace` is given, so an accidental second run cannot destroy existing rows; `--replace` drops and rebuilds every table, which is what a schema change requires. `--dry-run` reports the row count each table will receive without opening a connection. `--full-events` imports every synthetic event rather than the default bounded sample, which exists because the dashboard only aggregates that table and the full extract is by far the largest. `read_rows()` drops the Chinese field-description row by matching its exact first-cell marker from `config.DESCRIPTION_ROW_MARKERS`; an earlier heuristic that tested for the absence of digits silently discarded a real touchpoint row from the files that have no description row. `Importer.touchpoint()` creates each `Touchpoint` on first sight and reuses it thereafter, which is what makes the five-segment key the join between spend and attribution. The whole import runs in one session and commits once, so a failure part-way leaves the database untouched.
- Dependencies: SQLAlchemy, `psycopg`, and `python-dotenv`, plus `dashboard.config` and `dashboard.models`. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/import_to_database.py --dry-run`, then `script/verify_source_parity.py` against the loaded instance.

### `index.html`

Source: `web/index.html`

- Responsibility: Boot the dashboard in the visitor's browser — mount stlite over the copied `dashboard/` sources, declare the environment they run in, and hold a splash until the dashboard paints.
- Inputs: The stlite runtime at `./stlite/`, and every Python file and sample artifact `build_pages_site.mjs` copies, each declared at its repository-relative path so the Python's own `REPO_ROOT`-relative lookups resolve unchanged.
- Outputs: A mounted Streamlit application at the Pages root.
- Behavior contract: The file list is the loader's half of the contract `build_pages_site.mjs` enforces; a file copied but not listed here is a missing module in a visitor's console, which is why the build fails on the mismatch instead. `env` sets `DATABASE=false` and `DASHBOARD_HOSTED=true`, the second being what makes `config.use_database()` refuse the database rather than merely defaulting away from it. The theme is passed through `streamlitConfig` rather than a config file, because the browser build has no `.streamlit/` to read. The splash is removed by a `MutationObserver`, not by a timer, since a runtime slower than any timeout would reveal an empty page. What it watches for is **the navigation rail, not Streamlit's app container**: the container mounts as soon as the runtime starts, roughly twenty seconds before the script it runs emits anything, and lifting the splash then exposes the interval in which the app's CSS block is in the DOM but not yet applied — which renders the stylesheet to the visitor as literal text. The rail is the first thing `app.py` draws, so its presence is the evidence that the Python actually ran.
- Dependencies: `@stlite/browser`, served from the site itself rather than a CDN so the published build has no third-party runtime dependency.
- Verification: Serving the assembled `site/` and opening the root in a browser, which is the only environment where the Pyodide runtime actually executes. The splash contract is checked by sampling the page every 250 ms from navigation to first paint and requiring zero frames in which the splash is gone and the rail has not yet rendered; watching the app container instead produces 373 such frames.

### `build_pages_site.mjs`

Source: `script/build_pages_site.mjs`

- Responsibility: Assemble the GitHub Pages site — the dashboard at the root, the documentation under `/docs/`.
- Inputs: `web/index.html`, the `dashboard/` sources, the eleven sample artifacts the file-mode loaders read, the stlite runtime from `docs/node_modules/`, and the VitePress output in `docs/.vitepress/dist`.
- Outputs: `site/`, which is what the workflow uploads as the Pages artifact, plus a summary line naming the file counts and the total size.
- Behavior contract: The script **copies the same Python the local run executes**; there is no separate web codebase to drift. It fails when `web/index.html` does not list every file it copies, because a mismatch would otherwise reach a visitor as a missing-module error rather than a build failure. `dashboard/models.py` is excluded deliberately — it declares the PostgreSQL schema, which a browser cannot reach, and nothing imports it in file mode. Source maps are excluded from the runtime copy: at roughly 58 MB they are two thirds of the site and no visitor fetches them. A `.nojekyll` marker is written, without which Pages would drop the underscore-prefixed files inside the built assets. The script refuses to run when the documentation has not been built, naming the command that builds it.
- Dependencies: Node.js 22, and `@stlite/browser` installed as a `docs/` dev dependency.
- Verification: `node script/build_pages_site.mjs` after a documentation build, then serving `site/` and opening the root. The rendered result was verified in a real browser: the rail, five metric tiles, four Plotly traces, the "Sample data" status, and both outbound links resolving to the sibling documentation and the repository.

### `verify_source_parity.py`

Source: `script/verify_source_parity.py`

- Responsibility: Assert that every loader in `dashboard/data_source.py` returns the same columns, dtypes, and values whether `DATABASE` is true or false.
- Inputs: The committed artifacts, and a populated PostgreSQL instance configured in `.env`.
- Outputs: A pass message naming the number of loaders checked, or one line per difference identifying the loader and the field. Exit status is non-zero when any difference is found.
- Behavior contract: The two modes are probed in **separate subprocesses**, because `config.use_database()` is `lru_cache`d and one process therefore cannot hold both. `CHECKS` gives each tabular loader a set of sort keys, so the comparison is independent of each source's row order, and the numeric columns whose totals must agree. `BOOLEAN_COLUMNS` is checked by dtype as well as by sum, which is what catches the specific failure where the string `"false"` is read as truthy. `DOCUMENT_LOADERS` compares top-level key sets for the three loaders that return a nested mapping rather than a table. A loader added to `data_source.py` must be added here too; an unlisted loader is silently unchecked.
- Dependencies: pandas, plus everything `dashboard/data_source.py` needs. Installed with `uv sync --extra dashboard`.
- Verification: `uv run --extra dashboard python script/verify_source_parity.py`. It is a command rather than a unit test because it requires a populated database, which a clean checkout does not have.

### `run.sh` and `run.bat`

Source: `dashboard/run.sh`, `dashboard/run.bat`

- Responsibility: Start the local dashboard from a clean clone, on either platform, with one command.
- Inputs: An optional port as the first argument, defaulting to 8501. `uv` on `PATH`.
- Outputs: A running Streamlit server, with its URL printed before it starts.
- Behavior contract: Both resolve the repository root from the script's own location rather than the working directory, so the command works from anywhere. They exit with a message naming the installation page when `uv` is absent, rather than failing inside `uv sync`. They copy `sample.env` to `.env` when none exists, which is what makes a fresh clone start in file mode instead of failing on a missing variable; an existing `.env` is never overwritten, because it holds the operator's real credentials. `uv sync` is skipped when `import streamlit` already succeeds, so a warm checkout starts immediately.
- Dependencies: `uv`. Nothing else is assumed present.
- Verification: `./dashboard/run.sh` from a directory other than the repository root, against the live PostgreSQL mirror with `DATABASE=true`, which the sidebar then reported as connected.

