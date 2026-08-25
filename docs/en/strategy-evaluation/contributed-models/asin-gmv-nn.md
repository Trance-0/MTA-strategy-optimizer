---
title: ASIN-Free GMV Network
description: The contributed budget-to-revenue neural networks, their measured quality, and the adapter that runs them in this pipeline
compact: "Specifies adapters/asin_gmv_nn_adapter.py bridging contrib/mlp/code/train_models.py to CampaignResponseDataset. Held-out R-squared is negative (MLP -4.33, multitask -2.72), so predictions are not decision-grade; monotonicity 0.90-0.95 is the usable signal."
lang: en-US
source_files: modules/mta_strategy_evaluation/adapters/asin_gmv_nn_adapter.py
---

# ASIN-Free GMV Network

## Measured Quality First <span class="status-label status-verified" aria-label="Verified"></span>

::: danger Not usable for budget decisions
On the held-out test split, both contributed models have a **negative coefficient of determination (R-squared)**: `-4.3306` for the Multi-Layer Perceptron (MLP) and `-2.7178` for the multitask network. A negative R-squared means the model's predictions are further from the observed values than simply predicting the training mean would have been. Validation R-squared is negative too (`-2.0109` and `-0.8927`), so this is not one unlucky split.

No budget decision may be taken from this model's predicted revenue. The adapter exists so the model can be executed, measured, and improved inside this pipeline — not so its numbers can be acted on.
:::

The figures above are read from `contrib/mlp/results/metrics.json`, the contributor's own recorded run, and are not recomputed or restated more favourably here.

### What is nonetheless usable

The model's *directional* behaviour is sound. On the contributor's monotonicity check — raise every advertising budget by 10% and count the rows whose prediction rises — `0.9048` of rows rise for the MLP and `0.9524` for the multitask network, with `0.0` flat. A response model used by an optimizer must be increasing in budget, and this one substantially is.

So the honest summary is a model that has learned the *shape* of the budget-to-revenue relationship without learning its *level*. That distinction is what the adapter reports: direction as a measured signal, magnitude as unusable.

### Why the fit is poor

The contributor records the cause in `metrics.json` as a caveat, and the dataset statistics corroborate it. Of 424 panel rows, only 62 are real observations; the remaining 362 are synthetic. The splits are arranged so training is 342 rows of which every one is synthetic, while the test split is 42 real rows from the second half of July. The model is therefore trained on a simulator and tested on reality, and the gap between the two is what the negative R-squared measures. It is a data problem, not an architecture problem, which is why the adapter is worth having: retraining the same architecture on this project's canonical observations is the obvious next experiment.

## What the Contributed Model Is <span class="status-label status-verified" aria-label="Verified"></span>

`contrib/mlp/code/train_models.py` trains two hand-written networks in pure NumPy — no PyTorch, no scikit-learn — on a daily panel for a single product, predicting attributed revenue from how a day's advertising budget was split four ways.

#### Design matrix

Nineteen features on the contributor's own panel: four `log1p_budget_*` values and four `share_*` values across Sponsored Products (SP), Sponsored Brands (SB), Sponsored Display (SD), and Demand-Side Platform (DSP); `has_ad`; `is_weekend`; seven day-of-week indicators; and two market indicators, one per country in their data. The last group is sized by the data rather than fixed, so a panel covering one marketplace yields eighteen columns rather than nineteen. There is no Amazon Standard Identification Number (ASIN) feature, which is what the model's name records — an earlier version had one and it was removed.

#### The two networks

The MLP is a 32-16 hidden stack with a single output predicting `log1p(revenue)`. The multitask network shares that same stack and adds three heads: revenue, four traffic outputs predicting `log1p(impressions)` per advertising type, and one efficiency output predicting `log1p(sales_ad)`. The auxiliary heads are weighted at `0.3` and `0.2` against revenue's `1.0`, so they regularize the shared representation rather than compete with it.

#### Training

