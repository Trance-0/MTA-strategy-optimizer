---
title: Contributed Models
description: How externally contributed response models are stored verbatim, adapted, and kept out of the pipeline's trusted path
compact: "Governs modules/mta_strategy_evaluation/contrib/: one folder per model kind kept byte-identical, one adapter per model under adapters/. Covers contrib/mlp (ASIN-free GMV network) and the contrib/classical placeholder. Read before adding or adapting a contributed model."
lang: en-US
---

# Contributed Models

## Purpose <span class="status-label status-verified" aria-label="Verified"></span>

Two people are building response models for the strategy evaluation layer, and their work arrives as self-contained research code with its own data, its own results, and its own write-up. This section governs how that code is stored and how it is reached from the pipeline.

The arrangement separates two things that are easy to conflate: the contributor's artifact, which is a record of an experiment and must stay exactly as they produced it, and the project's use of that artifact, which must satisfy this repository's data model, its conservation contract, and its ground-truth isolation. Editing the first to satisfy the second would destroy the record. So the contributed code is never edited, and every obligation is met by an adapter written on this side of the boundary.

## Layout <span class="status-label status-verified" aria-label="Verified"></span>

```
modules/mta_strategy_evaluation/
  contrib/
    mlp/                # neural budget-to-revenue networks — verbatim, never edited
    classical/          # reserved for a non-neural response model, currently a README only
  adapters/
    asin_gmv_nn_adapter.py
  src/
  tests/
```

`contrib/` holds one plain subdirectory per contributed model. Each is named after **the kind of model it holds, not the person who wrote it**. A person's name is the wrong identifier for a code path for two reasons: contributions change hands, so a handover would rename a directory that adapters, tests, documentation, and the artifact schema all cite; and the folder's contents are what an adapter selects on — an adapter reads a multi-layer perceptron, not a colleague. Authorship is recorded where authorship belongs, in [the work-log roster](/worklog/) and in Git history, both of which survive a directory rename.

They are ordinary tracked directories rather than Git submodules: a submodule points at a remote repository, and these contributions arrived as files in this repository with no upstream of their own, so a submodule would name a remote that does not exist. If a contributor later publishes their work as its own repository, converting the directory is a mechanical change that does not affect any adapter.

`adapters/` holds one adapter per contributed model. An adapter is project code and follows every project rule; the folder it adapts follows none of them.

## The Verbatim Rule <span class="status-label status-verified" aria-label="Verified"></span>

Everything under `contrib/<model>/` is preserved byte-for-byte as the contributor produced it. Specifically, the project does not:

- reformat, rename, translate, or lint their files;
- fix a path, a hard-coded constant, or a dependency version inside their code;
- add an `__init__.py`, a type annotation, or a docstring to their modules;
- treat their `requirements.txt` as a build input.

That last point is the one with a visible consequence. `contrib/mlp/code/requirements.txt` declares `numpy>=2.0` and `matplotlib>=3.8`. Those same two lines are restated in the root `pyproject.toml` under the `strategy-evaluation` extra rather than read from their file, because reading it would make a contributor's file part of the build and therefore something the project would eventually need to edit.

Their prose is preserved too, in the language they wrote it in. `contrib/mlp/` contains three Chinese analysis documents and a Chinese field-description file; those are the contributor's own record and are not translated, matching the rule that a work-log page belongs to its author.

Renaming the directory itself is the one change the rule permits, because it touches no file's bytes. The move from a person-named folder to a model-named one was performed with `git mv`, and every file in it remains an `R100` rename — the same check step 1 of [Adding a Contributed Model](#adding-a-contributed-model) requires.

The obligation runs the other direction as well: an adapter must not write into a contributor's folder. Their `results/` directory is committed and is the record of the run they performed. When the pipeline retrains, it writes to `modules/mta_strategy_evaluation/outputs/`, which is ignored by the root `.gitignore`, so a retrain never dirties their tree and never produces a second, disagreeing copy of their results.

## What an Adapter Owes <span class="status-label status-verified" aria-label="Verified"></span>

An adapter is the only place where the contributed model meets this project's contracts, so it carries every obligation the contributed code does not:

#### Grain translation

The project's canonical grain is Campaign × marketplace × period. A contributed model is free to use any grain, and must be mapped onto the canonical one — or, where it cannot be, the adapter states the mismatch rather than papering over it.

#### Feature admissibility

Every feature name the adapter feeds the model passes `assert_no_forbidden_response_features`, so a contributed model cannot become a route by which attribution output or ground truth reaches a response model.

#### Import without execution

The adapter imports the contributed trainer as a module and calls its functions. It never copies, forks, or re-implements them, because a copy is a second version free to disagree with the original.

#### Honest reporting

An adapter reports the contributed model's measured quality alongside its predictions. A model whose held-out fit is worse than predicting the mean is reported as such, at the top of its own page, not in a closing caveat.

## The Contributed Models <span class="status-label status-verified" aria-label="Verified"></span>

### [ASIN-free GMV network](./asin-gmv-nn.md)

Two neural networks predicting Gross Merchandise Value (GMV) from a four-way advertising budget split, in `contrib/mlp/`, with its adapter. **Its held-out fit is negative, so it is not usable for decisions**; the page opens with that finding and explains what remains usable.

### `classical/`

Reserved for the second contribution to the evaluation module, a non-neural response model. It currently holds a `README.md` describing the layout an adapter will expect, and no model. Nothing in the pipeline references it, and `script/evaluate_strategies.py` does not fail when it is empty.

## Adding a Contributed Model <span class="status-label status-verified" aria-label="Verified"></span>

1. Place the contribution unchanged under `contrib/<model>/`, named after the kind of model rather than its author. Verify with `git diff --cached --find-renames --name-status` that every file is an `R100` rename or a clean add, so the tree can be shown to be verbatim.
2. If the contribution needs dependencies, restate them in the `strategy-evaluation` extra in `pyproject.toml`. Do not point the build at their file.
3. Write `adapters/<model>_adapter.py` meeting the four obligations above.
4. Write the owning page under `docs/en/strategy-evaluation/contributed-models/`, opening with the model's measured quality.
5. Register the adapter in `script/evaluate_strategies.py` so the stage can run it, and keep the stage working when the model is absent.

## Known Limitations <span class="status-label status-verified" aria-label="Verified"></span>

- The verbatim rule is a convention enforced by review, not by a mechanism. Nothing prevents an edit to `contrib/` other than this page and the rename check above.
- Neither contributed model was trained on this project's own data, so an adapter's predictions describe the contributor's dataset, not this repository's Campaigns, until a retrain on canonical data is performed.
- `contrib/` is excluded from the project's own linting and test discovery. A contributed file that fails to import is caught by its adapter's test, not by a repository-wide check.

## References

- [Strategy output](../strategy-output.md)
- [Evaluation layers](../evaluation-layers.md)
- [Running an evaluation](../running-an-evaluation.md)
- [Work log roster](/worklog/)
