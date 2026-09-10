---
title: Repository Rules Index
description: Every repository rule in one sentence, with the date it was introduced and who introduced it
compact: "One-sentence index of all 107 rules in AGENTS.md, numbered and grouped by its eighteen sections, each with its introduction date and author. Read this to review or audit the rule set; AGENTS.md carries the binding wording."
lang: en-US
---

# Repository Rules Index

This page lists every rule the repository enforces, one sentence each, so the whole set can be reviewed in one pass.

`AGENTS.md` at the repository root is the working copy those rules are written for, and it carries the binding wording. It is written for an agent reading the whole file before acting. This page is the counterpart for a person: same rules, one line each, in the same order and grouping, so a reader can check what exists and what it requires without reading the full text of all eighteen sections.

A line here is a pointer, never a substitute. Where a summary and `AGENTS.md` disagree, `AGENTS.md` governs and the summary is the defect.

## How to read an entry

Each entry has the form `<number>. [<date>, <author>] <rule>`.

The number is stable and continuous across the whole page, so a rule can be cited as "rule 63" in review without naming its section. The date is the day the rule's wording was introduced, read from `git log` on `AGENTS.md` rather than reconstructed, so a section whose rules accumulated over time carries different dates on different lines. Where a rule was later reworded in place, the date still marks its introduction.

Every rule to date was added by `ZheyuanWu`, committed under three author names — `Zheyuan Wu`, `Trance-0`, and one `Trnace-0` typo — which are one person.

Entries map one to one onto the bullets in `AGENTS.md`, with one exception: the deployment-inline bullet under Script placement carries two separate obligations and is listed here as 56 and 57.

When adding a rule to `AGENTS.md`, add its line here in the same commit.

## Specification-oriented programming

1. [2026-08-12, ZheyuanWu] `docs/en/` is the ground truth, so when documentation and code disagree the code is the defect.
2. [2026-08-12, ZheyuanWu] Write the specification page first, then change the code to match it.
3. [2026-08-12, ZheyuanWu] Never "correct" a page by copying current code behavior into it; report the drift and ask which side is authoritative.
4. [2026-08-12, ZheyuanWu] The documentation set must be sufficient alone for a reader with no source access to rebuild the project.

## File count and placement

5. [2026-09-07, ZheyuanWu] Create the fewest files the task allows, and check whether an existing file should hold the content first.
6. [2026-09-07, ZheyuanWu] Keep a deliverable in one file whenever its format can carry the whole thing, with the operations inline.
7. [2026-09-07, ZheyuanWu] Prefer inline commands in the format's own execution field over a companion file it merely calls.
8. [2026-09-07, ZheyuanWu] Do not split content across files to make each one shorter; only the 500-line documentation ceiling forces a split.
9. [2026-09-07, ZheyuanWu] Never create a markdown file outside `docs/`, including a `README.md` beside a configuration or module.
10. [2026-09-07, ZheyuanWu] The only root markdown exceptions are `README.md`, `AGENTS.md`, and `CREDITS.md`; do not add a fourth.
11. [2026-09-07, ZheyuanWu] Put notes, plans, and summaries in the ignored `/.agent-scratch/` and delete them when finished.

## Comments in scripts

12. [2026-09-07, ZheyuanWu] Comment the functional code in every maintained script so a reader can follow each stage without reconstructing intent.
13. [2026-09-07, ZheyuanWu] Mark each operational stage with a comment or an echoed progress marker naming the stage and its position.
14. [2026-09-07, ZheyuanWu] Comment the reasoning a command cannot state itself, and never restate what the command already says.
15. [2026-09-07, ZheyuanWu] Keep the file-level docstring and let inline comments carry the stage-by-stage detail beneath it.

## Dashboard interface layout

