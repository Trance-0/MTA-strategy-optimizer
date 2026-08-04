# Repository Instructions

## Documentation language preference

- Keep English as the active and default published documentation language.
- Preserve the detailed Chinese source pages under `docs/zh/`, but exclude them from site builds and do not expose Chinese-site navigation while Chinese publishing is disabled.
- Keep `/zh/` and legacy `/zh/...` URLs available only as a construction placeholder stating that detailed Chinese translation will be completed after the project is finalized; do not publish detailed Chinese content during this period.
- Do not delete or overwrite the preserved Chinese sources when updating English documentation.
- Re-enable the Chinese site only when the user explicitly requests it.

## Agent helper scripts

- Put every helper script an agent writes for its own use in the project-root `/script` folder. This includes one-off inspection, migration, scratch, and debugging scripts.
- `/script` is listed in `.gitignore`. Never commit its contents and never push them to the remote.
- Do not place agent helper scripts anywhere else. In particular, do not add them to `modules/*/scripts/` or `docs/scripts/`, which hold product command-line entry points and documentation build tooling respectively.
- Do not create a new `script` or `scripts` directory outside `/script` for agent-only work, and do not remove the existing product `scripts/` directories.
- Delete a helper script once its task is finished. If it turns out to be worth keeping, promote it into the relevant module's `scripts/` directory as a documented product entry point in its own commit, rather than leaving it in `/script`.

## Module layout

- `modules/mta_attribution/` — path building, the Markov and Shapley attribution models, and model comparison.
- `modules/mta_standard/` — the MTA-SIM dataloader, four-to-five segment adapter, model interface, output contract, and evaluator.
- `modules/mta_strategy_recommendation/` — the Campaign Group Ad Group count and budget initializer.
- Use `snake_case` for every directory and Python file. Hyphens are not valid in Python module names, and `modules.mta_strategy_recommendation.src` is imported as a real package path.
- Name a file after what it contains: one attribution model per `*_attribution_model.py` file, shared contracts in `*_contract.py`.
- Start every Python file with a module docstring stating what the file does and where it sits in the data flow.