Hand-written Adam optimizer, Huber loss in log space, dropout `0.15`, weight decay `1e-4`, up to 400 epochs with early stopping after 40 epochs without improvement, seeded at 42. Predictions are decoded back through `expm1` and clipped to twice the 95th percentile of training revenue, which stops a large logarithm from becoming an absurd revenue figure.

#### The mixture adjustment

The contributor's most interesting idea, and the one this project has no equivalent of. Each advertising type carries a prior elasticity (`sp` 0.40, `sb` 0.22, `sd` 0.16, `dsp` 0.12), and a change in budget *mix* multiplies the network's prediction by the ratio of the new mix's weighted quality to the old one's. It lets the model answer "what if I move money from Sponsored Products to Sponsored Brands" with a mechanism rather than by extrapolating from data that never contained that shift.

## The Grain Mismatch <span class="status-label status-verified" aria-label="Verified"></span>

The contributed model and this project describe advertising at different grains, and the adapter's main job is the translation.

The contributed model is keyed on **marketplace × date**, with one row carrying a four-way budget vector for one product. This project's canonical grain is **Campaign × marketplace × period**, where each Campaign has exactly one advertising product. Their row is a whole day's advertising mix; ours is one Campaign's day.

The adapter closes this by pivoting. Every `CampaignResponseObservation` sharing a marketplace and date becomes one row, and each Campaign's `ad_product` selects which of the four budget slots its `configured_budget` lands in:

- `SPONSORED_PRODUCTS` maps to `sp`, `SPONSORED_BRANDS` to `sb`, `SPONSORED_DISPLAY` to `sd`, and `AMAZON_DSP` to `dsp`.
- A slot with no Campaign gets budget `0.0` and share `0.0`.

That last rule is where the mismatch stops being cosmetic. This repository's live artifact carries **two** Campaigns — `CAMPAIGN-SEARCH` on `SPONSORED_PRODUCTS` and `CAMPAIGN-DISPLAY` on `AMAZON_DSP` — so two of the four slots are structurally empty in every row the adapter can build. The model was trained on a panel where all four were populated. The adapter records this as an explicit `absent_ad_types` diagnostic on its result rather than letting a reader assume the zeros are observed zero spend. They are not: they are advertising products this Campaign Group does not run.

Revenue maps cleanly: the contributed target is a day's attributed revenue, and `CampaignResponseObservation.total_revenue` is the same quantity summed across the Campaigns in that marketplace and day.

### Features are admissible

The nineteen feature names are budgets, shares, calendar indicators, and market indicators. None appears in `FORBIDDEN_RESPONSE_FEATURES`, and the adapter calls `assert_no_forbidden_response_features` on the list it builds before fitting anything. The contributed model cannot become a route by which attribution or ground truth reaches a response model.

## How the Adapter Runs Their Code <span class="status-label status-verified" aria-label="Verified"></span>

The contributed trainer is loaded as a module through `importlib` and its functions are called directly. It is never copied and never edited. Two properties of their file make this work, and both were verified rather than assumed:

1. `main()` is guarded by `if __name__ == "__main__"`, so importing the module trains nothing.
2. Its paths are self-locating from `Path(__file__).resolve().parent`, so the module works from its current location with no path patching.

Importing does have two side effects, which the adapter documents rather than suppresses: the module creates a `.mplconfig` directory beside itself and sets `MPLCONFIGDIR`, both at import time. `.mplconfig/` is therefore added to the root `.gitignore`, so a matplotlib font cache written into the contributor's folder cannot be committed and cannot make their tree look modified.

The adapter reuses these functions: `design_matrix` for the nineteen-column matrix, `Standardizer` for scaling, `train_multitask` and `train_mlp` for fitting, `apply_new_budgets` and `predict_with_mix` for scenarios, and `metrics` for scoring. The multitask network is the default because its held-out R-squared, while negative, is the better of the two.

### Two modes

#### Contributor panel mode

Reads `contrib/mlp/data/prediction_panel.csv` and reproduces the contributor's own experiment. Used to confirm the adapter drives their code correctly, and it is the only mode whose numbers should be compared against their `results/metrics.json`.

