/** Aggregate observed chart values and serialize their exact displayed rows. */
const FIELDS = ["cost", "sales", "purchases", "impressions", "clicks"];
const finite = value => typeof value === "number" && Number.isFinite(value);

export function safeRatio(numerator, denominator) {
  return finite(numerator) && finite(denominator) && denominator !== 0
    ? numerator / denominator : null;
}

function period(date, grain) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? "")) return null;
  const value = new Date(`${date}T00:00:00Z`);
  if (!Number.isFinite(value.getTime()) || value.toISOString().slice(0, 10) !== date) return null;
  if (grain === "month") return `${date.slice(0, 7)}-01`;
  if (grain === "week") value.setUTCDate(value.getUTCDate() - (value.getUTCDay() + 6) % 7);
  return value.toISOString().slice(0, 10);
}

export function aggregatePerformance(rows, grain = "day") {
  const groups = new Map();
  for (const row of rows) {
    const key = period(row.report_date, grain);
    if (!key) continue;
    if (!groups.has(key)) groups.set(key, { key, rows: 0, ...Object.fromEntries(FIELDS.map(field => [field, null])) });
    const group = groups.get(key);
    group.rows += 1;
    for (const field of FIELDS) if (finite(row[field])) group[field] = (group[field] ?? 0) + row[field];
  }
  return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key)).map(row => ({
    ...row, roas: safeRatio(row.sales, row.cost), ctr: safeRatio(row.clicks, row.impressions),
    cpc: safeRatio(row.cost, row.clicks), cpa: safeRatio(row.cost, row.purchases),
  }));
}

export function rowsToCsv(columns, rows) {
  const cell = value => {
    if (value == null || (typeof value === "number" && !Number.isFinite(value))) return "";
    let text = typeof value === "object" ? JSON.stringify(value) : String(value);
    if (typeof value === "string" && /^[\s]*[=+@-]/.test(text)) text = `'${text}`;
    return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
  };
  return [columns.map(column => cell(column.label ?? column.key)).join(","),
    ...rows.map(row => columns.map(column => cell(row[column.key])).join(","))].join("\r\n") + "\r\n";
}

export function downloadCsv(columns, rows, filename = "chart-values.csv") {
  const url = URL.createObjectURL(new Blob([rowsToCsv(columns, rows)], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.appendChild(link);
  try { link.click(); }
  finally {
    // WebKit may consume the object address asynchronously after activation.
    setTimeout(() => { link.remove(); URL.revokeObjectURL(url); }, 1000);
  }
}