16. [2026-09-09, ZheyuanWu] An option is one row with its name on the left and its control on the right, never stacked and never reversed.
17. [2026-09-09, ZheyuanWu] Use the shared `dashboard/src/style.css` primitives rather than a per-view layout.
18. [2026-09-09, ZheyuanWu] Give each option a helper sentence under its name, holding it back only for a trivial option.
19. [2026-09-09, ZheyuanWu] Never align one control or button row to the opposite side of another.
20. [2026-09-09, ZheyuanWu] `.field` is the toolbar shape for filters and view parameters only, never for settings.
21. [2026-09-09, ZheyuanWu] Never use an empty or non-breaking-space `<label>` as a spacer to align a button.
22. [2026-09-09, ZheyuanWu] Restyle a native control only where the native input stays in the markup with its accessibility behavior.
23. [2026-09-09, ZheyuanWu] Search a shared primitive across `dashboard/src/` before editing it, and fix non-conforming views in the same change set.

## Documentation frontmatter

24. [2026-08-12, ZheyuanWu] Every markdown file under `docs/en/`, `docs/version/`, and `docs/worklog/` must carry a `compact` field.
25. [2026-08-12, ZheyuanWu] `compact` is a self-contained summary an agent can route on without opening the page.
26. [2026-08-12, ZheyuanWu] Write `compact` for the routing decision, naming concrete modules, files, contracts, and commands.
27. [2026-08-12, ZheyuanWu] Keep `compact` to roughly 40 words on one line, without restating `title` or duplicating `description`.
28. [2026-08-12, ZheyuanWu] Update `compact` in the same edit that changes what the page specifies.

## Documentation language preference

29. [2026-08-03, ZheyuanWu] Keep English as the active and default published documentation language.
30. [2026-08-03, ZheyuanWu] Preserve `docs/zh/` sources but exclude them from site builds while Chinese publishing is disabled.
31. [2026-08-03, ZheyuanWu] Keep `/zh/` addresses available only as a construction placeholder.
32. [2026-08-03, ZheyuanWu] Do not delete or overwrite preserved Chinese sources when updating English documentation.
33. [2026-08-03, ZheyuanWu] Re-enable the Chinese site only on the user's explicit request.

## Documentation abbreviation and definition rules

34. [2026-08-11, ZheyuanWu] Expand every abbreviation on first occurrence per page, inline or linked to the definitions page.
35. [2026-08-11, ZheyuanWu] Assume no programming background and expand domain and metric abbreviations on first use.
36. [2026-08-11, ZheyuanWu] Re-expand a central term on first occurrence in each second-level section, not just once per page.
37. [2026-08-11, ZheyuanWu] Every expanded term needs a matching entry in `docs/en/definitions.md`.
38. [2026-08-11, ZheyuanWu] Link to the definitions anchor when a term's meaning is project-specific; expand inline when it is common knowledge.

## Documentation table usage

39. [2026-08-18, ZheyuanWu] A table is permitted only as a strict three-column comparison of exactly two items.
40. [2026-08-18, ZheyuanWu] Decompose every other list-shaped table into sub-level headings, one per item.
41. [2026-08-18, ZheyuanWu] Prefer fourth-level headings for definition lists, one heading per term.
42. [2026-08-18, ZheyuanWu] Treat any table that is not a two-item comparison as a defect to convert, not to reformat.
43. [2026-08-18, ZheyuanWu] `docs/en/introduction/data-models/` allows no tables at all and takes precedence there.

## Documentation file length

44. [2026-08-25, ZheyuanWu] No markdown file under `docs/en/`, `docs/version/`, `docs/worklog/`, or the root may exceed 500 lines.
45. [2026-08-25, ZheyuanWu] Convert an oversized page into a directory rather than compressing or deleting its content.
46. [2026-08-25, ZheyuanWu] Split on the page's own second-level sections, recursing a directory deeper when a section is still too long.
47. [2026-08-25, ZheyuanWu] The parent `index.md` is an introduction that stands alone, not a table of contents.
48. [2026-08-25, ZheyuanWu] Every split file carries its own `compact`, and `source_files` moves to the child owning that code.
49. [2026-08-25, ZheyuanWu] `docs/zh/` is exempt and must not be restructured.

