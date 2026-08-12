# Repository Instructions

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

## Script placement

- Keep every maintained project command-line entry point in the project-root `/script` directory. Its contents are tracked product code.
- Do not create project-owned `scripts/` or `script/` directories below `modules/` or `docs/`; those obsolete locations are ignored.
- Keep reusable business logic in the owning module's `src/` directory. Root scripts may import that logic but source modules must not import command wrappers.
- Installed `.agents` and `_bmad` tool bundles retain their internal `scripts/` directories because those paths are part of the vendored tools; do not relocate them as project commands.
- Put one-off agent inspection, migration, scratch, and debugging files in the ignored project-root `/.agent-scratch/` directory and delete them when finished.
- Start every maintained Python script with a module docstring that states its command purpose and place in the data flow. Start every maintained JavaScript script with an equivalent file-level documentation comment.

## Module layout

- `modules/mta_attribution/` — path building, every concrete attribution model, the shared attribution-model interface, and model comparison.
- `modules/mta_standard/` — framework-only MTA-SIM loading, four-to-five segment adaptation, model registration, execution, output validation, and evaluation. Do not place concrete attribution mathematics here.
- `modules/mta_strategy_recommendation/` — the Campaign Group Ad Group count and budget initializer.
- Use `snake_case` for every directory and Python file. Hyphens are not valid in Python module names, and `modules.mta_strategy_recommendation.src` is imported as a real package path.
- Name a file after what it contains: one attribution model per `*_attribution_model.py` file, shared contracts in `*_contract.py`.
- Start every Python file with a module docstring stating what the file does and where it sits in the data flow.
- Use package-native relative or fully qualified imports inside `modules/`. Do not mutate `sys.path` from reusable module code.

## Implementation documentation

- Every maintained implementation file under `modules/*/src/`, except `__init__.py`, must have exactly one English implementation page at `docs/en/implementation/<module>/<python_stem>.md`.
- The documentation filename must match the Python filename stem exactly. Its frontmatter must contain `source_file` with the repository-relative Python path.
- Each implementation page must state responsibility, inputs, outputs, dependencies, and the owning test file or verification command. Higher-level guides may link to these pages but must not replace them.
- Keep each editable Draw.io source and its generated light and dark SVG renders in the same documentation subdirectory as the first or canonical page that embeds it. Embed its basename through `DrawioDiagram` so VitePress selects `.light.drawio.svg` or `.dark.drawio.svg` automatically and links `.drawio` as the editable source. Reuse a diagram from other pages through a site-absolute `/en/...` basename; do not duplicate its source, create a shared diagram-assets directory, or make pages traverse parent directories for diagrams.

## Development workflow

- Treat `_bmad/`, `_bmad-output/`, and installed `.agents/` bundles as historical or optional tooling only. Do not use their workflow scripts as the project development process unless the user explicitly requests BMad.
- Use the repository's documented Git, Python, test, and documentation commands for normal development and verification.

## Version and change log

- Keep the current project version in the repository-root `VERSION` file.
- Every project commit must advance the version and document its material changes in `docs/logs/<version>.md` within the same commit.
- Use three-level semantic versions in the form `major.minor.patch`. The project manager controls major-version changes (for example, `1.x.x` to `2.x.x`), and human developers control minor-version changes (for example, `x.1.x` to `x.2.x`). Unless the user explicitly directs otherwise, an agent must preserve the current major and minor numbers and increment only the patch number (for example, `0.9.0` to `0.9.1`). Existing two-level historical versions such as `0.9` are treated as having an implicit patch value of zero.
- Update `docs/logs/index.md` whenever adding a version page. Base historical summaries on Git evidence and maintained work logs; do not invent changes or retroactive Git tags.
- Keep at most ten version pages under `docs/logs/`, excluding `index.md`. Before adding an eleventh, consolidate the oldest adjacent versions into one archived summary and update the index.
- Commit messages should summarize the same change set recorded on the version page. Do not create an undocumented commit, including documentation-only and workflow-only commits.
- GitHub Pages, built by `.github/workflows/deploy-pages.yml`, is the only maintained documentation deployment target. Do not add Cloudflare Pages or Wrangler deployment commands unless the user explicitly changes this policy.
