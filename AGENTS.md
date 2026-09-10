# Repository Instructions

## Specification-oriented programming

- Documentation under `docs/en/` is the ground truth of this project. Code is an implementation of the specification, not the definition of it. When documentation and code disagree, the documentation states the intent and the code is the defect, unless the user explicitly says the documentation is out of date.
- Write or update the specification page first, then change the code to match it. Do not treat a code change as complete until the owning page describes the new behavior.
- Never "correct" a documentation page by copying current code behavior into it. If the code has drifted, report the drift and ask which side is authoritative before editing.
- The documentation set must be sufficient on its own: a reader with no access to this repository's source should be able to rebuild an equivalent implementation from `docs/en/` alone. Treat it as the project's development memory.

## File count and placement

- **Create the fewest files the task allows.** Before adding a file, check whether an existing one should hold the content instead. Every additional file is another path to find, keep consistent, and update when the others change; a structure spread across several files costs more to read than the one file it replaces.
- **Keep a deliverable in one file whenever its format can carry the whole thing.** When asked for a deployment configuration, write one `.yaml` that holds the operations inline, rather than a YAML file plus a shell script plus a README. Comment blocks inside the file carry the operating steps, the required private variables, and the prerequisites, so the reader configures it from the file they are already looking at.
- Prefer inline commands in the format's own execution field — a `run: |` block, a job step, a package script — over a companion file the format merely calls. A configuration that installs helpers before it works cannot be copied into a cloud pipeline that has none of them.
- Do not split content across files to make each one shorter. The only size rule that forces a split is the 500-line documentation ceiling below, and it applies to markdown under `docs/`, not to configuration or code.
- **Never create a markdown file outside `docs/`.** Explanation belongs in the documentation set, where the `compact` routing field and the sidebar can find it. Do not add a `README.md` beside a configuration, a module, or a deployment directory to explain it; write or extend the owning page under `docs/en/` and link to it from a comment in the file itself.
- The exceptions are the existing repository-root files, which are entry points rather than documentation pages: `README.md` for a visitor, `AGENTS.md` for these instructions, and `CREDITS.md` for provenance. Edit those in place; do not add a fourth. Contributor-authored pages already under `modules/*/contrib/` belong to their owners and stay where they are.
- The same applies to notes, plans, checklists, and summaries: put them in the ignored `/.agent-scratch/` directory and delete them when finished, or write them into the owning documentation page. Do not leave a stray markdown file in a source or configuration directory.

## Comments in scripts

- **Comment the functional code in every maintained script.** A reader who did not write it must be able to follow what each stage does and why it is ordered that way, without reconstructing the intent from the commands.
- Mark the operational stages of a script — the clone, the validation gate, the synchronization, the tests, the build, the activation, the health check — with a comment or an echoed progress marker naming the stage and its position in the sequence.
- Comment the reasoning a command cannot state on its own: why a check must run before a destructive step, why a path is excluded, why a variable is unset after use, why a version is pinned. Do not restate what the command already says.
- Keep the file-level docstring or header comment required below, and let the inline comments carry the stage-by-stage detail underneath it.

## Dashboard interface layout

