---
title: GitHub to Gitea and Gitee Publication
compact: "mirror-to-gitea.yml and mirror-to-gitee.yml publish atomic main/master deployment snapshots with pinned first-level submodule files, no nested Git links, and no other branches or tags. Specifies deterministic provenance, validation, retries, credentials, direct Gitee access and manual verification."
source_files: .github/workflows/mirror-to-gitea.yml, .github/workflows/mirror-to-gitee.yml, .gitattributes
---

# GitHub to Gitea and Gitee Publication

GitHub owns authored code and submodule pins. Gitea and Gitee each provide a
generated deployment mirror of one branch: its default branch (`main`) contains one child of the
GitHub commit with the pins expanded into ordinary files, and `master` is an
alias for the same commit. Yunxiao clones Gitea `main`. Neither mirror carries another
branch or any tag. There is no separate snapshot branch and no development on
either mirror.

## Publication contract

Both workflows contain the same complete operation inline. Gitee at
`https://gitee.com/cross-industry-ai-applications/mat-08.git` must publish the
same file paths, modes and bytes as Gitea at
`https://git.trance-0.com/Trance-0/MTA-strategy-optimizer` when both runs use the
same GitHub revision and submodule pins. The steps below apply to both hosts.
Snapshot author names and workflow provenance identify the destination, so
commit identifiers can differ while the root tree identifiers must match.
Gitee uses direct access: its Git transport disables configured proxies and
sets both no-proxy environment forms for `gitee.com`. Local remote verification
must likewise bypass proxies for both mirror hosts.

1. Clone GitHub into a temporary bare repository. Freeze the default branch and
   its exact commit from this clone. The clone is a working copy only; which
   references reach Gitea is decided at step 6, not here.
2. Check out that commit on the GitHub runner. Restore its original GitHub
   origin so relative submodule addresses resolve correctly. Initialize the
   top-level pinned submodules with recursion disabled. The integration
   submodule links back to this project, so recursive initialization is forbidden.
3. Import each pinned tree directly into the snapshot index, including tracked
   files matched by ignore or export rules. Remove root `.gitmodules` and
   uninitialized nested Git links. Verify each downloaded revision against its pin.
   This import copies blobs by object identifier and applies no filter, so this
   repository must not convert submodule bytes. `external/** -text` in
   `.gitattributes` keeps that true: without it, a submodule file committed with
   carriage returns enters the index as written and is then rewritten on
   checkout, so step 5 finds a tree that differs from the index it was built
   from and fails. It would also break the digests the generator records over
   its own bytes.
4. Create one snapshot with the frozen default-branch commit as its sole parent.
   Record all top-level pins in its message. Fixed author, committer and source
   timestamp make unchanged inputs produce the same commit.
