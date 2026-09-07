---
title: Deployment Input Preflight
compact: "Manual and inline deployment checks for pinned generator files, Gitea snapshot parent history and missing toy configuration. No maintained preflight helper; the mirror workflow validates snapshots and deploy/yunxiao/pipeline.yaml rejects incomplete clones before rsync."
---

# Deployment Input Preflight

The supplied Yunxiao diagnosis reports missing
`ZheyuanWu/examples/baseline.toy.json` in run 42 and GitHub connection timeouts
in run 73 after recursive cloning was added. The former mirror published raw
GitHub references before completing the materialized snapshot, so a webhook
could start during that interval. These are supplied reports, not a new
inspection of the cloud pipeline.

## GitHub development checkout

Initialize the one required top-level generator pin from the repository root:

```sh
git submodule sync -- external/mta_sim_dataset
git -c submodule.recurse=false submodule update --init -- external/mta_sim_dataset
git submodule status -- external/mta_sim_dataset
```

The checked-out revision must equal the parent repository's recorded Git link.
Require the generator package entry points, its configuration loader and
`examples/baseline.toy.json`; parse that configuration as a
[JavaScript Object Notation (JSON)](/en/definitions#json-javascript-object-notation)
object. A directory left behind by an old run is not sufficient evidence.

## Gitea deployment checkout

The [mirror workflow](../environment/repository-mirror.md) validates the
materialized tree before its one atomic publication. Gitea `main` must have
no root `.gitmodules`, no Git links and a snapshot commit recording every
top-level pin. Its immediate parent is the frozen GitHub source commit.

Use depth two and disable recursion. The
[Yunxiao setup instructions](./yunxiao-ecs.md) describe the maintained
`deploy/yunxiao/pipeline.yaml` configuration to copy into the existing pipeline.
Its source gate runs before `rsync`; no separate preflight helper is needed. Never fetch
GitHub from that host or preserve stale generator source as a substitute for
the pinned snapshot.

## Source-only tests

Product unit tests may run without the external checkout. The real-generator
integration case skips only if its required source or toy configuration is
absent; a malformed present fixture fails. Release verification must therefore
check the source before running tests, rather than accepting that skip as
proof of deployability. The [adapter specification](/en/attribution/model-testing/)
owns the integration contract.
