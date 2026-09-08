---
title: Analysis Workbench Requirements Review
compact: "Reviews FR-1 through FR-15 against approved scope and current dataset, queue, response-model and evaluation contracts; identifies acceptance omissions and architecture gates before story extraction."
created: 2026-09-08
---

# Analysis Workbench Requirements Review

Terms used below: Functional Requirement (FR).

## Overall verdict

The Product Requirements Document describes the approved comprehensive release,
not only its chart improvements, and passes the requirements review gate.
Both substantive findings were corrected and verified: attribution requires
matched inputs and evidence-aware availability, and large-history acceptance
specifies 100,000 rows. Architecture preparation may proceed without another
product discovery round.

## Decision-readiness — strong

FR-1 through FR-5 establish explicit dataset selection, immutable observations
and result identity. FR-9 fixes the editable budget options and prevents unrelated
master-data drafts from being treated as model inputs. FR-15 and Exclusions keep
the work inside existing backend deployment boundaries. The decision log records
the user's approval and separates planning completion from delivered behavior.

## Substance over theater — strong

The working session is directly useful for integration acceptance: generate or
import, select, inspect, save, run, evaluate and recover. It does not claim a new
algorithm, a causal gain or an invented user research result. Explicit source
identity and unavailable-state handling address concrete defects in the current
file and cache boundaries.

## Strategic coherence — strong

The thesis is a usable, reproducible offline analysis session. Data ingestion,
charts, revisioned budgets, isolated runs and recovery all serve it. The
cross-cutting demonstration with two datasets and two plan revisions is an
appropriate success measure; arbitrary adoption targets would add no value.

## Done-ness clarity — strong after correction

Requirements have observable outcomes, including no partial publication,
no sample fallback, explicit interruption after restart and formal evaluation
states. The two omissions identified on the initial draft are resolved below.

### Findings

- **Resolved, originally medium: Restore the agreed large-history case** (Cross-cutting acceptance).
  "Large history" and "bounded chart marks" do not specify the agreed fixture
  size. The approved plan requires ten times ten thousand historical rows.
  *Fix:* require a 100,000-row history fixture with bounded plot marks, paging,
  lazy resources and correct current-filter export; keep keyboard and narrow
  layout checks in the browser acceptance. Numerical latency thresholds can be
  established from measured baseline evidence rather than invented here.
  *Verification:* the final document now explicitly requires 100,000-row history.
- **Resolved, originally medium: Match attribution capability to its actual input contract**
  (FR-4). "Paths enable attribution" can be read as authorizing a path-only run,
  while the existing stage consumes both aggregated paths and matching daily
  performance. *Fix:* require a validated matching path/performance scope;
  research presence establishes readable history, while response eligibility
  follows the existing evidence-support rules. Capability decisions must not
  merely test whether a filename exists.
  *Verification:* FR-4 now requires matched paths and performance and names
  evidence-support checks rather than file presence.

## Scope honesty — strong

The exclusions retain all important boundaries from the comprehensive plan.
Fixed ontology cases and the independent forecast remain demonstrations;
simulation truth stays excluded from normal model inputs. Unconnected entity
drafts are disclosed. There is no hidden requirement to build connectors,
advertising activation or new response mathematics.

## Downstream usability — adequate

The contiguous FR-1 through FR-15 identifiers and four vocabulary entries give
story creation stable references. Architecture must settle the following
existing-product seams explicitly before implementation; these are derived
engineering obligations, not unanswered product questions.

#### Dataset and run path isolation

`backend/services/model_datasets.py` currently writes prepared inputs into
`datasets/<stage>/`; `backend/services/jobs.py` writes stage-wide outputs and
can seed evaluation with default strategies. FR-5 and FR-10 require per-run
paths for frozen inputs and complete outputs, with explicit target-run selection
for evaluation. Preparing before queue admission must not overwrite an earlier
queued run's input. Default artifact restoration is allowed only for the
explicit compatibility source, never a newly registered dataset.

#### Original reports and model adapters

`modules/mta_standard/src/mta_sim_generator_adapter.py` distinguishes original
daily paths from the single-scope model paths. The generator's public files
currently omit the research snapshot. FR-1 and FR-2 require preserving that
distinction and registering validated research context when present. The
external template must choose the documented simulator format; legacy database
performance export has a different column set and needs its existing adapter.

#### Resource and cache boundaries

`backend/repository/snapshot.py` currently caches resource names and dates,
while repository readers use global configuration. FR-3 and FR-5 require the
selected dataset to reach resource readers and cache keys, including entities,
paths, knowledge references and model outputs. A dataset-local read error must
not activate unrelated sample or database data.

#### Persistence and evidence support

`backend/services/tasks.py` keeps operations in process memory. FR-13 requires
persisted run metadata and restart reconciliation, not serialization of worker
callbacks. The response model already distinguishes target history, transferred
evidence and insufficient support; those existing distinctions must drive
FR-4 and FR-8. Attribution credits must not become response features.

## Shape fit — strong

This is an incremental capability specification for one operator role. The
compact workflow and numbered requirements fit that task. A new market study,
large persona set or duplicate project-wide specification would slow delivery
without resolving an integration ambiguity.

## Mechanical notes

Requirement identifiers are contiguous and unique. The review found no
unresolved product-scope questions. Before publishing, reconcile abbreviated
terms used by the requirements with the repository's definitions and first-use
rules; this is documentation hygiene rather than an implementation gate.

The architecture review should verify the implementation seams above before
story extraction. Both acceptance corrections have been verified in the final
requirements document. This review does not claim that any release requirement
has been implemented or tested.

## Editorial structure review

The structural review preceded the prose review. Its purpose was to help the
operator and implementing engineer understand the agreed release and extract
testable stories. The reader type was human, using a strategic, conclusion-first
structure and the repository's heading-based style rules.

The initial reviewed body contained 1,257 words across nine major sections: Purpose and
user (88), Working session (82), Vocabulary (97), Data and scope requirements
(278), Analysis requirements (141), Plans, evaluation and recovery (337),
Cross-cutting acceptance (104), Exclusions and defaults (63), and Baseline
reconciliation (54); the remaining words are the document heading.

No substantive changes recommended — document structure is sound. The opening
states success before details, vocabulary precedes requirements, and acceptance
and exclusions serve distinct downstream decisions. The short working session
is useful orientation rather than redundant specification. Estimated reduction
is zero words; there is no length-reduction target.

## Editorial prose review

The prose review excluded frontmatter and heading markup, preserved the concise
capability-specification voice, and found one small terminology problem for the
repository's nonprogrammer audience.

#### Clarify digest on first use

Original text, Vocabulary / Dataset: "It has a source, scope, digest and declared
analysis capabilities."

Suggested text: "It has a source, scope, content fingerprint (digest) and declared
analysis capabilities. The fingerprint identifies the exact validated inputs."

Reason: digest is central to FR-3, FR-5 and FR-12 but otherwise unexplained.
This change explains the identity term without selecting a hashing algorithm.

## Research boundary

No external comparable-product research was used for this review. This is an
approved brownfield integration release whose remaining uncertainty concerns
local report contracts, storage, queue preparation and output lineage. The
repository evidence directly answers those questions; market comparisons would
not resolve either acceptance correction or justify new scope.
