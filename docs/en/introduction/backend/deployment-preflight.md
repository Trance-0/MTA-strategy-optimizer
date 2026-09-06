---
title: Deployment Input Preflight
compact: "check_deployment_inputs.py validates generator files and configuration before deployment; verifies Git submodule pins or materialized Gitea snapshot provenance and clean tracked inputs. Explains the missing-submodule failure, source-only test skips and host recovery."
source_files: script/check_deployment_inputs.py
test_files: tests/test_deployment_inputs.py
---

# Deployment Input Preflight

The September 5 host deployment stopped during the standard-module integration
test, before building the frontend. Its source synchronization retained old
`simulations/` directories but did not materialize
`ZheyuanWu/examples/baseline.toy.json`. Directory existence alone therefore
incorrectly enabled the external-generator test.

## Prepare the release checkout

Run these commands inside a fresh release checkout, before tests or copying
source into a running service:

```sh
git submodule sync -- external/mta_sim_dataset
git submodule update --init -- external/mta_sim_dataset
uv run python -X utf8 -B script/check_deployment_inputs.py
```

Initialize that submodule only, at the revision recorded in the parent checkout.
Do not use `--remote` or recursively retrieve the unrelated integration project.
The preflight is read-only. It requires the simulator package entry points,
configuration loader, and `baseline.toy.json`. It parses the configuration as
a [JavaScript Object Notation (JSON)](/en/definitions#json-javascript-object-notation)
object and compares the actual submodule commit to the parent's Git link.
Missing, changed, dirty, or mismatched inputs exit one with the initialization
remedy; valid pinned inputs exit zero. It does not contact a database or generate data.

The Gitea mirror can deliver a direct child of the GitHub revision with the
submodule materialized as ordinary tracked files. On that checkout, run only
the preflight command: the snapshot has no submodule to initialize. The check
requires a directory tree at the generator path, a Git link at the same path
in its immediate parent, the matching pin in the snapshot commit's recorded
provenance, and every required file tracked and unmodified. It validates the
committed snapshot supplied by the mirror; it does not independently fetch
the upstream generator to compare every byte. An ordinary directory without
that provenance fails. Shallow snapshots must include their immediate parent.

## Host deployment recovery

The attached host job runs an external deployment command rather than a tracked
repository entry point. Update that job to run the preparation block in its
temporary clone and stop on any failing command. A Gitea job must wait for the
materialized snapshot commit or initialize the GitHub pin itself; the intermediate
mirror update still contains only a Git link. The checkout must include the
materialized generator when synchronized to the host. Generated data, `.env`,
and dependency directories remain outside source replacement; retaining stale
source directories is not a substitute for a submodule checkout.

Validate in the fresh checkout before replacing the active service. Retain the
previous release and its runtime data until the new build and health checks pass.
The maintained production path remains the
[AppStack container](/en/introduction/backend/setups); this diagnosis does not
restore the retired host deployment bundle. Updating and rerunning the external
job requires access to its actual command and deployment environment.

## Source-only test behavior

Local clones without the external generator may run product unit tests. The
single real-generator integration test skips only when its required package or
toy configuration files are absent; remaining adapter tests always run. A
present malformed fixture fails the integration test. Release verification runs
the preflight first, so a source-only skip cannot silently certify a release.
The [adapter specification](/en/attribution/model-testing/) owns these tests.

## Source Files

### `script/check_deployment_inputs.py`

Source: `script/check_deployment_inputs.py`

- Responsibility: Reject incomplete or mismatched external generator inputs.
- Inputs: Repository root (default derived from this command's location).
- Outputs: Bounded diagnostic and exit code; no changes to the checkout.
- Dependencies: Python standard library and Git.
- Verification: `tests/test_deployment_inputs.py` uses temporary checkout trees and recorded Git responses
  representing complete, directory-only, missing-config, and wrong-revision inputs.

## Verification

- **Scope:** Release-input readiness before running the external generator.
- **Cases:** Complete checkout, stale directories, absent or malformed configuration,
  mismatched Git link, modified tracked generator files, and materialized
  snapshots with valid, missing or mismatched provenance.
- **Command:** `uv run python -X utf8 -B -m unittest discover -s tests -p 'test_deployment_inputs.py'`.
- **Limitations:** No remote deployment or database behavior is exercised.