- **An option is one row: its name on the left, the control that changes it on the right.** This holds for every control type — a select, a text field, a toggle, a button that performs the option's action, or a read-only value. Never stack a label above its control in an option row, and never put the control first. A reader who has learned where the name is and where the control is on one page must find both in the same place on every other page.
- Use the shared primitives in `dashboard/src/style.css` rather than a per-view layout: `.setting-group` for a titled section, `.setting-row` for one option inside it, `.setting-label` for the name, `.setting-control` for the control, and `.setting-block` for content in a group that is not an option. A boolean option is a `.setting-row` that is also a `.toggle`, with an `input.switch` in its control.
- **Give each option a helper sentence under its name**, in the `<small>` inside `.setting-label`, stating what the setting changes and what the alternative value does. Hold it back only for a trivial option — one whose label already says everything, such as a standard connection parameter or a filter naming the column it filters. A sentence under every row buries the rows that carry a real consequence.
- **Never align one control or button row to the opposite side of another.** A `.setting-row` puts its control on the right; a standalone action bar (`.rec-actions`) aligns left, everywhere, with the primary action last. Do not add a rule that flips one instance of either.
- `.field` remains the separate toolbar shape: a strip of compact controls that narrow the content directly below them, each labelled above it, inside `.filter-row`. It is for filters and view parameters, never for settings. Do not render the same field as a stacked `.field` in one view and a `.setting-row` in another — the PostgreSQL connection parameters appear on Settings and in the Data Generator export, and both are option rows.
- Never use an empty or `&nbsp;` `<label>` as a spacer to align a button with the fields beside it. A `<label>` wrapping no control is a defect a screen reader reports; use an action bar instead.
- Replacing a native control's appearance is allowed only where the native input remains in the markup and keeps its focus, keyboard, and accessibility behavior, as `.switch` does for a checkbox.
- Changing a shared primitive changes every view that uses it. Grep the class across `dashboard/src/` before editing it, and update the views that no longer conform in the same change set.

## Documentation frontmatter

- Every markdown file under `docs/en/`, `docs/version/`, and `docs/worklog/` must carry a `compact` frontmatter field.
- `compact` is a single-paragraph, self-contained summary of what the page specifies, written so that an agent can read only the `compact` fields across the documentation set and decide which full pages a given task requires.
- Write `compact` for the routing decision, not as marketing copy. Name the concrete modules, files, contracts, fields, and commands the page governs, so keyword matching against a task description succeeds.
- Keep `compact` to roughly 40 words or fewer, on one line. Do not restate the `title`, and do not duplicate the `description` field verbatim.
- Update `compact` in the same edit that changes what a page specifies.

## Documentation language preference

- Keep English as the active and default published documentation language.
- Preserve the detailed Chinese source pages under `docs/zh/`, but exclude them from site builds and do not expose Chinese-site navigation while Chinese publishing is disabled.
- Keep `/zh/` and legacy `/zh/...` URLs available only as a construction placeholder stating that detailed Chinese translation will be completed after the project is finalized; do not publish detailed Chinese content during this period.
- Do not delete or overwrite the preserved Chinese sources when updating English documentation.
- Re-enable the Chinese site only when the user explicitly requests it.

## Documentation abbreviation and definition rules

- For every markdown file under `docs/en/`, the **first occurrence** of an abbreviated term must include its full name in one of these two formats:
  - Inline expansion: `Multi-Touch Attribution (MTA)`
  - Linked to definition: `[MTA](/en/definitions#mta-multi-touch-attribution)`
- Assume the reader has no programming background. Expand terms like `MAE`, `RMSE`, `TVD`, `Rho`, `top_k`, `SKU`, `ASIN`, `CPC`, `CPM`, `DSP`, `DNN`, `ROAS`, `ROI`, `CPA` on first use within each page.
- When a term is central to a discussion and used many times, expand it on first occurrence in each major section (`##` heading level), not just once per page.
- Every abbreviated term expanded or linked in documentation must also have a corresponding entry in `docs/en/definitions.md` under the appropriate category.
- Link to the definitions page anchor when the term's meaning is nuanced in this project's context (e.g., `[AMC](/en/definitions#amc-amazon-marketing-cloud)`). Use inline expansion when the term is common knowledge (`Comma-Separated Values (CSV)`).

## Documentation table usage

- A Markdown table is permitted only as a strict side-by-side comparison of exactly two items: column one names the topic being compared, column two holds the first item's value for that topic, column three holds the second item's value. No other table shape is allowed anywhere under `docs/`.
- Every other kind of content that might otherwise be tempting to lay out as a table — a list of definitions, a list of components, a list of fields, a list of steps, a list of options — must be decomposed into sub-level headings instead. Prefer a fourth-level heading (`####`) per item; drop to a fifth-level heading (`#####`) only when the item already sits inside a fourth-level section.
- Prefer `####` specifically for definition lists: one heading per term, with its definition as the body underneath.
- When reviewing or authoring any page, treat a table that is not a two-item comparison as a defect. Convert each row into its own heading with that row's content underneath it, rather than trimming or reformatting the table.
- `docs/en/introduction/data-models/` carries a stricter, page-specific rule: no tables at all, including comparison tables. That rule is a narrower subset of this one and takes precedence within that directory.

