---
title: Release Decisions
compact: "User-approved September 8 scope, source authority reconciliation, BMad Fast path and artifact-location overrides for the comprehensive analysis-workbench release."
---

# Release Decisions

## 2026-09-08

#### Scope approvals

The user selected simulation plus standard file import plus a push interface;
standard templates rather than mapping; persistent selectable datasets rather
than replacement or cross-dataset comparison; and runnable budget plans rather
than consuming every master-data draft. The user approved the comprehensive
replacement plan and explicitly requested strict execution after leaving Plan
mode. That instruction authorizes continuing through the prepared workflow
without repeatedly seeking the same scope approval.

#### Workflow binding

Use BMad's Fast path with the supplied approved requirements. Communicate in
Chinese, write formal documentation in English, and bind the document workspace
and planning_artifacts to `docs/en/dashboard/release_plan/`. Bind
implementation_artifacts to its `stories/` directory. This page serves the
skill's decision-log role without creating a second hidden copy. Installed
skill bundles and historical records are not rewritten. No activation hooks or
external handoffs were configured. The old `ericson` config is not authorship.

#### Existing source authority

Work starts from main `5d218b1` (0.9.47), on the isolated feature branch
`codex/dashboard-workbench`, renamed to `feat/dashboard-workbench` at the
owner's request before release; the prior generator branch remains intact.
The approved plan explicitly retains the newer Knowledge Base references,
runnable evaluation and response optimizer. Their owning specs are the target
when reconciling outdated overview prose. This is an approved intent change,
not a decision to declare any observed code authoritative by default.

#### Delivery and ownership

Runtime outputs remain ignored. Each coherent release commit must carry its
patch version and the correct owner's work-log record. Do not push or deploy
without explicit instruction. Functional implementation and review now have [verification evidence](./verification.md).
Integrated acceptance includes native Safari zoom, real downloads and a
100,000-observation browser session. Planning artifacts alone remain
insufficient evidence of implementation.

## Design and architecture gate

The two design spines finalized without open questions, preserving the existing
theme and route structure. Architecture source review corrected report template
spelling, server-side execution refusal and evaluation synthetic provenance.
These are implementation details within the approved scope. Story extraction
continues under the user's explicit execution instruction; completion of these
design gates does not mark any product story implemented.

## Implementation review continuation

The user's repeated instruction to execute the approved plan covers fixing
review defects within that scope. BMad review menu choices to apply patches
were resolved by that existing authorization, without repeated permission.
Three independent review lanes completed; all concrete code findings were
fixed and verified. No public deployment or commit was performed.