5. Reject any remaining Git link. Require the generator package entry points,
   configuration loader and `examples/baseline.toy.json` to be tracked, present
   and unmodified; parse the configuration as a
   [JavaScript Object Notation (JSON)](/en/definitions#json-javascript-object-notation)
   object before publication.
6. Publish the snapshot as the default branch and, when that branch is `main`,
   as the Gitea `master` alias pointing at the same commit. Publish nothing
   else: delete every other local branch and tag before pushing, so the mirror
   carries exactly these references. Development branches belong to GitHub.
   Mirroring one would expose unreviewed work and let a webhook deploy from a
   branch that was never validated, so Gitea must never carry a feature,
   `codex/`, or any other non-default branch, nor a tag. Pruning is what removes
   the ones an earlier all-branch mirror already published.
7. Publish those references with one atomic force push that prunes. Compare the
   entire destination branch/tag set with the prepared references; a mismatch
   fails, so a destination branch that is not the default branch or its `master`
   alias fails the job rather than surviving unnoticed.
   The destination answers through a reverse proxy that intermittently returns
   its own 502 before the request reaches Gitea, which aborts reference discovery
   and publishes nothing. The push and this comparison therefore retry a
   transport fault — a 429 or 5xx status, an unresolvable host, a reset, timed
   out or unexpectedly dropped connection, or an empty reply — at most five times
   with a growing pause. Retrying is safe precisely because the push is atomic:
   an attempt applies every reference or none, so a later attempt resumes from
   the unchanged previous state. Every answer Gitea itself produces, including a
   rejected reference and a failed authentication, must fail immediately; never
   retry one, and never widen the retry to cover a refusal.

No destination reference changes before preparation succeeds. A failed pin,
invalid configuration, unsupported atomic push or rejected reference leaves
the old references intact. Never fall back to a non-atomic push. The raw
GitHub parent is never published to `main` before the complete snapshot, so
a webhook cannot start deployment during the old intermediate interval.

Snapshot-to-snapshot updates require force-update permission: each snapshot
is a child of its corresponding GitHub commit. The existing mirror account
must be allowed to update the destination branches. Concurrent mirror runs
remain serialized with `cancel-in-progress: false`.

## Run the existing Action

After the workflow change is committed and pushed to GitHub `main`:

1. Open the repository's **Actions** tab and select **Mirror GitHub to Gitea** or **Mirror GitHub to Gitee**.
2. Choose **Run workflow**, select `main`, then **Run workflow**.
3. Wait for snapshot preparation, atomic publication and reference verification
   to succeed. Do not deploy from a failed or unfinished mirror run.
4. Open the selected destination’s `main`. Its latest message must begin with
   `snapshot: materialize submodules`; the generator's toy configuration must
   be browsable as an ordinary file.
5. Apply the [Yunxiao settings](../backend/yunxiao-ecs.md), then run that pipeline.

The owner controls manual Action and pipeline runs. Agents provide these steps
and diagnose the resulting logs. The maintained pipeline configuration lives in
`deploy/yunxiao/pipeline.yaml`; copy it into the existing cloud job as documented.

## Authentication

Retain `GITEA_USERNAME`, `GITEA_PASSWORD` and `GITEA_REPOSITORY` secrets.
The existing destination validation accepts a complete
[Hypertext Transfer Protocol Secure (HTTPS)](/en/definitions#https-hypertext-transfer-protocol-secure)
address or `owner/repository.git` on `gitea.com`; embedded credentials and
invalid addresses fail. A temporary runner-local askpass file supplies the
secrets from the environment and is removed on exit. It is not a repository file.

Gitee retains `GITEE_USERNAME`, `GITEE_PASSWORD` and `GITEE_REPOSITORY`.
Its destination accepts only a complete secure `gitee.com` address or
`owner/repository.git`. Credentials remain in GitHub repository secrets and
are supplied through the same temporary askpass mechanism.

## Source Files

### Mirror workflows

Source: `.github/workflows/mirror-to-gitea.yml`, `.github/workflows/mirror-to-gitee.yml`

- Responsibility: Prepare and publish the full mirror using the inline sequence above.
- Inputs: Push, delete, manual or scheduled trigger and the corresponding destination secrets.
- Outputs: Verified final destination references or a failed job. Missing secrets
  retain the existing unconfigured warning and perform no publication.
- Dependencies: Git and Python on the GitHub runner; no project helper script.
- Verification: Parse configuration, check Bash syntax, exercise the inline
  transaction against disposable local Git repositories, then run the Action.

## Verification

Local disposable repositories must cover ignored tracked files, nested Git
links, complete snapshots, deterministic repetition, and pruning. A source
carrying several development branches and a tag must publish exactly `main` and
`master`; starting from a destination that already holds those branches, as an
earlier all-branch mirror left it, the same run must delete them. Replaying the preparation steps against a submodule file committed
with carriage returns must leave the snapshot tree unmodified; running the same
replay without the `external/**` rule must fail, so the check cannot pass
vacuously. A push whose first attempts fail with a gateway status must still
publish the exact prepared references, and a rejected reference, declined hook,
non-fast-forward or authentication failure must fail on its first attempt, so
the retry cannot mask a real refusal. Rejecting one reference or failing preparation must preserve every
destination reference. One-off verification helpers stay in ignored
`/.agent-scratch/` and are deleted after use. Only the production Action proves
Gitea authentication, permissions and actual webhook behavior.

Run the same disposable source through both workflow bodies and compare root
tree identifiers. Verify that invalid generator configuration changes neither
destination, and that rerunning unchanged input preserves each snapshot.
Only successful production runs against the same source revision establish
that the two live mirrors now contain identical files.
