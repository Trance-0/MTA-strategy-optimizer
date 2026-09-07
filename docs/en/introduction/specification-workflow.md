---
title: Specification Workflow and Retrieval
compact: "Manual compact-metadata retrieval and specification-first development without spec_docs.py. Product verification stays in verify.yml; one-off agent checks are local, root script/ is ignored, and maintained entry points live with their owning modules."
source_files: .github/workflows/verify.yml
---

# Specification Workflow and Retrieval

[Specification-Driven Development (SDD)](/en/definitions#sdd-specification-driven-development)
starts with the owning English specification. Code implements its contract;
passing tests alone cannot establish that the specification is complete.

## Make and verify a change

1. Search the `compact`, `source_files` and `test_files` metadata under `docs/en/`
   with normal text search, then read the relevant owning pages.
2. Compare intent, code, tests and Git history. Resolve contradictions with the
   owner instead of silently rewriting a specification to match drifting code.
3. Write the contract first, including signatures, fields, ordering, errors,
   edge cases and determinism. Then implement it and run the owning tests.
4. Inspect unique source ownership, compact summaries, abbreviation definitions,
   allowed comparisons and the 500-line page limit. Build the documentation to
   check links and publication behavior.
5. Prepare version history and the owner's work-log entry with the commit.

Every maintained implementation under `modules/*/src/`, `backend/` and
`dashboard/` has one owning English page, excluding `__init__.py`, tests and
generated assets. Its single `## Source Files` section names the files,
responsibility, inputs, outputs, dependencies and verification. Machine-readable
`source_files` and `test_files` values are comma-separated repository paths.
Pages with tests state verification scope, cases, commands and limits.

[Retrieval-Augmented Generation (RAG)](/en/definitions#rag-retrieval-augmented-generation)
here means selecting the relevant existing specifications before making a
change. It requires neither a separate index generator nor a persistent agent
helper. One-off audits and migration files belong in ignored `/.agent-scratch/`
and are deleted when finished.

## Product layout and commands

The root `script/` and `scripts/` directories are ignored and must not be
published. Model entry points live in their owning `modules/<module>/src/`
package and run with `python -m`; database and static-export entry points live
in `backend/`. Frontend build integration lives in `dashboard/build/`, and
documentation build integration in `docs/.vitepress/`. Package modules never
alter `sys.path` to import the project.

Optional `.agents` and `_bmad` bundles retain their vendor-owned layout.
Preserved Chinese pages and historical release/work-log entries are not
rewritten as part of current command-path changes.

The existing GitHub verification workflow initializes the pinned generator,
checks its exact pin, four required input files and object-shaped generator configuration inline, runs all six Python product suites and the frontend tests, and builds
the live client, static client and documentation. The removed `spec_docs.py`
and `check_deployment_inputs.py` helpers are not build dependencies.

## Source Files

### `.github/workflows/verify.yml`

Source: `.github/workflows/verify.yml`

- Responsibility: Run existing product verification and builds on pull
  requests, main pushes and manual runs, without project-root helper scripts.
- Inputs: Requested source revision, pinned generator and dependency locks.
- Outputs: Successful or failed product tests and build artifacts.
- Dependencies: GitHub Actions, Python 3.12, Node 22, uv, Git and npm.
- Verification: Run the same product suites and builds locally. Ask the owner
  to run the Action for verification in the hosted runner environment.
