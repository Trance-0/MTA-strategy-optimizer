/**
 * The label vocabulary and the small aggregations more than one view needs.
 *
 * Only presentation lives here. Nothing in this module computes an attribution
 * share or a budget figure: the values are read from the snapshot the pipeline
 * produced, and these helpers group, sort, and format them.
 *
 * Data flow:
 *     the snapshot -> here -> the seven views
 */

import { count, money, percent, ratio } from "../theme.js";

/** Outcome keys as the pipeline writes them, and how they are shown. */
export const OUTCOME_LABELS = {
  converted_users: "Converted users",
  purchase_count: "Purchases",
  revenue: "Revenue",
};

/** The share field that belongs to each outcome. */
export const OUTCOME_SHARE_COLUMNS = {
  converted_users: "converted_user_share",
  purchase_count: "purchase_count_share",
  revenue: "revenue_share",
};

/** The attributed-total field that belongs to each outcome. */
export const OUTCOME_VALUE_COLUMNS = {
  converted_users: "attributed_converted_users",
  purchase_count: "attributed_purchase_count",
  revenue: "attributed_revenue",
};

/**
 * The formats that are read right-aligned, so a column of numbers lines up on
 * its digits rather than on its first character.
 */
export const NUMERIC_FORMATS = new Set([
  "number",
  "money",
  "percent",
  "ratio",
  "share",
]);

const TABLE_COLLATOR = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

/**
 * Render one cell of a declared column.
 *
 * Shared by every table in the dashboard, so the same declaration produces the
 * same text wherever it is mounted and a new format cannot mean two things in
 * two places. An absent value is `--` rather than blank, so a missing number is
 * visibly missing.
 *
 * An array or an object is flattened here rather than at each call site: the
 * canonical entity records carry both — a Provider's supported ad products, a
 * Product's per-Provider identifiers — and `String(value)` renders the first as
 * a comma-joined list only by accident and the second as `[object Object]`.
 */
export function renderCell(column, row) {
  const value = row[column.key];
  if (typeof column.format === "function") return column.format(value, row);
  if (value === null || value === undefined || value === "") return "--";
  switch (column.format) {
    case "number":
      return count(value, column.digits ?? 0);
    case "money":
      return money(value, column.currency ?? "$");
    case "percent":
      return percent(value, column.digits ?? 2);
    case "share":
      return Number(value).toFixed(column.digits ?? 4);
    case "ratio":
      return ratio(value, column.digits ?? 2);
    case "flag":
      return value ? "Yes" : "No";
    default:
      if (Array.isArray(value)) return value.length ? value.join(", ") : "--";
      if (typeof value === "object") return JSON.stringify(value);
      return String(value);
  }
}

/** Advance one column through ascending, descending, and source order. */
export function nextTableSort(current, key) {
  if (current.key !== key || current.direction === null) {
    return { key, direction: "asc" };
  }
  if (current.direction === "asc") return { key, direction: "desc" };
  return { key: null, direction: null };
}

/**
 * Sort table rows without mutating them or losing their source-order ties.
 *
 * Missing values remain last in either direction. Numeric display formats use
 * their raw number; every other format follows the text visible to the reader.
 */
export function sortTableRows(rows, column, direction) {
  if (!column || !direction) return rows;
  const numeric = NUMERIC_FORMATS.has(column.format);
  const sign = direction === "desc" ? -1 : 1;
  return rows
    .map((row, index) => ({ row, index }))
    .sort((left, right) => {
      const leftRaw = left.row[column.key];
      const rightRaw = right.row[column.key];
      const leftMissing = leftRaw === null || leftRaw === undefined || leftRaw === "";
      const rightMissing = rightRaw === null || rightRaw === undefined || rightRaw === "";
      if (leftMissing && rightMissing) return left.index - right.index;
      if (leftMissing) return 1;
      if (rightMissing) return -1;

      let comparison;
      if (numeric) {
        const leftNumber = Number(leftRaw);
        const rightNumber = Number(rightRaw);
        const leftInvalid = !Number.isFinite(leftNumber);
        const rightInvalid = !Number.isFinite(rightNumber);
        if (leftInvalid && rightInvalid) return left.index - right.index;
        if (leftInvalid) return 1;
        if (rightInvalid) return -1;
        comparison = leftNumber - rightNumber;
      } else {
        comparison = TABLE_COLLATOR.compare(
          renderCell(column, left.row),
          renderCell(column, right.row),
        );
      }
      return comparison === 0 ? left.index - right.index : comparison * sign;
    })
    .map(({ row }) => row);
}

const CURRENCY_SYMBOLS = { USD: "$", EUR: "€", GBP: "£", JPY: "¥" };

/** Return the symbol for a currency code, falling back to the code. */
export function currencySymbol(code) {
  return CURRENCY_SYMBOLS[String(code ?? "").toUpperCase()] ?? `${code} `;
}

