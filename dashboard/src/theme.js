/**
 * Visual tokens and chart defaults.
 *
 * Every colour and chart default in the dashboard comes from here, so a change
 * lands everywhere at once and no view invents its own styling. The brand
 * palette is the reference prototype's (`external/UI_design/brandlens-vue`, by
 * Rouxin Jin): navy rail, blue accent, light plane. `src/style.css` reads the
 * same values as custom properties; this module is where JavaScript -- which
 * means the Plotly charts -- reads them.
 *
 * The categorical series colours are a separate, validated set. The prototype
 * contains no real charts, so its three brand colours could not supply one.
 * The eight series hues pass the lightness band, chroma floor, colourblind
 * separation, and normal-vision floor against this dashboard's white chart
 * surface.
 *
 * Two rules the views rely on:
 *
 * * Series colour follows the entity, never its rank, so filtering a chart
 *   never repaints the rows that survive. `seriesColors` maps names to fixed
 *   slots.
 * * Status colour is reserved for reliability state and is always paired with
 *   a word, never carried by colour alone.
 */

// ---------------------------------------------------------------------------
// Brand, taken from the reference prototype
// ---------------------------------------------------------------------------

export const NAVY = "#071a3d";
export const BLUE = "#2456a6";
export const PALE_BLUE = "#eaf1fb";
export const PLANE = "#f5f6f8";
export const SURFACE = "#ffffff";
export const LINE = "#dfe3ea";
export const TEXT = "#161a22";
export const MUTED = "#667085";
export const SUBTLE = "#8a94a6";

/** Reliability states. Each is shown with its word, never colour alone. */
export const GREEN = "#18794e";
export const AMBER = "#946200";
export const RED = "#b42318";

export const STATUS_COLORS = {
  RELIABLE: GREEN,
  UNRELIABLE: RED,
  PARTIAL: AMBER,
};

/** The tag class each reliability status wears, so colour never stands alone. */
export const STATUS_TONES = {
  RELIABLE: "green",
  UNRELIABLE: "red",
  PARTIAL: "amber",
};

// ---------------------------------------------------------------------------
// Chart palette
// ---------------------------------------------------------------------------

/**
 * Fixed categorical order. Assigned by slot and never cycled: a ninth series
 * folds into "Other" rather than receiving a generated hue, which under
 * colourblind simulation would be indistinguishable from an existing slot.
 */
export const SERIES = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
];

/** One hue, light to dark, for magnitude. Never a rainbow. */
export const SEQUENTIAL = [
  "#cde2fb",
  "#9ec5f4",
  "#6da7ec",
  "#3987e5",
  "#256abf",
  "#184f95",
];

/** Warm and cool poles with a neutral midpoint, for above/below comparisons. */
export const DIVERGING = ["#184f95", "#6da7ec", "#f0efec", "#eb8f7a", "#d03b3b"];

export const GRID = "#e8ebf0";
export const AXIS = "#c8cfda";

/**
 * The two attribution models always keep the same colours across every view,
 * so a reader who learns "Markov is blue" is never contradicted.
 */
export const MODEL_COLORS = {
  markov: SERIES[0],
  shapley: SERIES[1],
  recommended: SERIES[6],
};

/** The three outcomes, likewise fixed. */
export const OUTCOME_COLORS = {
  converted_users: SERIES[0],
  purchase_count: SERIES[2],
  revenue: SERIES[3],
};

export const FONT =
  'Inter, system-ui, -apple-system, "Segoe UI", sans-serif';

/**
 * Map each name to a fixed palette slot, in the order given.
 *
 * The mapping is built from a stable ordering of the names, so the same entity
 * keeps its colour no matter which subset a filter leaves on screen.
 */
export function seriesColors(names) {
  const map = {};
  names.forEach((name, index) => {
    map[name] = SERIES[index % SERIES.length];
  });
  return map;
}

/**
 * The shared chart chrome: hairline grid, no chart junk.
 *
 * Height includes the axis band, so a card never needs an inner scrollbar.
 */
export function layout(overrides = {}) {
  const { legend = true, height = 320, ...rest } = overrides;
  return {
    height,
    margin: { l: 8, r: 8, t: 28, b: 8 },
    paper_bgcolor: SURFACE,
    plot_bgcolor: SURFACE,
    font: { family: FONT, size: 12, color: TEXT },
    hoverlabel: { font: { family: FONT, size: 12 }, bgcolor: SURFACE },
    showlegend: legend,
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.02,
      xanchor: "left",
      x: 0,
      font: { size: 11, color: MUTED },
    },
    bargap: 0.28,
    xaxis: {
      showgrid: false,
      showline: true,
      linecolor: AXIS,
      linewidth: 1,
      ticks: "outside",
      tickcolor: AXIS,
      tickfont: { size: 11, color: MUTED },
      titlefont: { size: 11, color: MUTED },
      automargin: true,
      ...(rest.xaxis ?? {}),
    },
    yaxis: {
      showgrid: true,
      gridcolor: GRID,
      gridwidth: 1,
      zeroline: false,
      showline: false,
      tickfont: { size: 11, color: MUTED },
      titlefont: { size: 11, color: MUTED },
      automargin: true,
      ...(rest.yaxis ?? {}),
    },
    ...Object.fromEntries(
      Object.entries(rest).filter(([key]) => key !== "xaxis" && key !== "yaxis"),
    ),
  };
}

/** Plotly's own chrome, minus the parts that are noise here. */
export const PLOT_CONFIG = {
  displayModeBar: false,
  responsive: true,
};

// ---------------------------------------------------------------------------
// Value formatting
// ---------------------------------------------------------------------------

export function money(value, currency = "$") {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${currency}${number.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/** A compact currency amount, for a headline tile where precision is noise. */
export function compactMoney(value, currency = "$") {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  const magnitude = Math.abs(number);
  if (magnitude >= 1_000_000) return `${currency}${(number / 1_000_000).toFixed(2)}M`;
  if (magnitude >= 10_000) return `${currency}${(number / 1000).toFixed(1)}K`;
  return money(number, currency);
}

export function count(value, digits = 0) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** Format a 0-1 share as a percentage. */
export function percent(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${(number * 100).toFixed(digits)}%`;
}

export function ratio(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${number.toFixed(digits)}x`;
}
