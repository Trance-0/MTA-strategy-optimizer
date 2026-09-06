---
title: 'Complete the Data SIM configuration workflow'
type: 'feature'
created: '2026-09-04'
status: 'done'
baseline_commit: '4481fbd1d26e2824eabeec56b9b52dc32e7e0729'
context:
  - '{project-root}/AGENTS.md'
  - '{project-root}/docs/en/dashboard/data-generator.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Data Generator exposes only a small part of the reviewed MTA-SIM configuration, while most semantic errors appear only after a background run starts. Its sparse form and mixed capability messaging make editing unclear and unsafe.

**Approach:** Add a lossless sectioned Guided/JSON editor and authoritative no-side-effect backend preflight. Align capability messaging, tests, and English documentation while preserving run, preview, download, and PostgreSQL export contracts.

## Boundaries & Constraints

**Always:** Follow `docs/en/dashboard/data-generator.md`; keep English UI; preserve unknown keys, `provenance`, `null`, zero, and false; make the pinned loader final validation authority; return bounded JSON Pointer issues; validate before run allocation; keep GitHub Pages non-executable; keep keyboard and narrow-screen usability; use tests first; release as `0.9.43`.

**Ask First:** Relaxing the one-marketplace boundary, changing the external simulator contract, destructive export behavior, broader redesign, new dependencies, or changing the approved status/schema.

**Never:** Reimplement simulation logic; accept `extends` or client paths; create run state/artifacts during preflight; expose paths, credentials, connection strings, or ground truth; add drag-and-drop; modify unrelated pages; push the commit.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid preflight | Baseline/regional resolved toy object | `200`, valid true, empty issues; no artifacts | N/A |
| Invalid preflight | Field, ID, billing, reference, or regional error | `400 invalid_configuration` with path, section, message | Precise known pointer; safe root fallback |
| Unavailable | Backend disabled/simulator absent | Existing `503 generator_unavailable` | Static page shows explanation, no form |
| Mode change | Guided or valid JSON edit | Full object round-trips without loss | Invalid JSON blocks Guided mode |
| Dirty selection | Preset/variant change after edit | Change only after confirmation | Cancel preserves all state |
| Referenced delete | Path uses touchpoint | Refuse and locate first path | Focus reference context |
| Run | Local checks and preflight pass | Existing async workflow runs | Revalidate before ID/thread |

</frozen-after-approval>

## Code Map

- `docs/en/dashboard/data-generator.md` -- owning specification.
- `dashboard/src/views/DataGenerator.vue` -- capability, preset, preflight/run, preview, download, and export orchestration.
- `dashboard/src/components/GeneratorConfigEditor.vue` -- accordion, editor modes, cards, status, and issue focus.
- `dashboard/src/generator/configuration.js` -- lossless cloning, local validation, dirty comparison, and list operations.
- `dashboard/src/api/client.js`, `dashboard/src/App.vue` -- validation request and page-specific capability handling.
- `backend/api/data_generator.py`, `backend/services/data_generator.py` -- route, structured issues, loader preflight, sanitization, and run reuse.
- `backend/tests/test_data_generator.py`, `dashboard/tests/data-generator.test.js` -- regression coverage.
- `VERSION`, `docs/version/`, `docs/worklog/ZheyuanWu.md` -- release and contributor record.

## Tasks & Acceptance

**Execution:**
- [x] Test and implement valid baseline/regional preflight, structured errors, unavailable behavior, sanitization, zero side effects, and run-start reuse.
- [x] Test and implement lossless helpers plus Guided sections for basics, global behavior, one marketplace, ordered touchpoints, paths, and conditional regional fields.
- [x] Wire editor, dirty confirmation, issue mapping, and static capability state into the existing page/client while preserving downstream actions.
- [x] Finish specification/source ownership, `0.9.45` version records, and the approved Zheyuan Wu work-log entry.
- [x] Run full frontend/backend/dashboard/docs verification and inspect final scope and responsive browser behavior.

