# Credits and Data Provenance

## MTA-SIM synthetic dataset generator

This repository links [Trance-0/MTA-SIM-dataset](https://github.com/Trance-0/MTA-SIM-dataset) as the `external/mta_sim_dataset` Git submodule. The integration is pinned to commit `cc698a12a333919418a818e6cc450da9cf454682` and uses the public generator under `ZheyuanWu/`.

The generator manifest credits ZheyuanWu and GPT5.6-Sol. Its tracked examples and generated fixtures are synthetic public reference material; they are not customer data, Amazon data, or evidence obtained from any named advertiser.

The local `mta_standard` adapter preserves the generated four-segment source tables, derives the explicit CPC/CPM interaction mapping from the resolved generator configuration, and creates model-facing five-segment views. Simulation ground truth is evaluation-only and is never provided as a model feature.
