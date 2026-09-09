---
title: Story 1.1 Register Validated Datasets
compact: "Developer context for persistent dataset validation, public report formats, atomic manifests, dataset routes and evidence-aware capabilities; first implementation story in the approved workbench release."
status: done
story_id: "1.1"
baseline_commit: 5d218b1d37e37498ec7f17ee695b240ac027af7b
dependencies: ["0.1"]
---

# Story 1.1: Register Validated Datasets

Terms used below: Functional Requirement (FR), JavaScript Object Notation (JSON).

Status: done

## Story

As the requesting analyst, I want to push and retrieve validated datasets,
so that the backend preserves my inputs independently from temporary jobs.

This story delivers usable backend registration. Browser source selection,
generator hookup and file import experience follow in 1.2 through 1.4; do not
wait for those stories to make registration correct and independently testable.

## Acceptance Criteria

1. Given matching native report arrays, validation returns bounded preview,
   scope, counts and evidence-aware capabilities without publishing a dataset.
2. Given valid input, registration returns a server-issued `ds_<32hex>` identity
   and immutable content fingerprint; list/detail/private reads survive restart.
3. Given malformed dates, duplicate observation keys, mixed scope, invalid
   numeric values or inconsistent references, validation and registration return
   bounded role/row/field errors and publish no partial selectable directory.
4. Performance-only input supports observed charts; matching paths permit
   attribution; optimization requires existing response evidence, not a file.
   Ordinary inputs and previews never expose simulation truth as model features.
5. Public endpoints implement the owning route contract, reject arbitrary paths,
   retain existing transport limits and do not mutate a database or environment.

## Tasks / Subtasks

- [x] Implement validation and immutable registration in the dataset service
  using native report constants, touchpoint validators and research adapter
  (criteria 1–4); keep inputs and public manifests separate.
- [x] Add list/detail/templates/validate/register transport and register the
  blueprint with the existing app (criteria 1–5); both supported transports use
  one validator, even though the import screen is a later story.
- [x] Add temporary-root service and route tests for happy paths, malformed
  inputs, scope mismatch, optional data, atomic failures and restart reads
  (criteria 1–5); run relevant legacy app tests.
- [x] Verify the owning English specification, source coverage and no tracked
  runtime output; record real tests and changed files below before review.

## Dev Notes

### Owning contract and public interface

Read [Registered Analysis Datasets](../../datasets.md) in full before code.
It owns fields, validation, storage, error codes and source files. Architecture
fixes `/api/datasets` and runtime directories; do not create a second interface.

The public envelope is `{name, performance, paths?, research?}`. Native
performance fields are `MTA_SIM_ADS_FIELDS`, including `reportDate`, `accountId`
and `unitsSold`; paths use `MTA_SIM_PATH_REPORT_FIELDS`. Do not add required
`cost_type` or normalize public field names to snake_case. Public metadata uses
camelCase. Missing billing is unavailable; it must not be fabricated.

Use `validate_dataset(payload)`, `register_dataset(payload, source="api")`,
`get_dataset(id)`, `list_datasets()` and `register_generated_dataset(generated,
name)` as specified. Private `dataset_inputs(id)` returns native `performance`
and `paths` lists and optional `research`; `dataset_directory(id)` returns its
validated path. Capability keys are `performance`, `attribution`, `history`,
`optimization`, `evaluation`, each with `available` and `reason`. Evaluation
still needs the matching strategy-run check in the later workbench service.

Use `PIPELINE_OUTPUT_DIR/workbench/datasets/<id>/` and publish `manifest.json`
only with complete validated inputs through atomic directory rename. Private
files include `inputs.json`, native performance/path reports and an optional
`simulation_research.json`. Temporary parser files are removed. No absolute
paths, credentials, synthetic truth or Python objects enter public metadata.

### Existing files and integration points

`backend/app.py` currently creates Flask, registers existing blueprints, preserves
report key order and installs 26 MiB request protection with structured 413
errors. Add the dataset blueprint beside the existing ones; preserve proxy,
static-client, health, database and legacy route behavior.

`backend/config.py` already exposes `pipeline_output_directory()`; reuse it
without modifying global source configuration. Python requires version 3.12 or
later in `pyproject.toml`; use the locked environment and existing Flask extra.
No dependency upgrade or new runtime framework is part of this story.