## Documentation file length

- No markdown file under `docs/en/`, `docs/version/`, `docs/worklog/`, or the repository root may exceed **500 lines**. The limit is a hard ceiling, not a target: a page approaching it is already saying too much for one reader to hold.
- When a page would exceed 500 lines, do not compress it and do not delete content. Convert it into a directory: keep its `index.md` as the parent page that introduces the subject and states how the parts fit together, then give each component its own file beside it, and let the parent introduce each one in a sentence that links to it.
- Split on the page's own second-level (`##`) sections, because those are the boundaries the author already drew. A section that is itself too long splits again the same way, one directory deeper.
- The parent `index.md` is an introduction, not a table of contents: it must state what the subject is and why the components divide the way they do, so a reader who stops there still understands the whole.
- Every split file carries its own `compact` frontmatter, and the parent's `compact` describes the subject rather than listing the children. `source_files` moves to whichever child owns that code, not to the parent.
- `docs/zh/` is exempt: those pages are preserved sources under the language policy above and must not be restructured.

## Script placement

- Do not track a project-root `/script` or `/scripts` directory. Both are ignored. Remove one-off agent helpers instead of publishing them.
- Existing product functions belong to their owning module: Python entry points run with `python -m modules.<module>.src.<entry>` or `python -m backend.<entry>`; dashboard build integration belongs in `dashboard/build/`, and documentation build integration belongs in `docs/.vitepress/`.
- Do not create project-owned `scripts/` or `script/` directories below `modules/` or `docs/`; those obsolete locations are ignored.
- Keep reusable business logic and its command entry point in the owning module's `src/` directory, using package-native imports without `sys.path` changes. Do not replace `/script` with another shared helper directory.
- Installed `.agents` and `_bmad` tool bundles retain their internal `scripts/` directories because those paths are part of the vendored tools; do not relocate them as project commands.
- Put one-off agent inspection, migration, scratch, and debugging files in the ignored project-root `/.agent-scratch/` directory and delete them when finished.
- Keep the mirror operation inline in its existing GitHub Actions workflow. Keep only the maintained pipeline YAML in `deploy/yunxiao/`, with all deployment commands inline in `run: |`; do not add shell files, helper scripts, wrappers, or a `README.md` there. Its header comments carry the operating steps and private variables, and the specification lives at `docs/en/introduction/backend/yunxiao-ecs.md`. It must be ready to copy into the existing Yunxiao pipeline to repair deployment without first installing repository helpers. Ask the owner to run Actions or Yunxiao.
- Start every maintained Python script with a module docstring that states its command purpose and place in the data flow. Start every maintained JavaScript script with an equivalent file-level documentation comment.

## Ignore rules

- The project-root `.gitignore` is the only ignore list the project owns. Do not create a `.gitignore` under `dashboard/`, `docs/`, `modules/`, or any other project-owned directory; add the rule to the root file instead, so one list cannot drift from another and a reader has one place to look.
- Write Node and build patterns unanchored (`node_modules/`, `dist/`, `coverage/`) so they apply to every package in the tree rather than to one named directory. Anchor a pattern with a leading `/` only when the rule is genuinely specific to one location, such as `/dashboard/public/data/`.
- A pattern containing a slash is anchored to the directory holding the ignore file, so a nested path such as `.vitepress/cache/` matches only at the top level. Prefix it with `**/` when it must apply at any depth.
- Vendored trees under `external/` keep their own upstream ignore files. Those belong to their projects; do not edit or consolidate them.
- Never commit a build output, an installed dependency tree, or a generated data file. Each is produced from tracked sources by a documented command, so a committed copy is a second version free to disagree with the sources beside it, with nothing to say which is authoritative.

