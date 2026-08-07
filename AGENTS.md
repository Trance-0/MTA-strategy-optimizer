# Repository Instructions

## Documentation language preference

- Keep English as the active and default published documentation language.
- Preserve the detailed Chinese source pages under `docs/zh/`, but exclude them from site builds and do not expose Chinese-site navigation while Chinese publishing is disabled.
- Keep `/zh/` and legacy `/zh/...` URLs available only as a construction placeholder stating that detailed Chinese translation will be completed after the project is finalized; do not publish detailed Chinese content during this period.
- Do not delete or overwrite the preserved Chinese sources when updating English documentation.
- Re-enable the Chinese site only when the user explicitly requests it.

## Script placement

- Keep every maintained project command-line entry point in the project-root `/script` directory. Its contents are tracked product code.
- Do not create project-owned `scripts/` or `script/` directories below `modules/` or `docs/`; those obsolete locations are ignored.
- Keep reusable business logic in the owning module's `src/` directory. Root scripts may import that logic but source modules must not import command wrappers.
- Installed `.agents` and `_bmad` tool bundles retain their internal `scripts/` directories because those paths are part of the vendored tools; do not relocate them as project commands.
- Put one-off agent inspection, migration, scratch, and debugging files in the ignored project-root `/.agent-scratch/` directory and delete them when finished.
- Start every maintained Python script with a module docstring that states its command purpose and place in the data flow. Start every maintained JavaScript script with an equivalent file-level documentation comment.

## Module layout

- `modules/mta_attribution/` — path building, the Markov and Shapley attribution models, and model comparison.
- `modules/mta_standard/` — the MTA-SIM dataloader, four-to-five segment adapter, model interface, output contract, and evaluator.
- `modules/mta_strategy_recommendation/` — the Campaign Group Ad Group count and budget initializer.
- Use `snake_case` for every directory and Python file. Hyphens are not valid in Python module names, and `modules.mta_strategy_recommendation.src` is imported as a real package path.
- Name a file after what it contains: one attribution model per `*_attribution_model.py` file, shared contracts in `*_contract.py`.
- Start every Python file with a module docstring stating what the file does and where it sits in the data flow.
