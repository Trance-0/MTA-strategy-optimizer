/**
 * The label vocabulary and the small aggregations more than one view needs.
 *
 * Only presentation lives here. Nothing in this module computes an attribution
 * share or a budget figure: the values are read from the snapshot the pipeline
 * produced, and these helpers group, sort, and format them.
 *
 * Data flow:
 *     the snapshot -> here -> the six views
 */

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