**Acceptance Criteria:**
- Given either toy preset, when all supported sections validate, generation completes through existing preview/download/export actions.
- Given unknown data, when editing, formatting, changing modes, or preflighting, untouched values survive in the submitted object.
- Given local, backend, or upstream failures, each maps to its best-known section/field without leaking internal paths.
- Given GitHub Pages, Data Generator explains the backend requirement and offers no fake execution.
- Given 1280px or narrow layouts and keyboard use, sections and list controls work without page-level horizontal overflow.

## Spec Change Log

- 2026-09-05: Concurrent releases on `main` consumed the frozen planned
  `0.9.43` number. This work is recorded as `0.9.45`; the approved intent
  above remains unchanged.
- 2026-09-06: Acceptance hardening added exact field focus, malformed-structure
  recovery, bounded hostile inputs, request race guards, and selected-loader
  capability checks. Delivery moved to `feat/data-generator-config` on the
  latest `main` baseline, leaving `main` unchanged.

## Design Notes

Visible fields project over the complete object; they never rebuild it. Stable project-owned checks produce field paths, then the real MTA-SIM loader prevents preflight/run semantic drift. Explicit list buttons keep ordering accessible and dependency-free.

## Verification

**Commands:**
- `cd dashboard && npm test && npm run build` -- tests and production build pass.
- `uv run --extra backend python -X utf8 -m unittest discover -s backend/tests -t . -p 'test_*.py'` -- backend suite passes.
- `cd docs && npm run build` -- English documentation builds.
- `git status --short && git diff --check` -- scope and whitespace are clean.

**Manual checks (if no CLI):**
- Exercise both toy presets at 1280px and narrow widths, including keyboard card controls, previews, downloads, safe export opening, and static unavailable state.

## Suggested Review Order

**Contract and server boundary**

- Start with the published workflow, limits, deployment behavior, and source ownership.
  [`data-generator.md:53`](../../docs/en/dashboard/data-generator.md#L53)

- The preflight route preserves 200/400/503 compatibility and allocates no run.
  [`data_generator.py:60`](../../backend/api/data_generator.py#L60)

- One service entry performs bounded checks before invoking the authoritative loader.
  [`data_generator.py:196`](../../backend/services/data_generator.py#L196)

- Capability checks require only the selected loader and requested preset files.
  [`data_generator.py:261`](../../backend/services/data_generator.py#L261)

**Lossless editor and lifecycle**

- Full-object helpers reject unsafe JSON while preserving unknown configuration data.
  [`configuration.js:72`](../../dashboard/src/generator/configuration.js#L72)

- Guided edits repair malformed containers without rebuilding untouched values.
  [`GeneratorConfigEditor.vue:117`](../../dashboard/src/components/GeneratorConfigEditor.vue#L117)

- Structured issues open their section and focus the exact addressed control.
  [`GeneratorConfigEditor.vue:267`](../../dashboard/src/components/GeneratorConfigEditor.vue#L267)

- Preset sequencing and preflight timeout prevent stale or indefinitely blocked state.
  [`DataGenerator.vue:93`](../../dashboard/src/views/DataGenerator.vue#L93)

- Lifecycle tokens bind accepted preflight and polling to current state.
  [`lifecycle.js:8`](../../dashboard/src/generator/lifecycle.js#L8)

**Regression and release evidence**

- Backend tests pin both variants, side-effect freedom, bounds, and safe failures.
  [`test_data_generator.py:284`](../../backend/tests/test_data_generator.py#L284)

- Mounted frontend tests prove exact field focus and preset race protection.
  [`data-generator.test.js:350`](../../dashboard/tests/data-generator.test.js#L350)

- The patch record summarizes behavior and final verification counts.
  [`0.9.45.md:12`](../../docs/version/0.9.45.md#L12)