## Script placement

50. [2026-09-07, ZheyuanWu] Do not track a project-root `/script` or `/scripts` directory; remove one-off helpers instead of publishing them.
51. [2026-08-07, ZheyuanWu] Product entry points belong to their owning module, with build integration in `dashboard/build/` or `docs/.vitepress/`.
52. [2026-09-07, ZheyuanWu] Do not create project-owned `scripts/` directories below `modules/` or `docs/`.
53. [2026-08-07, ZheyuanWu] Keep reusable logic and its entry point in the owning module's `src/`, without import-path manipulation.
54. [2026-08-07, ZheyuanWu] Vendored `.agents` and `_bmad` bundles keep their internal `scripts/` directories.
55. [2026-08-07, ZheyuanWu] Put one-off inspection, migration, and debugging files in `/.agent-scratch/` and delete them when finished.
56. [2026-09-07, ZheyuanWu] Keep mirror and Yunxiao deployment commands inline in their [YAML (YAML Ain't Markup Language)](/en/definitions#yaml-yaml-aint-markup-language), with no companion shell file, wrapper, or `README.md`.
57. [2026-09-07, ZheyuanWu] Ask the owner to run Actions or Yunxiao rather than running them on their behalf.
58. [2026-08-07, ZheyuanWu] Start every maintained Python script with a module docstring and every JavaScript one with an equivalent header comment.

## Ignore rules

59. [2026-08-15, ZheyuanWu] The project-root `.gitignore` is the only ignore list the project owns; never add a second one.
60. [2026-08-15, ZheyuanWu] Write Node and build patterns unanchored, and anchor with a leading slash only when genuinely location-specific.
61. [2026-08-15, ZheyuanWu] A pattern containing a slash is anchored, so prefix it with `**/` when it must apply at any depth.
62. [2026-08-15, ZheyuanWu] Vendored trees under `external/` keep their own upstream ignore files.
63. [2026-08-15, ZheyuanWu] Never commit a build output, an installed dependency tree, or a generated data file.

## Media handling

64. [2026-08-15, ZheyuanWu] Media files are tracked when they are project or reference material; these rules govern reading, not existence.
65. [2026-08-15, ZheyuanWu] Never read media in bulk, because several images in one context window ends the session.
66. [2026-08-15, ZheyuanWu] Read at most one media file at a time, and only when the task requires seeing it.
67. [2026-08-15, ZheyuanWu] Prefer a textual probe over a screenshot when verifying a rendered page.
68. [2026-08-15, ZheyuanWu] Compare several media files by hash or size and open only the one that differs.

## Module layout

69. [2026-08-04, ZheyuanWu] `modules/mta_attribution/` owns path building, concrete attribution models, their interface, and comparison.
70. [2026-08-04, ZheyuanWu] `modules/mta_standard/` is framework-only, and concrete attribution mathematics must not live there.
71. [2026-08-04, ZheyuanWu] `modules/mta_strategy_recommendation/` owns the campaign and budget initializer.
72. [2026-08-25, ZheyuanWu] `modules/mta_strategy_evaluation/` owns the evaluation contract, with contributed code in a `contrib/` folder named after the model, never its author.
73. [2026-08-04, ZheyuanWu] Use lower-case underscore naming for every directory and Python file.
74. [2026-08-04, ZheyuanWu] Name a file after what it contains, one attribution model per file.
75. [2026-08-04, ZheyuanWu] Start every Python file with a module docstring stating its place in the data flow.
76. [2026-08-04, ZheyuanWu] Use package-native imports inside `modules/` and never manipulate the import path from reusable code.

## Implementation documentation

77. [2026-08-13, ZheyuanWu] Every maintained implementation file is covered by exactly one `## Source Files` section on the page describing its behavior.
78. [2026-08-13, ZheyuanWu] Give each file a third-level heading with its source path, responsibility, inputs, outputs, dependencies, and test.
79. [2026-08-13, ZheyuanWu] List every covered path in the page's `source_files` frontmatter field.
80. [2026-08-13, ZheyuanWu] The section is the code-level contract: entry points, field names, ordering, error handling, and determinism.
81. [2026-08-13, ZheyuanWu] A specification spanning several files belongs on the owning section's `index.md`.
82. [2026-08-11, ZheyuanWu] Keep each Draw.io source beside the page that embeds it and reuse it through a site-absolute basename.

## Development workflow

83. [2026-08-11, ZheyuanWu] Treat `_bmad/` and `.agents/` bundles as optional tooling, not the development process, unless BMad is requested.
84. [2026-08-11, ZheyuanWu] Use the repository's documented Git, Python, test, and documentation commands for normal work.

## Local preview before deployment

85. [2026-09-10, ZheyuanWu] When a change alters a major component or adds a feature, ask the owner whether to bring up a local Docker Compose preview before deploying.
86. [2026-09-10, ZheyuanWu] A major component is one whose failure changes what a user sees; a fix inside one module, test, or page is not.
87. [2026-09-10, ZheyuanWu] Preview through the existing `deploy/docker/compose.yaml` and its launcher, never a second compose file or preview-only Dockerfile.
88. [2026-09-10, ZheyuanWu] Database credentials for a preview come from the ignored root environment file, never from a tracked file.
89. [2026-09-10, ZheyuanWu] Report what the preview showed before asking to deploy.
90. [2026-09-10, ZheyuanWu] This page is the human-readable index of every rule; add a line here in the same edit that adds a rule to `AGENTS.md`.

## Version and change log

91. [2026-08-12, ZheyuanWu] Keep the current project version in the repository-root `VERSION` file.
92. [2026-08-12, ZheyuanWu] Every commit advances the version and documents its changes in a version page in that same commit.
93. [2026-08-12, ZheyuanWu] An agent increments only the patch number; minor and major numbers belong to human developers and the project manager.
94. [2026-08-12, ZheyuanWu] Update `docs/version/index.md` with each new page, basing history on Git evidence rather than invention.
95. [2026-08-17, ZheyuanWu] Never compact or merge older version pages; group each minor version into a folder and keep the latest four flat.
96. [2026-08-17, ZheyuanWu] Give every version page a distinct `order` value, since a tie falls back to misleading alphabetical sorting.
97. [2026-08-12, ZheyuanWu] Commit messages summarize the same change set as the version page, with no undocumented commits.
98. [2026-08-26, ZheyuanWu] Keep a commit message to at most 300 characters and three sentences, splitting the commit rather than stretching the limit.

## Work log

99. [2026-08-13, ZheyuanWu] `docs/version/` records what changed and `docs/worklog/` records who did it; keep the two separate.
100. [2026-08-13, ZheyuanWu] Each contributor owns one page named after them, with `index.md` as the roster.
101. [2026-08-13, ZheyuanWu] Use reverse-chronological date sections with at most three bullets each, merging rather than adding a fourth.
102. [2026-08-13, ZheyuanWu] A work-log page belongs to its owner; never edit, restructure, or translate another person's page.
103. [2026-08-13, ZheyuanWu] Compact the change set into today's entry automatically when preparing a commit, without asking first.
104. [2026-08-13, ZheyuanWu] Present the work-log entry together with the proposed commit message so both are reviewed at once.
105. [2026-08-13, ZheyuanWu] The version page, `VERSION` bump, work-log entry, and code all land in one commit.
106. [2026-08-15, ZheyuanWu] Confirmation to commit is not confirmation to push; push only when the owner asks in those terms.
107. [2026-08-12, ZheyuanWu] GitHub Pages is the only maintained documentation deployment target.