/** Turn an UPPER_SNAKE enum into readable title case. */
export function pretty(value) {
  return String(value ?? "")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

/**
 * Shorten a five-segment key for an axis tick.
 *
 * Drops the segments that are `UNSPECIFIED`, which carry no information and
 * would otherwise make every label the same length and unreadable.
 */
export function shortTouchpoint(key) {
  return String(key ?? "")
    .split(":")
    .filter((part) => part !== "UNSPECIFIED")
    .map(pretty)
    .join(" / ");
}

/** Sum one numeric field across rows, treating null as zero. */
export function sum(rows, field) {
  let total = 0;
  for (const row of rows) {
    const value = Number(row[field]);
    if (Number.isFinite(value)) total += value;
  }
  return total;
}

/**
 * Find the greatest finite value across one or more row fields.
 *
 * This is an iterative scan rather than `Math.max(...values)`: the database
 * history legitimately reaches 100,000 rows, which is more arguments than a
 * browser permits in one function call. The floor keeps an empty or entirely
 * absent series useful as a chart bound.
 */
export function maxOf(rows, fields, floor = 0) {
  let highest = Number(floor);
  if (!Number.isFinite(highest)) highest = 0;
  for (const row of rows) {
    for (const field of fields) {
      const value = Number(row[field]);
      if (Number.isFinite(value) && value > highest) highest = value;
    }
  }
  return highest;
}

/**
 * A row's value as a number, or null when it does not hold one.
 *
 * `Number(null)` and `Number("")` are both 0, so a plain coercion would place
 * a row whose measure is absent at the origin and count it as an observation
 * that was never recorded.
 */
function measure(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

/**
 * Merge observations into a fixed grid, counting how many fall in each cell.
 *
 * A scatter of the supported history draws one mark per observation, and at
 * 100,000 rows most of those marks land where another has already drawn: the
 * ink then says only "something is here", not how much. Counting into
 * `resolution × resolution` cells says how much, and bounds the drawn marks by
 * the grid rather than by the row count, so rendering cost stops following the
 * size of the history.
 *
 * Both axes share one bound because the pair being compared is budget against
 * spend in one currency, and the diagonal only reads as full delivery when a
 * step along x is the same amount as a step along y.
 *
 * Returns a dense row-major matrix with `null` for the cells nothing fell in,
 * beside the origin and cell size. That is Plotly's unambiguous heatmap form:
 * given only the coordinates of occupied cells it infers brick widths from the
 * spacing between them, which for a sparse grid produces bricks of uneven size
 * that misstate where an observation actually sat.
 */
export function densityGrid(rows, xField, yField, highest, resolution) {
  const size = Math.max(1, Math.floor(resolution));
  const span = Number(highest) > 0 ? Number(highest) : 1;
  const step = span / size;
  const counts = new Array(size * size).fill(null);
  let occupied = 0;
  let densest = 0;
  let total = 0;
  for (const row of rows) {
    const x = measure(row[xField]);
    const y = measure(row[yField]);
    if (x === null || y === null) continue;
    // Clamped rather than dropped: a value exactly at the bound belongs in the
    // last cell, and `floor(span / step)` addresses one past the end.
    const column = Math.min(size - 1, Math.max(0, Math.floor(x / step)));
    const line = Math.min(size - 1, Math.max(0, Math.floor(y / step)));
    const index = line * size + column;
    const current = counts[index];
    if (current === null) {
      counts[index] = 1;
      occupied += 1;
      if (densest < 1) densest = 1;
    } else {
      counts[index] = current + 1;
      if (counts[index] > densest) densest = counts[index];
    }
    total += 1;
  }
  const z = [];
  for (let line = 0; line < size; line += 1) {
    z.push(counts.slice(line * size, line * size + size));
  }
  return {
    z,
    // The centre of the first cell, which is where Plotly anchors a brick.
    x0: step / 2,
    y0: step / 2,
    dx: step,
    dy: step,
    size,
    step,
    occupied,
    densest,
    total,
  };
}

/**
 * Group rows by a key and sum the named fields within each group.
 *
 * Returns an array rather than a Map so a template can iterate it directly,
 * in first-seen order, which keeps a chart's category order stable across
 * reloads.
 */
export function groupSum(rows, keyOf, fields) {
  const groups = new Map();
  for (const row of rows) {
    const key = typeof keyOf === "function" ? keyOf(row) : row[keyOf];
    if (!groups.has(key)) {
      const entry = { key };
      for (const field of fields) entry[field] = 0;
      groups.set(key, entry);
    }
    const entry = groups.get(key);
    for (const field of fields) {
      const value = Number(row[field]);
      if (Number.isFinite(value)) entry[field] += value;
    }
  }
  return [...groups.values()];
}

/** The distinct non-empty values of a field, sorted. */
export function distinct(rows, field) {
  const values = new Set();
  for (const row of rows) {
    const value = row[field];
    if (value !== null && value !== undefined && value !== "") values.add(value);
  }
  return [...values].sort();
}

/** Sort a copy of `rows` by a numeric field. */
export function sortBy(rows, field, direction = "asc") {
  const sign = direction === "desc" ? -1 : 1;
  return [...rows].sort((left, right) => {
    const a = Number(left[field]);
    const b = Number(right[field]);
    if (!Number.isFinite(a) && !Number.isFinite(b)) return 0;
    if (!Number.isFinite(a)) return 1;
    if (!Number.isFinite(b)) return -1;
    return (a - b) * sign;
  });
}

/** Format a `YYYY-MM-DD` string as `Mon DD`, for a dense axis. */
export function shortDate(value) {
  if (!value) return "";
  const [, month, day] = String(value).split("-");
  const names = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return `${names[Number(month) - 1] ?? month} ${Number(day)}`;
}

/**
 * The reliability verdict's tone class.
 *
 * The word itself is always rendered beside it, so the colour is a second
 * encoding rather than the only one.
 */
export function statusTone(status) {
  const key = String(status ?? "").toUpperCase();
  if (key === "RELIABLE") return "green";
  if (key === "UNRELIABLE") return "red";
  if (key === "PARTIAL") return "amber";
  return "gray";
}
