---
title: Specification Workflow and Retrieval
compact: "spec_docs.py routes compact metadata and validates Trance-0 source/test ownership, verification fields and page structure. Defines specification-first changes and the integration gate; Knowledge Base, strategy evaluation and other contributors' work logs remain outside this adoption."
source_files: script/spec_docs.py, .github/workflows/verify.yml
test_files: tests/test_spec_docs.py
---

# Specification Workflow and Retrieval

[Specification-Driven Development (SDD)](/en/definitions#sdd-specification-driven-development)
starts with the intended behavior on its owning English page. Code and tests
implement that contract. A passing coverage check proves that the connections
exist; it cannot prove that prose completely specifies every algorithm.

## Make a change

1. Search the summaries for the affected behavior or source path.
2. Read the selected owning pages, including their source and verification
   sections. Follow only the dependency and definition links relevant to the task.
3. Compare intent, implementation, tests, and recent Git history. Report direct
   contradictions; do not silently copy implementation into a specification.
4. Write the accepted contract first: entry points, fields, units, ordering,
   errors, edge cases, and determinism. Then implement it and run its checks.
5. Run the documentation coverage check and production builds. Before committing,
   add the patch version and the owner's work-log entry under repository rules.

Historical work logs and releases explain decisions; they do not supersede an
owning English contract. Contributor source notes retain their language, content,
and publishing configuration. Notes marked `document_role: reference` are
retrieval context, not implementation authority.

## Adoption scope

This workflow currently governs Trance-0's pipeline, attribution, standard
framework, recommendation, backend, shared dashboard and deployment work.
Knowledge Base and strategy-evaluation code, tests, documentation and model
assets are excluded. Their existing contracts and behavior remain unchanged.
Other contributors' work logs are also excluded; the roster remains readable.
The explicit boundary is recorded in `EXCLUDED_PREFIXES` and `EXCLUDED_FILES`
in `script/spec_docs.py`; new files elsewhere still require coverage. Shared
pages may reference excluded paths without bringing them into this gate.
Extending adoption to another contributor requires a separate agreed change.

## Retrieve a small context

[Retrieval-Augmented Generation (RAG)](/en/definitions#rag-retrieval-augmented-generation)
does not require a vector database for this repository. A deterministic lexical
search over summaries and ownership paths is sufficient to route a task.

```sh
uv run python -X utf8 -B script/spec_docs.py search "history window stream" --limit 5
uv run python -X utf8 -B script/spec_docs.py search dashboard/src/App.vue
uv run python -X utf8 -B script/spec_docs.py index
uv run python -X utf8 -B script/spec_docs.py check
```

Commands print [JavaScript Object Notation (JSON)](/en/definitions#json-javascript-object-notation).
`index` returns one record per in-scope English specification in path order. `search`
returns at most `--limit` records (default five, positive integer). Records contain
`path`, `title`, `compact`, `source_files`, and `test_files`; no source code or
page body is emitted. Case-insensitive tokens match title, compact, page path,
and owned paths. Exact source/test path matches rank first, then token count,
then page path for stable ties. No match returns an empty array. Add
`--include-references` to either command to include preserved contributor notes.
Generated indexes go to standard output and must not be committed.

## One ownership and verification structure

#### Page metadata

`compact` is a quoted one-line routing summary of roughly 40 words or fewer.
`source_files` and `test_files` are comma-separated repository-relative paths,
not glob patterns. `source_files` names implementation and configuration;
`test_files` names the tests that verify this page. A test covering several
contracts has one owning page and may be linked from the others.

#### Source contracts

Each in-scope maintained implementation under `modules/*/src/`, `backend/`, and
`dashboard/` has one owner. Package `__init__.py` files, tests, assets, dependencies,
and generated outputs are excluded from that implementation census.
The owner's single `## Source Files` section contains `Source:` entries naming
all owned paths, responsibility, inputs, outputs, dependencies, and verification.
Existing grouped contracts may share an entry. Do not create a second code catalog.

#### Verification contracts

Each page with `test_files` has one `## Verification` section with four fields:
**Scope**, **Cases**, **Command**, and **Limitations**. Scope names the behavior;
Cases names representative normal, boundary, and failure paths; Command gives
the exact executable check; Limitations distinguishes source-text assertions,
runtime tests, external integration, and manual checks. Test implementation stays
in test files; prose describes observable acceptance rather than copying test code.

## Automated checks and limits

`check` exits zero when the structural checks pass and one when defects exist.
Its JSON result contains `errors`, `pages`, `sources`, `tests`, and `scope`
(the scope name and excluded prefixes/files). It rejects
missing or duplicate owners, stale or escaping paths, missing Source entries,
missing verification fields, merge markers, empty compact summaries, multiline
metadata, and Markdown pages above 500 lines. It checks compact and length in
in-scope English pages, releases, and work logs, and length in root Markdown pages.
Only Git-tracked and nonignored new product files participate, so build outputs
and optional vendored bundles never become product code by accident.

This gate does not certify semantic completeness, algorithm correctness,
abbreviation usage, or the meaning of comparison tables. Review those against
`AGENTS.md` when editing a page. Preserved Chinese sources are never rewritten.

The workflow `.github/workflows/verify.yml` runs on pull requests and pushes to
`main`: initialize only the pinned generator submodule, check deployment inputs,
run this structural gate, run the common, attribution, standard, recommendation
and backend Python suites and the existing dashboard suite,
then build the live dashboard, static dashboard, documentation, and combined site.
It uses Python 3.12, Node 22, locked dependencies, and file-mode fixtures.
No deployment, database mutation, or credential is needed by this workflow.

Root `.gitignore` must leave maintained `/script` entry points trackable;
temporary inspection helpers belong only under ignored `/.agent-scratch/`.

## Source Files

### `script/spec_docs.py`

Source: `script/spec_docs.py`

- Responsibility: Route agent context and validate documentation ownership.
- Inputs: Working-tree Markdown metadata and the Git product-file inventory.
- Outputs: Deterministic JSON to standard output; process status as above.
- Dependencies: Python standard library and Git; no embedding model or service.
- Verification: `tests/test_spec_docs.py` and the scoped `check` command.

### `.github/workflows/verify.yml`

Source: `.github/workflows/verify.yml`

- Responsibility: Exercise the documented release checks before deployment.
- Inputs: The requested revision, pinned submodule, and dependency lockfiles.
- Outputs: Failed or successful checks and local generated build artifacts.
- Dependencies: GitHub Actions, Python, uv, Node, and npm.
- Verification: Run the same commands locally; remote execution requires a push.

## Verification

- **Scope:** Metadata retrieval and structural coverage, independent of business logic.
- **Cases:** Stable relevance ordering; absent, duplicate and stale ownership;
  missing verification fields; contributor and reference exclusion; page length
  and conflict markers.
- **Command:** `uv run python -X utf8 -B -m unittest discover -s tests -p 'test_spec_docs.py'`.
- **Limitations:** Structural validation cannot establish semantic equivalence.