`modules/mta_standard/src/dataloader.py` owns ordered native report fields and
truth exclusions. `mta_sim_generator_adapter.py` distinguishes original daily
paths from model-aggregated paths; preserve original windows at registration.
Research eligibility uses the canonical research adapter, episode bridge,
response dataset and evidence-support logic. Never feed attribution credits,
evaluation-only outcomes or latent simulator quantities into the response model.

Current `backend/repository/history.py` and `research.py` consult global sources
and samples; they must not be used for registered reads. Story 1.2 owns explicit
resource projection. Current model_datasets stage-wide paths are not a valid
storage location for new immutable datasets.

### Testing and limits

Run `uv run --extra backend python -m unittest backend.tests.test_datasets`
and related app tests. Use temporary directories and patched runtime providers,
never the developer's database or generated history. Cover finite integer counts,
dates, converted users, unsupported touchpoints, scope consistency, duplicate
keys, unknown identifiers, optional research and interrupted atomic writes.
Validation previews contain at most 20 rows per input; returned issue lists and
error messages must be bounded. A failed registration cannot affect a preceding
successful dataset. Verify descriptor ordering and content digest determinism.

For the restart test, reconstruct service state from the same directory; an
in-memory dictionary surviving within one fixture does not prove persistence.
For capability tests, provide insufficient and supported research evidence and
assert a missing-evidence explanation rather than just a boolean.

### Source intelligence and scope boundaries

Main 0.9.47 is the confirmed starting point; 0.1 is completed planning evidence,
not a previous implementation story. The current public template was explicitly
reconciled during architecture review to avoid a third performance schema.
No latest-version research is necessary: this story uses installed standard
library/Flask behavior and existing locked interfaces, with no dependency
migration or emerging external integration.

The source contracts and context were checked against the create-story quality
checklist. Corrections needed for common mistakes are included directly above:
native field reuse, no fallback readers, truthful capabilities and temporary
runtime testing. No implementation has yet been claimed or tested by this story.

### References

- [Requirements](../prd.md): FR-2 through FR-5 and cross-cutting acceptance.
- [Architecture](../architecture.md): Persistent datasets, scoped resources and public surface.
- [Experience](../EXPERIENCE.md): Dataset context, import panel and recovery.
- [Epics](../epics.md): Epic 1 and story 1.1.
- [Readiness](../implementation-readiness-report-2026-09-08.md): READY planning gate.

## Dev Agent Record

### Agent Model Used

Codex, executing BMad dev-story with the approved source contract.

### Debug Log References

Red phases: missing dataset service, missing transport, and invalid numeric/scope cases failed before their implementations. Final command: `uv run --extra backend python -m unittest discover -s backend/tests` — 183 tests passed. A real initialized toy generator registered a persistent dataset with native attribution eligibility.

### Completion Notes List

Implemented immutable registration, canonical report validation, bounded previews, same-contract JSON/multipart routes, templates, deterministic content fingerprints, atomic publication and persistent rereads. Existing canonical adapters determine attribution and response-fit eligibility. Public observations exclude evaluation truth; private input reads verify the digest. App blueprint registration was coordinated with the root agent. Dataset-specific tests and all current backend regressions pass; browser acceptance remains with dependent stories.

### File List

- `backend/services/datasets.py`
- `backend/api/datasets.py`
- `backend/app.py` (blueprint registration by coordinating agent)
- `backend/tests/test_datasets.py`
- `docs/en/dashboard/datasets.md`

## Change Log

2026-09-08: Implemented and tested the registered dataset boundary; ready for code review. Dataset resource and generator integration tests share the focused test module and support dependent stories 1.2 and 1.3.

2026-09-08: Adversarial review corrections reject duplicate research observation identities, share complete date-window keys in history joins and verify malformed sidecar shapes remain bounded validation errors. Focused dataset/workbench/evaluation verification: 40 tests passed.

## Release Review

Implementation passed code and acceptance review. Review patches and evidence
are recorded in [release verification](../verification.md).

### Review Findings

- [x] [Review][Patch] Apply source, lifecycle, input and presentation corrections identified by the three review lanes; regression checks pass.