## Media handling

- Media files — images, video, PDFs, screenshots, and rendered diagrams — are tracked when they are project or reference material. Keeping them is the default; the rule below governs how an agent **reads** them, not whether they exist.
- **Never read media in bulk.** Loading several images into one context window exhausts it and terminates the session. This applies to the reference prototype under `external/UI_design/`, the research PDFs under `docs/research/`, the rendered diagrams, and any directory of screenshots.
- Read at most one media file at a time, and only when the task actually requires seeing it. Prefer the cheaper evidence first: a file listing, a size, a hash comparison, or a text extraction usually answers the question without opening the file at all.
- When verifying a rendered page, prefer a textual probe — a Document Object Model census, a console-error capture, a failed-request list — over a screenshot. Take a screenshot only to confirm a specifically visual property, and take one rather than a set.
- When several media files must be compared, compare them by hash or by size and open only the one that differs.

## Module layout

- `modules/mta_attribution/` — path building, every concrete attribution model, the shared attribution-model interface, and model comparison.
- `modules/mta_standard/` — framework-only MTA-SIM loading, four-to-five segment adaptation, model registration, execution, output validation, and evaluation. Do not place concrete attribution mathematics here.
- `modules/mta_strategy_recommendation/` — the Campaign Group Ad Group count and budget initializer.
- `modules/mta_strategy_evaluation/` — the shared StrategyOutput contract, artifact projections, evaluation episodes and layers, contributed-model adapters, and contributor-owned code under separate `contrib/<model>/` folders. Name a `contrib/` folder after the kind of model it holds (`mlp`, `classical`), never after its author: a contribution can change hands, and a path cited by code, tests, and documentation must not have to be renamed when it does. Authorship belongs in `docs/worklog/` and in Git history.
- Use `snake_case` for every directory and Python file. Hyphens are not valid in Python module names, and `modules.mta_strategy_recommendation.src` is imported as a real package path.
- Name a file after what it contains: one attribution model per `*_attribution_model.py` file, shared contracts in `*_contract.py`.
- Start every Python file with a module docstring stating what the file does and where it sits in the data flow.
- Use package-native relative or fully qualified imports inside `modules/`. Do not mutate `sys.path` from reusable module code.

## Implementation documentation

- Every maintained implementation file under `modules/*/src/` and `dashboard/`, except `__init__.py`, must be covered by exactly one `## Source Files` section on the English page that describes the behavior it implements. Code-level specification is not a section, a subsection, or a directory of its own: it belongs to the page it specifies, so a reader finds the contract beside the behavior rather than in a parallel tree. Do not create an `implementation/` directory or a project-wide catalog page.
- Within that section, give each Python file a third-level heading naming the file, then its repository-relative `Source:` path, then responsibility, inputs, outputs, dependencies, and the owning test file or verification command. Several files that share one contract, such as the interchangeable view modules, may share one entry provided it names every file it covers. A page whose subject has no Python file simply has no `## Source Files` section.
- List every path the section covers in the page's `source_files` frontmatter field, comma-separated and repository-relative, so the code a page owns is machine-readable.
- The section is the code-level specification for the files it names. It carries the behavior contract those files must satisfy: public entry points and their signatures, required field and column names, ordering and rounding rules, error and edge-case handling, and determinism guarantees.
- A specification that spans several files belongs on the owning section's `index.md`, with each file's entry linking to it.
- Keep each editable Draw.io source and its generated light and dark SVG renders in the same documentation subdirectory as the first or canonical page that embeds it. Embed its basename through `DrawioDiagram` so VitePress selects `.light.drawio.svg` or `.dark.drawio.svg` automatically and links `.drawio` as the editable source. Reuse a diagram from other pages through a site-absolute `/en/...` basename; do not duplicate its source, create a shared diagram-assets directory, or make pages traverse parent directories for diagrams.

