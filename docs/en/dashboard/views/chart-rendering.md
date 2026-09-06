---
title: "Deferred chart rendering"
compact: "PlotlyChart loads on mount, coalesces replacement props, avoids deep watchers, cancels detached draws and displays errors."
source_files: dashboard/src/components/PlotlyChart.vue
---

# Deferred chart rendering

`PlotlyChart.vue` imports the Plotly library only after a chart mounts. It
coalesces pending changes into an animation frame, watches replacement trace
and layout objects without deeply traversing history arrays, and draws the
latest props after loading. Unmount cancels scheduled work and purges any plot;
a late import must never render into a detached host. Library or render failures
show an accessible chart error while the values table remains usable.

## Source Files

### `PlotlyChart.vue`

Source: `dashboard/src/components/PlotlyChart.vue`

- Responsibility: Implement the reader-facing contract on this page.
- Inputs and outputs: Required traces array, optional layout object and label; render, loading error and unmount behavior are defined above.
- Dependencies: Vue and the dynamically imported Plotly library.
- Verification: `npm --prefix dashboard test`; production build and browser navigation.
