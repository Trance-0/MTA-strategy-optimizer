---
title: Yunxiao Host Deployment
compact: "deploy/yunxiao/pipeline.yaml defines the existing VMDockerDeploy job and deploys materialized Gitea main to the existing ECS host: private credential variables, nonrecursive clone, source gates before rsync, preserved runtime files, six Python suites, frontend build, service restart and health checks."
source_files: deploy/yunxiao/pipeline.yaml
---

# Yunxiao Host Deployment

Pipeline `1406431` uses its existing **拉取-测试-部署到ECS(非容器)**
`VMDockerDeploy` job to deploy to Alibaba Cloud
[Elastic Compute Service (ECS)](/en/definitions#ecs-elastic-compute-service)
without containers. `deploy/yunxiao/pipeline.yaml` is the complete replacement
configuration for this existing pipeline. All deployment commands are inline
in its `run: |` block. There is no additional shell file or bootstrap command.
The owner runs GitHub Actions and Yunxiao after reviewing their configuration.

## Configure the existing job

Keep `sources: {}`, machine group `u6c168aem8ppjg64`, execution user `root`,
`pauseStrategy: noPause`, one batch, no artifact download and the existing
failure-email plugin. Configure the push trigger for Gitea `main` only and
allow one concurrent deployment to this host. The command explicitly clones
`main`; `master` is an optional mirror alias, not another deployment trigger.

Open pipeline `1406431`, choose **Edit**, and replace its pipeline configuration
with the complete contents of `deploy/yunxiao/pipeline.yaml`. When editing only
the existing job in the visual editor, copy the contents of its `run: |` block
into the command field, without the YAML indentation.

[YAML (YAML Ain't Markup Language)](/en/definitions#yaml-yaml-aint-markup-language)
holds the existing stage, job, host and failure-email settings together with
the inline command. Its command performs its own Gitea clone and does not
require any deployment file to have been published or installed on the host.

#### Authentication and installed tools

Set `GITEA_PASSWORD` as a masked private variable available in the host
command's environment, using the existing Gitea password. `GITEA_USERNAME`
defaults to the existing `mta-user`; override it only for a different account.
No password is stored in the repository or the clone address. The inline Git
credential configuration reads these environment variables for this clone
only; it creates no helper file and writes no permanent credential setting.
Shell tracing and interactive prompts are disabled. After cloning, remove
these credential variables from the command environment before running tests.

The repository address remains
`https://git.trance-0.com/Trance-0/MTA-strategy-optimizer.git`, using
[Hypertext Transfer Protocol Secure (HTTPS)](/en/definitions#https-hypertext-transfer-protocol-secure).

The host must already provide a Unix shell, Git, rsync, curl, systemctl,
`/root/.local/bin/uv`, `/usr/local/bin/npm`, and the configured
`mta-backend.service` and nginx service. These are the existing deployment
prerequisites; the command does not provision the machine.

## Deployment sequence

1. Clone Gitea `main` with `--no-recurse-submodules`,
   `submodule.recurse=false`, `--depth 2` and `--single-branch`. No host command
   fetches GitHub or initializes a submodule.
2. Before changing live source, require no root `.gitmodules`, no Git link,
   an immediate parent commit and these ordinary tracked generator files under
   `external/mta_sim_dataset/ZheyuanWu/`: `simulations/__init__.py`,
   `simulations/baseline/mta_dataset/__init__.py`,
   `simulations/baseline/mta_dataset/configuration.py`, and
   `examples/baseline.toy.json`. The mirror Action has already validated the
   pins and configuration before publication.
3. Synchronize into `/opt/mta-app/backend` with deletion of stale source.
   Preserve `.env`, `.venv`, `node_modules`, `dashboard/dist`, Python caches,
   logs, `.mplconfig` and `generated/`. Never exclude the entire `external/`
   directory: the generator source must follow the published snapshot.
4. Run `uv sync --frozen --extra backend --extra strategy-evaluation`.
   Run common, attribution, standard, recommendation, evaluation and backend
   tests through `/opt/mta-app/backend/.venv/bin/python`. Set `DATABASE=false`
   only on each test process; do not alter `.env` or the service environment.
   Direct Python execution keeps both dependency extras installed.
5. In `dashboard/`, run `npm ci`, `npm test` and `npm run build` with
   `https://registry.npmmirror.com` as the package registry.
6. Synchronize the built frontend into `/opt/mta-app/frontend-dist`, restart
   `mta-backend.service`, wait three seconds and perform the existing direct,
   nginx, frontend-index and public health checks. The checks bypass proxies
   and retain ten-second connection and thirty-second request timeouts.
   Print `CICD DEPLOY OK` only after every command succeeds.

This retains the existing in-place deployment order. Source checks precede
source replacement, but tests and builds run after that replacement.
A failure stops subsequent commands; there is no automatic rollback.

## Run and inspect

After publishing the corrected [mirror workflow](../environment/repository-mirror.md),
open **GitHub Actions → Mirror GitHub to Gitea → Run workflow → main**.
Wait for success. Gitea `main` must show a commit beginning with
`snapshot: materialize submodules`, and the generator toy configuration must
be browsable as an ordinary file.

After saving the deployment command and private variables, click **Run** on
pipeline `1406431`. Verify no connection to `github.com`, successful tests and
frontend build, and all health checks before `CICD DEPLOY OK`. On failure,
provide the run number and the first failing command with surrounding logs.

## Source Files

### `deploy/yunxiao/pipeline.yaml`

Source: `deploy/yunxiao/pipeline.yaml`

- Responsibility: Preserve the existing pipeline structure and inline the clone,
  source gate, synchronization, tests, build, activation and health checks.
- Inputs: Existing host paths and machine group, private `GITEA_PASSWORD`,
  optional `GITEA_USERNAME`, and the published Gitea `main`.
- Outputs: Updated host source and frontend, restarted service, command logs,
  zero exit only after every check passes, and the existing failure-email plugin.
- Dependencies: Installed host tools and services listed above, locked Python
  and Node packages, and reachable Gitea/package registries. No external script
  is sourced or executed for deployment orchestration.
- Verification: Parse the configuration, extract and syntax-check its inline
  command, and exercise it with disposable command fakes. Actual connectivity
  requires the owner to save and run the existing Yunxiao pipeline.
