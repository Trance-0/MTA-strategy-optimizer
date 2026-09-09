---
title: Analysis Workbench Visual Design
name: Analysis Workbench
description: Visual inheritance and component treatment for the incremental Dashboard release.
compact: "Visual tokens and inherited Dashboard treatment for dataset context, import, charts, budget plans, model execution, evaluation, run history and recovery; paired with EXPERIENCE.md."
status: final
updated: 2026-09-08
sources: [prd.md, decision-log.md, ../views/visual-contract.md, ../navigation.md]
colors:
  plane: '#f5f6f8'
  surface: '#ffffff'
  text: '#161a22'
  muted: '#667085'
  border: '#dfe3ea'
  accent: '#2456a6'
  accent-soft: '#eaf1fb'
  rail: '#071a3d'
  read-only-accent: '#217346'
  read-only-soft: '#e6f2ea'
  read-only-rail: '#10331f'
  success: '#18794e'
  warning: '#946200'
  error: '#b42318'
  series-1: '#2a78d6'
  series-2: '#eb6834'
  series-3: '#1baf7a'
  series-4: '#eda100'
  series-5: '#e87ba4'
  series-6: '#008300'
  series-7: '#4a3aa7'
  series-8: '#e34948'
typography:
  body:
    fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif'
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.45'
  chart:
    fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif'
    fontSize: 12px
    fontWeight: '400'
  heading:
    note: 'Inherit existing page and card heading roles from dashboard/src/style.css.'
rounded:
  sm: 6px
  md: 9px
  full: 9999px
spacing:
  control-gap: 8px
  card-gap: 14px
  card-inset: 15px
  page-inset: 26px
  narrow-inset: 15px
components:
  dataset-context:
    background: '{colors.surface}'
    foreground: '{colors.text}'
    radius: '{rounded.md}'
  import-panel:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  analysis-card:
    background: '{colors.surface}'
    foreground: '{colors.text}'
    radius: '{rounded.md}'
  plan-editor:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  stage-runner:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  evaluation-report:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  run-history:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  recovery-panel:
    background: '{colors.surface}'
    radius: '{rounded.md}'
  reference-panel:
    background: '{colors.surface}'
    radius: '{rounded.md}'
---

# Analysis Workbench Visual Design

## Brand & Style

Inherit the current Dashboard's internal component system: its compact rail,
light working plane, bordered cards, existing type hierarchy and Plotly figures.
The release adds analysis capabilities without changing the brand. The paired
[experience contract](./EXPERIENCE.md) owns behavior. These two contracts take
precedence over any later mock or imported visual; business mathematics stays
in its existing owning specifications.

## Colors

Use {colors.plane} behind {colors.surface} cards and {colors.text} for required
labels. {colors.muted} carries context, never a disabled operation disguised as
help text. Deployment theme remains server-capability driven: connected
operations use {colors.accent}; the read-only demonstration uses
{colors.read-only-accent}. Do not recolor a registered dataset according to
whether its source was simulated or imported; communicate source with words.

Series colors inherit the eight-slot palette above. Slots follow stable entity
identity across filters; categories beyond the displayed palette are grouped as
Other. Markov uses {colors.series-1}, Shapley {colors.series-2}, and recommended
allocations {colors.series-7}. Status words accompany {colors.success},
{colors.warning} and {colors.error}; a green check means the named check passed,
not that a strategy will improve future revenue.

Required text must meet a 4.5:1 contrast target, large text 3:1, and focus or
essential control boundaries 3:1 against adjacent surfaces. Existing series
colors with weaker contrast require direct labels and readable value tables;
never make a thin colored mark the sole carrier of a conclusion.

## Typography

Body copy uses {typography.body.fontFamily} and {typography.body.fontSize}; chart
labels use {typography.chart.fontSize}. Keep existing page and card heading
roles. Values retain aligned numeric columns, currency labels and explicit
units. Compact numbers may appear in headline tiles, with precise values in
the paired table. Long dataset names wrap; identifiers are secondary selectable
text and never replace readable names.

## Layout & Spacing

Keep the current shell and {spacing.card-gap} card rhythm. Page margins inherit
{spacing.page-inset}, reducing to {spacing.narrow-inset} on narrow views. Dataset
context sits before the page's analysis content and stays reachable if a data
resource fails. Filters precede their cards; explanations sit beside the result
they qualify. Amount and ratio plots occupy separate cards, each with one
vertical axis. Result tables follow their figure, rather than occupying a
second modal.

At the existing 1024-pixel rail breakpoint, keep the horizontal navigation bar.
At 760 pixels and below, new paired cards and editors stack. Tables scroll
within their own container; the document must not acquire horizontal overflow.

## Elevation & Depth

Inherit current thin borders and restrained card depth. Errors and provenance
are inline content, not floating layers. Reserve overlays for the existing
confirmation and entity editing patterns; never stack dialogs.

## Shapes

New controls use {rounded.sm}; cards use {rounded.md}. Status badges inherit
existing shapes and always include text. Do not add illustrations, gradients,
decorative animation or a separate component library.

## Components

#### Dataset context

Use {components.dataset-context.background} with a labeled selector, followed by
source, market, currency and date scope. Capability descriptions wrap beneath
the selection. Keep the explicit legacy source or demonstration distinguishable
from registered datasets. This component is not a success-colored banner.

#### Import panel

Use {components.import-panel.background}. Arrange template access, labeled input
roles, preview and action footer in reading order. Required performance data
precedes optional paths and research context. Error summaries precede preview;
each issue retains its field or row label.

#### Analysis card

Use {components.analysis-card.background}; a card heading states the business
question, followed by scope, figure, value table and export action. A ranking
detail is a continuation of the same page. Data-unavailable text occupies the
figure area without fabricated marks. Apply the current shared Plotly chrome.

#### Plan editor

Use {components.plan-editor.background}. Place saved plan and revision identity
above name, total budget and usage policy. Separate Save revision from Run saved
revision. Entity drafts remain in their existing sections with a visible
Not connected to model runs notice.

#### Stage runner

Use {components.stage-runner.background}. Identity and options precede Run;
progress precedes the log and result actions. Evaluation adds a named target
strategy run. The chosen dataset remains visible even when no stage is enabled.

#### Evaluation report

Use {components.evaluation-report.background}. Display strategy identity, named
check summaries, baseline values, skipped items and limitations in that order.
Layer status and execution status occupy distinct labeled fields. Preserve
failure text alongside successful checks; no single decorative score summarizes
the complete evaluation.

#### Run history

Use {components.run-history.background}. Reuse paged list treatment with dataset,
stage, time and state; opening a record reveals provenance, parameters, logs
and declared downloads inline. Visually label an older selected run.

#### Recovery panel

Use {components.recovery-panel.background}. Separate source, storage and model
availability. Explain the failed operation and remedy directly above Retry.
Retain existing Settings sections and protected-configuration treatment.

#### Reference panel

Use {components.reference-panel.background}. Dataset-backed vocabulary and
entities retain the existing readable lists. Fixed Ontology Review and Willow
examples carry a persistent Demonstration label and distinct introduction.

## Do's and Don'ts

Keep source, result scope and limitations visible at the point of use. Use
consistent labels in figures, tables and downloads. Preserve existing static
and connected deployment identity. Do not encode dataset changes with new
colors, imply a refit through a date filter, or substitute sample results for
missing analysis.
