# Project Command Directory

All maintained project command-line entry points live in this directory. Reusable business logic remains under the owning module's `src/` directory; source modules do not import these command wrappers.

Run Python commands from the repository root with `uv run python -X utf8 -B script/<name>.py`. Documentation commands are invoked by `docs/package.json` or imported by the VitePress configuration.

## Primary commands

| Command | Purpose |
| --- | --- |
| `generate_mta_sim_dataset.py` | Run the pinned ZheyuanWu generator, aggregate its daily path windows, and validate the four-to-five-segment adapter |
| `run_pipeline.py` | Run the complete legacy five-segment attribution pipeline and publish its canonical outputs atomically |
| `run_attribution_models.py` | Run Markov and Shapley attribution on an existing path report |
| `compare_attribution_models.py` | Recompute comparison, summary, and recommendation files from stored model outputs |
| `build_path_report.py` | Aggregate touchpoint events into the local path-report contract |
| `validate_data_alignment.py` | Validate report scope, dates, touchpoint keys, billing rules, and daily coverage |
| `generate_initial_budget.py` | Generate or check the deterministic Campaign Group initial-budget seed |
| `validate_simulated_hierarchy.py` | Validate the strategy hierarchy, attribution bridge, capacity, and budget result |

## Legacy fixture compatibility

These commands preserve the behavior of the repository-specific generator that created the committed five-segment demonstration data. New data-generation work uses `generate_mta_sim_dataset.py`.

| Command | Purpose |
| --- | --- |
| `regenerate_simulated_dataset.py` | Reproduce the complete legacy data and attribution artifact set atomically |
| `generate_simulated_synthetic_user_events.py` | Reproduce the historical synthetic journey-event source |
| `generate_simulated_amc_touchpoint_events.py` | Reproduce anonymous touchpoint events for path construction |
| `generate_simulated_amazon_ads_report.py` | Reproduce the local five-segment daily Amazon Ads-style sample |
| `generate_simulated_touchpoint_entity_aggregate.py` | Reproduce the project-specific touchpoint-to-strategy entity bridge |

## Documentation tooling

| Command | Purpose |
| --- | --- |
| `copy_static_assets.mjs` | Copy research attachments, audit files, and Chinese placeholder routes after the documentation build |
| `static_pdf_dev_plugin.mjs` | Serve research PDFs with byte-range support during local VitePress development |
| `verify_cloudflare.mjs` | Verify the local Cloudflare Worker, English site, research PDFs, Chinese placeholders, and 404 behavior |

The `.agents` and `_bmad` directories are installed development-tool bundles. Their internal `scripts/` folders are vendored implementation details and are not project command locations.