## Development workflow

- Treat `_bmad/`, `_bmad-output/`, and installed `.agents/` bundles as historical or optional tooling only. Do not use their workflow scripts as the project development process unless the user explicitly requests BMad.
- Use the repository's documented Git, Python, test, and documentation commands for normal development and verification.

## Version and change log

- Keep the current project version in the repository-root `VERSION` file.
- Every project commit must advance the version and document its material changes in `docs/version/<version>.md` within the same commit. Each page is one small patch description covering a coherent change set.
- Use three-level semantic versions in the form `major.minor.patch`. The project manager controls major-version changes (for example, `1.x.x` to `2.x.x`), and human developers control minor-version changes (for example, `x.1.x` to `x.2.x`). Unless the user explicitly directs otherwise, an agent must preserve the current major and minor numbers and increment only the patch number (for example, `0.9.0` to `0.9.1`). Existing two-level historical versions such as `0.9` are treated as having an implicit patch value of zero.
- Update `docs/version/index.md` whenever adding a version page. Base historical summaries on Git evidence and maintained work logs; do not invent changes or retroactive Git tags.
- Never compact, merge, or summarize older version pages to save space. Every patch keeps its own full page permanently. Manage sidebar length with structure instead: group each minor version's patches into its own folder (`docs/version/0.9/`, `docs/version/0.8/`, ...), collapsed by default, with that minor version's base release as the folder's `index.md`. Keep only the most recent few patches (currently the latest four) as flat pages at the top of `docs/version/`, outside any folder.
- Give every version page a distinct `order` frontmatter value that sorts newest-first; do not let pages tie on `order`, since `sortMenusByFrontmatterOrder` falls back to alphabetical sorting on a tie and `"0.9.10"` sorts before `"0.9.2"` as a string.
- Commit messages should summarize the same change set recorded on the version page. Do not create an undocumented commit, including documentation-only and workflow-only commits.
- Keep a commit message no longer than the work-log entry it accompanies: **at most 300 characters, and at most three sentences summarizing the change set** for that version or patch. Count the whole message, subject and body together; trailers such as `Co-Authored-By` are metadata and do not count. The version page is where a change is explained in full, and the work log is where the detail belongs; the commit message says only which change it is. When three sentences cannot hold the change set, the commit is doing too much and should be split, not the limit stretched.

## Work log

- `docs/version/` records what changed in the repository. `docs/worklog/` records who did the work and when. Keep the two separate: a version page describes a patch, a work-log page describes a person's days.
- Each contributor owns one page at `docs/worklog/<GivenNameFamilyName>.md`, named in PascalCase after the person, for example `ZheyuanWu.md`. `docs/worklog/index.md` is the roster of everyone involved and their area of responsibility.
- Follow the established scheme: reverse-chronological `## YYYY-MM-DD` sections, each with a `### Completed` list and an optional `### Next` list. Record **at most three bullet points per section**; merge related work into one bullet rather than adding a fourth.
- A work-log page belongs to its owner. Do not edit another person's page, restructure their past entries, or translate a page whose author wrote it in another language.
- **When preparing a commit, compact the current change set into today's working-log entry automatically, without asking the owner first.** Only add or edit the entry on behalf of the agent's own owner; never write one for a person who is not the agent's owner, and never edit another owner's page.
- Present the work-log entry together with the proposed commit message so the owner reviews both at once. Both describe the same change set from two angles, so reviewing them side by side is what lets the owner see that they agree.
- Write the work-log entry, stage it with the change set, and create the commit in one operation — the work-log edit belongs to the commit it describes, never to a follow-up commit. The version page, the `VERSION` bump, the work-log entry, and the code all land together.
- Confirmation to commit is not confirmation to push. Push only when the owner asks for it in those terms.
- GitHub Pages, built by `.github/workflows/deploy-pages.yml`, is the only maintained documentation deployment target. Do not add Cloudflare Pages or Wrangler deployment commands unless the user explicitly changes this policy.