#### Canonical mode

Builds the panel from this project's `CampaignResponseObservation` rows. This is the mode the pipeline runs. On the current artifact it has 20 marketplace-days against an 18-column design matrix — one column narrower than the contributor's own, because the market indicator is one-hot encoded over the marketplaces actually present and this artifact has only `TOY` where their panel had two countries. Twenty rows is far below the 100 the adapter requires before calling a held-out split meaningful, so it returns a structured `insufficient_data` result instead of a trained model. That refusal is the correct outcome today, and it is reported as such rather than as a failure.

## Source Files <span class="status-label status-verified" aria-label="Verified"></span>

### `asin_gmv_nn_adapter.py`

Source: `modules/mta_strategy_evaluation/adapters/asin_gmv_nn_adapter.py`

- Responsibility: Load the contributed trainer without modifying it, pivot canonical Campaign-period observations onto its four-way advertising-type grain, fit and score it, and report its measured quality with the negative-R-squared caveat attached.
- Inputs: A `CampaignResponseDataset`, or the contributor's own panel file.
- Outputs: `AdaptedPanel`, `ContributedModelFit`, `load_contributed_trainer()`, `panel_from_response_dataset(dataset)`, `fit_contributed_model(panel, ...)`, `contributed_model_report(...)`, and the `AD_TYPE_BY_AD_PRODUCT` mapping.
- Public entry points: `fit_contributed_model(panel, *, network="multitask", minimum_rows=MINIMUM_PANEL_ROWS)` returns a `ContributedModelFit` whose `is_usable` is false whenever the panel is too small or the fitted held-out R-squared is not positive; it never raises for a poor fit.
- Required field names: reads only `campaign_id`, `marketplace`, `report_start_date`, `ad_product`, `configured_budget`, and `total_revenue` from each observation.
- Error handling: raises `ContributedModelError` when NumPy is not installed (naming `uv sync --extra strategy-evaluation`), when the contributed trainer cannot be found, and when an observation carries an advertising product outside the four the model knows. Returns a non-usable fit, rather than raising, for insufficient data.
- Determinism: seeded from the contributed module's own `SEED = 42`; row order is sorted by marketplace and date before the matrix is built, so the same dataset yields the same matrix.
- Dependencies: `modules/mta_strategy_recommendation/src/response_dataset.py`; the contributed module loaded at runtime through `importlib`; NumPy through the `strategy-evaluation` extra. Imports nothing from `modules/mta_strategy_evaluation/contrib/` at module scope, so the package imports cleanly when NumPy is absent.
- Verification: `modules/mta_strategy_evaluation/tests/test_asin_gmv_nn_adapter.py`, which skips the fitting cases when NumPy is not installed and always runs the pivot and admissibility cases.

## Current Availability <span class="status-label status-verified" aria-label="Verified"></span>

The adapter is implemented and tested. Against the current committed artifact it returns `insufficient_data`, because 20 marketplace-days cannot support a 19-feature network. Running it on the contributor's own panel reproduces their recorded metrics.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The model's held-out R-squared is negative. This is the governing limitation and everything below is secondary to it.
- Two of the four advertising-type slots are always empty on this project's data, so the mixture adjustment operates over a degenerate mix and its elasticity ratio is close to constant.
- The contributor's prior elasticities were chosen for their dataset and are not estimated from this project's data.
- `contrib/mlp/code/build_dataset.py` cannot be re-run here: it reads an absolute path on the contributor's own machine, recorded in `dataset_stats.json`. Only `prediction_panel.csv`, its committed output, is usable.
- The panel is a single product (SK-II) in two markets. Nothing establishes that its learned elasticities transfer to this project's Campaign Groups.
- Canonical mode has never produced a usable fit, so the pivot is verified by its tests rather than by a successful training run on project data.

## References

- [Contributed models](./index.md)
- [Strategy output](../strategy-output.md)
- [Running an evaluation](../running-an-evaluation.md)
- [Campaign budget response model and optimizer](/en/strategy-recommendation/campaign-budget-optimizer.md)
